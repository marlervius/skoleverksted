from __future__ import annotations

import json
from collections import deque

from Skoleverksted.backend.platform.document_revision import (
    apply_repair_patch,
    bind_claim,
    build_document_revision,
    build_repair_patch,
    canonical_document_content,
)
from Skoleverksted.backend.platform.evidence import canonical_source_url, source_from_observed, source_has_usable_snapshot
from Skoleverksted.backend.platform.models import TruthClaim, TruthPassport, TruthSource
from Skoleverksted.backend.platform.quality_gate import run_quality_pipeline
from Skoleverksted.backend.platform.truth import TruthAudit


def _audit(content: str, claims: list[TruthClaim], *, sources: list[TruthSource] | None = None) -> TruthAudit:
    return TruthAudit(
        content=content,
        passport=TruthPassport(
            status="verified" if not claims or all(item.status == "verified" for item in claims) else "needs_review",
            register_complete=True,
            coverage_percent=100,
            verified_claims=sum(item.status == "verified" for item in claims),
            total_claims=len(claims),
            claims=claims,
            sources=sources or [],
        ),
    )


def test_standard_variant_is_a_reference_not_a_second_audit_target():
    original = json.dumps({
        "canonical": {"text": "Norge ble selvstendig i 1905."},
        "variants": {"standard": {"text": "Norge ble selvstendig i 1905."}, "støtte": "Forklar med egne ord."},
    }, ensure_ascii=False)
    canonical = canonical_document_content(original)
    payload = json.loads(canonical)
    assert payload["variants"]["standard"] == {"$ref": "$.canonical"}
    nodes = build_document_revision(canonical).nodes
    assert sum(node.content == "Norge ble selvstendig i 1905." for node in nodes) == 1


def test_unicode_and_escaped_json_are_patched_as_decoded_node_content():
    content = json.dumps({"text": "«Månen» er Norges hovedstad. Trygg avslutning."}, ensure_ascii=False)
    claim = TruthClaim(
        claim="Månen er Norges hovedstad.", exact_text="«Månen» er Norges hovedstad.",
        status="unsupported", action="remove", content_type="fact",
    )
    bound = bind_claim(claim, build_document_revision(content))
    patch, reason = build_repair_patch(bound)
    assert reason == ""
    result = apply_repair_patch(content, patch)
    assert result.applied
    assert json.loads(result.content)["text"] == "Trygg avslutning."
    assert "[Utelatt:" not in result.content


def test_patch_rejects_stale_hash_and_ambiguous_occurrences():
    content = json.dumps({"a": "Feil påstand.", "b": "Feil påstand."}, ensure_ascii=False)
    claim = TruthClaim(claim="Feil", exact_text="Feil påstand.", status="unsupported", action="remove", content_type="fact")
    ambiguous = bind_claim(claim, build_document_revision(content))
    assert ambiguous.node_id == ""
    single = bind_claim(claim, build_document_revision("Feil påstand."))
    patch, _ = build_repair_patch(single)
    stale = patch.model_copy(update={"expected_revision": "deadbeef"})
    assert apply_repair_patch("Feil påstand.", stale).code == "anchor_mismatch"


def test_url_policy_keeps_functional_query_identity_and_requires_snapshot():
    first = canonical_source_url("https://www.example.org/article?id=1&utm_source=search")
    second = canonical_source_url("https://www.example.org/article?id=2")
    assert first == "https://www.example.org/article?id=1"
    assert second == "https://www.example.org/article?id=2"
    assert first != second
    model_only = source_from_observed({"url": first, "origin": "model", "fetch_status": "model_reported"})
    teacher_only = source_from_observed({"url": first, "origin": "teacher", "fetch_status": "provided"})
    assert model_only is not None and not source_has_usable_snapshot(model_only)
    assert teacher_only is not None and not source_has_usable_snapshot(teacher_only)


