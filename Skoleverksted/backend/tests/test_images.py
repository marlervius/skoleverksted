from __future__ import annotations

import os
import sys
import weakref
from pathlib import Path
from types import ModuleType, SimpleNamespace

from Skoleverksted.backend.platform import images


def test_normalize_image_mode_supports_legacy_aliases() -> None:
    assert images.normalize_image_mode(None) == "none"
    assert images.normalize_image_mode("real") == "commons"
    assert images.normalize_image_mode("WIKIMEDIA") == "commons"
    assert images.normalize_image_mode("ai") == "ai"
    assert images.normalize_image_mode("unknown") == "none"


def test_text_model_uses_current_stable_default(monkeypatch) -> None:
    monkeypatch.delenv("GOOGLE_MODEL", raising=False)
    assert images._text_model() == "gemini-3.5-flash"


def test_license_filter_fails_closed() -> None:
    assert images._is_free_license("CC BY-SA 4.0")
    assert images._is_free_license("Public domain")
    assert images._is_free_license("CC0")
    assert not images._is_free_license("")
    assert not images._is_free_license("All rights reserved")
    assert not images._is_free_license("CC BY-NC 4.0")


def test_none_mode_never_starts_the_image_crew(monkeypatch) -> None:
    def unexpected(*args, **kwargs):
        raise AssertionError("the image crew must not run in none mode")

    monkeypatch.setattr(images, "_plan_image", unexpected)
    assert (
        images.resolve_image(
            "none",
            topic="Energi",
            subject="Naturfag",
            level="VG1",
            text="Kort tekst",
        )
        is None
    )


def test_ai_failure_is_fail_safe(monkeypatch) -> None:
    monkeypatch.setattr(images, "_plan_image", lambda *args, **kwargs: {"motif": "energi"})
    monkeypatch.setattr(images, "_ai_image", lambda *args, **kwargs: None)
    assert (
        images.resolve_image(
            "ai",
            topic="Energi",
            subject="Naturfag",
            level="VG1",
            text="Kort tekst",
        )
        is None
    )


def test_public_metadata_does_not_leak_local_path() -> None:
    result = images.ImageResult(
        source="ai",
        credit="KI-generert",
        local_path=os.path.join("private", "temporary.png"),
    )
    metadata = result.public_metadata()
    assert "local_path" not in metadata
    assert metadata["source"] == "ai"


def test_commons_critic_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(images, "_crew_llm", lambda: (_ for _ in ()).throw(RuntimeError("offline")))
    candidate = {
        "title": "Department of Energy building",
        "description": "An office building",
        "url": "https://example.invalid/image.jpg",
    }
    assert images._select_candidate({"motif": "solar energy"}, [candidate]) is None


def test_visual_quality_gate_requires_available_verification(monkeypatch) -> None:
    monkeypatch.setattr(images, "_api_key", lambda: "")
    assert not images._verify_image_bytes(
        {"motif": "solar energy"},
        b"not-an-image",
        "image/jpeg",
        "Wikimedia Commons",
    )


def test_image_generation_falls_back_when_interactions_fails(monkeypatch) -> None:
    expected = b"small-fake-png"

    class BrokenInteractions:
        def create(self, **kwargs):
            raise RuntimeError("legacy interactions schema")

    class WorkingModels:
        def generate_content(self, **kwargs):
            inline = SimpleNamespace(data=expected, mime_type="image/png")
            return SimpleNamespace(parts=[SimpleNamespace(inline_data=inline)])

    fake_client = SimpleNamespace(interactions=BrokenInteractions(), models=WorkingModels())
    fake_genai = ModuleType("google.genai")
    fake_genai.Client = lambda **kwargs: fake_client
    fake_genai.types = SimpleNamespace(
        GenerateContentConfig=lambda **kwargs: SimpleNamespace(**kwargs)
    )
    fake_google = ModuleType("google")
    fake_google.genai = fake_genai
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
    monkeypatch.setattr(images, "_api_key", lambda: "test-key")
    monkeypatch.setattr(images, "_supports_current_interactions_schema", lambda: True)

    path = images.generate_ai_image("Pedagogisk illustrasjon")
    try:
        assert path is not None
        assert Path(path).read_bytes() == expected
    finally:
        if path:
            Path(path).unlink(missing_ok=True)


def test_visual_verifier_keeps_google_client_open_during_request(monkeypatch) -> None:
    events: list[str] = []
    requests: list[dict] = []

    class FakeModels:
        def __init__(self, client) -> None:
            self._client = weakref.ref(client)

        def generate_content(self, **kwargs):
            client = self._client()
            if client is None or client.closed:
                raise RuntimeError("Cannot send a request, as the client has been closed.")
            events.append("request")
            requests.append(kwargs)
            return SimpleNamespace(text='{"approved": true, "reason": "relevant"}')

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            self.closed = False
            self.models = FakeModels(self)

        def close(self) -> None:
            if not self.closed:
                self.closed = True
                events.append("close")

        def __del__(self) -> None:
            self.close()

    fake_genai = ModuleType("google.genai")
    fake_genai.Client = FakeClient
    fake_genai.types = SimpleNamespace(
        Part=SimpleNamespace(from_bytes=lambda **kwargs: SimpleNamespace(**kwargs))
    )
    fake_google = ModuleType("google")
    fake_google.genai = fake_genai
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
    monkeypatch.setattr(images, "_api_key", lambda: "test-key")

    assert images._verify_image_bytes(
        {
            "motif": "Et vulkanutbrudd",
            "rationale": "Forklare geologiske prosesser",
            "context_topic": "Historiske spor",
            "context_subject": "Historie",
            "context_level": "VG1",
        },
        b"fake-image",
        "image/png",
        "KI",
    )
    assert events == ["request", "close"]
    prompt = requests[0]["contents"][0]
    assert "Historiske spor" in prompt
    assert "sprekker" in prompt
    assert "IKKE i seg selv avslagsgrunn" in prompt


