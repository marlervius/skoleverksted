"""Global, fail-closed verification and export gate for Skoleverksted.

All generators submit canonical text here before teacher approval.  The engine
owns the bounded repair loop, claim-level quarantine and version/digest checks;
renderers and HTTP routes are deliberately not allowed to reinterpret status.
"""

from __future__ import annotations

import ast
import hashlib
import json
import logging
import operator
import re
import time
from dataclasses import dataclass
from typing import Callable, Iterable

from .models import (
    ReleaseManifest,
    QualityQuarantineItem,
    QualityRevisionRound,
    RepairChange,
    TruthClaim,
    TruthPassport,
    TruthSource,
)
from .document_revision import (
    apply_repair_patch,
    build_document_revision,
    build_repair_patch,
    canonical_document_content,
)
from .truth import (
    TruthAudit,
    _blocked_passport,
    audit_truth,
    content_claim_is_resolved,
    content_type_requires_external_source,
)
from .quality_runtime import (
    QualityLayerCancelled,
    QualityLayerTimeout,
    env_float,
    env_int,
    run_bounded_sync,
)


logger = logging.getLogger(__name__)

DEFAULT_MODEL_CALL_TIMEOUT_SECONDS = 45.0
DEFAULT_MAX_MODEL_ATTEMPTS = 2
DEFAULT_TRUTH_LAYER_TIMEOUT_SECONDS = 120.0
DEFAULT_MAX_REVISION_ROUNDS = 5


def quality_model_timeout_seconds() -> float:
    return env_float("QUALITY_GATE_MODEL_TIMEOUT_SECONDS", DEFAULT_MODEL_CALL_TIMEOUT_SECONDS)


def quality_layer_timeout_seconds() -> float:
    return env_float("QUALITY_GATE_TIMEOUT_SECONDS", DEFAULT_TRUTH_LAYER_TIMEOUT_SECONDS)


def quality_max_model_attempts() -> int:
    return env_int("QUALITY_GATE_MAX_MODEL_ATTEMPTS", DEFAULT_MAX_MODEL_ATTEMPTS, maximum=2)


def quality_max_revision_rounds() -> int:
    # This is an operation budget, not an approval threshold.  The loop stops
    # early on no progress and only a freshly re-audited revision can pass.
    return env_int("QUALITY_GATE_MAX_REVISION_ROUNDS", DEFAULT_MAX_REVISION_ROUNDS, maximum=8)


MAX_REVISION_ROUNDS = DEFAULT_MAX_REVISION_ROUNDS

# Mathematics has its own deterministic evidence chain: SymPy verifies
# mathematical claims and the LaTeX checker verifies the rendered document.
# Do not send ordinary mathematical notation through the web fact auditor;
# doing so makes a provider outage look like a bad answer key and blocks PDF
# generation for otherwise valid worksheets.  A custom auditor is still
# honoured below so tests and explicitly requested review workflows remain
# fail-closed.
MATHEMATICS_GENERATORS: frozenset[str] = frozenset(
    {
        "matematikk.material",
        "matematikk.differentiated",
        "matematikk.exercise_variant",
        "matematikk.editor_ai_action",
    }
)

# This is the contract surface.  A new generator must be registered here and
# covered by the contract test before it can be shipped through the unified app.
GENERATOR_CONTRACTS: frozenset[str] = frozenset(
    {
        "platform.year_plan",
        "platform.compendium",
        "platform.teaching_package.presentation",
        "platform.teaching_package.student_sheet",
        "platform.teaching_package.exercise_sheet",
        "platform.teaching_package.answer_key",
        "platform.teaching_package.teacher_guide",
        "platform.theme_pack.teacher_guide",
        "fag.learning_sheet",
        "fag.differentiated",
        "fag.assessment",
        "fag.lesson_sequence",
        "fag.docx",
        "norsk.learning_sheet",
        "norsk.preview_pdf",
        "norsk.dual_level",
        "norsk.multi_level",
        "matematikk.material",
        "matematikk.differentiated",
        "matematikk.exercise_variant",
        "matematikk.editor_ai_action",
    }
)

EXPORT_CONTRACTS: frozenset[str] = frozenset(
    {
        "platform.compendium.pdf",
        "platform.compendium.docx",
        "platform.teaching_package.pdf",
        "platform.teaching_package.docx",
        "platform.teaching_package.pptx",
        "platform.teaching_package.zip",
        "platform.year_plan.material",
        "platform.theme_pack.teacher_guide",
        "fag.pdf",
        "fag.docx",
        "norsk.pdf",
        "norsk.zip",
        "matematikk.pdf",
        "matematikk.docx",
        "matematikk.pptx",
        "matematikk.shared_pdf",
    }
)


def content_digest(content: str) -> str:
    return hashlib.sha256(str(content or "").replace("\r\n", "\n").strip().encode("utf-8")).hexdigest()


def claim_requires_evidence(claim: TruthClaim) -> bool:
    return content_type_requires_external_source(claim.content_type)


