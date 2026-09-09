"""Exercise the real research, retrieval and assessment boundary (fake SDK/HTTP)."""
import json
import socket
import threading
import time
from email.message import Message
from io import BytesIO
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest
from google import genai

from Skoleverksted.backend.platform import compendium, evidence, truth
from Skoleverksted.backend.platform.quality_gate import run_quality_pipeline
from Skoleverksted.backend.platform.quality_runtime import QualityLayerCancelled

URL = "https://snl.no/Mesopotamia"
REDIRECT = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/source"
FACT = "Mesopotamia ligger mellom elvene Eufrat og Tigris."
CONTENT = FACT + " Drøft hvorfor tilgang til vann var viktig for utviklingen av jordbruk."


class Page(BytesIO):
    def __init__(self, raw, url=URL, content_type="text/html; charset=utf-8"):
        super().__init__(raw)
        self.url = url
        self.status = 200
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        self.read_sizes = []

    def geturl(self):
        return self.url

    def getcode(self):
        return self.status

    def read(self, size=-1):
        self.read_sizes.append(size)
        return super().read(size)


def public_dns(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **kw: [(2, 1, 6, "", ("93.184.216.34", 443))])


def install_research_provider(monkeypatch, *, fact=FACT, content=CONTENT,
                              field_path="$", available_on_retry=True):
    """First research has no metadata; later research can recover a real snapshot."""
    calls = []
    fetches = []
    public_dns(monkeypatch)

    def open_page(request, **kwargs):
        fetches.append(request.full_url)
        if request.full_url == REDIRECT:
            raise HTTPError(REDIRECT, 302, "redirect", {"Location": URL}, None)
        assert request.full_url == URL
        return Page(("<nav>Irrelevant navigation</nav><main>" + fact + "</main>").encode())

    monkeypatch.setattr(evidence, "build_opener", lambda *a: SimpleNamespace(open=open_page))

    class Client:
        def __init__(self, **kwargs):
            self.models = self

        def close(self):
            pass

        def generate_content(self, *, config, contents, **kwargs):
            calls.append(config)
            if config.tools:
                assert config.response_mime_type is None
                assert config.response_json_schema is None
                assert "vanlig prosa" in contents
                recovered = available_on_retry and len(calls) > 1
                chunks = [SimpleNamespace(web=SimpleNamespace(uri=REDIRECT, title="Mesopotamia"))] if recovered else []
                return SimpleNamespace(text="Researchnotat med kilder.", candidates=[SimpleNamespace(
                    grounding_metadata=SimpleNamespace(grounding_chunks=chunks),
                )])
            assert config.response_mime_type == "application/json"
            assert not config.tools
            if fetches:
                assert fact in contents
                assert '"fetch_status": "fetched"' in contents
                assert '"excerpt": "' + fact in contents
            # Even an overconfident model without grounding must remain blocked.
            return SimpleNamespace(text=json.dumps({
                "summary": "Kontrollert.",
                "coverage": {"complete": True, "covered_node_paths": ["$"]},
                "claims": [{"claim": fact, "exact_text": fact, "status": "verified", "action": "keep",
                            "replacement": "", "source_urls": [URL], "evidence": fact,
                            "confidence": 0.99, "content_type": "fact", "field_path": field_path}],
            }), candidates=[])

    monkeypatch.setenv("GOOGLE_API_KEY", "test-key-not-used")
    monkeypatch.setattr(genai, "Client", Client)
    return calls, fetches


@pytest.mark.parametrize("available", [True, False])
def test_missing_grounding_metadata_recovers_before_any_content_deletion(monkeypatch, available):
    calls, fetches = install_research_provider(monkeypatch, available_on_retry=available)
    result = run_quality_pipeline(generator_id="fag.learning_sheet", content=CONTENT,
                                  topic="Oldtiden", subject="Historie", level="VG2")
    assert len(calls) == 4
    assert result.source_approved is available
    assert result.approved_content == CONTENT
    assert not result.quarantine
    if available:
        assert fetches == [REDIRECT, URL]
        assert result.passport.claims[0].source_urls == [URL]
        assert result.release_manifest.evidence_snapshot_ids
    else:
        assert not fetches
        assert result.stop_reason == "automatic_source_recovery_exhausted"


def test_large_page_retains_bounded_article_snapshot_and_closes_response(monkeypatch):
    public_dns(monkeypatch)
    page = Page(("<nav>" + "menu " * 60_000 + "</nav><main>" + FACT + "</main><script>" + "x" * 1_000_000).encode())
    monkeypatch.setattr(evidence, "build_opener", lambda *a: SimpleNamespace(open=lambda *a, **kw: page))
    observation = evidence.fetch_source_snapshot(URL)
    assert observation.source.excerpt == FACT
    assert observation.source.fetch_status == "fetched"
    assert max(page.read_sizes) <= 1_000_000
    assert page.closed


