"""Bounded automatic repair of the actual final mathematics candidate."""

from datetime import datetime
import re
import time

import structlog

from app.models.llm import LLMInterface
from app.models.state import AgentRole, AgentStep, PipelineState, PipelineStatus
from app.pipeline.cancel import is_cancelled
from app.pipeline.document_edits import apply_edits, edit_prompt
from app.public_errors import RELEASE_VERIFICATION_ERROR
from app.verification.math_checker import MathChecker, format_errors_for_agent
from app.verification.content_quality import evaluate_content_quality, format_quality_report_for_author
from Skoleverksted.backend.platform.quality_gate import run_quality_pipeline
from Skoleverksted.backend.platform.quality_runtime import run_bounded_sync

logger = structlog.get_logger()

_MAX_REPAIRS = 10
_MAX_STALLED_REPAIRS = 2
_CLAIMS_PER_REPAIR = 6  # Leave space for language/source edits in the eight-edit response.
# One whole-chapter round (fact audit, math proof, rubric) can take minutes.
# The budget bounds how long repairs may continue; it never cuts a started
# verification short, because an unverified document cannot be released.
_RELEASE_BUDGET_SECONDS = 360
_MODEL_CALL_SECONDS = 150
# A repair is pointless unless it and the re-verification of its result fit.
_MIN_REPAIR_ROUND_SECONDS = 90


class _ReviewRequired(ValueError):
    """A checked draft remains unresolved after the bounded repair budget."""


def _release(state: PipelineState, step: AgentStep, body: str, quality, repairs: int,
             advisory: bool) -> bool:
    """Record the exact revision that passed every machine-provable check."""
    state.final_latex_body = body
    state.edited_latex_body = body
    state.verified_latex_body = body
    state.truth_passport = quality.passport.model_dump(mode="json")
    state.quality_rounds = [item.model_dump(mode="json") for item in quality.rounds]
    state.quarantine = [item.model_dump(mode="json") for item in quality.quarantine]
    state.quality_stop_reason = quality.stop_reason
    state.verification_content = body
    state.release_manifest = quality.release_manifest.model_dump(mode="json") if quality.release_manifest else {}
    state.source_approved = quality.source_approved
    step.output_summary = (
        f"Automatisk sluttkontroll bestått etter {repairs} reparasjoner"
        + (f" — {len(state.content_quality.issues)} forbedringsforslag står igjen" if advisory else "")
    )
    logger.info("release_verification_passed", job_id=state.job_id, repairs=repairs, advisory=advisory)
    return True


