"""Bounded automatic repair of the actual final mathematics candidate."""

from datetime import datetime
import re
import time

from app.models.llm import LLMInterface
from app.models.state import AgentRole, AgentStep, PipelineState, PipelineStatus
from app.pipeline.cancel import is_cancelled
from app.pipeline.document_edits import apply_edits, edit_prompt
from app.verification.math_checker import MathChecker, format_errors_for_agent
from app.verification.content_quality import evaluate_content_quality, format_quality_report_for_author
from Skoleverksted.backend.platform.quality_gate import run_quality_pipeline
from Skoleverksted.backend.platform.quality_runtime import run_bounded_sync


def prepare_release(state: PipelineState) -> bool:
    """Reserve two repairs after layout; every mutation gets a fresh audit.

    The earlier author budget may already be spent. This separate, bounded
    budget prevents that from handing unresolved work back to the teacher.
    No PDF or approval from an earlier revision survives a failed check.
    """
    body = (state.final_latex_body or state.edited_latex_body
            or state.verified_latex_body or state.raw_latex_body)
    match = re.search(r"\\begin\{document\}(.*?)\\end\{document\}", state.full_document, re.S)
    if match:
        body = match.group(1).strip()
    step = AgentStep(agent=AgentRole.MATH_VERIFIER)
    state.current_agent = AgentRole.MATH_VERIFIER
    deadline = time.monotonic() + 180
    seen = set()
    state.teacher_approved_at = ""
    state.approved_digest = ""
    try:
        for attempt in range(3):
            if is_cancelled(state.job_id):
                raise RuntimeError("Avbrutt av bruker")
            if not body.strip():
                raise ValueError("Sluttkontrollen mottok tomt innhold")
            if body in seen:
                raise ValueError("Reparasjonen ga ingen endring")
            seen.add(body)
            state.math_verification = MathChecker().verify(body)
            state.math_verification_attempts += 1
            quality = run_quality_pipeline(
                generator_id="matematikk.material", content=body,
                topic=state.request.topic, subject="Matematikk", level=state.request.grade,
                cancel_check=lambda: is_cancelled(state.job_id),
            )
            # The shared gate may patch content. Check that exact revision too.
            body = quality.approved_content
            state.math_verification = MathChecker().verify(body)
            state.content_quality = evaluate_content_quality(body, state.request)
            if state.request.material_type == "kapittel":
                from app.verification.semantic_quality import evaluate_semantic_quality
                score, issues = run_bounded_sync(
                    lambda: evaluate_semantic_quality(body, state.request),
                    timeout_seconds=max(0.1, deadline - time.monotonic()),
                    cancel_check=lambda: is_cancelled(state.job_id),
                    operation_name="final content quality check",
                )
                state.content_quality.semantic_score = score
                state.content_quality.issues.extend(issues)
                if issues and score < 70:
                    state.content_quality.passed = False
                    state.content_quality.score = min(state.content_quality.score, score)
            mv = state.math_verification
            if (mv.all_correct and not mv.claims_incorrect and not mv.claims_unparseable
                    and quality.source_approved and state.content_quality.passed):
                state.final_latex_body = body
                state.edited_latex_body = body
                state.verified_latex_body = body
                step.output_summary = f"Automatisk sluttkontroll bestått etter {attempt} reparasjoner"
                return True
            if attempt == 2 or time.monotonic() >= deadline:
                break
            feedback = "\n".join([
                format_errors_for_agent(mv),
                format_quality_report_for_author(state.content_quality),
                *quality.deterministic_failures,
                quality.passport.summary if not quality.source_approved else "",
            ])
            prompt = edit_prompt(body, feedback)
            response = run_bounded_sync(
                lambda: LLMInterface(temperature=0).invoke(
                    "Du reparerer matematikkmateriell automatisk. Bevar oppgaver, fasit, "
                    "læringsmål og nødvendig figurinnhold. Returner kun JSON-endringslisten. "
                    "Ikke be om lærergjennomgang og ikke skjul påstander for kontrollen.", prompt),
                timeout_seconds=max(0.1, deadline - time.monotonic()),
                cancel_check=lambda: is_cancelled(state.job_id),
                operation_name="automatic mathematics release repair",
            )
            body = apply_edits(body, response)
        raise ValueError("Sluttkandidaten bestod ikke alle kontrollene")
    except Exception as exc:
        step.error = str(exc)
        state.status = PipelineStatus.FAILED
        state.error_message = (
            "Avbrutt av bruker" if is_cancelled(state.job_id) else
            "Appen kunne ikke rette og verifisere materialet etter automatiske "
            "reparasjonsforsøk. Genereringen ble stoppet før eksport."
        )
        state.warning_reason = "verification"
        state.pdf_base64 = ""
        state.pdf_path = ""
        state.source_approved = False
        state.teacher_approved_at = ""
        state.approved_digest = ""
        state.release_manifest = {}
        return False
    finally:
        step.completed_at = datetime.now()
        step.duration_seconds = (step.completed_at - step.started_at).total_seconds()
        state.steps.append(step)
        state.current_agent = None
        state.total_duration_seconds = sum(s.duration_seconds for s in state.steps)
        state.total_tokens = sum(s.total_tokens for s in state.steps)
