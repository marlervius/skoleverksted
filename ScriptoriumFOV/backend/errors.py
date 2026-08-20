"""Domain exceptions with safe, user-visible messages (Norwegian).

Provider response bodies and prompts deliberately stay out of these objects.  A
generation error can therefore be stored in progress state and returned to the
browser without leaking credentials or model output.
"""

from __future__ import annotations


class GenerationError(RuntimeError):
    """A classified, supportable failure in the generation pipeline."""

    code = "generation_failed"
    public_message = "Genereringen kunne ikke fullføres. Du kan prøve igjen."
    retryable = True

    def __init__(
        self,
        message: str | None = None,
        *,
        external_status: int | None = None,
        technical_detail: str = "",
    ) -> None:
        super().__init__(message or self.public_message)
        self.public_message = message or self.public_message
        self.external_status = external_status
        self.technical_detail = technical_detail


class ModelTimeoutError(GenerationError):
    code = "model_timeout"
    public_message = (
        "Tekstgeneratoren svarte ikke innen tidsgrensen. Innholdet ble ikke "
        "lagret. Du kan prøve igjen."
    )


class ModelRateLimitError(GenerationError):
    code = "model_rate_limited"
    public_message = (
        "Tekstgeneratoren har for stor belastning akkurat nå. Innholdet ble "
        "ikke lagret. Vent litt og prøv igjen."
    )


class ModelNotFoundError(GenerationError):
    code = "model_not_found"
    public_message = (
        "Tekstgeneratoren er feilkonfigurert. Ingen tekst ble lagret. Oppgi "
        "request-ID-en til support."
    )
    retryable = False


class ModelConfigurationError(GenerationError):
    code = "model_configuration_error"
    public_message = (
        "Tekstgeneratoren mangler gyldig konfigurasjon. Ingen tekst ble lagret. "
        "Oppgi request-ID-en til support."
    )
    retryable = False


class ModelResponseInvalidError(GenerationError):
    code = "model_response_invalid"
    public_message = (
        "AI-svaret kunne ikke kvalitetssikres. Ingen ukontrollert tekst ble "
        "lagret. Prøv genereringen på nytt."
    )

    def __init__(self, code: str = "model_response_invalid") -> None:
        super().__init__()
        self.code = code


class ModelProviderError(GenerationError):
    code = "model_provider_error"
    public_message = (
        "Tekstgeneratoren returnerte en feil. Innholdet ble ikke lagret. Du kan "
        "prøve igjen."
    )


class ImageGenerationError(GenerationError):
    code = "image_generation_failed"
    public_message = (
        "Læringsinnholdet er klart, men KI-bildet kunne ikke lages. Prøv bildet "
        "på nytt eller fortsett uten bilde."
    )


class GenerationCancelledError(GenerationError):
    code = "generation_cancelled"
    public_message = "Genereringen ble avbrutt."
    retryable = False


class GeminiQuotaExceededError(ModelRateLimitError):
    """
    Raised when Google Gemini returns 429 / RESOURCE_EXHAUSTED or quota errors.

    `user_message` is shown in the API progress / UI; `technical_detail` is for logging & backoff.
    """

    def __init__(self, user_message: str, *, technical_detail: str = ""):
        super().__init__(user_message, external_status=429, technical_detail=technical_detail)
        self.user_message = user_message