def claim_is_resolved(claim: TruthClaim) -> bool:
    return content_claim_is_resolved(
        content_type=claim.content_type,
        status=claim.status,
        source_urls=claim.source_urls,
    )


def _mathematics_truth_audit(
    *,
    content: str,
    topic: str,
    subject: str,
) -> TruthAudit:
    """Create the explicit non-web passport for deterministic math content.

    This is not a blanket approval for mathematical correctness.  The shared
    pipeline still runs ``deterministic_math_failures`` and the math graph
    already rejects incorrect SymPy answers.  The passport simply records
    that web evidence is not the applicable gate for notation, exercises,
    transformations, and answer keys.
    """
    return TruthAudit(
        content=content,
        passport=TruthPassport(
            version="3.0",
            content_revision=content_digest(content),
            status="verified",
            topic=topic,
            subject=subject,
            coverage_percent=100,
            verified_claims=0,
            total_claims=0,
            register_complete=True,
            claims=[],
            sources=[],
            limitations=[
                "Matematikkinnhold vurderes med SymPy og LaTeX-kontroll, ikke web-faktasøk.",
                "Eventuelle eksterne virkelighetsopplysninger i teksten må fortsatt leses av lærer.",
            ],
            summary=(
                "Matematikkens uttrykk og fasit følger den deterministiske "
                "SymPy-kontrollen. Web-faktasøk er ikke nødvendig for dette innholdet."
            ),
        ),
    )


