import json
from collections import deque
from types import SimpleNamespace

from ScriptoriumFOV.backend import agents, main
from ScriptoriumFOV.backend.progress_store import clear_progress, initialize_progress
from ScriptoriumFOV.backend.tests.pdf_fixture import build_valid_pdf_bytes
from Skoleverksted.backend.platform import compendium
from Skoleverksted.backend.platform.models import TruthClaim, TruthPassport, TruthSource
from Skoleverksted.backend.platform.quality_gate import (
    QualityGateResult,
    content_digest,
    run_quality_pipeline,
)
from Skoleverksted.backend.platform.truth import TruthAudit


SOURCE = TruthSource(
    title="Udir – konkret fagartikkel",
    url="https://udir.no/laring-og-trivsel/lareplanverket/",
    publisher="Utdanningsdirektoratet",
    source_tier="primary",
    origin="grounding",
    fetch_status="grounded",
)


def _audit(content: str, claims: list[TruthClaim], status: str) -> TruthAudit:
    verified = sum(claim.status == "verified" for claim in claims)
    return TruthAudit(
        content=content,
        passport=TruthPassport(
            version="2.0",
            status=status,
            content_revision=content_digest(content),
            verified_claims=verified,
            total_claims=len(claims),
            coverage_percent=round(100 * verified / max(1, len(claims))),
            claims=claims,
            sources=[SOURCE],
        ),
    )


def test_teacher_source_urls_are_part_of_cache_identity_and_truth_context():
    first = agents._get_cache_key(
        "Arbeidsliv", "Norsk", "A2.1", {}, None, None, None,
        "Samme kildetekst", "https://udir.no/side-a",
    )
    second = agents._get_cache_key(
        "Arbeidsliv", "Norsk", "A2.1", {}, None, None, None,
        "Samme kildetekst", "https://udir.no/side-b",
    )
    sources = agents._provided_truth_sources(
        "Les også https://www.ssb.no/arbeid-og-lonn/sysselsetting",
        "https://udir.no/laring-og-trivsel/lareplanverket/",
    )

    assert first != second
    assert [item["url"] for item in sources] == [
        "https://udir.no/laring-og-trivsel/lareplanverket/",
        "https://www.ssb.no/arbeid-og-lonn/sysselsetting",
    ]
    assert all(item["origin"] == "teacher" for item in sources)


def test_structured_claim_is_automatically_rewritten_and_reaudited():
    original = json.dumps(
        {
            "text": "Norge har nitti millioner innbyggere. Les teksten.",
            "worksheet": "Svar på spørsmålene.",
            "language_exercises": None,
        },
        ensure_ascii=False,
    )
    unsafe = TruthClaim(
        claim="Norge har nitti millioner innbyggere.",
        exact_text="nitti millioner",
        status="unsupported",
        action="qualify",
        replacement="om lag 5,6 millioner",
        content_type="number",
    )
    verified = TruthClaim(
        claim="Norge har om lag 5,6 millioner innbyggere.",
        exact_text="Norge har om lag 5,6 millioner innbyggere.",
        status="verified",
        action="keep",
        source_urls=[SOURCE.url],
        evidence="Den konkrete kildesiden dokumenterer folketallet.",
        confidence=0.95,
        content_type="number",
    )
    calls = deque([
        _audit(original, [unsafe], "source_unavailable"),
        None,
    ])

    def audit(**kwargs):
        response = calls.popleft()
        if response is not None:
            return response
        assert "nitti millioner" not in kwargs["content"]
        assert "om lag 5,6 millioner" in kwargs["content"]
        return _audit(kwargs["content"], [verified], "verified")

    result = run_quality_pipeline(
        generator_id="norsk.learning_sheet",
        content=original,
        topic="Norge",
        subject="Samfunnsfag",
        level="A2.1",
        audit=audit,
    )

    assert result.source_approved
    assert result.passport.status == "verified"
    assert "nitti millioner" not in result.approved_content
    assert "om lag 5,6 millioner" in result.approved_content
    assert result.quarantine[0].original_text == "nitti millioner"


def test_grounding_sources_are_collected_from_every_candidate():
    def candidate(url: str, title: str):
        return SimpleNamespace(
            grounding_metadata=SimpleNamespace(
                grounding_chunks=[
                    SimpleNamespace(web=SimpleNamespace(uri=url, title=title))
                ]
            )
        )

    response = SimpleNamespace(
        candidates=[
            candidate("https://udir.no/side-en", "Udir side én"),
            candidate("https://ssb.no/side-to", "SSB side to"),
        ]
    )

    sources = compendium._grounding_sources(response)

    assert [item.url for item in sources] == [
        "https://udir.no/side-en",
        "https://ssb.no/side-to",
    ]


def test_pdf_recheck_reuses_sources_and_structured_content(monkeypatch):
    job_id = "norsk-source-recheck"
    clear_progress(job_id)
    initialize_progress(job_id, 3, "Starter", request_id="request-source-recheck")
    pdf_bytes = build_valid_pdf_bytes()
    provided = [SOURCE.model_dump(mode="json")]
    captured = {}
    document = json.dumps(
        {
            "text": "Kontrollert tekst.",
            "worksheet": "Kontrollert oppgave.",
            "language_exercises": None,
        },
        ensure_ascii=False,
    )
    passport = TruthPassport(
        version="2.0",
        status="verified",
        content_revision=content_digest(document),
        claims=[],
        sources=[SOURCE],
    )
    quality = QualityGateResult(
        approved_content=document,
        passport=passport,
        rounds=[],
        quarantine=[],
        stop_reason="source_approved",
        deterministic_failures=[],
    )

    def run_quality(**kwargs):
        captured.update(kwargs)
        return quality

    monkeypatch.setattr(main, "run_quality_pipeline", run_quality)
    monkeypatch.setattr(main, "create_lesson_pdf", lambda **_kwargs: pdf_bytes)

    try:
        request = main.PreviewPDFRequest(
            topic="Arbeidsliv",
            subject="Norsk",
            level="A2.1",
            text="Kontrollert tekst.",
            worksheet="Kontrollert oppgave.",
            options={"grammar_tasks": True},
            provided_sources=provided,
        )
        main.generate_pdf_from_json_background(job_id, request)

        assert json.loads(captured["content"]) == json.loads(document)
        assert captured["provided_sources"] == provided
        state = main.get_progress(job_id)
        assert state["job_status"] == "completed"
        assert state["pdf_bytes"] == pdf_bytes
    finally:
        clear_progress(job_id)
