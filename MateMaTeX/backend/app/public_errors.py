"""Convert internal generation failures to safe, actionable user messages."""

from __future__ import annotations


_SAFE_PREFIXES = (
    "Avbrutt av bruker",
    "SymPy fant ",
    "Endelig fasitkontroll feilet",
    "Materialet leveres ikke",
)


def public_generation_error(error: object) -> str:
    """Return a Norwegian message without leaking SDK or credential details."""
    message = str(error or "").strip()
    if not message:
        return "KI-genereringen feilet midlertidig. Prøv igjen."
    if message.startswith(_SAFE_PREFIXES):
        return message

    normalized = message.casefold()
    if any(
        marker in normalized
        for marker in (
            "authentication",
            "api_key",
            "api key",
            "auth_token",
            "authorization",
            "credentials",
            "permission_denied",
            "unauthenticated",
        )
    ):
        return (
            "Modelltjenesten mangler gyldig Google API-nøkkel. "
            "Kontroller GOOGLE_API_KEY på serveren."
        )
    if any(
        marker in normalized
        for marker in (
            "model not found",
            "model_not_found",
            "models/",
            "not found for api version",
        )
    ):
        return (
            "Den valgte KI-modellen er ikke tilgjengelig. "
            "Kontroller modelloppsettet på serveren."
        )
    if any(
        marker in normalized
        for marker in (
            "429",
            "quota",
            "rate limit",
            "rate_limit",
            "resource_exhausted",
            "too many requests",
        )
    ):
        return (
            "KI-tjenesten er midlertidig overbelastet eller kvoten er brukt opp. "
            "Vent litt og prøv igjen."
        )
    if any(
        marker in normalized
        for marker in ("timeout", "timed out", "deadline exceeded", "deadline_exceeded")
    ):
        return "KI-tjenesten brukte for lang tid. Prøv igjen."

    return "KI-genereringen feilet midlertidig. Prøv igjen."
