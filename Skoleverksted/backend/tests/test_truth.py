from Skoleverksted.backend.platform.models import CompendiumSource
from Skoleverksted.backend.platform.truth import audit_truth


CONTENT = (
    "## Historie\n\n"
    "Unionen mellom Norge og Sverige ble oppløst i 1905. "
    "En hemmelig traktat fra 1904 bestemte alle detaljene."
)


def test_truth_layer_accepts_only_urls_observed_in_grounding(monkeypatch):
    def fake_call(*_args, **_kwargs):
        return (
            {
                "summary": "Én påstand er dokumentert, én er ikke dokumentert.",
                "claims": [
                    {
                        "claim": "Unionen ble oppløst i 1905.",
                        "exact_text": "Unionen mellom Norge og Sverige ble oppløst i 1905.",
                        "status": "verified",
                        "action": "keep",
                        "replacement": "",
                        "source_urls": ["https://www.stortinget.no/no/Stortinget-og-demokratiet/Historikk/1905/"],
                        "evidence": "Stortinget dokumenterer unionsoppløsningen.",
                        "confidence": 0.99,
                    },
                    {
                        "claim": "En hemmelig traktat bestemte alle detaljene.",
                        "exact_text": "En hemmelig traktat fra 1904 bestemte alle detaljene.",
                        "status": "verified",
                        "action": "keep",
                        "replacement": "",
                        "source_urls": ["https://oppdiktet.example/falsk-kilde"],
                        "evidence": "Påstått kildebelegg.",
                        "confidence": 0.9,
                    },
                ],
            },
            [
                CompendiumSource(
                    title="Unionsoppløsningen i 1905",
                    url="https://www.stortinget.no/no/Stortinget-og-demokratiet/Historikk/1905/?utm_source=google",
                    publisher="Stortinget",
                )
            ],
        )

    monkeypatch.setattr(
        "Skoleverksted.backend.platform.compendium._call_google_json",
        fake_call,
    )

    result = audit_truth(
        content=CONTENT,
        topic="Unionsoppløsningen",
        subject="Historie",
        level="VG2",
    )

    assert result.passport.status == "verified"
    assert result.passport.coverage_percent == 50
    assert result.passport.verified_claims == 1
    assert result.passport.claims[1].status == "unsupported"
    assert result.passport.claims[1].action == "remove"
    assert "hemmelig traktat" not in result.content
    assert all("oppdiktet.example" not in source.url for source in result.passport.sources)


def test_truth_layer_is_fail_closed_when_safe_edit_cannot_be_applied(monkeypatch):
    def fake_call(*_args, **_kwargs):
        return (
            {
                "summary": "Påstanden kan ikke dokumenteres.",
                "claims": [
                    {
                        "claim": "En hemmelig traktat bestemte alle detaljene.",
                        "exact_text": "Denne teksten finnes ikke i dokumentet.",
                        "status": "unsupported",
                        "action": "remove",
                        "replacement": "",
                        "source_urls": [],
                        "evidence": "",
                        "confidence": 0.2,
                    }
                ],
            },
            [
                CompendiumSource(
                    title="Unionsoppløsningen i 1905",
                    url="https://www.stortinget.no/no/Stortinget-og-demokratiet/Historikk/1905/",
                    publisher="Stortinget",
                )
            ],
        )

    monkeypatch.setattr(
        "Skoleverksted.backend.platform.compendium._call_google_json",
        fake_call,
    )

    result = audit_truth(
        content=CONTENT,
        topic="Unionsoppløsningen",
        subject="Historie",
        level="VG2",
    )

    assert result.passport.status == "needs_review"
    assert result.content == CONTENT
    assert any("kunne ikke endres" in item for item in result.passport.limitations)


def test_truth_layer_blocks_output_when_research_is_unavailable(monkeypatch):
    def fail(*_args, **_kwargs):
        raise RuntimeError("research unavailable")

    monkeypatch.setattr(
        "Skoleverksted.backend.platform.compendium._call_google_json",
        fail,
    )

    result = audit_truth(
        content=CONTENT,
        topic="Unionsoppløsningen",
        subject="Historie",
        level="VG2",
    )

    assert result.passport.status == "blocked"
    assert result.content == CONTENT
    assert result.passport.verified_claims == 0
    assert result.passport.limitations


def test_teacher_source_may_count_but_model_only_source_may_not(monkeypatch):
    teacher_url = "https://www.udir.no/lk20/his01-03"

    def fake_call(*_args, **_kwargs):
        return (
            {
                "summary": "Læreplanpåstanden er kontrollert.",
                "claims": [
                    {
                        "claim": "Læreplanen har et kompetansemål.",
                        "exact_text": "Unionen mellom Norge og Sverige ble oppløst i 1905.",
                        "status": "verified",
                        "action": "keep",
                        "replacement": "",
                        "source_urls": [teacher_url],
                        "evidence": "Læreren har oppgitt kilden.",
                        "confidence": 0.9,
                    }
                ],
            },
            [],
        )

    monkeypatch.setattr(
        "Skoleverksted.backend.platform.compendium._call_google_json",
        fake_call,
    )

    without_teacher_source = audit_truth(
        content=CONTENT,
        topic="Unionsoppløsningen",
        subject="Historie",
        level="VG2",
    )
    with_teacher_source = audit_truth(
        content=CONTENT,
        topic="Unionsoppløsningen",
        subject="Historie",
        level="VG2",
        provided_sources=[{"title": "Læreplan i historie", "url": teacher_url}],
    )

    assert without_teacher_source.passport.claims[0].status == "unsupported"
    assert with_teacher_source.passport.claims[0].status == "verified"
    assert with_teacher_source.passport.status == "verified"
