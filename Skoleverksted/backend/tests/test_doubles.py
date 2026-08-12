from __future__ import annotations

import pytest

from Skoleverksted.backend.tests.doubles import (
    FakeDocumentStore,
    FakeExternalServices,
    FakeJobStream,
    FakeModelProvider,
    FakeProviderError,
    FakeSourceResult,
    FakeSourceService,
    ModelScenario,
    TERMINAL_JOB_STATUSES,
)


@pytest.mark.parametrize("scenario", list(ModelScenario))
def test_model_double_exposes_each_failure_contract(scenario: ModelScenario):
    provider = FakeModelProvider(scenario=scenario, slow_seconds=0)
    if scenario in {
        ModelScenario.TIMEOUT,
        ModelScenario.RATE_LIMIT,
        ModelScenario.SERVER_ERROR,
        ModelScenario.REPEATED_ERROR,
        ModelScenario.CANCELLED,
    }:
        with pytest.raises(FakeProviderError):
            provider.complete("syntetisk forespørsel")
    elif scenario is ModelScenario.NEVER_ENDING:
        assert provider.calls == 0
        return
    else:
        reply = provider.complete("syntetisk forespørsel")
        assert reply.scenario is scenario
    assert provider.calls == 1


def test_source_fake_distinguishes_support_and_404():
    service = FakeSourceService({
        "https://example.test/good": FakeSourceResult(
            "https://example.test/good", 200, "evidence", supports_claim=True
        ),
    })

    assert service.fetch("https://example.test/good").supports_claim
    assert service.fetch("https://example.test/dead").status == 404
    assert service.requests == ["https://example.test/good", "https://example.test/dead"]


def test_document_store_rejects_path_traversal():
    store = FakeDocumentStore()
    store.put("synthetic/file.pdf", b"%PDF-1.4")
    assert store.get("synthetic/file.pdf").startswith(b"%PDF")
    with pytest.raises(ValueError, match="usikkert filnavn"):
        store.put("../production.pdf", b"do-not-write")


def test_job_stream_requires_explicit_terminal_state():
    stream = FakeJobStream()
    stream.emit({"status": "generating", "progress": 50})
    assert not stream.terminal()
    stream.emit({"status": "needs_teacher_review", "progress": 100})
    assert stream.terminal()
    assert "generating" not in TERMINAL_JOB_STATUSES


def test_external_service_bundle_has_named_isolated_adapters():
    services = FakeExternalServices()
    assert services.ndla is not services.grep_lk20
    assert services.grep_lk20 is not services.wikimedia_commons
    assert services.documents.files == {}
    assert services.jobs.events == []
