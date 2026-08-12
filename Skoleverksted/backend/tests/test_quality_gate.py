from __future__ import annotations

import json
from collections import deque
import threading
import time

import pytest

from Skoleverksted.backend.platform.models import TruthClaim, TruthPassport, TruthSource
from Skoleverksted.backend.platform.quality_gate import (
    EXPORT_CONTRACTS,
    GENERATOR_CONTRACTS,
    deterministic_math_failures,
    require_export_ready,
    run_quality_pipeline,
)
from Skoleverksted.backend.platform.quality_runtime import QualityLayerCancelled
from Skoleverksted.backend.platform.truth import TruthAudit


SOURCE = TruthSource(
    title="SSB tabell",
    url="https://ssb.no/statbank/table/12345",
    publisher="SSB",
    source_tier="primary",
    origin="grounding",
    fetch_status="grounded",
)


def _audit(content: str, claims: list[TruthClaim], *, status: str = "needs_review") -> TruthAudit:
    verified = sum(claim.status == "verified" for claim in claims)
    return TruthAudit(
        content=content,
        passport=TruthPassport(
            status=status,
            verified_claims=verified,
            total_claims=len(claims),
            coverage_percent=round(100 * verified / max(1, len(claims))),
            claims=claims,
            sources=[SOURCE],
        ),
    )


def test_wrong_claim_is_corrected_then_rechecked():
    original = "## Fakta\nNorge har 90 millioner innbyggere."
    corrected = "## Fakta\nNorge har om lag 5,6 millioner innbyggere."
    calls = deque(
        [
            _audit(
                corrected,
                [TruthClaim(
                    claim="Norge har 90 millioner innbyggere.",
                    exact_text="Norge har 90 millioner innbyggere.",
                    status="unsupported",
                    action="qualify",
                    replacement="Norge har om lag 5,6 millioner innbyggere.",
                    content_type="number",
                )],
            ),
            _audit(
                corrected,
                [TruthClaim(
                    claim="Norge har om lag 5,6 millioner innbyggere.",
                    exact_text="Norge har om lag 5,6 millioner innbyggere.",
                    status="verified",
                    source_urls=[SOURCE.url],
                    content_type="number",
                )],
                status="verified",
            ),
        ]
    )

    def fake(**kwargs):
        return calls.popleft()

    result = run_quality_pipeline(
        generator_id="platform.teaching_package.student_sheet",
        content=original,
        topic="Norge",
        subject="Samfunnsfag",
        level="VG1",
        audit=fake,
    )
    assert result.source_approved
    assert result.approved_content == corrected
    assert len(result.rounds) == 2


def test_unsupported_claim_is_quarantined_and_never_exported():
    original = "## Fakta\nDen hemmelige avtalen ble signert på Månen.\n\nTrygg tekst."
    unsupported = TruthClaim(
        claim="Avtalen ble signert på Månen.",
        exact_text="Den hemmelige avtalen ble signert på Månen.",
        status="unsupported",
        action="remove",
        content_type="fact",
        location="Seksjon 1: Fakta",
        evidence="Ingen av de undersøkte kildene støtter formuleringen.",
    )
    responses = deque([
        _audit(original, [unsupported]),
        _audit("## Fakta\nTrygg tekst.", [], status="not_evaluated"),
    ])

    result = run_quality_pipeline(
        generator_id="platform.teaching_package.presentation",
        content=original,
        topic="Avtalen",
        subject="Historie",
        level="VG2",
        max_rounds=1,
        audit=lambda **kwargs: responses.popleft(),
    )
    assert result.source_approved
    assert len(result.quarantine) == 1
    assert "Månen" not in result.approved_content
    assert "Månen" in result.quarantine[0].original_text


def test_source_unavailable_without_an_audited_claim_register_stays_blocked():
    content = (
        "## Oppgave\nSammenlign to perspektiver og begrunn svaret ditt. "
        "Bruk fagbegreper og vis tydelig hvordan du tenker."
    )

    result = run_quality_pipeline(
        generator_id="fag.learning_sheet",
        content=content,
        topic="Perspektiver",
        subject="Historie",
        level="VG2",
        audit=lambda **kwargs: _audit(kwargs["content"], [], status="source_unavailable"),
    )

    assert not result.source_approved
    assert result.passport.status == "source_unavailable"
    assert result.approved_content == content


