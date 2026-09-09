"""Automatic recovery uses the real truth/repair gates, with offline providers."""
import threading
import time
from types import SimpleNamespace

import pytest

from Skoleverksted.backend.platform import compendium, quality_gate, truth
from Skoleverksted.backend.platform.models import TruthClaim, TruthPassport, TruthSource
from Skoleverksted.backend.platform.quality_runtime import QualityLayerCancelled, QualityLayerTimeout


CONTENT = (
    "Unionen mellom Norge og Sverige ble oppløst i 1905. "
    "Drøft hvordan du kan bruke kilder til å undersøke denne historiske hendelsen."
)
URL = "https://www.stortinget.no/no/Stortinget-og-demokratiet/Historikk/1905/"


def source(url=URL, **changes):
    values = dict(title="Historisk kilde", url=url, origin="grounding", fetch_status="fetched",
                  snapshot_id="snapshot-1905", snapshot_hash="a" * 64, excerpt=CONTENT)
    return TruthSource(**(values | changes))


def payload(url=URL):
    return {
        "summary": "Den historiske påstanden er kontrollert.",
        "coverage": {"complete": True, "covered_node_paths": ["$"]},
        "claims": [{"claim": CONTENT.split(". ")[0], "exact_text": CONTENT.split(". ")[0] + ".",
                    "status": "verified", "action": "keep", "replacement": "",
                    "source_urls": [url], "evidence": "Kilden dokumenterer unionsoppløsningen i 1905.",
                    "confidence": 0.99, "content_type": "fact", "field_path": "$"}],
    }


def run(**kwargs):
    return quality_gate.run_quality_pipeline(
        generator_id="fag.learning_sheet", content=CONTENT, topic="Unionsoppløsningen",
        subject="Historie", level="VG2", **kwargs,
    )


