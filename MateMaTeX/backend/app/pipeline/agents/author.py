"""
Author agent node — Writes LaTeX body content with TikZ illustrations.

This is the second agent. It takes the pedagogical plan and produces
complete LaTeX body content. It may be called multiple times if
the math verifier or content-quality gate requests fixes.
"""

from __future__ import annotations

from datetime import datetime

import structlog

from app.config import get_config
from app.curriculum import format_boundaries_for_prompt, get_language_level_instructions
from app.models.llm import LLMInterface
from app.models.state import AgentRole, AgentStep, PipelineState
from app.pipeline.prompts.author import (
    FEW_SHOT_EXAMPLES,
    SYSTEM_PROMPT,
    build_author_fix_prompt,
    build_author_prompt,
    build_author_quality_fix_prompt,
)

logger = structlog.get_logger()


def run_author(state: PipelineState) -> PipelineState:
    """
    Execute the author agent: write LaTeX body content.

    Retry mode is driven by ``state.author_retry_reason`` (set by graph routers),
    not by math_verification_attempts (which counts verifier runs, not failures).

    Reads: state.pedagogical_plan, state.math_verification, state.raw_latex_body
    Writes: state.raw_latex_body, state.steps
    """
    step = AgentStep(agent=AgentRole.AUTHOR)
    state.current_agent = AgentRole.AUTHOR

    reason = (state.author_retry_reason or "").strip().lower()
    state.author_retry_reason = ""

    is_math_retry = reason == "math"
    is_quality_retry = reason == "quality"
    if is_quality_retry:
        state.content_quality_attempts += 1

    logger.info(
        "author_start",
        job_id=state.job_id,
        is_math_retry=is_math_retry,
        is_quality_retry=is_quality_retry,
        math_verifier_runs=state.math_verification_attempts,
        quality_attempt=state.content_quality_attempts,
    )

    try:
        config = get_config()
        llm = LLMInterface(temperature=config.llm.temperature)

        # Build system prompt with few-shot examples
        system_parts = [SYSTEM_PROMPT, "\n=== EKSEMPLER PÅ PERFEKT OUTPUT ===\n"]
        for ex in FEW_SHOT_EXAMPLES:
            system_parts.append(f"INPUT: {ex['input']}\nOUTPUT:\n{ex['output']}\n---\n")

        full_system = "\n".join(system_parts)

        if is_math_retry:
            from app.verification.math_checker import format_errors_for_agent

            error_report = format_errors_for_agent(state.math_verification)
            user_prompt = build_author_fix_prompt(
                current_latex=state.raw_latex_body,
                error_report=error_report,
            )
            step.input_summary = (
                f"MATH RETRY: fixing {state.math_verification.claims_incorrect} errors"
            )
        elif is_quality_retry:
            from app.verification.content_quality import format_quality_report_for_author

            quality_report = format_quality_report_for_author(state.content_quality)
            user_prompt = build_author_quality_fix_prompt(
                pedagogical_plan=state.pedagogical_plan,
                current_latex=state.raw_latex_body,
                quality_report=quality_report,
                grade=state.request.grade,
                content_options=state.request.model_dump(),
            )
            step.input_summary = (
                f"QUALITY RETRY #{state.content_quality_attempts}: "
                f"score {state.content_quality.score}/100"
            )
        else:
            grade_context = state.curriculum_context or format_boundaries_for_prompt(
                state.request.grade
            )
            language_instructions = get_language_level_instructions(
                state.request.language_level
            )

            user_prompt = build_author_prompt(
                pedagogical_plan=state.pedagogical_plan,
                grade=state.request.grade,
                grade_context=grade_context,
                language_instructions=language_instructions,
                content_options=state.request.model_dump(),
            )
            step.input_summary = f"Plan: {state.pedagogical_plan[:100]}..."

        response = llm.invoke(full_system, user_prompt)
        body = response.strip()

        import re as _re

        body = _re.sub(r'^```(?:latex|tex)?\s*\n?', '', body)
        body = _re.sub(r'\n?```\s*$', '', body)
        body = _re.sub(
            r'\\documentclass.*?\\begin\{document\}\s*',
            '',
            body,
            flags=_re.DOTALL,
        )
        body = _re.sub(r'\\end\{document\}.*$', '', body, flags=_re.DOTALL)
        body = _re.sub(r'\\includegraphics\s*(?:\[.*?\])?\s*\{.*?\}', '', body)

        from app.latex.text_sanitize import sanitize_latex_body

        state.raw_latex_body = sanitize_latex_body(body.strip())

        step.output_summary = f"LaTeX body ({len(state.raw_latex_body)} chars)"
        logger.info(
            "author_complete",
            job_id=state.job_id,
            body_length=len(state.raw_latex_body),
            is_math_retry=is_math_retry,
            is_quality_retry=is_quality_retry,
        )

    except Exception as e:
        step.error = str(e)
        logger.error("author_failed", job_id=state.job_id, error=str(e))
        raise

    finally:
        step.completed_at = datetime.now()
        step.duration_seconds = (step.completed_at - step.started_at).total_seconds()
        step.retries = state.content_quality_attempts if is_quality_retry else state.math_verification_attempts
        state.steps.append(step)

    return state