def test_source_unavailable_instruction_only_content_is_safe_to_preview():
    content = (
        "## Oppgave\nSammenlign to perspektiver og begrunn svaret ditt. "
        "Bruk fagbegreper og vis tydelig hvordan du tenker."
    )
    instruction = TruthClaim(
        claim="Sammenlign to perspektiver.",
        exact_text="Sammenlign to perspektiver og begrunn svaret ditt.",
        status="verified",
        action="keep",
        content_type="instruction",
    )

    result = run_quality_pipeline(
        generator_id="fag.learning_sheet",
        content=content,
        topic="Perspektiver",
        subject="Historie",
        level="VG2",
        audit=lambda **kwargs: _audit(
            kwargs["content"], [instruction], status="source_unavailable"
        ),
    )

    assert result.source_approved
    assert result.passport.status == "verified"


def test_unsupported_claim_inside_json_is_removed_before_preview():
    original = json.dumps(
        {
            "text": "Trygg innledning. Den hemmelige avtalen ble signert på Månen. Trygg avslutning.",
            "worksheet": "Drøft kildenes troverdighet.",
        },
        ensure_ascii=False,
    )
    unsafe = TruthClaim(
        claim="Avtalen ble signert på Månen.",
        exact_text="signert på Månen",
        status="unsupported",
        action="remove",
        content_type="fact",
        location="Hovedtekst",
    )
    responses = deque([
        _audit(original, [unsafe], status="source_unavailable"),
        _audit("", [], status="source_unavailable"),
    ])

    result = run_quality_pipeline(
        generator_id="fag.learning_sheet",
        content=original,
        topic="Kildekritikk",
        subject="Historie",
        level="VG2",
        max_rounds=1,
        audit=lambda **kwargs: responses.popleft(),
    )

    payload = json.loads(result.approved_content)
    assert result.source_approved
    assert len(result.quarantine) == 1
    assert "Månen" not in payload["text"]
    assert "Utelatt" in payload["text"]
    assert payload["worksheet"] == "Drøft kildenes troverdighet."


def test_structured_cleanup_is_reaudited_until_new_claims_are_gone():
    original = json.dumps(
        {
            "text": "Første udokumenterte påstand. Trygg innledning.",
            "worksheet": "Andre udokumenterte påstand. Drøft temaet.",
        },
        ensure_ascii=False,
    )
    first_claim = TruthClaim(
        claim="Første påstand",
        exact_text="Første udokumenterte påstand",
        status="unsupported",
        action="remove",
        content_type="fact",
        location="Fagtekst",
    )
    second_claim = TruthClaim(
        claim="Andre påstand",
        exact_text="Andre udokumenterte påstand.",
        status="unsupported",
        action="remove",
        content_type="fact",
        location="Oppgaver",
    )
    calls = 0

    def progressive_audit(**kwargs):
        nonlocal calls
        calls += 1
        candidate = kwargs["content"]
        if "Første udokumenterte" in candidate:
            return _audit(candidate, [first_claim], status="source_unavailable")
        if "Andre udokumenterte" in candidate:
            return _audit(candidate, [second_claim], status="source_unavailable")
        return _audit(candidate, [], status="source_unavailable")

    result = run_quality_pipeline(
        generator_id="fag.learning_sheet",
        content=original,
        topic="Kildekritikk",
        subject="Historie",
        level="VG2",
        audit=progressive_audit,
    )

    payload = json.loads(result.approved_content)
    assert calls == 3, calls
    assert result.source_approved
    assert result.passport.status == "verified"
    assert len(result.quarantine) == 2
    assert "Første udokumenterte" not in payload["text"]
    assert "Andre udokumenterte" not in payload["worksheet"]