_BIN_OPS: dict[type[ast.operator], Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}
_UNARY_OPS: dict[type[ast.unaryop], Callable[[float], float]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _numeric_expression(value: str) -> float:
    node = ast.parse(value.replace("^", "**"), mode="eval").body

    def evaluate(item: ast.AST) -> float:
        if isinstance(item, ast.Constant) and isinstance(item.value, (int, float)):
            return float(item.value)
        if isinstance(item, ast.BinOp) and type(item.op) in _BIN_OPS:
            return _BIN_OPS[type(item.op)](evaluate(item.left), evaluate(item.right))
        if isinstance(item, ast.UnaryOp) and type(item.op) in _UNARY_OPS:
            return _UNARY_OPS[type(item.op)](evaluate(item.operand))
        raise ValueError("Uttrykket inneholder elementer som ikke kan kontrolleres deterministisk.")

    return evaluate(node)


def deterministic_math_failures(content: str) -> list[str]:
    """Check plain numeric equalities without executing arbitrary input."""
    failures: list[str] = []
    pattern = re.compile(r"(?<![\w\\])(-?\d+(?:[.,]\d+)?(?:\s*[-+*/^]\s*-?\d+(?:[.,]\d+)?)+)\s*=\s*(-?\d+(?:[.,]\d+)?)")
    for match in pattern.finditer(content):
        left, right = (part.replace(",", ".") for part in match.groups())
        try:
            if abs(_numeric_expression(left) - float(right)) > 1e-9:
                failures.append(match.group(0))
        except (SyntaxError, TypeError, ValueError, ZeroDivisionError, OverflowError):
            failures.append(match.group(0))
    return failures


def _remove_exact_claim(content: str, exact: str) -> tuple[str, bool]:
    exact = exact.strip()
    if not exact or content.count(exact) != 1:
        return content, False
    start = content.find(exact)
    end = start + len(exact)
    # Only remove a complete sentence/line.  Ambiguous fragments stay blocked
    # until the teacher edits them, preventing accidental context damage.
    before = content[:start].rstrip(" \t")
    raw_after = content[end:]
    after = raw_after.lstrip(" \t")
    if before and before[-1] not in ".!?\n\r:;":
        return content, False
    if after and exact[-1:] not in ".!?" and after[0] not in ".!?\n\r":
        return content, False
    if after[:1] in ".!?":
        after = after[1:].lstrip(" \t")
    joiner = "\n" if before.endswith(("\n", "\r")) or after.startswith(("\n", "\r")) else " "
    return (before.rstrip() + joiner + after.lstrip()).strip(), True


def _remove_exact_claim_from_json(
    content: str,
    exact: str,
    *,
    action: str = "remove",
    replacement: str = "",
) -> tuple[str, bool]:
    """Repair one unambiguous claim inside JSON string values.

    A qualified replacement is applied only when the claim occurs once in the
    complete document. The exact revised JSON is always audited again before it
    can become source-approved. If a precise replacement/removal is unsafe, the
    complete affected field is withheld so unresolved text cannot leak.
    """
    try:
        payload = json.loads(content)
    except (TypeError, json.JSONDecodeError):
        return content, False

    exact = exact.strip()
    safe_replacement = replacement.strip()
    if not exact:
        return content, False

    changed = False
    occurrences = content.count(exact)
    withheld_notice = "[Utelatt: denne delen kunne ikke kildeverifiseres.]"

    def revise(value: object) -> object:
        nonlocal changed
        if isinstance(value, str) and exact in value:
            if (
                action == "qualify"
                and safe_replacement
                and safe_replacement != exact
                and occurrences == 1
            ):
                changed = True
                return value.replace(exact, safe_replacement, 1)

            # A unique, complete sentence can be removed precisely. If the
            # fragment is repeated or partial, withhold every affected field.
            revised, applied = _remove_exact_claim(value, exact)
            if applied and occurrences == 1:
                changed = True
                return revised
            changed = True
            return withheld_notice
        if isinstance(value, list):
            return [revise(item) for item in value]
        if isinstance(value, dict):
            return {key: revise(item) for key, item in value.items()}
        return value

    revised_payload = revise(payload)
    if not changed:
        return content, False
    return json.dumps(revised_payload, ensure_ascii=False), True


def _quarantine_item(claim: TruthClaim) -> QualityQuarantineItem:
    return QualityQuarantineItem(
        claim_id=claim.id,
        content_type=claim.content_type,
        original_text=claim.exact_text or claim.claim,
        location=claim.location or "Ukjent seksjon",
        reason=claim.evidence or "Påstanden mangler tilstrekkelig dokumentasjon.",
        source_attempts=claim.source_attempts,
        suggested_replacement=claim.replacement,
        omission_consequence="Teksten er utelatt fra godkjent innhold og alle eksportformater.",
    )


def _withhold_unresolved_claims(
    content: str,
    claims: Iterable[TruthClaim],
    quarantine: dict[str, QualityQuarantineItem],
) -> tuple[str, list[TruthClaim], bool]:
    """Apply bounded decoded-node patches for unresolved claims.

    Kept as a compatibility helper for older callers.  It intentionally does
    not put ``[Utelatt …]`` into student content and an absent substring is not
    evidence that a previous repair succeeded.
    """
    current = content
    unsafe: list[TruthClaim] = []
    handled = False
    for claim in claims:
        bound = claim
        revision = build_document_revision(current)
        if not bound.node_id:
            from .document_revision import bind_claim
            bound = bind_claim(bound, revision)
        patch, _ = build_repair_patch(bound)
        result = apply_repair_patch(current, patch) if patch else None
        if result and result.applied:
            current = result.content
            handled = True
            item = _quarantine_item(bound).model_copy(update={"status": "removed"})
            quarantine.setdefault(f"{bound.id}:{item.original_text}", item)
        else:
            unsafe.append(bound)
    return current, unsafe, handled


def _changes(content_after: str, claims: Iterable[TruthClaim]) -> list[RepairChange]:
    result: list[RepairChange] = []
    for claim in claims:
        if claim_is_resolved(claim):
            continue
        applied = bool(claim.exact_text and claim.exact_text not in content_after)
        result.append(
            RepairChange(
                issue_id=claim.id,
                action=claim.action,
                result="applied" if applied else "manual_review",
                before=claim.exact_text or claim.claim,
                after=claim.replacement if applied else "",
                reason=(
                    "Fagredaktøren endret påstanden før ny kontroll."
                    if applied
                    else "Påstanden kunne ikke endres sikkert automatisk."
                ),
                source_refs=claim.source_urls,
            )
        )
    return result


@dataclass(frozen=True)
class QualityGateResult:
    approved_content: str
    passport: TruthPassport
    rounds: list[QualityRevisionRound]
    quarantine: list[QualityQuarantineItem]
    stop_reason: str
    deterministic_failures: list[str]
    release_manifest: ReleaseManifest | None = None

    @property
    def source_approved(self) -> bool:
        unresolved = [claim for claim in self.passport.claims if not claim_is_resolved(claim)]
        return (
            self.passport.register_complete
            and not unresolved
            and not self.deterministic_failures
            and self.passport.status == "verified"
            and self.passport.version == "3.0"
            and self.passport.content_revision == content_digest(self.approved_content)
            and self.release_manifest is not None
            and self.release_manifest.document_hash == content_digest(self.approved_content)
        )

    @property
    def quality_status(self) -> str:
        """Terminal product status; never infer approval from partial content."""
        return "source_approved" if self.source_approved else "needs_teacher_review"


def verify_teacher_export(
    *,
    generator_id: str,
    export_id: str,
    content: str,
    topic: str,
    subject: str,
    level: str,
    teacher_approved: bool,
    provided_sources: Iterable[object] = (),
) -> QualityGateResult:
    """Verify an ad-hoc editor/export payload and bind approval to its hash.

    If the controller needs to alter or quarantine anything, the one-shot
    export is rejected: the teacher must first review the revised content.
    """
    result = run_quality_pipeline(
        generator_id=generator_id,
        content=content,
        topic=topic,
        subject=subject,
        level=level,
        provided_sources=provided_sources,
    )
    if result.approved_content != content or result.quarantine:
        raise PermissionError(
            "Eksportporten er lukket: kontrollen endret eller utelot innhold; "
            "vis den kontrollerte revisjonen for læreren før ny godkjenning."
        )
    require_export_ready(
        export_id=export_id,
        content=content,
        verification_status=result.passport.status,
        verified_revision=result.passport.content_revision,
        verification_version=result.passport.version,
        teacher_approved=teacher_approved,
        approved_revision=content_digest(content) if teacher_approved else "",
        release_manifest=result.release_manifest.model_dump(mode="json") if result.release_manifest else None,
    )
    return result


def _run_quality_pipeline_legacy(
    *,
    generator_id: str,
    content: str,
    topic: str,
    subject: str,
    level: str,
    provided_sources: Iterable[object] = (),
    max_rounds: int | None = None,
    audit: Callable[..., TruthAudit] = audit_truth,
    cancel_check: Callable[[], bool] | None = None,
    progress_callback: Callable[[dict[str, object]], None] | None = None,
    request_id: str = "",
    timeout_seconds: float | None = None,
) -> QualityGateResult:
    if generator_id not in GENERATOR_CONTRACTS:
        raise ValueError(f"Generatoren mangler global verifikasjonskontrakt: {generator_id}")
    if not content.strip():
        raise ValueError("Tomt innhold kan ikke passere kvalitetspipelinen.")
    configured_rounds = quality_max_revision_rounds()
    max_rounds = max(1, min(configured_rounds, max_rounds or configured_rounds))
    total_budget = timeout_seconds or quality_layer_timeout_seconds()
    deadline = time.monotonic() + total_budget
    current = content
    seen: set[str] = set()
    rounds: list[QualityRevisionRound] = []
    final: TruthPassport | None = None
    stop_reason = ""
    previous_score = (-1, 10**9)
    quarantine_by_text: dict[str, QualityQuarantineItem] = {}
    budget_exhausted = False

    def emit_progress(message: str, *, round_number: int, claims_found: int = 0,
                      claims_verified: int = 0, quarantined: int = 0) -> None:
        remaining = max(0.0, deadline - time.monotonic())
        event: dict[str, object] = {
            "message": message,
            "step": "truth_layer",
            "revision_round": round_number,
            "max_revision_rounds": max_rounds,
            "claims_checked": claims_found,
            "claims_verified": claims_verified,
            "claims_quarantined": quarantined,
            "remaining_seconds": round(remaining, 1),
        }
        if progress_callback:
            progress_callback(event)

    def invoke_audit(*, round_number: int) -> TruthAudit:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise QualityLayerTimeout("truth layer budget exhausted")
        if cancel_check and cancel_check():
            raise QualityLayerCancelled("truth layer cancelled")
        if generator_id in MATHEMATICS_GENERATORS and audit is audit_truth:
            emit_progress(
                "Matematikkontroll: bruker SymPy/LaTeX – web-faktasøk er ikke nødvendig",
                round_number=round_number,
            )
            return _mathematics_truth_audit(
                content=current,
                topic=topic,
                subject=subject,
            )
        kwargs: dict[str, object] = {
            "content": current,
            "topic": topic,
            "subject": subject,
            "level": level,
            "provided_sources": provided_sources,
        }
        # Keep custom deterministic test auditors backwards-compatible while
        # giving the production auditor the cancellation/request context.
        if audit is audit_truth:
            kwargs.update(
                cancel_check=cancel_check,
                call_timeout_seconds=min(quality_model_timeout_seconds(), remaining),
                max_attempts=quality_max_model_attempts(),
                request_id=request_id,
            )
        emit_progress(
            f"Kontrollerer påstander – runde {round_number} av {max_rounds}",
            round_number=round_number,
        )
        return run_bounded_sync(
            lambda: audit(**kwargs),
            timeout_seconds=min(quality_model_timeout_seconds(), remaining),
            cancel_check=cancel_check,
            operation_name=f"truth audit round {round_number}",
        )

    logger.info(
        "quality_gate_started",
        extra={
            "request_id": request_id,
            "generator_id": generator_id,
            "model_call_timeout_s": quality_model_timeout_seconds(),
            "max_model_attempts": quality_max_model_attempts(),
            "max_revision_rounds": max_rounds,
            "budget_s": total_budget,
        },
    )

    for round_number in range(1, max_rounds + 1):
        before = content_digest(current)
        repeated_revision = before in seen
        seen.add(before)
        logger.info(
            "verification_round_started",
            extra={"request_id": request_id, "round_number": round_number},
        )
        logger.info(
            "revision_started",
            extra={"request_id": request_id, "round_number": round_number},
        )
        try:
            outcome = invoke_audit(round_number=round_number)
        except QualityLayerCancelled:
            logger.info(
                "job_cancelled",
                extra={"request_id": request_id, "stage": "truth_layer", "round_number": round_number},
            )
            raise
        except QualityLayerTimeout:
            budget_exhausted = True
            stop_reason = "truth_layer_timeout"
            logger.warning(
                "quality_gate_budget_exhausted",
                extra={"request_id": request_id, "round_number": round_number},
            )
            break
        next_content = outcome.content
        final = outcome.passport.model_copy(update={"version": "3.0", "content_revision": content_digest(next_content)})
        unresolved = [claim for claim in final.claims if not claim_is_resolved(claim)]
        next_content, _round_unsafe, _handled = _withhold_unresolved_claims(
            next_content,
            unresolved,
            quarantine_by_text,
        )
        final.content_revision = content_digest(next_content)
        verified = len(final.claims) - len(unresolved)
        score = (verified, len(unresolved))
        changed = next_content != current
        progress = (not repeated_revision) and (
            changed or score[0] > previous_score[0] or score[1] < previous_score[1]
        )
        status = "completed"
        if round_number > 1 and not progress:
            status = "no_progress"
            stop_reason = "Revisjonen ga ingen målbar fremgang."
        elif round_number == max_rounds and unresolved:
            status = "max_rounds"
            stop_reason = f"Revisjonsløkken stoppet trygt etter {max_rounds} runder."
        elif not unresolved:
            stop_reason = "Alle kontrollerte påstander er løst."
        changes = _changes(next_content, final.claims)
        rounds.append(
            QualityRevisionRound(
                round_number=round_number,
                before_revision=before,
                after_revision=content_digest(next_content),
                claims_found=len(final.claims),
                claims_verified=verified,
                corrected_count=sum(change.result == "applied" for change in changes),
                unresolved_count=len(unresolved),
                changed=changed,
                status=status,  # type: ignore[arg-type]
                summary=final.summary,
                changes=changes,
            )
        )
        logger.info(
            "verification_round_completed",
            extra={
                "request_id": request_id,
                "round_number": round_number,
                "claims_found": len(final.claims),
                "claims_verified": verified,
                "claims_quarantined": 0,
            },
        )
        logger.info(
            "revision_completed",
            extra={
                "request_id": request_id,
                "round_number": round_number,
                "changed": changed,
                "claims_verified": verified,
                "claims_unresolved": len(unresolved),
            },
        )
        emit_progress(
            f"{verified} av {len(final.claims)} påstander verifisert",
            round_number=round_number,
            claims_found=len(final.claims),
            claims_verified=verified,
        )
        current = next_content
        previous_score = score
        if not unresolved or status == "no_progress":
            break

    if final is None:
        final = _blocked_passport(
            topic,
            subject,
            "Automatisk faktakontroll nådde tidsgrensen før den kunne evaluere innholdet.",
            status="verification_failed",
        )

    # The final controller always checks the exact export candidate again.  A
    # re-audit may discover claims that became visible only after earlier JSON
    # fields were withheld, so keep the cleanup bounded but iterative.
    unsafe: list[TruthClaim] = []
    for controller_round in range(max_rounds):
        unresolved = [item for item in final.claims if not claim_is_resolved(item)]
        if not unresolved or budget_exhausted:
            break
        quarantine_before = set(quarantine_by_text)
        current, unsafe, handled = _withhold_unresolved_claims(
            current,
            unresolved,
            quarantine_by_text,
        )
        for original_text in set(quarantine_by_text) - quarantine_before:
            item = quarantine_by_text[original_text]
            logger.info(
                "claim_quarantined",
                extra={
                    "request_id": request_id,
                    "claim_id": item.claim_id,
                    "content_type": item.content_type,
                    "location": item.location,
                },
            )
        if not handled:
            break
        try:
            final_outcome = invoke_audit(round_number=len(rounds) + controller_round + 1)
            final = final_outcome.passport.model_copy(
                update={"version": "3.0", "content_revision": content_digest(current)}
            )
        except QualityLayerCancelled:
            logger.info("job_cancelled", extra={"request_id": request_id, "stage": "truth_layer"})
            raise
        except QualityLayerTimeout:
            budget_exhausted = True
            stop_reason = "truth_layer_timeout"
            logger.warning("quality_gate_budget_exhausted", extra={"request_id": request_id})
            break
    remaining = [item for item in final.claims if not claim_is_resolved(item)]
    # Only the claims in the passport for the exact final candidate may block
    # preview.  Keeping an earlier ``unsafe`` list here would reject content
    # that a later re-audit has already confirmed no longer contains it.
    unsafe = remaining
    quarantine = list(quarantine_by_text.values())
    if unsafe:
        final.status = "needs_review"
        final.limitations = list(dict.fromkeys([
            *final.limitations,
            "Minst én uløst påstand kunne ikke skilles trygt fra teksten og må redigeres av læreren.",
        ]))
    elif (
        final.status not in {"verification_failed", "blocked"}
        and not [claim for claim in final.claims if not claim_is_resolved(claim)]
        and (
            final.status != "source_unavailable"
            or bool(quarantine)
            # A source-unavailable passport with no evidence-bearing claims is
            # a valid language worksheet only when the auditor returned an
            # explicit typed claim register. An empty register is fail-closed.
            or (
                bool(final.claims)
                and not any(claim_requires_evidence(claim) for claim in final.claims)
            )
        )
    ):
        # Non-factual documents and documents cleaned by quarantine are valid
        # without inventing a source.  Evidence-bearing claims remain subject
        # to claim_is_resolved above.
        final.status = "verified"
        final.content_revision = content_digest(current)
        stop_reason = "Alle kontrollerte påstander er løst eller trygt utelatt."
    failures = deterministic_math_failures(current)
    if failures:
        final.status = "needs_review"
        final.limitations = list(dict.fromkeys([
            *final.limitations,
            f"{len(failures)} matematisk(e) likhet(er) feilet deterministisk kontroll.",
        ]))
    if budget_exhausted:
        final.status = "needs_review"
        final.limitations = list(dict.fromkeys([
            *final.limitations,
            "Sannhetslaget nådde tidsgrensen. Uverifisert innhold krever lærerkontroll.",
        ]))
    if stop_reason == "":
        if unsafe or [claim for claim in final.claims if not claim_is_resolved(claim)]:
            stop_reason = "truth_layer_unresolved_claims"
        else:
            stop_reason = "source_approved"
    result = QualityGateResult(
        approved_content=current,
        passport=final,
        rounds=rounds,
        quarantine=quarantine,
        stop_reason=stop_reason,
        deterministic_failures=failures,
    )
    if result.source_approved:
        logger.info(
            "quality_gate_completed",
            extra={"request_id": request_id, "status": result.quality_status, "rounds": len(rounds)},
        )
    else:
        logger.info(
            "teacher_review_returned",
            extra={
                "request_id": request_id,
                "status": result.quality_status,
                "stop_reason": result.stop_reason,
                "quarantined": len(quarantine),
            },
        )
    return result


def _release_manifest(content: str, passport: TruthPassport) -> ReleaseManifest:
    revision = build_document_revision(content)
    return ReleaseManifest(
        document_revision_id=revision.revision_id,
        document_hash=content_digest(content),
        node_hashes={node.node_id: node.content_hash for node in revision.nodes},
        claim_revisions={claim.id: claim.claim_revision for claim in passport.claims},
        evidence_snapshot_ids=[source.snapshot_id for source in passport.sources if source.snapshot_id],
        renderer_version="quality-gate-3.0",
    )


def run_quality_pipeline(
    *,
    generator_id: str,
    content: str,
    topic: str,
    subject: str,
    level: str,
    provided_sources: Iterable[object] = (),
    max_rounds: int | None = None,
    audit: Callable[..., TruthAudit] = audit_truth,
    cancel_check: Callable[[], bool] | None = None,
    progress_callback: Callable[[dict[str, object]], None] | None = None,
    request_id: str = "",
    timeout_seconds: float | None = None,
) -> QualityGateResult:
    """Run the revisioned, evidence-first quality workflow.

    One loop iteration means one audit of one exact revision.  Repairs are
    small compare-and-swap node patches, and a changed document always returns
    through a later audit before it can be approved.  This deliberately has no
    second hidden cleanup loop.
    """
    if generator_id not in GENERATOR_CONTRACTS:
        raise ValueError(f"Generatoren mangler global verifikasjonskontrakt: {generator_id}")
    if not content.strip():
        raise ValueError("Tomt innhold kan ikke passere kvalitetspipelinen.")
    configured_rounds = quality_max_revision_rounds()
    rounds_limit = max(1, min(configured_rounds, max_rounds or configured_rounds))
    deadline = time.monotonic() + (timeout_seconds or quality_layer_timeout_seconds())
    current = canonical_document_content(content)
    active_sources = list(provided_sources)
    rounds: list[QualityRevisionRound] = []
    quarantine: dict[str, QualityQuarantineItem] = {}
    final: TruthPassport | None = None
    stop_reason = ""
    budget_exhausted = False
    seen_operations: set[tuple[str, tuple[str, ...], tuple[str, ...]]] = set()
    last_audited_revision = ""

    def emit(message: str, round_number: int, *, claims_found: int = 0, claims_verified: int = 0) -> None:
        if progress_callback:
            progress_callback({
                "message": message,
                "step": "delta_verifying",
                "phase": "verifying",
                "revision_round": round_number,
                "max_revision_rounds": rounds_limit,
                "claims_checked": claims_found,
                "claims_verified": claims_verified,
                "remaining_seconds": round(max(0.0, deadline - time.monotonic()), 1),
            })

    def invoke(round_number: int) -> TruthAudit:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise QualityLayerTimeout("truth layer budget exhausted")
        if cancel_check and cancel_check():
            raise QualityLayerCancelled("truth layer cancelled")
        if generator_id in MATHEMATICS_GENERATORS and audit is audit_truth:
            return _mathematics_truth_audit(content=current, topic=topic, subject=subject)
        kwargs: dict[str, object] = {
            "content": current, "topic": topic, "subject": subject, "level": level,
            "provided_sources": tuple(active_sources),
        }
        if audit is audit_truth:
            kwargs.update(
                cancel_check=cancel_check,
                call_timeout_seconds=min(quality_model_timeout_seconds(), remaining),
                max_attempts=quality_max_model_attempts(),
                request_id=request_id,
            )
        emit(f"Kontrollerer dokumentrevisjon – runde {round_number} av {rounds_limit}", round_number)
        return run_bounded_sync(
            lambda: audit(**kwargs),
            timeout_seconds=min(quality_model_timeout_seconds(), remaining),
            cancel_check=cancel_check,
            operation_name=f"truth audit round {round_number}",
        )

    for round_number in range(1, rounds_limit + 1):
        before = content_digest(current)
        try:
            outcome = invoke(round_number)
        except QualityLayerCancelled:
            raise
        except QualityLayerTimeout:
            budget_exhausted = True
            stop_reason = "truth_layer_timeout"
            break
        # A complete model-written document is not a patch.  Refusing it avoids
        # losing fields/dependencies behind a seemingly successful audit.
        if audit is audit_truth and canonical_document_content(outcome.content) != current:
            final = outcome.passport.model_copy(update={
                "version": "3.0", "status": "needs_review", "content_revision": before,
                "limitations": [*outcome.passport.limitations, "Revisoren returnerte en full dokumentmutasjon i stedet for en nodepatch."],
            })
            stop_reason = "unexpected_full_document_mutation"
            rounds.append(QualityRevisionRound(
                round_number=round_number, before_revision=before, after_revision=before,
                claims_found=len(final.claims), claims_verified=0,
                unresolved_count=len(final.claims), status="failed", summary=final.summary,
            ))
            break
        explicit_coverage = outcome.passport.register_complete
        final = outcome.passport.model_copy(update={
            "version": "3.0", "content_revision": before, "register_complete": explicit_coverage,
        })
        last_audited_revision = before
        active_sources = [*active_sources, *final.sources]
        unresolved = [claim for claim in final.claims if not claim_is_resolved(claim)]
        verified = len(final.claims) - len(unresolved)
        evidence_ids = tuple(sorted(source.snapshot_id or source.url for source in final.sources))
        signature = (before, tuple(sorted(f"{claim.id}:{claim.status}" for claim in unresolved)), evidence_ids)
        if signature in seen_operations:
            final.status = "needs_review"
            stop_reason = "no_progress_same_revision_and_evidence"
            rounds.append(QualityRevisionRound(
                round_number=round_number, before_revision=before, after_revision=before,
                claims_found=len(final.claims), claims_verified=verified,
                unresolved_count=len(unresolved), status="no_progress", summary=final.summary,
            ))
            break
        seen_operations.add(signature)
        if not explicit_coverage:
            final.status = "needs_review"
            stop_reason = "incomplete_claim_register"
            rounds.append(QualityRevisionRound(
                round_number=round_number, before_revision=before, after_revision=before,
                claims_found=len(final.claims), claims_verified=verified,
                unresolved_count=len(unresolved), status="failed", summary=final.summary,
            ))
            break
        if not unresolved:
            # An empty unresolved list is not a licence to erase a technical
            # or incomplete audit outcome.  In particular, a fetch failure
            # can report aggregate counters before individual claims exist.
            # Only the truth layer may return a green, complete register.
            if final.status != "verified":
                no_external_claims = (
                    final.total_claims == 0
                    or (
                        len(final.claims) == final.total_claims
                        and not any(
                            content_type_requires_external_source(claim.content_type)
                            for claim in final.claims
                        )
                    )
                )
                if no_external_claims:
                    # An explicit complete register may establish that the
                    # candidate has no remaining web-fact obligations.  This
                    # is distinct from accepting a partial aggregate result.
                    final.status = "verified"
                    stop_reason = "all_non_external_claims_checked"
                else:
                    stop_reason = "truth_layer_did_not_verify_complete_register"
            else:
                stop_reason = "all_claims_verified"
            rounds.append(QualityRevisionRound(
                round_number=round_number, before_revision=before, after_revision=before,
                claims_found=len(final.claims), claims_verified=verified,
                unresolved_count=0,
                status="completed" if final.status == "verified" else "failed",
                summary=final.summary,
            ))
            if final.status == "verified":
                emit(f"{verified} av {len(final.claims)} påstander er kontrollert", round_number, claims_found=len(final.claims), claims_verified=verified)
            break

        candidate = current
        changes: list[RepairChange] = []
        unresolved_after_patch: list[TruthClaim] = []
        for claim in unresolved:
            # Rebind after each patch: two claims in one node must not share a
            # stale content hash.
            from .document_revision import bind_claim
            bound = bind_claim(claim, build_document_revision(candidate))
            patch, code = build_repair_patch(bound)
            patch_result = apply_repair_patch(candidate, patch) if patch else None
            if patch_result and patch_result.applied:
                candidate = patch_result.content
                status = "replaced" if patch and patch.after else "removed"
                item = _quarantine_item(bound).model_copy(update={"status": status})
                quarantine.setdefault(f"{bound.id}:{item.original_text}", item)
                changes.append(RepairChange(
                    issue_id=bound.id, action=bound.action, result="applied",
                    before=patch.before if patch else bound.exact_text,
                    after=patch.after if patch else "", reason=bound.evidence or "Avgrenset nodepatch anvendt.",
                    source_refs=bound.source_urls,
                ))
            else:
                failure_code = patch_result.code if patch_result else code
                unresolved_after_patch.append(bound)
                changes.append(RepairChange(
                    issue_id=bound.id, action=bound.action, result="manual_review",
                    before=bound.exact_text or bound.claim, reason=failure_code or "Patchen kunne ikke forankres trygt.",
                    source_refs=bound.source_urls,
                ))
        changed = candidate != current
        rounds.append(QualityRevisionRound(
            round_number=round_number, before_revision=before,
            after_revision=content_digest(candidate), claims_found=len(final.claims),
            claims_verified=verified, corrected_count=sum(change.result == "applied" for change in changes),
            unresolved_count=len(unresolved_after_patch), changed=changed,
            status="completed" if changed else "no_progress", summary=final.summary, changes=changes,
        ))
        if not changed:
            final.status = "needs_review"
            stop_reason = "anchor_mismatch_or_learning_requirement"
            break
        current = candidate
        if round_number == rounds_limit:
            final.status = "needs_review"
            stop_reason = "repair_requires_delta_verification"

    if final is None:
        final = _blocked_passport(topic, subject, "Automatisk faktakontroll nådde tidsgrensen før den kunne evaluere innholdet.", status="verification_failed")
        final.version = "3.0"
        final.content_revision = content_digest(current)
    if budget_exhausted:
        final.status = "needs_review"
        final.limitations = list(dict.fromkeys([*final.limitations, "Sannhetslaget nådde tidsgrensen før en kontrollert sluttkandidat forelå."]))
    if content_digest(current) != last_audited_revision:
        final.status = "needs_review"
        stop_reason = stop_reason or "repair_requires_delta_verification"
    failures = deterministic_math_failures(current)
    if failures:
        final.status = "needs_review"
        final.limitations = list(dict.fromkeys([*final.limitations, f"{len(failures)} matematisk(e) likhet(er) feilet deterministisk kontroll."]))
    if not stop_reason:
        stop_reason = "source_approved" if final.status == "verified" else "truth_layer_unresolved_claims"
    manifest = _release_manifest(current, final)
    result = QualityGateResult(
        approved_content=current, passport=final, rounds=rounds,
        quarantine=list(quarantine.values()), stop_reason=stop_reason,
        deterministic_failures=failures, release_manifest=manifest,
    )
    logger.info(
        "quality_gate_completed" if result.source_approved else "teacher_review_returned",
        extra={"request_id": request_id, "status": result.quality_status, "rounds": len(rounds), "stop_reason": stop_reason},
    )
    return result


def require_export_ready(
    *,
    export_id: str,
    content: str,
    verification_status: str,
    verified_revision: str,
    teacher_approved: bool,
    approved_revision: str,
    verification_version: str = "",
    quarantined_texts: Iterable[str] = (),
    responsibility_approved: bool = False,
    release_manifest: dict[str, object] | None = None,
) -> None:
    """Single server-side invariant used immediately before bytes are served."""
    if export_id not in EXPORT_CONTRACTS:
        raise ValueError(f"Eksporten mangler global kvalitetskontrakt: {export_id}")
    revision = content_digest(content)
    reasons: list[str] = source_approval_reasons(
        content=content,
        verification_status=verification_status,
        verification_version=verification_version,
        verified_revision=verified_revision,
        quarantined_texts=quarantined_texts,
        responsibility_approved=responsibility_approved,
        release_manifest=release_manifest,
    )
    if not teacher_approved:
        reasons.append("lærergodkjenning mangler")
    if approved_revision != revision:
        reasons.append("lærergodkjenningen gjelder en annen innholdsversjon")
    if reasons:
        raise PermissionError("Eksportporten er lukket: " + "; ".join(reasons) + ".")


def source_approval_reasons(
    *,
    content: str,
    verification_status: str,
    verified_revision: str,
    verification_version: str = "",
    quarantined_texts: Iterable[str] = (),
    responsibility_approved: bool = False,
    release_manifest: dict[str, object] | None = None,
) -> list[str]:
    """Machine-gate reasons shared by preview and final export checks."""
    revision = content_digest(content)
    reasons: list[str] = []
    # A responsibility flag records a teacher decision; it is never a bypass
    # for evidence, revision binding, or the machine gate.
    if verification_version != "3.0":
        reasons.append("innholdet er kontrollert med en eldre kvalitetsmodell")
    if verification_status != "verified":
        reasons.append("innholdet er ikke kildegodkjent")
    if verified_revision != revision:
        reasons.append("verifikasjonen gjelder en annen innholdsversjon")
    if release_manifest is None:
        reasons.append("release-manifest mangler")
    else:
        if str(release_manifest.get("contract_version") or "") != "3.0":
            reasons.append("release-manifestet mangler eller har feil kontraktsversjon")
        if str(release_manifest.get("document_hash") or "") != revision:
            reasons.append("release-manifestet gjelder en annen innholdsversjon")
    leaked = [text for text in quarantined_texts if text.strip() and text.strip() in content]
    if leaked:
        reasons.append("karantenetekst finnes i eksportgrunnlaget")
    return reasons
