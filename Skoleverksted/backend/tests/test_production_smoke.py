"""The production smoke test must prove the access gate, not just availability."""

from __future__ import annotations

import pytest

from scripts import production_smoke as smoke

READY = {
    "status": "ready",
    "runtime": {"latex_engine": "pdflatex"},
    "access_gate": {"enforced": True, "code_configured": True},
}


class FakeServer:
    """Answers like production, with switches for each way it can go wrong."""

    def __init__(self, **overrides):
        self.ready = overrides.get("ready", READY)
        self.anonymous_status = overrides.get("anonymous_status", 401)
        self.login_status = overrides.get("login_status", 200)
        self.authorised_status = overrides.get("authorised_status", 200)
        self.pages_status = overrides.get("pages_status", 200)
        self.calls: list[tuple[str, str]] = []

    def __call__(self, url, *, payload=None, token=""):
        self.calls.append(("POST" if payload is not None else "GET", url + (" [token]" if token else "")))
        if url.endswith("/health/ready"):
            return 200, self.ready
        if url.endswith("/access/login"):
            return self.login_status, ({"token": "sv1_x"} if self.login_status == 200 else {"detail": "no"})
        if "/api/" in url:
            return (self.authorised_status if token else self.anonymous_status), {}
        return self.pages_status, ""


def test_a_healthy_gated_deployment_passes():
    assert smoke.run_once(FakeServer()) == []


@pytest.mark.parametrize("status", [200, 404, 500, 0])
def test_an_open_or_broken_api_fails_the_smoke_test(status):
    errors = smoke.run_once(FakeServer(anonymous_status=status))
    assert any("without an access code" in error for error in errors)
    assert len(errors) == 3  # platform, Fag and the mathematics proxy are each checked


def test_a_backend_that_lost_its_gate_fails_even_if_everything_else_is_fine():
    ungated = {**READY, "access_gate": {"enforced": False, "code_configured": False}}
    assert any("access gate is not enforced" in error for error in smoke.run_once(FakeServer(ready=ungated)))

    old_release = {key: value for key, value in READY.items() if key != "access_gate"}
    assert any("access gate is not enforced" in error for error in smoke.run_once(FakeServer(ready=old_release)))


def test_missing_frontend_pages_are_reported():
    assert any("frontend /personvern" in error for error in smoke.run_once(FakeServer(pages_status=502)))


def test_signed_in_path_signs_in_once_and_checks_both_entrances():
    server = FakeServer()
    assert smoke.run_authorised("kode", server) == []
    assert [call for call in server.calls if "/access/login" in call[1]] == [("POST", f"{smoke.BACKEND}/api/platform/access/login")]
    assert sum("[token]" in call[1] for call in server.calls) == 2


def test_signed_in_path_reports_a_rejected_code_and_a_blocked_token():
    assert any("access login" in error for error in smoke.run_authorised("kode", FakeServer(login_status=401)))
    assert any("valid token" in error for error in smoke.run_authorised("kode", FakeServer(authorised_status=403)))


def test_main_passes_without_a_code_but_says_the_signed_in_path_was_skipped(capsys):
    assert smoke.main(FakeServer(), attempts=1, delay=0, code="") == 0
    assert "SMOKE_ACCESS_CODE is not set" in capsys.readouterr().out


def test_main_never_retries_a_rejected_code(monkeypatch):
    """A stale CI secret must not hammer the throttled login and lock teachers out."""
    server = FakeServer(login_status=401)
    monkeypatch.setattr(smoke.time, "sleep", lambda _: None)

    assert smoke.main(server, attempts=1, delay=0, code="stale") == 1
    logins = [call for call in server.calls if "/access/login" in call[1]]
    assert len(logins) == 1


def test_main_retries_availability_until_the_new_release_is_live(monkeypatch):
    states = iter([FakeServer(anonymous_status=200), FakeServer(anonymous_status=200), FakeServer()])
    current = {"server": next(states)}

    def call(url, **kwargs):
        return current["server"](url, **kwargs)

    def advance(_):
        current["server"] = next(states)

    monkeypatch.setattr(smoke.time, "sleep", advance)
    assert smoke.main(call, attempts=5, delay=0, code="") == 0


def test_main_fails_after_all_retries_when_the_api_stays_open(monkeypatch):
    monkeypatch.setattr(smoke.time, "sleep", lambda _: None)
    assert smoke.main(FakeServer(anonymous_status=200), attempts=3, delay=0, code="") == 1


def test_unreachable_server_is_reported_not_raised(monkeypatch):
    def refuse(*_args, **_kwargs):
        raise OSError("network down")

    monkeypatch.setattr(smoke.urllib.request, "urlopen", refuse)
    status, body = smoke.request("http://127.0.0.1:9/health")
    assert status == 0 and "network down" in body
