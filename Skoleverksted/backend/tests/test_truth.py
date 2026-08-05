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

    assert result.passport.status == "needs_review"
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


def test_truth_layer_does_not_replace_a_partial_qualify_span(monkeypatch):
    def fake_call(*_args, **_kwargs):
        return (
            {
                "summary": "Påstanden trenger en forsiktig formulering.",
                "claims": [{
                    "claim": "En del av setningen må kvalifiseres.",
                    "exact_text": "Norge",
                    "status": "interpretation",
                    "action": "qualify",
                    "replacement": "landet",
                    "source_urls": [],
                    "evidence": "Dette er en tolkning.",
                    "confidence": 0.8,
                }],
            },
            [],
        )

    monkeypatch.setattr(
        "Skoleverksted.backend.platform.compendium._call_google_json",
        fake_call,
    )

    content = CONTENT + "\n\nNorge fikk en ny grunnlov i 1814."
    result = audit_truth(
        content=content,
        topic="Grunnloven",
        subject="Historie",
        level="VG2",
    )

    assert result.content == content
    assert any("kunne ikke endres" in item for item in result.passport.limitations)


def test_truth_layer_does_not_remove_a_partial_sentence_span(monkeypatch):
    def fake_call(*_args, **_kwargs):
        return (
            {
                "summary": "Påstanden kan ikke dokumenteres.",
                "claims": [{
                    "claim": "Norge er nevnt uten dokumentasjon.",
                    "exact_text": "Norge",
                    "status": "unsupported",
                    "action": "remove",
                    "replacement": "",
                    "source_urls": [],
                    "evidence": "",
                    "confidence": 0.2,
                }],
            },
            [],
        )

    monkeypatch.setattr(
        "Skoleverksted.backend.platform.compendium._call_google_json",
        fake_call,
    )

    content = CONTENT + "\n\nNorge fikk en ny grunnlov i 1814."
    result = audit_truth(
        content=content,
        topic="Grunnloven",
        subject="Historie",
        level="VG2",
    )

    assert result.content == content
    assert result.passport.removed_claims == []
    assert any("kunne ikke endres" in item for item in result.passport.limitations)


def test_truth_layer_remove_with_punctuation_preserves_the_next_sentence(monkeypatch):
    def fake_call(*_args, **_kwargs):
        return (
            {
                "summary": "Den første påstanden mangler dokumentasjon.",
                "claims": [{
                    "claim": "Unionen ble oppløst i 1905.",
                    "exact_text": "Unionen mellom Norge og Sverige ble oppløst i 1905.",
                    "status": "unsupported",
                    "action": "remove",
                    "replacement": "",
                    "source_urls": [],
                    "evidence": "",
                    "confidence": 0.2,
                }],
            },
            [],
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

    assert result.content == "## Historie\n\nEn hemmelig traktat fra 1904 bestemte alle detaljene."
    assert result.passport.removed_claims == ["Unionen ble oppløst i 1905."]


def test_truth_layer_remove_without_punctuation_preserves_the_next_sentence(monkeypatch):
    def fake_call(*_args, **_kwargs):
        return (
            {
                "summary": "Den første påstanden mangler dokumentasjon.",
                "claims": [{
                    "claim": "Unionen ble oppløst i 1905.",
                    "exact_text": "Unionen mellom Norge og Sverige ble oppløst i 1905",
                    "status": "unsupported",
                    "action": "remove",
                    "replacement": "",
                    "source_urls": [],
                    "evidence": "",
                    "confidence": 0.2,
                }],
            },
            [],
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

    assert result.content == "## Historie\n\nEn hemmelig traktat fra 1904 bestemte alle detaljene."


def test_truth_layer_qualifies_a_complete_sentence_and_preserves_its_neighbour(monkeypatch):
    replacement = "Unionen ble formelt oppløst i 1905."

    def fake_call(*_args, **_kwargs):
        return (
            {
                "summary": "Den første påstanden trenger presisering.",
                "claims": [{
                    "claim": "Unionen ble oppløst i 1905.",
                    "exact_text": "Unionen mellom Norge og Sverige ble oppløst i 1905.",
                    "status": "interpretation",
                    "action": "qualify",
                    "replacement": replacement,
                    "source_urls": [],
                    "evidence": "Presisert formulering.",
                    "confidence": 0.8,
                }],
            },
            [],
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

    assert result.content == (
        "## Historie\n\n"
        f"{replacement} En hemmelig traktat fra 1904 bestemte alle detaljene."
    )
    assert not any("kunne ikke endres" in item for item in result.passport.limitations)


def test_truth_layer_leaves_repeated_exact_text_unmodified(monkeypatch):
    repeated = (
        "## Historie\n\n"
        "Unionen ble oppløst i 1905. Unionen ble oppløst i 1905. "
        "Dette er en tredje setning som gjør teksten lang nok for kontroll."
    )

    def fake_call(*_args, **_kwargs):
        return (
            {
                "summary": "Treffet er tvetydig.",
                "claims": [{
                    "claim": "Unionen ble oppløst i 1905.",
                    "exact_text": "Unionen ble oppløst i 1905.",
                    "status": "unsupported",
                    "action": "remove",
                    "replacement": "",
                    "source_urls": [],
                    "evidence": "",
                    "confidence": 0.2,
                }],
            },
            [],
        )

    monkeypatch.setattr(
        "Skoleverksted.backend.platform.compendium._call_google_json",
        fake_call,
    )

    result = audit_truth(
        content=repeated,
        topic="Unionsoppløsningen",
        subject="Historie",
        level="VG2",
    )

    assert result.content == repeated
    assert result.passport.removed_claims == []
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

    assert result.passport.status == "verification_failed"
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


def test_generic_homepage_cannot_make_a_claim_green(monkeypatch):
    def fake_call(*_args, **_kwargs):
        return (
            {
                "summary": "Kilden er for generell.",
                "claims": [{
                    "claim": "Unionen ble oppløst.",
                    "exact_text": "Unionen mellom Norge og Sverige ble oppløst i 1905.",
                    "status": "verified",
                    "action": "keep",
                    "replacement": "",
                    "source_urls": ["https://www.stortinget.no"],
                    "evidence": "Forsiden dokumenterer ikke påstanden.",
                    "confidence": 0.99,
                }],
            },
            [CompendiumSource(title="Stortinget", url="https://www.stortinget.no")],
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

    assert result.passport.status == "source_unavailable"
    assert result.passport.claims[0].status == "unsupported"


def test_truth_distinguishes_unavailable_sources_from_not_evaluated(monkeypatch):
    def no_claims(*_args, **_kwargs):
        return ({"summary": "Ingen påstander.", "claims": []}, [])

    monkeypatch.setattr("Skoleverksted.backend.platform.compendium._call_google_json", no_claims)
    unavailable = audit_truth(
        content=CONTENT,
        topic="Unionsoppløsningen",
        subject="Historie",
        level="VG2",
    )
    evaluated_without_claims = audit_truth(
        content=CONTENT,
        topic="Unionsoppløsningen",
        subject="Historie",
        level="VG2",
        provided_sources=[{"title": "Stortinget", "url": "https://www.stortinget.no/1905"}],
    )
    assert unavailable.passport.status == "source_unavailable"
    assert evaluated_without_claims.passport.status == "not_evaluated"
