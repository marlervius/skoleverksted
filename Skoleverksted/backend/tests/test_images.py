from __future__ import annotations

import os
import sys
import weakref
import io
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from Skoleverksted.backend.platform import images


def test_normalize_image_mode_supports_legacy_aliases() -> None:
    assert images.normalize_image_mode(None) == "none"
    assert images.normalize_image_mode("real") == "commons"
    assert images.normalize_image_mode("WIKIMEDIA") == "commons"
    assert images.normalize_image_mode("ai") == "ai"
    assert images.normalize_image_mode("unknown") == "none"


def test_text_model_uses_current_stable_default(monkeypatch) -> None:
    monkeypatch.delenv("GOOGLE_MODEL", raising=False)
    assert images._text_model() == "gemini-3.8-flash"


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
    monkeypatch.setattr(
        images,
        "_normalize_image_for_documents",
        lambda value: (value, "image/png"),
    )

    path = images.generate_ai_image("Pedagogisk illustrasjon")
    try:
        assert path is not None
        assert Path(path).read_bytes() == expected
    finally:
        if path:
            Path(path).unlink(missing_ok=True)


def test_webp_image_is_normalized_to_a_real_png() -> None:
    image_module = pytest.importorskip("PIL.Image")
    source = io.BytesIO()
    image_module.new("RGB", (320, 240), "#6B8FA3").save(source, format="WEBP")

    normalized, mime_type = images._normalize_image_for_documents(source.getvalue())

    assert mime_type == "image/png"
    assert normalized.startswith(b"\x89PNG\r\n\x1a\n")
    with image_module.open(io.BytesIO(normalized)) as decoded:
        assert decoded.format == "PNG"
        assert decoded.size == (320, 240)


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


def test_commons_search_accepts_svg_through_raster_thumbnail(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "query": {
                    "pages": {
                        "1": {
                            "title": "File:Photosynthesis diagram.svg",
                            "imageinfo": [{
                                "mime": "image/svg+xml",
                                "width": 1200,
                                "height": 800,
                                "url": "https://upload.wikimedia.org/photosynthesis.svg",
                                "thumburl": "https://upload.wikimedia.org/1000px-photosynthesis.svg.png",
                                "extmetadata": {
                                    "LicenseShortName": {"value": "CC BY-SA 4.0"},
                                    "ImageDescription": {
                                        "value": "A clear diagram of photosynthesis in a green plant"
                                    },
                                    "Artist": {"value": "Example author"},
                                },
                            }],
                        },
                    },
                },
            }

    fake_requests = ModuleType("requests")
    fake_requests.get = lambda *_args, **_kwargs: FakeResponse()
    monkeypatch.setitem(sys.modules, "requests", fake_requests)

    candidates = images._search_wikimedia(
        "photosynthesis diagram",
        {
            "motif": "photosynthesis in a green plant",
            "search_queries": ["photosynthesis diagram"],
            "fallback_search_queries": [],
        },
    )

    assert len(candidates) == 1
    assert candidates[0]["url"].endswith(".svg.png")
    assert candidates[0]["original_url"] is None
    assert candidates[0]["page_url"].endswith("Photosynthesis_diagram.svg")


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
    selected_motifs: list[str] = []

    def fake_search(query: str, plan: dict):
        searches.append(query)
        return [fallback_candidate] if query == "Roman mosaic" else []

    monkeypatch.setattr(images, "_search_wikimedia", fake_search)
    monkeypatch.setattr(
        images,
        "_select_candidate",
        lambda plan, candidates: (
            selected_motifs.append(str(plan.get("motif"))) or candidates[0]
            if candidates
            else None
        ),
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
            "fallback_motif": "A clearly visible Roman floor mosaic",
            "fallback_caption": "En romersk gulvmosaikk",
            "caption": "Romersk mosaikk",
        }
    )

    assert result is not None
    assert searches == ["Dominus Julius detailed educational photograph", "Roman mosaic"]
    assert selected_motifs == ["A clearly visible Roman floor mosaic"]
    assert result.caption == "En romersk gulvmosaikk"
    assert result.local_path == str(local_copy)