def test_claim_removed_by_auditor_is_reaudited_instead_of_left_blocking():
    original = json.dumps(
        {
            "text": "En udokumentert påstand. Trygg innledning.",
            "worksheet": "Drøft temaet.",
        },
        ensure_ascii=False,
    )
    cleaned = json.dumps(
        {
            "text": "Trygg innledning.",
            "worksheet": "Drøft temaet.",
        },
        ensure_ascii=False,
    )
    removed_claim = TruthClaim(
        claim="En udokumentert påstand.",
        exact_text="En udokumentert påstand.",
        status="unsupported",
        action="remove",
        content_type="fact",
        location="Fagtekst",
    )
    responses = deque([
        _audit(cleaned, [removed_claim], status="source_unavailable"),
        _audit(cleaned, [], status="source_unavailable"),
    ])

    result = run_quality_pipeline(
        generator_id="fag.learning_sheet",
        content=original,
        topic="Kildekritikk",
        subject="Historie",
        level="VG2",
        audit=lambda **_kwargs: responses.popleft(),
    )

    assert result.source_approved
    assert result.passport.status == "verified"
    assert result.approved_content == cleaned
    assert len(result.quarantine) == 1


def test_repeated_unsafe_fragment_withholds_every_affected_json_field():
    original = json.dumps(
        {
            "text": "Kilder må alltid være kritiske. Trygg innledning.",
            "worksheet": "Forklar hvorfor kilder må alltid være kritiske.",
            "teacher_key": "Trygg veiledning.",
        },
        ensure_ascii=False,
    )
    repeated = TruthClaim(
        claim="Kilder må alltid være kritiske.",
        exact_text="må alltid være kritiske",
        status="unsupported",
        action="remove",
        content_type="fact",
        location="Fagtekst og oppgaver",
    )
    responses = deque([
        _audit(original, [repeated], status="source_unavailable"),
        _audit("", [], status="source_unavailable"),
    ])

    result = run_quality_pipeline(
        generator_id="fag.learning_sheet",
        content=original,
        topic="Kildekritikk",
        subject="Historie",
        level="VG2",
        max_rounds=1,
        audit=lambda **_kwargs: responses.popleft(),
    )

    payload = json.loads(result.approved_content)
    assert result.source_approved
    assert len(result.quarantine) == 1
    assert "må alltid være kritiske" not in result.approved_content
    assert "Utelatt" in payload["text"]
    assert "Utelatt" in payload["worksheet"]
    assert payload["teacher_key"] == "Trygg veiledning."


def test_fabricated_or_irrelevant_source_does_not_resolve_claim():
    claim = TruthClaim(
        claim="Påstand",
        exact_text="Påstand.",
        status="verified",
        source_urls=[],
        content_type="fact",
        evidence="Modellen sier at en kilde finnes.",
    )
    responses = deque([
        _audit("Påstand.", [claim], status="verified"),
        _audit("", [], status="not_evaluated"),
    ])
    result = run_quality_pipeline(
        generator_id="fag.learning_sheet",
        content="Påstand.",
        topic="Tema",
        subject="Historie",
        level="VG2",
        max_rounds=1,
        audit=lambda **kwargs: responses.popleft(),
    )
    assert len(result.quarantine) == 1


def test_math_is_checked_deterministically():
    assert deterministic_math_failures("2 + 2 = 5") == ["2 + 2 = 5"]
    assert deterministic_math_failures("2 + 2 = 4") == []


def test_quote_and_number_require_observed_sources_but_instructions_do_not():
    quote = TruthClaim(
        claim="Hun sa at reformen var ferdig.",
        exact_text='Hun sa: "Reformen er ferdig."',
        status="verified",
        content_type="quote",
        source_urls=[],
    )
    responses = deque([
        _audit('Hun sa: "Reformen er ferdig."\n\nSammenlign to perspektiver.', [quote], status="verified"),
        _audit("Sammenlign to perspektiver.", [TruthClaim(
            claim="Sammenlign to perspektiver.", exact_text="Sammenlign to perspektiver.",
            status="verified", content_type="instruction",
        )], status="verified"),
    ])
    result = run_quality_pipeline(
        generator_id="fag.assessment",
        content='Hun sa: "Reformen er ferdig."\n\nSammenlign to perspektiver.',
        topic="Reform", subject="Samfunnsfag", level="VG2", max_rounds=1,
        audit=lambda **_: responses.popleft(),
    )
    assert result.source_approved
    assert len(result.quarantine) == 1
    assert "Reformen er ferdig" not in result.approved_content
    assert "Sammenlign" in result.approved_content