def test_provider_timeout_is_retried_automatically_and_exact_pdf_revision_is_ready(monkeypatch):
    calls = []

    def provider(*args, **kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise QualityLayerTimeout("provider temporarily unavailable")
        return payload(), [source()]

    monkeypatch.setattr(compendium, "_call_google_json", provider)
    result = run()
    assert len(calls) == 2
    assert result.source_approved
    assert result.approved_content == CONTENT
    assert result.release_manifest.document_hash == quality_gate.content_digest(CONTENT)
    assert result.release_manifest.evidence_snapshot_ids == ["snapshot-1905"]
    # The ordinary download action still supplies the existing teacher gate.
    quality_gate.require_export_ready(
        export_id="fag.pdf", content=CONTENT, verification_status=result.passport.status,
        verified_revision=result.passport.content_revision, verification_version=result.passport.version,
        teacher_approved=True, approved_revision=quality_gate.content_digest(CONTENT),
        release_manifest=result.release_manifest.model_dump(),
    )


def test_round_allows_retrieval_after_the_model_call_budget(monkeypatch):
    monkeypatch.setattr(quality_gate, "quality_model_timeout_seconds", lambda: 0.02)

    def auditor(**kwargs):
        time.sleep(0.07)  # Several individually bounded calls/retrievals.
        return truth.TruthAudit(content=kwargs["content"], passport=TruthPassport(
            status="verified", register_complete=True,
        ))

    assert run(audit=auditor, timeout_seconds=1).source_approved


def test_incomplete_register_gets_another_audit_without_changing_content(monkeypatch):
    calls = []

    def provider(*args, **kwargs):
        calls.append(args)
        response = payload()
        response["coverage"]["complete"] = len(calls) > 1
        return response, [source()]

    monkeypatch.setattr(compendium, "_call_google_json", provider)
    result = run()
    assert len(calls) == 2
    assert result.source_approved
    assert result.approved_content == CONTENT


def test_permanent_provider_failure_terminates_without_releasing_a_pdf(monkeypatch):
    calls = []

    def provider(*args, **kwargs):
        calls.append(args)
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(compendium, "_call_google_json", provider)
    result = run()
    assert len(calls) == 2
    assert not result.source_approved
    assert result.approved_content == CONTENT
    assert result.stop_reason == "incomplete_claim_register"


def test_unavailable_observed_source_is_researched_again_before_content_repairs(monkeypatch):
    calls = []

    def provider(*args, **kwargs):
        calls.append(args)
        return payload(), [source(fetch_status="timeout") if len(calls) == 1 else source()]

    monkeypatch.setattr(compendium, "_call_google_json", provider)
    result = run()
    assert len(calls) == 2
    assert result.source_approved
    assert not result.quarantine
    assert result.approved_content == CONTENT


def test_permanent_source_outage_never_deletes_learning_content(monkeypatch):
    monkeypatch.setattr(compendium, "_call_google_json", lambda *a, **kw: (payload(), [source(fetch_status="timeout")]))
    result = run()
    assert not result.source_approved
    assert result.stop_reason == "automatic_source_recovery_exhausted"
    assert result.approved_content == CONTENT
    assert not result.quarantine


def test_automatic_retry_does_not_skip_patch_reverification(monkeypatch):
    candidates = []

    def auditor(**kwargs):
        content = kwargs["content"]
        candidates.append(content)
        if len(candidates) == 1:
            raise QualityLayerTimeout("temporary")
        wrong_date = "i 1905." in content
        claim = TruthClaim(
            claim="Syntetisk testdato", exact_text=CONTENT.split(". ")[0] + "." if wrong_date else content.split(". ")[0] + ".",
            status="unsupported" if wrong_date else "verified", content_type="fact",
            action="qualify" if wrong_date else "keep", replacement="En syntetisk testhendelse fant sted i 1906.",
            source_urls=[] if wrong_date else [URL],
        )
        return truth.TruthAudit(content=content, passport=TruthPassport(
            status="needs_review" if wrong_date else "verified", register_complete=True,
            claims=[claim], total_claims=1, verified_claims=0 if wrong_date else 1,
        ))

    result = run(audit=auditor)
    assert len(candidates) == 3
    assert candidates[0] == candidates[1] == CONTENT
    assert candidates[2] == result.approved_content != CONTENT
    assert result.source_approved
    assert len(result.rounds) == 2


def test_outer_timeout_cancels_owned_auditor_before_it_can_retry(monkeypatch):
    stopped = threading.Event()

    def auditor(**kwargs):
        while not kwargs["cancel_check"]():
            time.sleep(0.002)
        stopped.set()
        raise QualityLayerCancelled("owned attempt stopped")

    monkeypatch.setattr(quality_gate, "audit_truth", auditor)
    result = run(audit=auditor, timeout_seconds=0.04)
    assert stopped.wait(1)
    assert not result.source_approved
    assert result.stop_reason == "truth_layer_timeout"


def test_source_fetch_prioritises_a_citation_after_the_first_three_results(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    candidates = [source(f"https://example.org/page/{i}", fetch_status="grounded", snapshot_id="") for i in range(4)]
    candidates.append(source(fetch_status="grounded", snapshot_id=""))
    fetched = []
    monkeypatch.setattr(compendium, "_call_google_json", lambda *a, **kw: (payload(), candidates))

    def fetch(url, **kwargs):
        fetched.append(url)
        return SimpleNamespace(source=source(url))

    monkeypatch.setattr(truth, "fetch_source_snapshot", fetch)
    result = run()
    assert fetched[0] == URL
    assert len(fetched) == 5
    assert result.source_approved


def test_truth_grounding_extraction_does_not_fetch_redirects_twice(monkeypatch):
    redirect = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/test"
    monkeypatch.setattr(compendium, "_resolve_grounding_redirect", lambda url: pytest.fail("extra page fetch"))
    response = SimpleNamespace(candidates=[SimpleNamespace(grounding_metadata=SimpleNamespace(
        grounding_chunks=[SimpleNamespace(web=SimpleNamespace(uri=redirect, title="Kilde"))],
    ))])
    sources = compendium._grounding_sources(response, resolve_redirects=False)
    assert len(sources) == 1
    assert sources[0].url == sources[0].observed_uri == redirect
    assert sources[0].origin == "grounding"