def test_thirteen_repairable_claims_are_removed_then_delta_verified_without_placeholder():
    unsafe = [f"Ubekreftet detalj {number}." for number in range(13)]
    content = " ".join([*unsafe, "Trygg læringsaktivitet."])

    def audit(**kwargs):
        candidate = kwargs["content"]
        remaining = [sentence for sentence in unsafe if sentence in candidate]
        return _audit(candidate, [
            TruthClaim(claim=sentence, exact_text=sentence, status="unsupported", action="remove", content_type="fact")
            for sentence in remaining
        ])

    result = run_quality_pipeline(
        generator_id="fag.learning_sheet", content=content, topic="Syntetisk", subject="Historie", level="VG2",
        audit=audit, max_rounds=3,
    )
    assert result.source_approved
    assert result.approved_content == "Trygg læringsaktivitet."
    assert len(result.quarantine) == 13
    assert "[Utelatt:" not in result.approved_content


def test_thirteen_necessary_claims_fail_instead_of_approving_an_empty_document():
    unsafe = [f"Nødvendig detalj {number}." for number in range(13)]
    content = " ".join(unsafe)

    def audit(**kwargs):
        candidate = kwargs["content"]
        return _audit(candidate, [
            TruthClaim(claim=sentence, exact_text=sentence, status="unsupported", action="remove", content_type="fact")
            for sentence in unsafe if sentence in candidate
        ])

    result = run_quality_pipeline(
        generator_id="fag.learning_sheet", content=content, topic="Syntetisk", subject="Historie", level="VG2",
        audit=audit, max_rounds=3,
    )
    assert not result.source_approved
    assert result.stop_reason == "anchor_mismatch_or_learning_requirement"
    assert "[Utelatt:" not in result.approved_content


def test_new_snapshot_source_is_available_to_the_following_delta_audit():
    source = TruthSource(
        title="Kilde", url="https://example.org/article?id=1", origin="grounding", fetch_status="fetched",
        snapshot_id="snapshot-1", snapshot_hash="a" * 64, excerpt="Norge ble selvstendig i 1905.",
    )
    calls: list[int] = []

    def audit(**kwargs):
        calls.append(len(kwargs["provided_sources"]))
        if len(calls) == 1:
            return _audit(kwargs["content"], [TruthClaim(
                claim="Norge ble selvstendig i 1905.", exact_text="Norge ble selvstendig i 1905.",
                status="unsupported", action="qualify", replacement="Norge ble selvstendig i 1905.", content_type="fact",
            )], sources=[source])
        return _audit(kwargs["content"], [TruthClaim(
            claim="Norge ble selvstendig i 1905.", exact_text="Norge ble selvstendig i 1905.",
            status="verified", source_urls=[source.url], content_type="fact",
        )], sources=[source])

    # First patch is intentionally a no-op, so use a source-backed replacement
    # that changes wording while keeping the fixture deterministic.
    def changing_audit(**kwargs):
        if not calls:
            calls.append(len(kwargs["provided_sources"]))
            return _audit(kwargs["content"], [TruthClaim(
                claim="Norge ble selvstendig i 1905.", exact_text="Norge ble selvstendig i 1905.",
                status="unsupported", action="qualify", replacement="Norge ble en selvstendig stat i 1905.", content_type="fact",
            )], sources=[source])
        calls.append(len(kwargs["provided_sources"]))
        return _audit(kwargs["content"], [TruthClaim(
            claim="Norge ble en selvstendig stat i 1905.", exact_text="Norge ble en selvstendig stat i 1905.",
            status="verified", source_urls=[source.url], content_type="fact",
        )], sources=[source])

    result = run_quality_pipeline(
        generator_id="fag.learning_sheet", content="Norge ble selvstendig i 1905.",
        topic="1905", subject="Historie", level="VG2", audit=changing_audit, max_rounds=3,
    )
    assert result.source_approved
    assert calls == [0, 1]