def prepare_release(state: PipelineState) -> bool:
    """Repair in small batches after layout; every mutation gets a fresh audit.

    The earlier author budget may already be spent. This separate, bounded
    budget gives large chapters enough rounds while progress is being made.
    Two stalled repairs, ten total repairs, or the deadline stop the loop.
    An unresolved draft never inherits an earlier PDF or approval.

    A document is released only when every machine-provable check passes.
    Pedagogical suggestions from the rubric drive repairs while budget lasts,
    and are then delivered as notes rather than withholding a proven document.
    """
    body = (state.final_latex_body or state.edited_latex_body
            or state.verified_latex_body or state.raw_latex_body)
    match = re.search(r"\\begin\{document\}(.*?)\\end\{document\}", state.full_document, re.S)
    if match:
        body = match.group(1).strip()
    step = AgentStep(agent=AgentRole.MATH_VERIFIER)
    state.current_agent = AgentRole.MATH_VERIFIER
    deadline = time.monotonic() + _RELEASE_BUDGET_SECONDS
    seen = set()
    repair_error = ""
    previous_problems = None
    stalled = 0
    state.teacher_approved_at = ""
    state.automatic_approved_revision = ""
    state.approved_digest = ""
    try:
        for attempt in range(_MAX_REPAIRS + 1):
            if is_cancelled(state.job_id):
                raise RuntimeError("Avbrutt av bruker")
            if not body.strip():
                raise ValueError("Sluttkontrollen mottok tomt innhold")
            seen.add(body)
            state.math_verification_attempts += 1
            quality = run_quality_pipeline(
                generator_id="matematikk.material", content=body,
                topic=state.request.topic, subject="Matematikk", level=state.request.grade,
                cancel_check=lambda: is_cancelled(state.job_id),
            )
            # The shared gate may patch content. Prove that exact revision.
            body = quality.approved_content
            state.math_verification = MathChecker().verify(body)
            state.content_quality = evaluate_content_quality(body, state.request)
            rules_passed = state.content_quality.passed
            semantic_issues = []
            if state.request.material_type == "kapittel":
                from app.verification.semantic_quality import evaluate_semantic_quality
                try:
                    score, issues = run_bounded_sync(
                        lambda: evaluate_semantic_quality(body, state.request),
                        timeout_seconds=_MODEL_CALL_SECONDS,
                        cancel_check=lambda: is_cancelled(state.job_id),
                        operation_name="final content quality check",
                    )
                except Exception as exc:
                    if is_cancelled(state.job_id):
                        raise
                    # The rubric is advisory. Its unavailability is reported
                    # honestly, but cannot fail a mathematically proven document.
                    logger.warning("release_rubric_unavailable", job_id=state.job_id,
                                   error=str(exc), error_type=type(exc).__name__)
                    state.content_quality.semantic_summary = (
                        "Den faglige KI-vurderingen kunne ikke fullføres denne gangen.")
                else:
                    state.content_quality.semantic_score = score
                    state.content_quality.issues.extend(issues)
                    semantic_issues = issues
                    if score < 70:
                        state.content_quality.passed = False
                        state.content_quality.score = min(state.content_quality.score, score)
            mv = state.math_verification
            language_issues = [i for i in state.content_quality.issues if i.code == "language"]
            # Only machine-provable defects withhold the document. The rubric's
            # pedagogical suggestions are opinions: they steer every remaining
            # repair round, but a proven document is never held back — and never
            # handed to a teacher for manual sign-off — because of them.
            blocking = (not mv.all_correct or mv.claims_incorrect or mv.claims_unparseable
                        or not quality.source_approved or not rules_passed or language_issues)
            advisory = bool(semantic_issues) or state.content_quality.semantic_score < 70
            # Compare verified problems, not merely whether the model changed
            # text. Rewording an unresolved claim cannot buy unlimited retries.
            problems = (
                mv.claims_incorrect,
                mv.claims_unparseable,
                int(not quality.source_approved),
                int(not rules_passed),
                len(state.content_quality.issues),
                100 - state.content_quality.score,
            )
            if previous_problems is not None:
                stalled = 0 if problems < previous_problems else stalled + 1
            previous_problems = problems
            budget_spent = (attempt == _MAX_REPAIRS or stalled >= _MAX_STALLED_REPAIRS
                            or deadline - time.monotonic() < _MIN_REPAIR_ROUND_SECONDS)
            if not blocking and (not advisory or budget_spent):
                return _release(state, step, body, quality, attempt, advisory)
            if budget_spent:
                break
            feedback = "\n".join([
                format_errors_for_agent(mv, max_claims=_CLAIMS_PER_REPAIR),
                format_quality_report_for_author(state.content_quality),
                *(f"SPRÅKFEIL SOM MÅ RETTES: {i.message}" for i in language_issues),
                *quality.deterministic_failures,
                quality.passport.summary if not quality.source_approved else "",
            ])
            # Retry the repair itself when the model is slow, fails or returns
            # an unusable edit list. Re-auditing an unchanged document would
            # only spend the budget that the repair needs.
            candidate = None
            for _call in range(_MAX_STALLED_REPAIRS + 1):
                if deadline - time.monotonic() < _MIN_REPAIR_ROUND_SECONDS:
                    break
                prompt = edit_prompt(body, "\n".join([feedback, repair_error]))
                step.retries += 1
                try:
                    response = run_bounded_sync(
                        lambda: LLMInterface(temperature=0).invoke(
                            "Du reparerer matematikkmateriell automatisk. Bevar oppgaver, fasit, "
                            "læringsmål og nødvendig figurinnhold. Returner kun JSON-endringslisten. "
                            "Ikke be om lærergjennomgang og ikke skjul påstander for kontrollen.", prompt),
                        timeout_seconds=min(_MODEL_CALL_SECONDS, deadline - time.monotonic()),
                        cancel_check=lambda: is_cancelled(state.job_id),
                        operation_name="automatic mathematics release repair",
                    )
                    candidate = apply_edits(body, response)
                    if candidate in seen:
                        raise ValueError("Reparasjonen ga ingen ny endring")
                    break
                except Exception as exc:
                    if is_cancelled(state.job_id):
                        raise
                    candidate = None
                    # A rejected edit never mutates the candidate. Give the
                    # model actionable feedback; a failed call needs none.
                    repair_error = (
                        f"Forrige endringsliste ble avvist: {exc}. "
                        "Returner en gyldig JSON-endringsliste som retter de uløste problemene."
                        if isinstance(exc, ValueError) else ""
                    )
                    logger.warning("release_repair_rejected", job_id=state.job_id,
                                   attempt=attempt + 1, reason=str(exc), error_type=type(exc).__name__)
            if candidate is None:
                break  # No usable repair: decide on the last verified revision.
            body = candidate
            repair_error = ""
        # The loop only ends here after `body` was verified in its last round.
        if not blocking:
            return _release(state, step, body, quality, attempt, advisory)
        raise _ReviewRequired("Sluttkandidaten bestod ikke alle kontrollene")
    except Exception as exc:
        step.error = str(exc)
        state.status = PipelineStatus.FAILED
        errors = state.math_verification.errors[:3]
        if is_cancelled(state.job_id):
            state.error_message = "Avbrutt av bruker"
        elif isinstance(exc, _ReviewRequired) and errors:
            # A proven fasit error survived every repair. Say which, so the
            # failure is actionable instead of a generic stop.
            state.error_message = (
                f"SymPy fant {state.math_verification.claims_incorrect} feil i fasiten som "
                f"ikke lot seg reparere automatisk. Materialet leveres ikke. Kontroller: "
                + " | ".join(f"{c.latex_expression.strip()}: {c.error_message.strip()}" for c in errors)
            )
        else:
            state.error_message = RELEASE_VERIFICATION_ERROR
        state.warning_reason = "verification"
        state.pdf_base64 = ""
        state.pdf_path = ""
        state.source_approved = False
        state.teacher_approved_at = ""
        state.automatic_approved_revision = ""
        state.approved_digest = ""
        state.release_manifest = {}
        state.compiled_document_digest = ""
        state.latex_compilation.pdf_base64 = ""
        state.latex_compilation.pdf_bytes = None
        state.latex_compilation.pdf_path = ""
        if (isinstance(exc, _ReviewRequired) and body.strip()
                and not state.math_verification.claims_incorrect and not is_cancelled(state.job_id)):
            # Review is a terminal draft state, never an approval or export.
            state.status = PipelineStatus.REVIEW_REQUIRED
            state.error_message = "Appen klarte ikke å verifisere hele dokumentet innen forsøksgrensen. Utkastet er bevart, men er ikke klart til bruk. Prøv igjen for en ny automatisk kontroll og reparasjon."
            state.final_latex_body = body
            state.verification_content = body
            if match:
                state.full_document = state.full_document[:match.start(1)] + body + state.full_document[match.end(1):]
            else:
                from app.latex.preamble import wrap_with_style
                state.full_document = wrap_with_style(body, state.request.pdf_style)
            step.error = ""
            step.output_summary = state.error_message
        logger.warning(
            "release_review_required" if state.status == PipelineStatus.REVIEW_REQUIRED else "release_verification_failed", job_id=state.job_id,
            error=str(exc), error_type=type(exc).__name__, repairs=step.retries,
            incorrect=state.math_verification.claims_incorrect,
            unparseable=state.math_verification.claims_unparseable,
        )
        return False
    finally:
        step.completed_at = datetime.now()
        step.duration_seconds = (step.completed_at - step.started_at).total_seconds()
        state.steps.append(step)
        state.current_agent = None
        state.total_duration_seconds = sum(s.duration_seconds for s in state.steps)
        state.total_tokens = sum(s.total_tokens for s in state.steps)