def test_truncated_script_is_never_a_source_excerpt(monkeypatch):
    public_dns(monkeypatch)
    page = Page(b"<script>" + b"untrusted code " * 100_000)
    monkeypatch.setattr(evidence, "build_opener", lambda *a: SimpleNamespace(open=lambda *a, **kw: page))
    assert evidence.fetch_source_snapshot(URL).source.fetch_status == "irrelevant"


def test_failed_redirect_target_keeps_canonical_identity(monkeypatch):
    public_dns(monkeypatch)
    def open_page(request, **kwargs):
        if request.full_url == REDIRECT:
            raise HTTPError(REDIRECT, 302, "redirect", {"Location": URL}, None)
        raise HTTPError(URL, 403, "forbidden", {}, None)
    monkeypatch.setattr(evidence, "build_opener", lambda *a: SimpleNamespace(open=open_page))
    source = evidence.fetch_source_snapshot(REDIRECT).source
    assert source.url == URL
    assert source.observed_uri == REDIRECT
    assert source.fetch_status == "forbidden"
    assert not evidence.source_has_usable_snapshot(source)


def test_redirect_to_internal_network_remains_blocked(monkeypatch):
    public_dns(monkeypatch)
    opened = []
    def open_page(request, **kwargs):
        opened.append(request.full_url)
        raise HTTPError(REDIRECT, 302, "redirect", {"Location": "http://127.0.0.1/private"}, None)
    monkeypatch.setattr(evidence, "build_opener", lambda *a: SimpleNamespace(open=open_page))
    with pytest.raises(evidence.UnsafeSourceUrl):
        evidence.fetch_source_snapshot(REDIRECT)
    assert opened == [REDIRECT]


def test_declared_character_set_and_norwegian_url():
    assert evidence._plain_excerpt("<main>År og språk.</main>".encode("latin-1"), charset="iso-8859-1") == "År og språk."
    assert evidence.canonical_source_url("https://snl.no/språk") == "https://snl.no/spr%C3%A5k"


def test_source_collection_cancellation_does_not_wait_for_slow_pages(monkeypatch):
    cancelled = threading.Event()
    running = threading.Event()
    finish = threading.Event()
    def slow(*args, **kwargs):
        running.set()
        finish.wait(2)
        raise TimeoutError()
    monkeypatch.setattr(evidence, "fetch_source_snapshot", slow)
    def cancel():
        running.wait(1)
        cancelled.set()
    thread = threading.Thread(target=cancel)
    thread.start()
    try:
        started = time.monotonic()
        with pytest.raises(QualityLayerCancelled):
            evidence.collect_source_snapshots([URL], cancel_check=cancelled.is_set)
        assert time.monotonic() - started < 1
    finally:
        finish.set()
        thread.join()


def test_failed_patch_returns_feedback_and_reverifies_replacement(monkeypatch):
    seen = []
    replacement = "Mesopotamia er et historisk område ved Eufrat og Tigris."
    def assessor(prompt, **kwargs):
        seen.append(prompt)
        ready = replacement in prompt.split("<TEKST>")[1].split("</TEKST>")[0]
        repaired = len(seen) > 1
        from Skoleverksted.backend.platform.models import TruthSource
        return {
            "coverage": {"complete": True, "covered_node_paths": ["$"]},
            "claims": [{"claim": replacement if ready else FACT, "exact_text": replacement if ready else FACT,
                        "status": "verified" if ready else "unsupported", "action": "keep" if ready else "qualify" if repaired else "remove",
                        "replacement": replacement if repaired and not ready else "", "content_type": "fact",
                        "field_path": "$.canonical", "source_urls": [URL], "evidence": replacement}],
        }, [TruthSource(title="Kilde", url=URL, fetch_status="fetched", snapshot_id="s", snapshot_hash="a" * 64, excerpt=replacement)]
    monkeypatch.setattr(compendium, "_call_google_json", assessor)
    original = json.dumps({"canonical": FACT, "worksheet": "Undersøk hvilken rolle elvene spilte for jordbruket."}, ensure_ascii=False)
    result = run_quality_pipeline(generator_id="fag.learning_sheet", content=original,
                                  topic="Oldtiden", subject="Historie", level="VG2")
    assert result.source_approved
    assert len(seen) == 3
    assert "learning_requirement_lost" in seen[1]
    assert json.loads(result.approved_content)["canonical"] == replacement
    assert result.release_manifest.document_hash == result.passport.content_revision
