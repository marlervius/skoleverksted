from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

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
    from google import genai

    expected = b"small-fake-png"

    class BrokenInteractions:
        def create(self, **kwargs):
            raise RuntimeError("legacy interactions schema")

    class WorkingModels:
        def generate_content(self, **kwargs):
            inline = SimpleNamespace(data=expected, mime_type="image/png")
            return SimpleNamespace(parts=[SimpleNamespace(inline_data=inline)])

    fake_client = SimpleNamespace(interactions=BrokenInteractions(), models=WorkingModels())
    monkeypatch.setattr(genai, "Client", lambda **kwargs: fake_client)
    monkeypatch.setattr(images, "_api_key", lambda: "test-key")
    monkeypatch.setattr(images, "_supports_current_interactions_schema", lambda: True)

    path = images.generate_ai_image("Pedagogisk illustrasjon")
    try:
        assert path is not None
        assert Path(path).read_bytes() == expected
    finally:
        if path:
            Path(path).unlink(missing_ok=True)
