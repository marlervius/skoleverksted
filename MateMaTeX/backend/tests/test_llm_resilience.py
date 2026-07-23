from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.config import Settings
from app.models.llm import LLMInterface, _PROVIDER_FACTORIES
from app.public_errors import public_generation_error


class _FakeModel:
    def __init__(self, error: str | None = None):
        self.error = error

    def invoke(self, _messages):
        if self.error:
            raise RuntimeError(self.error)
        return SimpleNamespace(content="ok", usage_metadata={})


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
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class LLMResilienceTests(unittest.TestCase):
    def test_production_defaults_use_google_for_primary_and_fallback(self):
        settings = Settings(_env_file=None)
        self.assertEqual(settings.primary_provider, "google")
        self.assertEqual(settings.primary_model, "gemini-3.5-flash")
        self.assertEqual(settings.fallback_provider, "google")
        self.assertEqual(settings.fallback_model, "gemini-3.1-flash-lite")

    def test_unconfigured_fallback_provider_is_disabled(self):
        calls: list[tuple[str, str]] = []

        def google_factory(model, _cfg, _temperature):
            calls.append(("google", model))
            return _FakeModel()

        def anthropic_factory(model, _cfg, _temperature):
            calls.append(("anthropic", model))
            return _FakeModel()

        cfg = _config(
            fallback_provider="anthropic",
            fallback_model="claude-fallback",
            anthropic_api_key="",
        )
        with patch.dict(
            _PROVIDER_FACTORIES,
            {"google": google_factory, "anthropic": anthropic_factory},
        ):
            interface = LLMInterface(cfg)

        self.assertEqual(calls, [("google", "gemini-primary")])
        self.assertIsNone(interface._fallback)

    def test_fallback_failure_does_not_mask_primary_failure(self):
        def google_factory(model, _cfg, _temperature):
            if model == "gemini-primary":
                return _FakeModel("primary model unavailable")
            return _FakeModel("fallback quota exceeded")

        with patch.dict(_PROVIDER_FACTORIES, {"google": google_factory}):
            interface = LLMInterface(_config())
            with self.assertRaisesRegex(RuntimeError, "primary model unavailable"):
                interface.invoke("system", "user")


class PublicGenerationErrorTests(unittest.TestCase):
    def test_authentication_sdk_error_is_not_exposed(self):
        raw = (
            "Could not resolve authentication method. Expected one of api_key, "
            "auth_token, or credentials to be set."
        )
        message = public_generation_error(raw)
        self.assertEqual(
            message,
            "Modelltjenesten mangler gyldig Google API-nøkkel. "
            "Kontroller GOOGLE_API_KEY på serveren.",
        )
        self.assertNotIn("authentication", message.casefold())

    def test_unknown_internal_error_is_generic(self):
        self.assertEqual(
            public_generation_error("AttributeError: secret internal implementation"),
            "KI-genereringen feilet midlertidig. Prøv igjen.",
        )

    def test_math_safety_error_remains_actionable(self):
        message = "SymPy fant 2 feil i fasiten. Materialet leveres ikke."
        self.assertEqual(public_generation_error(message), message)


if __name__ == "__main__":
    unittest.main()
