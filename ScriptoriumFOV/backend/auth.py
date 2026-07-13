"""
Simple shared-secret auth via APP_PASSWORD and Authorization: Bearer <password>.

If APP_PASSWORD is unset or empty, auth is disabled (for local development).
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


def app_password_configured() -> bool:
    return bool(os.getenv("APP_PASSWORD", "").strip())


def password_matches(given: str, expected: str) -> bool:
    """Constant-time compare using SHA-256 digests (handles unequal lengths)."""
    gh = hashlib.sha256(given.encode("utf-8")).digest()
    eh = hashlib.sha256(expected.encode("utf-8")).digest()
    return hmac.compare_digest(gh, eh)


def verify_password_plain(given: str) -> bool:
    expected = os.getenv("APP_PASSWORD", "").strip()
    if not expected:
        return True
    return password_matches(given, expected)


async def require_app_password(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> None:
    """Dependency: enforce Bearer password when APP_PASSWORD is set."""
    expected = os.getenv("APP_PASSWORD", "").strip()
    if not expected:
        return
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Autentisering kreves. Bruk header: Authorization: Bearer <passord>",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not password_matches(creds.credentials, expected):
        raise HTTPException(
            status_code=401,
            detail="Feil passord.",
            headers={"WWW-Authenticate": "Bearer"},
        )
