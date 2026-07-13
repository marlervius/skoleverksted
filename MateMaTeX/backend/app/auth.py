"""
Authentication for FastAPI.

Supports optional MATE_API_KEY and Supabase JWT (Bearer) for user identity.
"""

from __future__ import annotations

import structlog
from fastapi import HTTPException, Header, Query

from app.config import get_settings

logger = structlog.get_logger()


def _extract_bearer(authorization: str) -> str:
    if authorization.startswith("Bearer "):
        return authorization.removeprefix("Bearer ").strip()
    return ""


def _looks_like_jwt(token: str) -> bool:
    return token.count(".") == 2 and not token.startswith("mate_")


def _verify_supabase_jwt(token: str) -> str | None:
    settings = get_settings()
    if not settings.supabase_jwt_secret:
        return None
    try:
        import jwt

        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
        sub = payload.get("sub")
        if sub:
            return str(sub)
    except Exception as e:
        logger.warning("auth_jwt_rejected", error=str(e))
    return None


def _resolve_user_from_token(token: str) -> str | None:
    """Return user id from JWT or API key match."""
    if not token:
        return None
    if _looks_like_jwt(token):
        return _verify_supabase_jwt(token)
    settings = get_settings()
    if settings.mate_api_key and token == settings.mate_api_key:
        return "api-user"
    return None


async def get_current_user(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str = Header(default=""),
) -> str:
    """
    Return user id for the request.

    Priority: X-API-Key / Bearer JWT / Bearer API key.
    """
    settings = get_settings()
    token = (x_api_key or "").strip() or _extract_bearer(authorization)

    user_id = _resolve_user_from_token(token)
    if user_id:
        return user_id

    if not settings.mate_api_key:
        if settings.environment == "production":
            raise HTTPException(
                status_code=503,
                detail="API key not configured (set MATE_API_KEY in production)",
            )
        return "anonymous"

    logger.warning("auth_api_key_rejected", has_header=bool(token))
    raise HTTPException(
        status_code=401,
        detail="Invalid or missing API key (use X-API-Key or Authorization: Bearer)",
    )


async def get_optional_user(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str = Header(default=""),
) -> str | None:
    """Like get_current_user but returns None when no valid credentials."""
    token = (x_api_key or "").strip() or _extract_bearer(authorization)
    return _resolve_user_from_token(token)


async def require_stream_access(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str = Header(default=""),
    api_key: str | None = Query(
        default=None,
        description="Optional API key for SSE clients that cannot set headers (discouraged; prefer Next.js proxy).",
    ),
) -> str:
    """
    Same rules as get_current_user, but also accepts ``api_key`` query param
    for EventSource-only clients. Prefer server-side proxy with X-API-Key.
    """
    settings = get_settings()
    token = (
        (x_api_key or "").strip()
        or _extract_bearer(authorization)
        or (api_key or "").strip()
    )

    user_id = _resolve_user_from_token(token)
    if user_id:
        return user_id

    if not settings.mate_api_key:
        if settings.environment == "production":
            raise HTTPException(
                status_code=503,
                detail="API key not configured (set MATE_API_KEY in production)",
            )
        return "anonymous"

    logger.warning("stream_auth_rejected", has_token=bool(token))
    raise HTTPException(
        status_code=401,
        detail="Invalid or missing API key for stream (X-API-Key, Bearer, or api_key query)",
    )
