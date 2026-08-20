"""Stable generation stages, output validation and provider error mapping."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

try:
    from .errors import (
        GenerationError,
        ModelConfigurationError,
        ModelNotFoundError,
        ModelProviderError,
        ModelRateLimitError,
        ModelResponseInvalidError,
        ModelTimeoutError,
    )
except ImportError:  # pragma: no cover - supports the legacy flat test import
    from errors import (
        GenerationError,
        ModelConfigurationError,
        ModelNotFoundError,
        ModelProviderError,
        ModelRateLimitError,
        ModelResponseInvalidError,
        ModelTimeoutError,
    )


@dataclass(frozen=True)
class PipelineStep:
    number: int
    key: str
    name: str


# This is the real order in the ordinary PDF flow.  The quality gate runs
# after model output and before any paid or remote image operation.
PIPELINE_STEPS = (
    PipelineStep(1, "content_generation", "Genererer og strukturerer læringsinnhold"),
    PipelineStep(2, "quality_assurance", "Fakta-, kilde- og kvalitetskontroll"),
    PipelineStep(3, "image_processing", "Bildevalg og bildebehandling"),
    PipelineStep(4, "document_build", "Dokumentbygging og eksportkontroll"),
)

STEP_BY_KEY = {step.key: step for step in PIPELINE_STEPS}


def _external_status(message: str) -> int | None:
    match = re.search(r"(?:status(?:_code)?[=:\s]+|\b)(4\d\d|5\d\d)\b", message, re.I)
    return int(match.group(1)) if match else None


def classify_model_error(exc: BaseException) -> GenerationError:
    """Map provider/library exceptions to a safe and stable error contract."""

    if isinstance(exc, GenerationError):
        return exc
    raw = str(exc)
    lowered = raw.casefold()
    status = _external_status(raw)
    if isinstance(exc, TimeoutError) or any(
        marker in lowered for marker in ("timed out", "timeout", "deadline exceeded")
    ):
        return ModelTimeoutError(external_status=status, technical_detail=type(exc).__name__)
    if status == 429 or "resource_exhausted" in lowered or "rate limit" in lowered or "quota" in lowered:
        return ModelRateLimitError(external_status=status or 429, technical_detail=type(exc).__name__)
    if status == 404 and "model" in lowered or "model" in lowered and "not found" in lowered:
        return ModelNotFoundError(external_status=status, technical_detail=type(exc).__name__)
    if any(marker in lowered for marker in ("api key", "credential", "authentication", "permission denied")):
        return ModelConfigurationError(external_status=status, technical_detail=type(exc).__name__)
    return ModelProviderError(external_status=status, technical_detail=type(exc).__name__)


def validate_model_outputs(
    *,
    text: object,
    worksheet: object,
    language_exercises_raw: object = None,
) -> dict[str, Any] | None:
    """Reject empty or malformed model fields before the truth layer sees them."""

    clean_text = str(text or "").strip()
    clean_worksheet = str(worksheet or "").strip()
    if not clean_text:
        raise ModelResponseInvalidError("model_response_empty")
    if not clean_worksheet:
        raise ModelResponseInvalidError("model_response_missing_field")

    if language_exercises_raw in (None, ""):
        return None
    if isinstance(language_exercises_raw, dict):
        parsed = language_exercises_raw
    elif isinstance(language_exercises_raw, str):
        try:
            parsed = json.loads(language_exercises_raw)
        except json.JSONDecodeError as exc:
            raise ModelResponseInvalidError() from exc
    else:
        raise ModelResponseInvalidError()
    if not isinstance(parsed, dict):
        raise ModelResponseInvalidError()
    for field in ("grammar_tasks", "vocabulary_tasks", "syntax_tasks"):
        value = parsed.get(field, [])
        if not isinstance(value, list):
            raise ModelResponseInvalidError()
    return parsed
