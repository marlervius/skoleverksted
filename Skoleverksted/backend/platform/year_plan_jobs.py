"""Background generation for year plans.

The HTTP request only registers the work.  Planning and the global quality
pipeline may make several model calls, so they must not depend on a browser
connection staying open.
"""

from __future__ import annotations

import logging
import threading

from .models import (
    QualityQuarantineItem,
    TruthPassport,
    YearPlanCreate,
    YearPlanGenerateRequest,
)
from .quality_gate import content_digest, run_quality_pipeline
from .queue import get_durable_job_queue
from .store import get_platform_store
from .truth import TruthAudit
from .year_planner import build_year_plan


logger = logging.getLogger(__name__)


class YearPlanGenerationError(RuntimeError):
    """A teacher-safe generation failure."""


_AI_FALLBACK_REASON = (
    "AI-utkastet bestod ikke kildesjekken og ble forkastet. "
    "Planen du ser er en kontrollert reserveplan basert på lærerens mål og faste rammer."
)


def _mark_safe_fallback(plan: YearPlanCreate) -> YearPlanCreate:
    """Make the fail-closed fallback visible without retaining AI text."""
    plan.quality_stop_reason = _AI_FALLBACK_REASON
    plan.quarantine = [
        QualityQuarantineItem(
            content_type="interpretation",
            original_text="AI-generert årsplanutkast",
            location="Automatisk årsplanlegging",
            reason=(
                "Utkastet kunne ikke kildegodkjennes etter den automatiske "
                "revisjonsløkken og er derfor ikke lagret."
            ),
            suggested_replacement="Kontrollert, deterministisk reserveplan",
            omission_consequence=(
                "Ingen tekst fra det avviste AI-utkastet er med i årsplanen. "
                "Lærerens innsendte kompetansemål er bevart."
            ),
            status="removed",
        ),
        *plan.quarantine,
    ]
    if plan.truth_passport is not None:
        plan.truth_passport.summary = (
            "AI-utkastet ble forkastet av kildesjekken. Lagret plan er en "
            "deterministisk reserveplan med lærerens egne mål og uten "
            "ukontrollert AI-tekst."
        )
    return plan


def _verify_year_plan(
    proposal: YearPlanCreate,
    request: YearPlanGenerateRequest,
) -> YearPlanCreate:
    canonical = proposal.model_dump_json(exclude={
        "truth_passport", "quality_rounds", "quarantine", "quality_stop_reason",
        "content_revision", "approved_at", "approved_revision",
    })
    deterministic_audit = None
    if proposal.planning_source == "fallback":
        deterministic_audit = lambda **kwargs: TruthAudit(
            content=kwargs["content"],
            passport=TruthPassport(
                version="2.0",
                status="verified",
                topic=proposal.title,
                subject=proposal.subject,
                coverage_percent=100,
                summary="Deterministisk reserveplan; rammer og mål er lærerinput.",
            ),
        )
    quality = run_quality_pipeline(
        generator_id="platform.year_plan",
        content=canonical,
        topic=proposal.title,
        subject=proposal.subject,
        level=proposal.level,
        **({"audit": deterministic_audit} if deterministic_audit else {}),
    )
    if not quality.source_approved:
        if request.use_ai:
            logger.warning(
                "AI-utkastet til årsplanen %s ble blokkert; bygger kontrollert reserveplan.",
                proposal.title,
            )
            fallback_request = request.model_copy(update={"use_ai": False})
            fallback = build_year_plan(fallback_request)
            if _AI_FALLBACK_REASON not in fallback.notes:
                fallback.notes = f"{_AI_FALLBACK_REASON} {fallback.notes}".strip()
            return _mark_safe_fallback(_verify_year_plan(fallback, fallback_request))
        raise YearPlanGenerationError(
            "Årsplanen kunne ikke kildegodkjennes automatisk. Prøv igjen; ingen ukontrollert plan ble lagret."
        )
    try:
        controlled = YearPlanCreate.model_validate_json(quality.approved_content)
    except ValueError as exc:
        raise YearPlanGenerationError(
            "Den kontrollerte årsplanen hadde ugyldig struktur. Prøv igjen; ingen ufullstendig plan ble lagret."
        ) from exc
    controlled.truth_passport = quality.passport
    controlled.quality_rounds = quality.rounds
    controlled.quarantine = quality.quarantine
    controlled.quality_stop_reason = quality.stop_reason
    controlled.content_revision = content_digest(quality.approved_content)
    return controlled


def build_verified_year_plan(request: YearPlanGenerateRequest) -> YearPlanCreate:
    """Build the proposal and pass the exact persisted structure through quality control."""
    return _verify_year_plan(build_year_plan(request), request)


def run_year_plan_job(job_id: str, request: YearPlanGenerateRequest) -> None:
    """Generate, verify and persist one plan independently of the HTTP request."""
    store = get_platform_store()
    queue = get_durable_job_queue()
    try:
        with queue.claim(job_id, auto_complete=False):
            current = store.get_job(job_id)
            if current is None or current.status == "cancelled":
                return
            store.update_job_state(
                job_id,
                status="planning",
                message="AI-crewet lager faglig progresjon og perioder …",
                progress=15,
                retryable=True,
            )
            proposal = build_year_plan(request)
            store.update_job_state(
                job_id,
                status="verifying",
                message="AI-crewet kontrollerer fakta, kilder og struktur …",
                progress=50,
                retryable=True,
            )

            # Reuse the already-built proposal. This avoids a second planner
            # model call while still exercising the same verification helper.
            controlled = _verify_year_plan(proposal, request)

            store.update_job_state(
                job_id,
                status="generating",
                message="Den godkjente årsplanen lagres …",
                progress=90,
                retryable=True,
            )
            plan = store.create_year_plan(controlled)
            store.update_job_result_summary(
                job_id,
                {
                    "plan_id": plan.id,
                    "title": plan.title,
                    "subject": plan.subject,
                    "level": plan.level,
                    "school_year": plan.school_year,
                    "planning_source": plan.planning_source,
                },
            )
            if plan.planning_source == "fallback":
                queue.finish(
                    job_id,
                    message=(
                        "AI-utkastet ble forkastet. En trygg reserveplan er "
                        "lagret med lærerens kompetansemål."
                    ),
                )
            else:
                queue.finish(job_id, message="Årsplanen er ferdig generert og kildekontrollert.")
    except YearPlanGenerationError as exc:
        queue.fail(job_id, str(exc))
    except Exception:
        logger.exception("Årsplanjobben %s feilet", job_id)
        queue.fail(
            job_id,
            "Årsplanen kunne ikke ferdigstilles. Prøv igjen; ingen ufullstendig plan ble lagret.",
        )


def start_year_plan_worker(job_id: str, request: YearPlanGenerateRequest) -> None:
    threading.Thread(
        target=run_year_plan_job,
        args=(job_id, request.model_copy(deep=True)),
        name=f"year-plan-{job_id[-8:]}",
        daemon=True,
    ).start()
