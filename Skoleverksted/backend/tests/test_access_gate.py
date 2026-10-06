"""The shared access gate that fronts the whole pilot API."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from ScriptoriumFOV.backend.auth import platform_access_granted, require_app_password
from Skoleverksted.backend.platform import access
from Skoleverksted.backend.platform.access import (
    ACCESS_SCOPE_KEY,
    AccessGateMiddleware,
    LoginThrottle,
    issue_token,
    verify_token,
)

CODE = "pilot-kode-2026"
ORIGIN = "http://localhost:3000"


def build_app() -> FastAPI:
    """Same middleware order as the real entrypoint, with stand-in routes."""
    app = FastAPI()
    app.add_middleware(AccessGateMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[ORIGIN],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(access.router, prefix="/api/platform/access")

    @app.get("/")
    def root():
        return {"name": "Skoleverksted"}

    @app.get("/health")
    def health():
        return {"status": "healthy"}

    @app.get("/health/ready")
    def ready():
        return {"status": "ready"}

    @app.get("/api/platform/jobs")
    def jobs(request: Request):
        return {"granted": bool(request.scope.get(ACCESS_SCOPE_KEY)), "items": []}

    @app.get("/api/fag/generate-lesson-stream/{job_id}")
    def stream(job_id: str):
        return {"job_id": job_id}

    @app.post("/api/fag/generate-lesson-start")
    def start():
        return {"job_id": "abc"}

    for method, path in (
        ("get", "/api/matematikk/sharing/abc"),
        ("get", "/api/matematikk/sharing/abc/pdf"),
        ("post", "/api/matematikk/sharing/abc/access"),
        ("post", "/api/matematikk/sharing"),
        ("post", "/api/matematikk/sharing/abc/clone"),
    ):
        getattr(app, method)(path)(lambda: {"ok": True})

    # Norsk keeps its own optional password check; the gate must satisfy it.
    norsk = FastAPI()

    @norsk.get("/auth/config")
    async def auth_config(request: Request):
        return {"password_required": not platform_access_granted(request)}

    @norsk.get("/generation-status/{generation_id}")
    async def status(generation_id: str, _auth: None = Depends(require_app_password)):
        return {"id": generation_id}

    app.mount("/api/norsk", norsk)
    return app


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("ACCESS_TOKEN_TTL_HOURS", raising=False)
    monkeypatch.setenv("APP_PASSWORD", CODE)
    monkeypatch.setattr(access, "_throttle", LoginThrottle())


@pytest.fixture
def client() -> TestClient:
    return TestClient(build_app())


def login(client: TestClient, code: str = CODE):
    return client.post("/api/platform/access/login", json={"code": code})


def bearer(value: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {value}"}


# --- who gets in ---------------------------------------------------------


def test_every_api_route_is_closed_without_credentials(client):
    for method, path in (
        ("get", "/api/platform/jobs"),
        ("get", "/api/fag/generate-lesson-stream/abc"),
        ("post", "/api/fag/generate-lesson-start"),
        ("get", "/api/norsk/generation-status/abc"),
        ("post", "/api/matematikk/sharing"),
        ("post", "/api/matematikk/sharing/abc/clone"),
    ):
        response = getattr(client, method)(path)
        assert response.status_code == 401, path
        body = response.json()
        assert body["code"] == "access_required"
        assert response.headers["www-authenticate"] == "Bearer"


def test_documentation_and_unknown_paths_are_closed_too(client):
    assert client.get("/docs").status_code == 401
    assert client.get("/openapi.json").status_code == 401
    assert client.get("/api/fag/health").status_code == 401


def test_open_when_no_code_is_configured_outside_production(client, monkeypatch):
    monkeypatch.delenv("APP_PASSWORD")
    assert client.get("/api/platform/jobs").status_code == 200
    assert client.get("/api/platform/access/status").json() == {
        "required": False,
        "authenticated": True,
        "configured": True,
    }


def test_production_without_a_code_fails_closed(client, monkeypatch):
    monkeypatch.delenv("APP_PASSWORD")
    monkeypatch.setenv("ENVIRONMENT", "production")

    response = client.get("/api/platform/jobs")
    assert response.status_code == 503
    assert response.json()["code"] == "access_not_configured"
    assert client.post("/api/platform/access/login", json={"code": "x"}).status_code == 503
    # Health checks stay reachable so the host can report the misconfiguration.
    assert client.get("/health").status_code == 200
    assert client.get("/api/platform/access/status").json()["configured"] is False


def test_health_and_login_are_public_but_nothing_else(client):
    assert client.get("/").status_code == 200
    assert client.get("/health").status_code == 200
    assert client.get("/health/ready").status_code == 200
    assert client.head("/health").status_code in {200, 405}
    assert client.get("/api/platform/access/status").status_code == 200


def test_shared_mathematics_links_stay_open_but_creating_and_cloning_do_not(client):
    assert client.get("/api/matematikk/sharing/abc").status_code == 200
    assert client.get("/api/matematikk/sharing/abc/pdf").status_code == 200
    assert client.post("/api/matematikk/sharing/abc/access").status_code == 200
    assert client.post("/api/matematikk/sharing").status_code == 401
    assert client.post("/api/matematikk/sharing/abc/clone").status_code == 401
    # A look-alike path must not slip through the exemption.
    assert client.get("/api/matematikk/sharing/abc/extra/pdf").status_code in {401, 404}
    assert client.get("/api/matematikk/sharingx/abc").status_code == 401


# --- credentials ---------------------------------------------------------


def test_shared_code_as_bearer_is_accepted_and_marks_the_scope(client):
    response = client.get("/api/platform/jobs", headers=bearer(CODE))
    assert response.status_code == 200
    assert response.json()["granted"] is True


def test_wrong_code_and_wrong_scheme_are_rejected(client):
    assert client.get("/api/platform/jobs", headers=bearer("feil")).status_code == 401
    assert client.get("/api/platform/jobs", headers={"Authorization": f"Basic {CODE}"}).status_code == 401
    assert client.get("/api/platform/jobs", headers={"Authorization": CODE}).status_code == 401


def test_login_issues_a_token_that_works_as_header(client):
    response = login(client)
    assert response.status_code == 200
    token = response.json()["token"]
    assert response.json()["expires_at"] > time.time()
    assert response.headers["cache-control"] == "no-store"
    assert "." not in token, "a dotted token would be mistaken for a JWT by the mathematics app"
    assert client.get("/api/platform/jobs", headers=bearer(token)).status_code == 200


def test_token_may_travel_in_the_url_for_downloads_and_streams(client):
    token = login(client).json()["token"]
    assert client.get(f"/api/fag/generate-lesson-stream/abc?access_token={token}").status_code == 200


def test_url_credentials_are_read_only_and_never_the_raw_code(client):
    token = login(client).json()["token"]
    assert client.post(f"/api/fag/generate-lesson-start?access_token={token}").status_code == 401
    assert client.get(f"/api/platform/jobs?access_token={CODE}").status_code == 401
    assert client.get("/api/platform/jobs?access_token=garbage").status_code == 401


def test_expired_tampered_and_foreign_tokens_are_rejected(client):
    expired, _ = issue_token(CODE, now=time.time() - 7200, ttl_seconds=60)
    assert client.get("/api/platform/jobs", headers=bearer(expired)).status_code == 401

    good = login(client).json()["token"]
    prefix, expiry, signature = good.split("_")
    tampered = f"{prefix}_{int(expiry) + 86400}_{signature}"
    assert client.get("/api/platform/jobs", headers=bearer(tampered)).status_code == 401
    flipped = signature[:-1] + ("0" if signature[-1] != "0" else "1")
    assert client.get("/api/platform/jobs", headers=bearer(f"{prefix}_{expiry}_{flipped}")).status_code == 401

    other, _ = issue_token("annen-kode")
    assert client.get("/api/platform/jobs", headers=bearer(other)).status_code == 401


def test_changing_the_code_revokes_every_outstanding_token(client, monkeypatch):
    token = login(client).json()["token"]
    assert client.get("/api/platform/jobs", headers=bearer(token)).status_code == 200
    monkeypatch.setenv("APP_PASSWORD", "ny-kode-2026-x")
    assert client.get("/api/platform/jobs", headers=bearer(token)).status_code == 401


def test_token_lifetime_is_configurable_and_clamped(monkeypatch):
    assert access.token_ttl_seconds({}) == 12 * 3600
    assert access.token_ttl_seconds({"ACCESS_TOKEN_TTL_HOURS": "2"}) == 2 * 3600
    assert access.token_ttl_seconds({"ACCESS_TOKEN_TTL_HOURS": "100000"}) == 24 * 7 * 3600
    assert access.token_ttl_seconds({"ACCESS_TOKEN_TTL_HOURS": "0"}) == 3600
    assert access.token_ttl_seconds({"ACCESS_TOKEN_TTL_HOURS": "abc"}) == 12 * 3600


def test_verify_token_rejects_malformed_input():
    for value in ("", "sv1", "sv1_1_2", "x" * 200, "sv1_99999999999999_" + "a" * 64, "sv2_9999999999_" + "a" * 64):
        assert verify_token(value, CODE) is False
    token, _ = issue_token(CODE)
    assert verify_token(token, CODE) is True
    assert verify_token(token, "") is False


# --- status --------------------------------------------------------------


def test_status_reflects_whether_the_browser_is_signed_in(client):
    assert client.get("/api/platform/access/status").json() == {
        "required": True,
        "authenticated": False,
        "configured": True,
    }
    token = login(client).json()["token"]
    signed_in = client.get("/api/platform/access/status", headers=bearer(token)).json()
    assert signed_in["authenticated"] is True
    stale = client.get("/api/platform/access/status", headers=bearer("sv1_1_" + "0" * 64)).json()
    assert stale["authenticated"] is False


# --- brute force ---------------------------------------------------------


def test_login_rejects_a_wrong_code_without_revealing_anything(client):
    response = login(client, "gjetting")
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_access_code"
    assert "token" not in response.json()


def test_repeated_failures_are_throttled_even_for_the_right_code(client):
    for _ in range(8):
        assert login(client, "feil").status_code == 401
    blocked = login(client, CODE)
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "too_many_attempts"
    assert int(blocked.headers["retry-after"]) >= 1


def test_throttle_window_expires_and_a_global_ceiling_holds():
    throttle = LoginThrottle(per_client=2, overall=3, window_seconds=10)
    throttle.record_failure("a", now=0)
    throttle.record_failure("a", now=1)
    assert throttle.retry_after("a", now=2) > 0
    assert throttle.retry_after("b", now=2) == 0
    assert throttle.retry_after("a", now=12) == 0

    throttle = LoginThrottle(per_client=5, overall=3, window_seconds=10)
    for client_name in ("a", "b", "c"):
        throttle.record_failure(client_name, now=0)
    assert throttle.retry_after("someone-new", now=1) > 0
    assert throttle.retry_after("someone-new", now=11) == 0


def test_throttle_forgets_old_clients_so_memory_stays_bounded():
    throttle = LoginThrottle(per_client=2, overall=10_000, window_seconds=10, max_clients=5)
    for index in range(50):
        throttle.record_failure(f"spoofed-{index}", now=0)
    assert len(throttle._clients) <= 5


# --- browser behaviour ---------------------------------------------------


def test_preflight_is_answered_without_credentials(client):
    response = client.options(
        "/api/platform/jobs",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ORIGIN


def test_rejections_carry_cors_headers_so_the_browser_can_read_the_401(client):
    response = client.get("/api/platform/jobs", headers={"Origin": ORIGIN})
    assert response.status_code == 401
    assert response.headers["access-control-allow-origin"] == ORIGIN


# --- the Norsk module ----------------------------------------------------


def test_norsk_trusts_the_gate_and_does_not_ask_for_the_code_again(client):
    token = login(client).json()["token"]
    assert client.get("/api/norsk/auth/config", headers=bearer(token)).json() == {"password_required": False}
    assert client.get("/api/norsk/generation-status/abc", headers=bearer(token)).status_code == 200


def test_norsk_keeps_checking_the_password_when_run_standalone(monkeypatch):
    """Without the platform gate the module's own password check still applies."""
    standalone = FastAPI()

    @standalone.get("/generation-status/{generation_id}")
    async def status(generation_id: str, _auth: None = Depends(require_app_password)):
        return {"id": generation_id}

    client = TestClient(standalone)
    assert client.get("/generation-status/abc").status_code == 401
    assert client.get("/generation-status/abc", headers=bearer("feil")).status_code == 401
    assert client.get("/generation-status/abc", headers=bearer(CODE)).status_code == 200


# --- wiring --------------------------------------------------------------


def test_entrypoint_orders_cors_outside_the_gate_and_the_gate_outside_telemetry():
    """Later `add_middleware` is outer. A rejected request must never reach the
    job telemetry, and the browser must still be able to read the 401."""
    source = (Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")
    telemetry = source.index("app.add_middleware(JobTelemetryMiddleware)")
    gate = source.index("app.add_middleware(AccessGateMiddleware)")
    cors = source.index("CORSMiddleware,\n    allow_origins")
    assert telemetry < gate < cors
    assert 'app.include_router(access_router, prefix="/api/platform/access")' in source
