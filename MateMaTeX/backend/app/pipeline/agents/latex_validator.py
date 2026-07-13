"""
LaTeX validator node — Compiles the document with pdflatex to check for errors.
"""

from __future__ import annotations

import base64
from datetime import datetime
from pathlib import Path

import structlog

from app.config import get_config, get_settings
from app.latex.preamble import wrap_with_style
from app.models.state import AgentRole, AgentStep, PipelineState
from app.verification.latex_checker import LatexChecker

logger = structlog.get_logger()


def _persist_pdf(job_id: str, pdf_bytes: bytes) -> str:
    """Write compiled PDF to a stable per-job path so endpoints can serve it."""
    out_dir = Path(get_settings().output_dir) / "pipeline_pdfs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{job_id}.pdf"
    out_path.write_bytes(pdf_bytes)
    return str(out_path)


def run_latex_validator(state: PipelineState) -> PipelineState:
    """
    Compile the document with pdflatex to validate it.

    Reads: state.edited_latex_body
    Writes: state.full_document, state.latex_compilation, state.latex_fix_attempts
    """
    step = AgentStep(agent=AgentRole.LATEX_VALIDATOR)
    state.current_agent = AgentRole.LATEX_VALIDATOR

    logger.info(
        "latex_validator_start",
        job_id=state.job_id,
        attempt=state.latex_fix_attempts + 1,
    )

    try:
        # Wrap with preamble
        body = state.edited_latex_body
        if state.latex_fix_attempts > 0 and state.full_document:
            # On retry, use the fixed full document directly
            full_doc = state.full_document
        else:
            full_doc = wrap_with_style(body, state.request.pdf_style)

        state.full_document = full_doc

        # Compile
        config = get_config()
        checker = LatexChecker(pdflatex_path=config.pdflatex_path)
        result = checker.check(full_doc)

        state.latex_compilation = result
        state.latex_fix_attempts += 1

        if result.success:
            state.final_latex_body = state.edited_latex_body
            if result.pdf_bytes:
                try:
                    state.pdf_path = _persist_pdf(state.job_id, result.pdf_bytes)
                    state.pdf_base64 = base64.b64encode(result.pdf_bytes).decode("ascii")
                except OSError as persist_err:
                    state.pdf_path = ""
                    state.pdf_base64 = ""
                    logger.warning(
                        "latex_pdf_persist_failed",
                        job_id=state.job_id,
                        error=str(persist_err),
                    )
            else:
                state.pdf_path = ""
                state.pdf_base64 = ""
            logger.info("latex_validation_passed", job_id=state.job_id, pdf_path=state.pdf_path)
        else:
            logger.warning(
                "latex_validation_failed",
                job_id=state.job_id,
                errors=result.errors[:3],
                attempt=state.latex_fix_attempts,
            )

        step.output_summary = (
            f"{'PASS' if result.success else 'FAIL'}: "
            f"{len(result.errors)} errors, {len(result.warnings)} warnings"
        )

    except Exception as e:
        step.error = str(e)
        state.latex_fix_attempts += 1
        if get_settings().verification_fail_open:
            state.final_latex_body = state.edited_latex_body
            logger.warning("latex_validator_error_fail_open", job_id=state.job_id, error=str(e))
        else:
            logger.error("latex_validator_error_fail_closed", job_id=state.job_id, error=str(e))

    finally:
        step.completed_at = datetime.now()
        step.duration_seconds = (step.completed_at - step.started_at).total_seconds()
        state.steps.append(step)

    return state