def test_time_sensitive_claim_is_withheld_when_freshness_cannot_be_shown():
    content = "Arbeidsledigheten er 3 prosent akkurat nå.\n\nDrøft mulige årsaker."
    stale = TruthClaim(
        claim="Arbeidsledigheten er 3 prosent akkurat nå.",
        exact_text="Arbeidsledigheten er 3 prosent akkurat nå.",
        status="time_sensitive",
        content_type="number",
        source_urls=[SOURCE.url],
        evidence="Kilden er ikke datert for inneværende periode.",
    )
    responses = deque([
        _audit(content, [stale]),
        _audit("Drøft mulige årsaker.", [], status="not_evaluated"),
    ])
    result = run_quality_pipeline(
        generator_id="norsk.learning_sheet", content=content,
        topic="Arbeidsliv", subject="Samfunnsfag", level="B1", max_rounds=1,
        audit=lambda **_: responses.popleft(),
    )
    assert result.source_approved
    assert result.quarantine[0].content_type == "number"
    assert "3 prosent" not in result.approved_content


def test_inconsistent_task_answer_is_blocked_as_a_math_claim():
    content = "Oppgave: Hva er 6 / 2? Svar: 4."
    claim = TruthClaim(
        claim=content,
        exact_text=content,
        status="unsupported",
        content_type="mathematics",
        evidence="Fasiten samsvarer ikke med oppgaven.",
    )
    result = run_quality_pipeline(
        generator_id="matematikk.exercise_variant", content=content,
        topic="Divisjon", subject="Matematikk", level="VG1", max_rounds=1,
        audit=lambda **kwargs: _audit(kwargs["content"], [claim]),
    )
    assert not result.source_approved
    assert result.passport.status == "needs_review"


def test_teacher_added_source_can_turn_reverification_green():
    content = "Norge ble selvstendig i 1905."
    unresolved = TruthClaim(claim=content, exact_text=content, status="unsupported", content_type="fact")
    first = run_quality_pipeline(
        generator_id="platform.teaching_package.teacher_guide", content=content,
        topic="1905", subject="Historie", level="VG2", max_rounds=1,
        audit=lambda **kwargs: _audit(kwargs["content"], [unresolved]),
    )
    assert not first.source_approved
    verified = TruthClaim(
        claim=content, exact_text=content, status="verified", content_type="fact",
        source_urls=[SOURCE.url], evidence="Lærerkilden støtter påstanden.",
    )
    second = run_quality_pipeline(
        generator_id="platform.teaching_package.teacher_guide", content=content,
        topic="1905", subject="Historie", level="VG2", provided_sources=[SOURCE],
        audit=lambda **kwargs: _audit(kwargs["content"], [verified], status="verified"),
    )
    assert second.source_approved


def test_export_gate_binds_verification_and_teacher_approval_to_exact_text():
    content = "Godkjent tekst."
    from Skoleverksted.backend.platform.quality_gate import content_digest

    revision = content_digest(content)
    require_export_ready(
        export_id="platform.teaching_package.pdf",
        content=content,
        verification_status="verified",
        verified_revision=revision,
        verification_version="2.0",
        teacher_approved=True,
        approved_revision=revision,
        quarantined_texts=["Utelatt tekst."],
    )
    with pytest.raises(PermissionError, match="annen innholdsversjon"):
        require_export_ready(
            export_id="platform.teaching_package.pdf",
            content=content + " Endret.",
            verification_status="verified",
            verified_revision=revision,
            verification_version="2.0",
            teacher_approved=True,
            approved_revision=revision,
        )
    with pytest.raises(PermissionError, match="karantenetekst"):
        require_export_ready(
            export_id="platform.teaching_package.pdf",
            content="Godkjent tekst. Utelatt tekst.",
            verification_status="verified",
            verified_revision=content_digest("Godkjent tekst. Utelatt tekst."),
            verification_version="2.0",
            teacher_approved=True,
            approved_revision=content_digest("Godkjent tekst. Utelatt tekst."),
            quarantined_texts=["Utelatt tekst."],
        )


