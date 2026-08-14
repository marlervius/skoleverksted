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
    QualityQuarantineItem,
    QualityRevisionRound,
    RepairChange,
    TruthClaim,
    TruthPassport,
    TruthSource,
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
DEFAULT_MAX_REVISION_ROUNDS = 2


def quality_model_timeout_seconds() -> float:
    return env_float("QUALITY_GATE_MODEL_TIMEOUT_SECONDS", DEFAULT_MODEL_CALL_TIMEOUT_SECONDS)


def quality_layer_timeout_seconds() -> float:
    return env_float("QUALITY_GATE_TIMEOUT_SECONDS", DEFAULT_TRUTH_LAYER_TIMEOUT_SECONDS)


def quality_max_model_attempts() -> int:
    return env_int("QUALITY_GATE_MAX_MODEL_ATTEMPTS", DEFAULT_MAX_MODEL_ATTEMPTS, maximum=2)


def quality_max_revision_rounds() -> int:
    return env_int("QUALITY_GATE_MAX_REVISION_ROUNDS", DEFAULT_MAX_REVISION_ROUNDS, maximum=2)


MAX_REVISION_ROUNDS = DEFAULT_MAX_REVISION_ROUNDS

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


def _remove_exact_claim_from_json(content: str, exact: str) -> tuple[str, bool]:
    """Remove one unambiguous claim from a JSON string value.

    Several generators submit structured JSON as their canonical verification
    document.  Treating that serialization as prose makes a perfectly complete
    sentence look unsafe to remove because it is surrounded by JSON quotes.  We
    therefore inspect string *values*, apply the same sentence-boundary rules
    there, and serialize the otherwise unchanged structure again.
    """
    try:
        payload = json.loads(content)
    except (TypeError, json.JSONDecodeError):
        return content, False

    exact = exact.strip()
    if not exact:
        return content, False

    removed = False
    withheld_notice = "[Utelatt: denne delen kunne ikke kildeverifiseres.]"

    def revise(value: object) -> object:
        nonlocal removed
        if isinstance(value, str) and exact in value:
            # A unique, complete sentence can be removed precisely.  If the
            # fragment is repeated (inside this field or elsewhere in the JSON)
            # there is no safe single target, so withhold every affected field.
            # This is intentionally conservative: losing surrounding prose is
            # preferable to leaking one unresolved claim into student material.
            revised, applied = _remove_exact_claim(value, exact)
            if applied and content.count(exact) == 1:
                removed = True
                return revised
            # A model can return only an entity or phrase as ``exact_text``.
            # Removing that fragment may change the meaning of the surrounding
            # sentence, so quarantine the complete JSON field instead.  This
            # deliberately sacrifices some safe prose rather than leaking an
            # unresolved claim into student material.
            removed = True
            return withheld_notice
        if isinstance(value, list):
            return [revise(item) for item in value]
        if isinstance(value, dict):
            return {key: revise(item) for key, item in value.items()}
        return value

    revised_payload = revise(payload)
    if not removed:
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
    """Remove unresolved claims from the exact export candidate.

    ``audit_truth`` can revise prose directly, while structured generators use
    JSON.  This controller handles both and records every omitted claim.  A
    claim already absent from the candidate still counts as handled because the
    passport being inspected describes the previous revision and must be
    refreshed against the cleaned text.
    """
    current = content
    unsafe: list[TruthClaim] = []
    handled = False
    for claim in claims:
        exact = claim.exact_text.strip()
        removed = bool(exact and exact not in current)
        revised = current
        if not removed:
            revised, removed = _remove_exact_claim(current, exact)
        if not removed:
            revised, removed = _remove_exact_claim_from_json(current, exact)
        if removed:
            current = revised
            handled = True
            item = _quarantine_item(claim)
            quarantine.setdefault(item.original_text, item)
        else:
            unsafe.append(claim)
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

    @property
    def source_approved(self) -> bool:
        unresolved = [claim for claim in self.passport.claims if not claim_is_resolved(claim)]
        return not unresolved and not self.deterministic_failures and self.passport.status == "verified"

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
    )
    return result


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
        final = outcome.passport.model_copy(update={"version": "2.0", "content_revision": content_digest(next_content)})
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
                update={"version": "2.0", "content_revision": content_digest(current)}
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
            # a valid language worksheet, not a factual failure.
            or not any(claim_requires_evidence(claim) for claim in final.claims)
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
) -> list[str]:
    """Machine-gate reasons shared by preview and final export checks."""
    revision = content_digest(content)
    reasons: list[str] = []
    if not responsibility_approved and verification_version != "2.0":
        reasons.append("innholdet er kontrollert med en eldre kvalitetsmodell")
    if not responsibility_approved and verification_status != "verified":
        reasons.append("innholdet er ikke kildegodkjent")
    if not responsibility_approved and verified_revision != revision:
        reasons.append("verifikasjonen gjelder en annen innholdsversjon")
    leaked = [text for text in quarantined_texts if text.strip() and text.strip() in content]
    if leaked:
        reasons.append("karantenetekst finnes i eksportgrunnlaget")
    return reasons
