"""Shared access code in front of the whole API for the closed teacher pilot.

``APP_PASSWORD`` is the one shared code. Before this gate only the Norsk module
checked it, so Fag, the platform API and the mathematics proxy were open to
anyone who knew the public backend address.

* Every route needs ``Authorization: Bearer <token-or-code>``. Downloads and
  event streams that the browser opens without custom headers may carry the
  token as ``?access_token=`` on GET/HEAD instead.
* The login endpoint trades the code for a signed token that expires, so the
  code itself never has to appear in a URL. Changing ``APP_PASSWORD`` revokes
  every outstanding token.
* Only health checks, the login/status pair and the capability links for shared
  mathematics sheets are reachable without credentials.
* In production a missing code fails closed instead of silently opening the API.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import time
from collections import deque
from collections.abc import Awaitable, Callable, Mapping
from typing import Any
from urllib.parse import parse_qs

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


#: Set on the ASGI scope once a request is authorised, so mounted domain apps
#: (which keep their own optional password check) can trust the platform gate.
ACCESS_SCOPE_KEY = "skoleverksted.access_granted"

# No dots: the mathematics app treats any three-part dotted bearer as a JWT.
TOKEN_PREFIX = "sv1"
_TOKEN_RE = re.compile(rf"^{TOKEN_PREFIX}_(\d{{1,12}})_([0-9a-f]{{64}})$")
_SIGNING_CONTEXT = b"skoleverksted-access-token-v1"

DEFAULT_TOKEN_TTL_HOURS = 12
MAX_TOKEN_TTL_HOURS = 24 * 7

_READ_METHODS = frozenset({"GET", "HEAD"})
_PUBLIC_ROUTES: tuple[tuple[frozenset[str], re.Pattern[str]], ...] = (
    (_READ_METHODS, re.compile(r"^/$")),
    (_READ_METHODS, re.compile(r"^/health(?:/ready)?$")),
    (_READ_METHODS, re.compile(r"^/api/platform/access/status$")),
    (frozenset({"POST"}), re.compile(r"^/api/platform/access/login$")),
    # Shared mathematics sheets are capability links meant for people without a
    # code. Creating (POST /sharing) and cloning stay behind the gate.
    (_READ_METHODS, re.compile(r"^/api/matematikk/sharing/[^/]+$")),
    (frozenset({"POST"}), re.compile(r"^/api/matematikk/sharing/[^/]+/access$")),
    (_READ_METHODS, re.compile(r"^/api/matematikk/sharing/[^/]+/pdf$")),
)


def access_code(environ: Mapping[str, str] | None = None) -> str:
    env = os.environ if environ is None else environ
    return env.get("APP_PASSWORD", "").strip()


def is_production(environ: Mapping[str, str] | None = None) -> bool:
    env = os.environ if environ is None else environ
    return env.get("ENVIRONMENT", "").strip().lower() == "production"


def access_enforced(environ: Mapping[str, str] | None = None) -> bool:
    """True when requests need credentials (a code exists, or production)."""
    return bool(access_code(environ)) or is_production(environ)


def token_ttl_seconds(environ: Mapping[str, str] | None = None) -> int:
    env = os.environ if environ is None else environ
    try:
        hours = float(env.get("ACCESS_TOKEN_TTL_HOURS", "") or DEFAULT_TOKEN_TTL_HOURS)
    except ValueError:
        hours = DEFAULT_TOKEN_TTL_HOURS
    return int(max(1.0, min(float(MAX_TOKEN_TTL_HOURS), hours)) * 3600)


def _signing_key(code: str) -> bytes:
    return hmac.new(code.encode("utf-8"), _SIGNING_CONTEXT, hashlib.sha256).digest()


def _signature(code: str, expires_at: int) -> str:
    message = f"{TOKEN_PREFIX}_{expires_at}".encode("ascii")
    return hmac.new(_signing_key(code), message, hashlib.sha256).hexdigest()


def issue_token(code: str, *, now: float | None = None, ttl_seconds: int | None = None) -> tuple[str, int]:
    """Return ``(token, expires_at_epoch_seconds)`` signed with the shared code."""
    issued = time.time() if now is None else now
    expires_at = int(issued) + (token_ttl_seconds() if ttl_seconds is None else ttl_seconds)
    return f"{TOKEN_PREFIX}_{expires_at}_{_signature(code, expires_at)}", expires_at


def verify_token(token: str, code: str, *, now: float | None = None) -> bool:
    if not code:
        return False
    match = _TOKEN_RE.match(token or "")
    if not match:
        return False
    expires_at = int(match.group(1))
    if expires_at <= (time.time() if now is None else now):
        return False
    return hmac.compare_digest(match.group(2), _signature(code, expires_at))


def code_matches(given: str, expected: str) -> bool:
    """Constant-time compare using digests, so unequal lengths do not leak."""
    given_digest = hashlib.sha256(given.encode("utf-8")).digest()
    expected_digest = hashlib.sha256(expected.encode("utf-8")).digest()
    return hmac.compare_digest(given_digest, expected_digest)


def is_public_route(method: str, path: str) -> bool:
    method = method.upper()
    return any(method in methods and pattern.match(path) for methods, pattern in _PUBLIC_ROUTES)


def _bearer(authorization: str) -> str:
    scheme, _, value = authorization.partition(" ")
    return value.strip() if scheme.lower() == "bearer" else ""


def credentials_valid(
    *,
    method: str,
    authorization: str,
    query_token: str,
    environ: Mapping[str, str] | None = None,
    now: float | None = None,
) -> bool:
    code = access_code(environ)
    if not code:
        return False
    bearer = _bearer(authorization)
    if bearer and (verify_token(bearer, code, now=now) or code_matches(bearer, code)):
        return True
    # Only the signed token may travel in a URL, and only on read requests.
    return method.upper() in _READ_METHODS and verify_token(query_token, code, now=now)


def _decode(value: bytes) -> str:
    return value.decode("latin-1")


def _scope_credentials(scope: Mapping[str, Any]) -> tuple[str, str]:
    authorization = ""
    for key, value in scope.get("headers", []):
        if key == b"authorization":
            authorization = _decode(value)
            break
    query = parse_qs(_decode(scope.get("query_string", b"")), keep_blank_values=False)
    return authorization, (query.get("access_token") or [""])[0]


_UNAUTHORIZED = {
    "detail": "Tilgangskode kreves. Logg inn på nytt.",
    "code": "access_required",
    "retryable": False,
}
_NOT_CONFIGURED = {
    "detail": "Tilgang er ikke konfigurert på serveren.",
    "code": "access_not_configured",
    "retryable": False,
}


class AccessGateMiddleware:
    """Pure ASGI gate so event streams and file downloads pass through untouched."""

    def __init__(self, app: Callable[..., Awaitable[None]]):
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Callable[..., Any], send: Callable[..., Any]) -> None:
        scope_type = scope.get("type")
        if scope_type not in {"http", "websocket"} or not access_enforced():
            await self.app(scope, receive, send)
            return

        method = str(scope.get("method", "GET")).upper()
        # CORS preflights carry no credentials by design; the CORS layer answers them.
        if method == "OPTIONS" or is_public_route(method, str(scope.get("path", ""))):
            await self.app(scope, receive, send)
            return

        if not access_code():
            rejection = JSONResponse(_NOT_CONFIGURED, status_code=503, headers={"Cache-Control": "no-store"})
        else:
            authorization, query_token = _scope_credentials(scope)
            if credentials_valid(method=method, authorization=authorization, query_token=query_token):
                scope[ACCESS_SCOPE_KEY] = True
                await self.app(scope, receive, send)
                return
            rejection = JSONResponse(
                _UNAUTHORIZED,
                status_code=401,
                headers={"WWW-Authenticate": "Bearer", "Cache-Control": "no-store"},
            )

        if scope_type == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        await rejection(scope, receive, send)


def access_granted(request: Request) -> bool:
    """Whether the platform gate already authorised this request."""
    return bool(request.scope.get(ACCESS_SCOPE_KEY))


class LoginThrottle:
    """Slow down code guessing: failures per client plus a global backstop.

    Client addresses come from proxy headers and can be spoofed, so the global
    ceiling is what actually bounds an attacker. It is deliberately generous
    enough that a few mistyped codes in a classroom do not lock anyone out.
    """

    def __init__(self, *, per_client: int = 8, overall: int = 60, window_seconds: int = 600, max_clients: int = 2048):
        self.per_client = per_client
        self.overall = overall
        self.window = window_seconds
        self.max_clients = max_clients
        self._clients: dict[str, deque[float]] = {}
        self._all: deque[float] = deque()

    def _prune(self, now: float) -> None:
        cutoff = now - self.window
        while self._all and self._all[0] <= cutoff:
            self._all.popleft()
        for client in [key for key, hits in self._clients.items() if not hits or hits[-1] <= cutoff]:
            del self._clients[client]
        for hits in self._clients.values():
            while hits and hits[0] <= cutoff:
                hits.popleft()

    def retry_after(self, client: str, now: float | None = None) -> int:
        """Seconds to wait before another attempt, or 0 if attempts are allowed."""
        moment = time.monotonic() if now is None else now
        self._prune(moment)
        waits = []
        hits = self._clients.get(client)
        if hits and len(hits) >= self.per_client:
            waits.append(hits[0] + self.window - moment)
        if len(self._all) >= self.overall:
            waits.append(self._all[0] + self.window - moment)
        return max(1, int(max(waits) + 1)) if waits else 0

    def record_failure(self, client: str, now: float | None = None) -> None:
        moment = time.monotonic() if now is None else now
        self._prune(moment)
        if client not in self._clients and len(self._clients) >= self.max_clients:
            del self._clients[next(iter(self._clients))]
        self._clients.setdefault(client, deque()).append(moment)
        self._all.append(moment)


_throttle = LoginThrottle()


def get_login_throttle() -> LoginThrottle:
    return _throttle


def client_id(request: Request) -> str:
    for header in ("cf-connecting-ip", "x-forwarded-for"):
        value = request.headers.get(header, "").split(",")[0].strip()
        if value:
            return value[:64]
    return request.client.host if request.client else "unknown"


class LoginBody(BaseModel):
    code: str = Field(default="", max_length=256)


router = APIRouter(tags=["access"])
_NO_STORE = {"Cache-Control": "no-store"}


@router.get("/status")
async def access_status(request: Request) -> JSONResponse:
    """Tell the browser whether it must sign in and whether it already has."""
    required = access_enforced()
    authorization, query_token = _scope_credentials(request.scope)
    authenticated = (not required) or credentials_valid(
        method=request.method, authorization=authorization, query_token=query_token
    )
    return JSONResponse(
        {"required": required, "authenticated": authenticated, "configured": bool(access_code()) or not required},
        headers=_NO_STORE,
    )


@router.post("/login")
async def access_login(body: LoginBody, request: Request) -> JSONResponse:
    code = access_code()
    if not code:
        if access_enforced():
            return JSONResponse(_NOT_CONFIGURED, status_code=503, headers=_NO_STORE)
        return JSONResponse({"required": False, "token": None, "expires_at": None}, headers=_NO_STORE)

    throttle = get_login_throttle()
    client = client_id(request)
    wait = throttle.retry_after(client)
    if wait:
        return JSONResponse(
            {
                "detail": "For mange forsøk. Vent litt og prøv igjen.",
                "code": "too_many_attempts",
                "retryable": True,
                "retry_after": wait,
            },
            status_code=429,
            headers={**_NO_STORE, "Retry-After": str(wait)},
        )

    if not code_matches(body.code.strip(), code):
        throttle.record_failure(client)
        return JSONResponse(
            {"detail": "Feil tilgangskode.", "code": "invalid_access_code", "retryable": False},
            status_code=401,
            headers=_NO_STORE,
        )

    token, expires_at = issue_token(code)
    return JSONResponse({"required": True, "token": token, "expires_at": expires_at}, headers=_NO_STORE)