def test_revision_loop_stops_without_progress():
    claim = TruthClaim(claim="Ukjent.", exact_text="fragment", status="unsupported", content_type="fact")
    calls = 0

    def unchanged(**kwargs):
        nonlocal calls
        calls += 1
        return _audit(kwargs["content"], [claim])

    result = run_quality_pipeline(
        generator_id="platform.teaching_package.teacher_guide",
        content="Et fragment som ikke kan fjernes trygt.",
        topic="Tema",
        subject="Historie",
        level="VG2",
        audit=unchanged,
    )
    assert calls == 2
    assert result.rounds[-1].status == "no_progress"
    assert not result.source_approved


def test_hanging_audit_terminates_with_teacher_review_and_timeout_reason():
    def hanging_audit(**_kwargs):
        time.sleep(5)
        return _audit("Tekst som aldri rekker å bli kontrollert.", [])

    started = time.monotonic()
    result = run_quality_pipeline(
        generator_id="fag.learning_sheet",
        content="Tekst som aldri rekker å bli kontrollert.",
        topic="Tema",
        subject="Historie",
        level="VG2",
        timeout_seconds=0.05,
        audit=hanging_audit,
    )

    assert time.monotonic() - started < 1
    assert result.quality_status == "needs_teacher_review"
    assert result.stop_reason == "truth_layer_timeout"
    assert not result.source_approved


def test_cancellation_stops_the_quality_layer_before_another_round():
    cancelled = threading.Event()

    def audit_that_waits(**_kwargs):
        while not cancelled.is_set():
            time.sleep(0.01)
        return _audit("Tekst.", [])

    def cancel_soon():
        time.sleep(0.05)
        cancelled.set()

    threading.Thread(target=cancel_soon, daemon=True).start()
    with pytest.raises(QualityLayerCancelled):
        run_quality_pipeline(
            generator_id="fag.learning_sheet",
            content="Dette er tekst som venter på kansellering og er lang nok.",
            topic="Tema",
            subject="Historie",
            level="VG2",
            timeout_seconds=1,
            cancel_check=cancelled.is_set,
            audit=audit_that_waits,
        )


def test_every_known_generator_and_export_family_has_a_contract():
    expected_generators = {
        "platform.year_plan", "platform.compendium",
        "fag.learning_sheet", "fag.differentiated", "fag.assessment", "fag.lesson_sequence",
        "norsk.learning_sheet", "norsk.preview_pdf", "norsk.dual_level", "norsk.multi_level",
        "matematikk.material", "matematikk.differentiated", "matematikk.exercise_variant",
    }
    assert expected_generators <= GENERATOR_CONTRACTS
    assert {
        "platform.compendium.pdf", "platform.compendium.docx",
        "platform.teaching_package.pdf", "platform.teaching_package.docx",
        "platform.teaching_package.pptx", "platform.teaching_package.zip",
        "platform.year_plan.material", "platform.theme_pack.teacher_guide",
        "fag.pdf", "fag.docx", "norsk.pdf", "norsk.zip",
        "matematikk.pdf", "matematikk.docx", "matematikk.pptx", "matematikk.shared_pdf",
    } == EXPORT_CONTRACTS


def test_old_quality_model_is_rejected_until_reverified():
    from Skoleverksted.backend.platform.quality_gate import content_digest
    content = "Eldre innhold."
    revision = content_digest(content)
    with pytest.raises(PermissionError, match="eldre kvalitetsmodell"):
        require_export_ready(
            export_id="fag.pdf", content=content, verification_status="verified",
            verification_version="1.0", verified_revision=revision,
            teacher_approved=True, approved_revision=revision,
        )


def test_unknown_future_generator_or_export_fails_closed():
    with pytest.raises(ValueError, match="mangler global verifikasjonskontrakt"):
        run_quality_pipeline(
            generator_id="future.unregistered",
            content="Innhold",
            topic="Tema",
            subject="Fag",
            level="Nivå",
            audit=lambda **kwargs: _audit(kwargs["content"], [], status="verified"),
        )
    with pytest.raises(ValueError, match="mangler global kvalitetskontrakt"):
        require_export_ready(
            export_id="future.unregistered",
            content="Innhold",
            verification_status="verified",
            verified_revision="x",
            verification_version="2.0",
            teacher_approved=True,
            approved_revision="x",
        )
