"""
Model-agnostic LLM interface.

Supports: Google Gemini, Anthropic Claude, OpenAI GPT, local Ollama models.
Implements automatic fallback: if primary model fails, tries secondary.
"""

from __future__ import annotations

from typing import Any

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import LLMProviderConfig, get_config

logger = structlog.get_logger()


def _message_content_to_str(content: Any) -> str:
    """
    Normalize AIMessage.content to a single string.

    Newer Gemini / multimodal models may return a list of blocks (dicts or str)
    instead of a plain string — callers expect str and would fail on .strip().
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                if "text" in block:
                    parts.append(str(block["text"]))
            else:
                t = getattr(block, "text", None)
                if t is not None:
                    parts.append(str(t))
                else:
                    parts.append(str(block))
        return "".join(parts)
    return str(content)


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------
def _create_google(model: str, api_key: str, temperature: float) -> BaseChatModel:
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=model,
        google_api_key=api_key,
        temperature=temperature,
        convert_system_message_to_human=True,
        # Allow long, theory-rich chapters without truncating the body.
        max_output_tokens=8192,
    )


def _create_anthropic(model: str, api_key: str, temperature: float) -> BaseChatModel:
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(
        model=model,
        anthropic_api_key=api_key,
        temperature=temperature,
        max_tokens=8192,
    )


def _create_openai(model: str, api_key: str, temperature: float) -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model,
        api_key=api_key,
        temperature=temperature,
    )


def _create_ollama(model: str, base_url: str, temperature: float) -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    # Ollama exposes an OpenAI-compatible API
    return ChatOpenAI(
        model=model,
        base_url=f"{base_url}/v1",
        api_key="ollama",  # Ollama doesn't need a real key
        temperature=temperature,
    )


_PROVIDER_FACTORIES = {
    "google": lambda m, cfg, t: _create_google(m, cfg.google_api_key, t),
    "anthropic": lambda m, cfg, t: _create_anthropic(m, cfg.anthropic_api_key, t),
    "openai": lambda m, cfg, t: _create_openai(m, cfg.openai_api_key, t),
    "ollama": lambda m, cfg, t: _create_ollama(m, cfg.ollama_base_url, t),
}

_PROVIDER_CREDENTIALS = {
    "google": ("google_api_key", "GOOGLE_API_KEY"),
    "anthropic": ("anthropic_api_key", "ANTHROPIC_API_KEY"),
    "openai": ("openai_api_key", "OPENAI_API_KEY"),
}


# ---------------------------------------------------------------------------
# Unified interface
# ---------------------------------------------------------------------------
class LLMInterface:
    """
    Unified LLM interface with automatic fallback.

    Usage:
        llm = LLMInterface(config)
        response = llm.invoke(system_prompt, user_prompt)
    """

    def __init__(
        self,
        config: LLMProviderConfig | None = None,
        *,
        provider: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
    ):
        cfg = config or get_config().llm
        self._config = cfg
        self._temperature = temperature if temperature is not None else cfg.temperature

        # Primary model
        primary_provider = provider or cfg.primary_provider
        primary_model = model or cfg.primary_model
        self._primary = self._build(primary_provider, primary_model)

        # Fallback model (only if different from primary)
        if (
            cfg.fallback_provider != primary_provider
            or cfg.fallback_model != primary_model
        ):
            try:
                self._fallback = self._build(cfg.fallback_provider, cfg.fallback_model)
            except Exception as fallback_config_error:
                logger.warning(
                    "fallback_llm_disabled",
                    provider=cfg.fallback_provider,
                    model=cfg.fallback_model,
                    error=str(fallback_config_error),
                )
                self._fallback = None
        else:
            self._fallback = None

        self._provider_name = primary_provider
        self._model_name = primary_model
        self.last_usage: dict[str, int] = {"input_tokens": 0, "output_tokens": 0}

    def _extract_usage(self, response: Any) -> None:
        usage = getattr(response, "usage_metadata", None) or getattr(response, "response_metadata", {}).get("token_usage")
        if isinstance(usage, dict):
            self.last_usage = {
                "input_tokens": int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0),
                "output_tokens": int(usage.get("output_tokens") or usage.get("completion_tokens") or 0),
            }
        else:
            self.last_usage = {"input_tokens": 0, "output_tokens": 0}

    def _build(self, provider: str, model: str) -> BaseChatModel:
        factory = _PROVIDER_FACTORIES.get(provider)
        if factory is None:
            raise ValueError(
                f"Unknown LLM provider: {provider!r}. "
                f"Supported: {', '.join(_PROVIDER_FACTORIES)}"
            )
        credential = _PROVIDER_CREDENTIALS.get(provider)
        if credential is not None:
            attribute, environment_variable = credential
            if not str(getattr(self._config, attribute, "") or "").strip():
                raise ValueError(
                    f"{provider.title()}-leverandøren mangler {environment_variable}."
                )
        return factory(model, self._config, self._temperature)

    @property
    def provider(self) -> str:
        return self._provider_name

    @property
    def model(self) -> str:
        return self._model_name

    def invoke(self, system_prompt: str, user_prompt: str) -> str:
        """
        Send a system+user prompt pair to the LLM. Returns the text response.
        Falls back to secondary model on failure.
        """
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        try:
            response = self._primary.invoke(messages)
            self._extract_usage(response)
            return _message_content_to_str(response.content)
        except Exception as primary_err:
            logger.warning(
                "primary_llm_failed",
                provider=self._provider_name,
                model=self._model_name,
                error=str(primary_err),
            )

            if self._fallback is not None:
                try:
                    logger.info("attempting_fallback_llm")
                    response = self._fallback.invoke(messages)
                    self._extract_usage(response)
                    return _message_content_to_str(response.content)
                except Exception as fallback_err:
                    logger.error(
                        "fallback_llm_failed",
                        provider=self._config.fallback_provider,
                        model=self._config.fallback_model,
                        error=str(fallback_err),
                    )
                    # Preserve the primary failure: a secondary provider/model
                    # must never mask the actual reason the configured model failed.
                    raise primary_err from fallback_err

            raise primary_err

    async def ainvoke(self, system_prompt: str, user_prompt: str) -> str:
        """Async version of invoke."""
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        try:
            response = await self._primary.ainvoke(messages)
            self._extract_usage(response)
            return _message_content_to_str(response.content)
        except Exception as primary_err:
            logger.warning(
                "primary_llm_failed",
                provider=self._provider_name,
                model=self._model_name,
                error=str(primary_err),
            )
            if self._fallback is not None:
                try:
                    response = await self._fallback.ainvoke(messages)
                    self._extract_usage(response)
                    return _message_content_to_str(response.content)
                except Exception as fallback_err:
                    logger.error(
                        "fallback_llm_failed",
                        provider=self._config.fallback_provider,
                        model=self._config.fallback_model,
                        error=str(fallback_err),
                    )
                    raise primary_err from fallback_err
            raise primary_err


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------
def get_llm(
    *,
    provider: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
) -> LLMInterface:
    """Create an LLM interface with optional overrides."""
    return LLMInterface(
        provider=provider,
        model=model,
        temperature=temperature,
    )
