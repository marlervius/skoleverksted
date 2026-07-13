"""
Math verifier node — Uses SymPy to verify all mathematical claims.

This is NOT an LLM agent. It is a programmatic verification step that
extracts math claims from the LaTeX and verifies them symbolically.
"""

from __future__ import annotations

from datetime import datetime

import structlog

from app.config import get_settings
from app.models.state import AgentRole, AgentStep, PipelineState
from app.verification.math_checker import MathChecker

logger = structlog.get_logger()


def run_math_verifier(state: PipelineState) -> PipelineState:
    """
    Run SymPy-based math verification on the author's LaTeX output.

    Reads: state.raw_latex_body
    Writes: state.math_verification, state.math_verification_attempts, state.verified_latex_body
    """
    step = AgentStep(agent=AgentRole.MATH_VERIFIER)
    state.current_agent = AgentRole.MATH_VERIFIER

    logger.info(
        "math_verifier_start",
        job_id=state.job_id,
        attempt=state.math_verification_attempts + 1,
    )

    try:
        checker = MathChecker()
        result = checker.verify(state.raw_latex_body)

        state.math_verification = result
        state.math_verification_attempts += 1

        if result.all_correct:
            state.verified_latex_body = state.raw_latex_body
            logger.info(
                "math_verification_passed",
                job_id=state.job_id,
                claims_checked=result.claims_checked,
            )
        else:
            logger.warning(
                "math_verification_failed",
                job_id=state.job_id,
                incorrect=result.claims_incorrect,
                total=result.claims_checked,
                attempt=state.math_verification_attempts,
            )
            from app.pipeline.routing_helpers import can_retry_math

            if can_retry_math(state):
                state.author_retry_reason = "math"

        step.output_summary = result.summary

    except Exception as e:
        step.error = str(e)
        state.math_verification_attempts += 1
        if get_settings().verification_fail_open:
            state.verified_latex_body = state.raw_latex_body
            logger.warning("math_verifier_error_fail_open", job_id=state.job_id, error=str(e))
        else:
            logger.error("math_verifier_error_fail_closed", job_id=state.job_id, error=str(e))

    finally:
        step.completed_at = datetime.now()
        step.duration_seconds = (step.completed_at - step.started_at).total_seconds()
        state.steps.append(step)

    return state


def run_final_math_verifier(state: PipelineState) -> PipelineState:
    """Verify the editor's final body so an edit cannot invalidate the fasit badge."""
    step = AgentStep(agent=AgentRole.MATH_VERIFIER)
    state.current_agent = AgentRole.MATH_VERIFIER
    source = (
        state.edited_latex_body
        or state.verified_latex_body
        or state.raw_latex_body
    )

    logger.info("final_math_verifier_start", job_id=state.job_id)
    try:
        result = MathChecker().verify(source)
        state.math_verification = result
        state.math_verification_attempts += 1
        if result.all_correct:
            state.verified_latex_body = source
        step.output_summary = f"Endelig fasitkontroll: {result.summary}"
        logger.info(
            "final_math_verifier_complete",
            job_id=state.job_id,
            incorrect=result.claims_incorrect,
            unparseable=result.claims_unparseable,
        )
    except Exception as e:
        step.error = str(e)
        state.math_verification_attempts += 1
        if not get_settings().verification_fail_open:
            state.error_message = f"Endelig fasitkontroll feilet: {e}"
        logger.error("final_math_verifier_failed", job_id=state.job_id, error=str(e))
    finally:
        step.completed_at = datetime.now()
        step.duration_seconds = (step.completed_at - step.started_at).total_seconds()
        state.steps.append(step)

    return state
