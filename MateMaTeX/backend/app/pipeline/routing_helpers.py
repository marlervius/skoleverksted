"""Shared routing helpers for pipeline agents (state must be set in nodes, not routers)."""

from __future__ import annotations

from datetime import datetime

from app.config import get_config
from app.models.state import AgentRole, ContentQualityReport, PipelineState


def author_run_count(state: PipelineState) -> int:
    return sum(1 for s in state.steps if s.agent == AgentRole.AUTHOR)


def over_time_budget(state: PipelineState) -> bool:
    try:
        budget = get_config().pipeline_max_seconds
    except Exception:
        return False
    elapsed = (datetime.now() - state.created_at).total_seconds()
    return elapsed > budget


def math_errors_worth_author_retry(state: PipelineState) -> bool:
    mv = state.math_verification
    incorrect = mv.claims_incorrect
    if incorrect <= 0:
        return False
    if mv.claims_unparseable >= incorrect * 10:
        return False
    verified = max(0, mv.claims_checked - mv.claims_unparseable)
    if incorrect <= 3 and verified < 10 and mv.claims_unparseable > verified:
        return False
    return True


def can_retry_math(state: PipelineState) -> bool:
    config = get_config()
    # A confirmed fasit error must get at least one author correction pass.
    # The noise heuristic below is useful for later passes on documents with
    # many unparseable claims, but previously caused immediate failure after
    # the first verifier run (with no opportunity for the author to fix it).
    first_correction = state.math_verification_attempts == 1
    return (
        not state.math_verification.all_correct
        and state.math_verification.claims_incorrect > 0
        and state.math_verification_attempts < config.max_verification_retries
        and (first_correction or math_errors_worth_author_retry(state))
        and not over_time_budget(state)
        and author_run_count(state) < config.max_author_runs
    )


def can_retry_content_quality(state: PipelineState, report: ContentQualityReport) -> bool:
    if state.request.material_type != "kapittel" or report.passed:
        return False
    config = get_config()
    return (
        state.content_quality_attempts < config.max_content_quality_retries
        and not over_time_budget(state)
        and author_run_count(state) < config.max_author_runs
    )
