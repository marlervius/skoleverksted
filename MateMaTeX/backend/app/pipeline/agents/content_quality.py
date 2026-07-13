"""
Content quality gate — validates kapittel completeness before LaTeX compile.

Retries the author when coverage, examples, graphs, or off-topic guards fail.
"""

from __future__ import annotations

from datetime import datetime

import structlog

from app.models.state import AgentRole, AgentStep, PipelineState
from app.pipeline.routing_helpers import can_retry_content_quality
from app.verification.content_quality import evaluate_content_quality

logger = structlog.get_logger()


def run_content_quality(state: PipelineState) -> PipelineState:
    """
    Evaluate edited (or verified) LaTeX against curriculum + kapittel standards.

    Reads: state.edited_latex_body / verified / raw
    Writes: state.content_quality, state.steps, author_retry_reason (when retrying)
    """
    step = AgentStep(agent=AgentRole.CONTENT_QUALITY)
    state.current_agent = AgentRole.CONTENT_QUALITY

    body = state.edited_latex_body or state.verified_latex_body or state.raw_latex_body

    logger.info(
        "content_quality_start",
        job_id=state.job_id,
        material_type=state.request.material_type,
        body_len=len(body),
    )

    try:
        report = evaluate_content_quality(body, state.request)

        if state.request.material_type == "kapittel":
            from app.verification.semantic_quality import evaluate_semantic_quality

            sem_score, sem_issues = evaluate_semantic_quality(body, state.request)
            report.semantic_score = sem_score
            if sem_issues:
                report.issues.extend(sem_issues)
                if sem_score < 70:
                    report.score = min(report.score, sem_score)
                    report.passed = report.passed and sem_score >= 70
                report.semantic_summary = (
                    f"Semantisk vurdering: {sem_score}/100 "
                    f"({len(sem_issues)} observasjoner)"
                )

        state.content_quality = report

        if report.passed:
            step.output_summary = f"Quality OK ({report.score}/100)"
            logger.info(
                "content_quality_pass",
                job_id=state.job_id,
                score=report.score,
            )
        else:
            n_issues = len(report.issues)
            step.output_summary = f"Quality FAIL ({report.score}/100, {n_issues} issues)"
            logger.warning(
                "content_quality_fail",
                job_id=state.job_id,
                score=report.score,
                issues=n_issues,
                missing=report.missing_subtopics,
            )
            if can_retry_content_quality(state, report):
                state.author_retry_reason = "quality"
                state.skip_editor_once = True
                logger.info(
                    "content_quality_scheduled_retry",
                    job_id=state.job_id,
                    next_attempt=state.content_quality_attempts + 1,
                )

    except Exception as e:
        step.error = str(e)
        logger.error("content_quality_error", job_id=state.job_id, error=str(e))

    finally:
        step.completed_at = datetime.now()
        step.duration_seconds = (step.completed_at - step.started_at).total_seconds()
        state.steps.append(step)

    return state
