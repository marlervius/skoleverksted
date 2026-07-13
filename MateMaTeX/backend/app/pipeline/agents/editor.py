"""
Editor agent node — Quality control, cleanup, final validation.
"""

from __future__ import annotations

from datetime import datetime

import structlog

from app.config import get_config
from app.models.llm import LLMInterface
from app.models.state import AgentRole, AgentStep, PipelineState
from app.pipeline.prompts.editor import SYSTEM_PROMPT, build_editor_prompt

logger = structlog.get_logger()


def run_editor(state: PipelineState) -> PipelineState:
    """
    Execute the editor agent: quality-check and clean the LaTeX content.

    Reads: state.verified_latex_body
    Writes: state.edited_latex_body, state.steps
    """
    step = AgentStep(agent=AgentRole.EDITOR)
    state.current_agent = AgentRole.EDITOR

    logger.info("editor_start", job_id=state.job_id)

    source_latex = state.verified_latex_body or state.raw_latex_body

    try:
        config = get_config()
        fast_types = {
            t.strip()
            for t in config.skip_editor_material_types.split(",")
            if t.strip()
        }
        if config.skip_editor or state.request.material_type in fast_types:
            state.edited_latex_body = state.verified_latex_body
            step.output_summary = "Rask modus — redaktør hoppet over"
            logger.info(
                "editor_skipped",
                job_id=state.job_id,
                material_type=state.request.material_type,
            )
        else:
            llm = LLMInterface(temperature=config.llm.temperature)

            user_prompt = build_editor_prompt(
                latex_content=source_latex,
                language_level=state.request.language_level,
                material_type=state.request.material_type,
            )

            import re as _re

            response = llm.invoke(SYSTEM_PROMPT, user_prompt)
            body = response.strip()

            # Strip markdown code fences
            body = _re.sub(r'^```(?:latex|tex)?\s*\n?', '', body)
            body = _re.sub(r'\n?```\s*$', '', body)

            # Strip preamble if editor re-introduced it
            body = _re.sub(
                r'\\documentclass.*?\\begin\{document\}\s*',
                '',
                body,
                flags=_re.DOTALL,
            )
            body = _re.sub(r'\\end\{document\}.*$', '', body, flags=_re.DOTALL)

            from app.latex.text_sanitize import sanitize_latex_body

            state.edited_latex_body = sanitize_latex_body(body.strip()) or source_latex

            step.output_summary = f"Edited LaTeX ({len(state.edited_latex_body)} chars)"
            logger.info(
                "editor_complete",
                job_id=state.job_id,
                body_length=len(state.edited_latex_body),
            )

    except Exception as e:
        step.error = str(e)
        # Fallback: use verified content as-is
        state.edited_latex_body = source_latex
        logger.error("editor_failed", job_id=state.job_id, error=str(e))

    finally:
        step.completed_at = datetime.now()
        step.duration_seconds = (step.completed_at - step.started_at).total_seconds()
        state.steps.append(step)

    return state