def test_commons_download_retries_429_and_reuses_successful_bytes(monkeypatch) -> None:
    calls: list[str] = []
    delays: list[float] = []

    class FakeResponse:
        def __init__(self, status: int, data: bytes = b"") -> None:
            self.status_code = status
            self.headers = {
                "Content-Type": "image/jpeg",
                **({"Retry-After": "1.5"} if status == 429 else {}),
            }
            self._data = data
            self.closed = False

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise RuntimeError(f"HTTP {self.status_code}")

        def iter_content(self, chunk_size: int):
            yield self._data

        def close(self) -> None:
            self.closed = True

    responses = iter([FakeResponse(429), FakeResponse(200, b"verified-image")])
    fake_requests = ModuleType("requests")

    def fake_get(url: str, **kwargs):
        calls.append(url)
        return next(responses)

    fake_requests.get = fake_get
    monkeypatch.setitem(sys.modules, "requests", fake_requests)
    monkeypatch.setattr(images.time, "sleep", delays.append)

    downloaded = images._download_remote_candidate(
        {"title": "Relevant mosaic", "url": "https://upload.wikimedia.org/example.jpg"}
    )

    assert downloaded == (b"verified-image", "image/jpeg")
    assert len(calls) == 2
    assert delays == [1.5]


def test_commons_uses_verified_reserve_and_returns_local_copy(tmp_path, monkeypatch) -> None:
    first = {
        "url": "https://upload.wikimedia.org/first.jpg",
        "title": "First",
        "description": "Relevant first candidate",
        "creator": "Creator A",
        "license": "CC BY 4.0",
        "page_url": "https://commons.wikimedia.org/wiki/File:First",
    }
    reserve = {
        "url": "https://upload.wikimedia.org/reserve.jpg",
        "title": "Reserve",
        "description": "Relevant reserve candidate",
        "creator": "Creator B",
        "license": "CC BY-SA 4.0",
        "page_url": "https://commons.wikimedia.org/wiki/File:Reserve",
    }
    local_copy = tmp_path / "commons.jpg"
    local_copy.write_bytes(b"same-bytes-used-for-verification-and-pdf")
    attempted: list[str] = []

    monkeypatch.setattr(images, "_search_wikimedia", lambda *args, **kwargs: [first, reserve])
    monkeypatch.setattr(images, "_select_candidate", lambda plan, candidates: first)

    def fake_verified_path(plan: dict, candidate: dict):
        attempted.append(candidate["title"])
        return None if candidate is first else str(local_copy)

    monkeypatch.setattr(images, "_verified_remote_candidate_path", fake_verified_path)

    result = images._commons_image(
        {
            "motif": "Roman mosaic",
            "search_queries": ["Roman mosaic"],
            "caption": "Romersk mosaikk",
            "alt_text": "En romersk mosaikk",
        }
    )

    assert result is not None
    assert attempted == ["First", "Reserve"]
    assert result.title == "Reserve"
    assert result.local_path == str(local_copy)
    assert result.image_url == reserve["url"]


def test_commons_runs_broader_search_after_empty_primary_round(tmp_path, monkeypatch) -> None:
    fallback_candidate = {
        "url": "https://upload.wikimedia.org/broad.jpg",
        "title": "Broad result",
        "description": "Relevant broad result",
        "creator": "Creator",
        "license": "CC BY-SA 4.0",
        "page_url": "https://commons.wikimedia.org/wiki/File:Broad",
    }
    local_copy = tmp_path / "broad.jpg"
    local_copy.write_bytes(b"verified")
    searches: list[str] = []

    def fake_search(query: str, plan: dict):
        searches.append(query)
        return [fallback_candidate] if query == "Roman mosaic" else []

    monkeypatch.setattr(images, "_search_wikimedia", fake_search)
    monkeypatch.setattr(
        images,
        "_select_candidate",
        lambda plan, candidates: candidates[0] if candidates else None,
    )
    monkeypatch.setattr(
        images,
        "_verified_remote_candidate_path",
        lambda plan, candidate: str(local_copy),
    )

    result = images._commons_image(
        {
            "motif": "Late Roman villa floor mosaic with daily life scene",
            "search_queries": ["Dominus Julius detailed educational photograph"],
            "fallback_search_queries": ["Roman mosaic"],
            "caption": "Romersk mosaikk",
        }
    )

    assert result is not None
    assert searches == ["Dominus Julius detailed educational photograph", "Roman mosaic"]
    assert result.local_path == str(local_copy)
