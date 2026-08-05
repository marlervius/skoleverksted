"""
Tests for truncated-response detection.

A model that stops because it ran out of output tokens returns text that looks
fine and ends mid-sentence. It compiles, so it reaches the teacher as a finished
PDF. That must never be treated as content.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.config import Settings
from app.models.llm import (
    _PROVIDER_FACTORIES,
    LLMInterface,
    TruncatedResponseError,
    _finish_reason,
)


class _Model:
    """Stands in for a chat model, returning a chosen stop reason."""

    def __init__(self, metadata: dict | None = None, content: str = "halv tekst"):
        self.metadata = metadata or {}
        self.content = content

    def invoke(self, _messages):
        return SimpleNamespace(
            content=self.content,
            usage_metadata={},
            response_metadata=self.metadata,
        )


def _config(**overrides):
    values = {
        "primary_provider": "google",
        "primary_model": "gemini-primary",
        "fallback_provider": "google",
        "fallback_model": "gemini-fallback",
        "google_api_key": "google-secret",
        "anthropic_api_key": "",
        "openai_api_key": "",
        "ollama_base_url": "http://localhost:11434",
        "temperature": 0.1,
        "max_output_tokens": 32768,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _interface(primary: _Model, fallback: _Model | None = None, **cfg_overrides):
    models = [primary] if fallback is None else [primary, fallback]
    calls = iter(models)
    factories = dict(
        _PROVIDER_FACTORIES,
        google=lambda _m, _cfg, _t, _n: next(calls),
    )
    cfg = _config(**cfg_overrides)
    if fallback is None:
        cfg.fallback_model = cfg.primary_model  # disables the fallback
    with patch.dict(_PROVIDER_FACTORIES, factories, clear=True):
        return LLMInterface(cfg)


class FinishReasonTests(unittest.TestCase):
    def test_reads_every_spelling_providers_use(self):
        cases = {
            "MAX_TOKENS": "max_tokens",          # Gemini
            "max_tokens": "max_tokens",          # Anthropic
            "length": "length",                  # OpenAI
        }
        for raw, expected in cases.items():
            for key in ("finish_reason", "stop_reason", "finishReason"):
                response = SimpleNamespace(response_metadata={key: raw})
                self.assertEqual(_finish_reason(response), expected)

    def test_reads_the_nested_gemini_candidate_form(self):
        response = SimpleNamespace(
            response_metadata={"candidates": [{"finishReason": "MAX_TOKENS"}]}
        )
        self.assertEqual(_finish_reason(response), "max_tokens")

    def test_missing_or_odd_metadata_is_not_treated_as_truncation(self):
        for metadata in ({}, None, "not-a-dict", {"finish_reason": None}):
            response = SimpleNamespace(response_metadata=metadata)
            self.assertEqual(_finish_reason(response), "")


class TruncationRejectionTests(unittest.TestCase):
    def test_a_completed_response_passes_through(self):
        llm = _interface(_Model({"finish_reason": "STOP"}, content="hel tekst"))
        self.assertEqual(llm.invoke("sys", "user"), "hel tekst")

    def test_a_response_with_no_metadata_still_passes_through(self):
        """Never fail closed on a provider that simply reports nothing."""
        llm = _interface(_Model({}, content="hel tekst"))
        self.assertEqual(llm.invoke("sys", "user"), "hel tekst")

    def test_a_truncated_response_raises_instead_of_returning_text(self):
        llm = _interface(_Model({"finish_reason": "MAX_TOKENS"}))
        with self.assertRaises(TruncatedResponseError) as caught:
            llm.invoke("sys", "user")
        self.assertIn("ufullstendig", str(caught.exception))

    def test_a_truncated_primary_falls_over_to_the_fallback(self):
        llm = _interface(
            _Model({"finish_reason": "MAX_TOKENS"}),
            _Model({"finish_reason": "STOP"}, content="komplett"),
            fallback_model="gemini-fallback",
        )
        self.assertEqual(llm.invoke("sys", "user"), "komplett")

    def test_both_truncated_surfaces_the_truncation(self):
        llm = _interface(
            _Model({"finish_reason": "MAX_TOKENS"}),
            _Model({"finish_reason": "MAX_TOKENS"}),
            fallback_model="gemini-fallback",
        )
        with self.assertRaises(TruncatedResponseError):
            llm.invoke("sys", "user")


class OutputBudgetTests(unittest.TestCase):
    def test_the_cap_clears_the_largest_document_we_make(self):
        """
        A hefte is budgeted at 8000 output tokens and the editor re-emits the
        whole body on top of that. The old 8192 cap sat below that ceiling.
        """
        settings = Settings(_env_file=None)
        self.assertGreaterEqual(settings.max_output_tokens, 16384)

    def test_the_cap_reaches_the_provider(self):
        seen: list[int] = []

        def factory(_model, _cfg, _temperature, max_tokens):
            seen.append(max_tokens)
            return _Model({"finish_reason": "STOP"})

        cfg = _config(max_output_tokens=24576, fallback_model="gemini-primary")
        with patch.dict(_PROVIDER_FACTORIES, {"google": factory}, clear=True):
            LLMInterface(cfg)
        self.assertEqual(seen, [24576])

    def test_a_config_without_the_field_still_builds(self):
        """Older config objects must not break the interface."""
        cfg = _config(fallback_model="gemini-primary")
        del cfg.max_output_tokens
        with patch.dict(
            _PROVIDER_FACTORIES,
            {"google": lambda _m, _c, _t, _n: _Model({"finish_reason": "STOP"})},
            clear=True,
        ):
            llm = LLMInterface(cfg)
        self.assertEqual(llm.invoke("sys", "user"), "halv tekst")


if __name__ == "__main__":
    unittest.main()