def test_photosynthesis_uses_language_free_leaf_reserve(tmp_path, monkeypatch) -> None:
    leaf = {
        "url": "https://upload.wikimedia.org/green-leaf.jpg",
        "title": "Green leaf with sunlight.jpg",
        "description": "Green leaf with sunlight",
        "creator": "Example creator",
        "license": "CC0",
        "page_url": "https://commons.wikimedia.org/wiki/File:Green_leaf_with_sunlight.jpg",
    }
    local_copy = tmp_path / "leaf.png"
    local_copy.write_bytes(b"verified-leaf")
    searches: list[str] = []
    selected_motifs: list[str] = []

    def fake_search(query: str, plan: dict):
        searches.append(query)
        return [leaf] if query == "green leaf sunlight close up" else []

    def fake_select(plan: dict, candidates: list[dict]):
        if not candidates:
            return None
        selected_motifs.append(str(plan.get("motif")))
        return candidates[0]

    monkeypatch.setattr(images, "_search_wikimedia", fake_search)
    monkeypatch.setattr(images, "_select_candidate", fake_select)
    monkeypatch.setattr(
        images,
        "_verified_remote_candidate_path",
        lambda plan, candidate: str(local_copy),
    )

    result = images._commons_image({
        "context_topic": "Fotosyntesen",
        "context_subject": "Naturfag",
        "motif": "En enkel tegning av hele fotosyntesen",
        "search_queries": ["photosynthesis diagram Norwegian"],
        "fallback_search_queries": ["photosynthesis plant"],
        "caption": "Fotosyntesen",
    })

    assert result is not None
    assert searches[:2] == [
        "photosynthesis diagram Norwegian",
        "green leaf sunlight close up",
    ]
    assert selected_motifs == [
        "A clear close-up photograph of healthy green leaves in natural sunlight"
    ]
    assert result.caption == "Grønne blader i sollys"


def test_commons_gallery_keeps_safe_alternatives_when_critic_rejects_primary(
    monkeypatch,
) -> None:
    primary = {
        "url": "https://upload.wikimedia.org/wikipedia/commons/a/ab/Primary.jpg",
        "title": "Complex photosynthesis chart.jpg",
        "description": "A complex chart",
        "creator": "Creator A",
        "license": "CC BY-SA 4.0",
        "page_url": "https://commons.wikimedia.org/wiki/File:Primary.jpg",
        "score": 2000,
    }
    fallback = {
        "url": "https://upload.wikimedia.org/wikipedia/commons/b/bc/Leaves.jpg",
        "title": "Green leaves in sunlight.jpg",
        "description": "Healthy green leaves in natural sunlight",
        "creator": "Creator B",
        "license": "CC0",
        "page_url": "https://commons.wikimedia.org/wiki/File:Leaves.jpg",
        "score": 1000,
    }
    monkeypatch.setattr(
        images,
        "_plan_image",
        lambda *args, **kwargs: {
            "motif": "A simple photosynthesis diagram",
            "rationale": "Support understanding",
            "search_queries": ["photosynthesis diagram"],
            "fallback_search_queries": ["green leaves sunlight"],
            "fallback_motif": "Green leaves in sunlight",
            "fallback_caption": "Grønne blader i sollys",
            "fallback_alt_text": "Grønne blader i sollys",
        },
    )

    def fake_search(query: str, plan: dict, limit: int = 6):
        return [primary] if query == "photosynthesis diagram" else [fallback]

    monkeypatch.setattr(images, "_search_wikimedia", fake_search)
    monkeypatch.setattr(
        images,
        "_select_candidate",
        lambda plan, candidates: (
            fallback if candidates and candidates[0] is fallback else None
        ),
    )

    gallery = images.discover_commons_images(
        topic="Fotosyntesen",
        subject="Naturfag",
        level="A2.2",
        text="Planter trenger lys.",
    )

    assert [candidate["title"] for candidate in gallery] == [
        fallback["title"],
        primary["title"],
    ]
    assert gallery[0]["recommended"] is True
    assert gallery[0]["caption"] == "Grønne blader i sollys"
    assert gallery[1]["review_status"] == "teacher_review"
    assert all(candidate["license"] for candidate in gallery)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "https://upload.wikimedia.org/wikipedia/commons/a/ab/Example.jpg",
            True,
        ),
        (
            "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Example.jpg/800px-Example.jpg",
            True,
        ),
        ("http://upload.wikimedia.org/wikipedia/commons/a/ab/Example.jpg", False),
        ("https://upload.wikimedia.org.evil.test/wikipedia/commons/a.jpg", False),
        ("https://example.org/image.jpg", False),
    ],
)
def test_commons_image_url_allowlist(url: str, expected: bool) -> None:
    assert images.is_trusted_commons_image_url(url) is expected
