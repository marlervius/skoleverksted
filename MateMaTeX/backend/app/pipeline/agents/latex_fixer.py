"""
LaTeX fixer agent node — Automatically fixes compilation errors.
"""

from __future__ import annotations

import re
from datetime import datetime

import structlog

from app.config import get_config
from app.models.llm import LLMInterface
from app.models.state import AgentRole, AgentStep, PipelineState
from app.pipeline.prompts.latex_fixer import SYSTEM_PROMPT, build_fixer_prompt
from app.verification.latex_checker import format_latex_errors_for_agent

logger = structlog.get_logger()


def _strip_comments_for_count(s: str) -> str:
    """Remove LaTeX comments so brace counting ignores commented-out braces."""
    return re.sub(r"(?<!\\)%.*", "", s)


def _try_rule_based_fix(full_document: str) -> str | None:
    """
    Attempt to repair common, well-understood LaTeX errors without an LLM call.

    Handles the two most frequent failures we see in logs:
      * Unbalanced { } braces (often causes a premature `\\end{document}` error).
      * Unclosed \\begin{env} ... environments.

    Returns the fixed document if a safe change was made, else None.
    """
    match = re.search(r"(.*\\begin\{document\})(.*)(\\end\{document\}.*)", full_document, re.DOTALL)
    if not match:
        return None
    head, body, tail = match.group(1), match.group(2), match.group(3)

    changed = False

    # 1. Close unclosed environments (in reverse order of opening).
    begins = re.findall(r"\\begin\{([^}]+)\}", body)
    ends = re.findall(r"\\end\{([^}]+)\}", body)
    end_counts: dict[str, int] = {}
    for e in ends:
        end_counts[e] = end_counts.get(e, 0) + 1
    open_counts: dict[str, int] = {}
    for b in begins:
        open_counts[b] = open_counts.get(b, 0) + 1
    missing_ends: list[str] = []
    for env in reversed(begins):
        if open_counts.get(env, 0) > end_counts.get(env, 0):
            missing_ends.append(env)
            end_counts[env] = end_counts.get(env, 0) + 1
    if missing_ends:
        body = body + "\n" + "\n".join(f"\\end{{{env}}}" for env in missing_ends)
        changed = True

    # 2. Balance stray { } braces (ignore escaped \{ \} and comments).
    counting = _strip_comments_for_count(body)
    counting = re.sub(r"\\[{}]", "", counting)
    open_braces = counting.count("{")
    close_braces = counting.count("}")
    if open_braces > close_braces:
        body = body + ("}" * (open_braces - close_braces))
        changed = True

    if not changed:
        return None
    return head + body + tail


def run_latex_fixer(state: PipelineState) -> PipelineState:
    """
    Fix LaTeX compilation errors using an LLM.

    Reads: state.full_document, state.latex_compilation
    Writes: state.full_document, state.edited_latex_body, state.steps
    """
    step = AgentStep(agent=AgentRole.LATEX_FIXER)
    state.current_agent = AgentRole.LATEX_FIXER

    logger.info(
        "latex_fixer_start",
        job_id=state.job_id,
        errors=len(state.latex_compilation.errors),
    )

    try:
        # Fast path: fix common trivial errors with deterministic rules (no LLM,
        # no rate limits, no multi-minute wait). The validator recompiles next.
        rule_fixed = _try_rule_based_fix(state.full_document)
        if rule_fixed is not None:
            state.full_document = rule_fixed
            body_match = re.search(
                r"\\begin\{document\}(.*?)\\end\{document\}",
                rule_fixed,
                re.DOTALL,
            )
            if body_match:
                state.edited_latex_body = body_match.group(1).strip()
            step.output_summary = "Rettet med regler (uten LLM)"
            logger.info("latex_fixer_rule_based", job_id=state.job_id)
            return state

        config = get_config()
        llm = LLMInterface(temperature=0.1)  # Very low temp for precise fixes

        error_report = format_latex_errors_for_agent(state.latex_compilation)
        layout_mode = bool(
            state.layout_fix_attempts > 0
            and any("Layout-problemer" in e for e in state.latex_compilation.errors)
        )
        user_prompt = build_fixer_prompt(
            full_document=state.full_document,
            compilation_errors=error_report,
            layout_mode=layout_mode,
        )

        response = llm.invoke(SYSTEM_PROMPT, user_prompt)
        fixed_doc = response.strip()

        # Clean LLM output: strip markdown code fences that LLMs often add
        import re as _re
        # Remove ```latex ... ``` or ``` ... ``` wrapping
        fixed_doc = _re.sub(r'^```(?:latex|tex)?\s*\n?', '', fixed_doc)
        fixed_doc = _re.sub(r'\n?```\s*$', '', fixed_doc)
        fixed_doc = fixed_doc.strip()

        # Strip any prose the LLM prepended before the actual LaTeX document
        for latex_start_marker in (r'\documentclass', r'\begin{document}'):
            idx = fixed_doc.find(latex_start_marker)
            if idx > 0:
                logger.debug("latex_fixer_stripped_prose", chars_removed=idx)
                fixed_doc = fixed_doc[idx:].strip()
                break

        # Validate that the fixed document still contains \begin{document}
        if r'\begin{document}' not in fixed_doc:
            logger.warning("latex_fixer_missing_begin_document", doc_start=fixed_doc[:100])
            # Fall back to the original document — don't overwrite with garbage
            fixed_doc = state.full_document
        else:
            # The fixer returns the full document (with preamble)
            state.full_document = fixed_doc

        # Also extract body for consistency
        import re
        body_match = re.search(
            r'\\begin\{document\}(.*?)\\end\{document\}',
            fixed_doc,
            re.DOTALL,
        )
        if body_match:
            state.edited_latex_body = body_match.group(1).strip()

        step.output_summary = f"Fixed document ({len(fixed_doc)} chars)"
        logger.info("latex_fixer_complete", job_id=state.job_id)

    except Exception as e:
        step.error = str(e)
        logger.error("latex_fixer_failed", job_id=state.job_id, error=str(e))

    finally:
        step.completed_at = datetime.now()
        step.duration_seconds = (step.completed_at - step.started_at).total_seconds()
        state.steps.append(step)

    return state
