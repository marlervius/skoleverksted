"""Post-deploy smoke tests for the complete public Skoleverksted path.

Besides availability the smoke test proves that the pilot's access gate is on:
anonymous callers must be refused by the backend and by the Vercel mathematics
proxy. With ``SMOKE_ACCESS_CODE`` set it also signs in once and checks that an
authorised caller gets through, which exercises both deployments, the shared
server-side secret and Render's mounted mathematics app.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable


FRONTEND = os.getenv("SMOKE_FRONTEND_URL", "https://skoleverksted.vercel.app").rstrip("/")
BACKEND = os.getenv("SMOKE_BACKEND_URL", "https://skoleverksted-api.onrender.com").rstrip("/")
# A Render rebuild after a merge takes several minutes; keep trying that long.
ATTEMPTS = int(os.getenv("SMOKE_ATTEMPTS", "48"))
DELAY_SECONDS = float(os.getenv("SMOKE_DELAY_SECONDS", "10"))

Call = Callable[..., "tuple[int, dict | str]"]

ESTIMATE = {
    "grade": "10. trinn",
    "topic": "brøk",
    "material_type": "arbeidsark",
    "language_level": "standard",
    "num_exercises": 2,
    "difficulty": "Middels",
    "include_theory": True,
    "include_examples": True,
    "include_exercises": True,
    "include_solutions": True,
    "include_graphs": False,
    "competency_goals": [],
    "extra_instructions": "",
}


def request(url: str, *, payload: dict | None = None, token: str = "") -> tuple[int, dict | str]:
    """Return ``(status, body)``; status 0 means the server could not be reached."""
    headers = {"Content-Type": "application/json", "User-Agent": "skoleverksted-smoke/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers=headers,
        method="POST" if payload is not None else "GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8", errors="replace")
            try:
                body: dict | str = json.loads(raw)
            except json.JSONDecodeError:
                body = raw[:300]
            return response.status, body
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")[:300]
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return 0, f"{type(exc).__name__}: {exc}"


def run_once(call: Call = request) -> list[str]:
    """Availability plus the checks that need no credentials."""
    errors: list[str] = []
    status, ready = call(f"{BACKEND}/health/ready")
    if status != 200 or not isinstance(ready, dict) or ready.get("status") != "ready":
        errors.append(f"backend readiness: HTTP {status} {ready}")
    else:
        if ready.get("runtime", {}).get("latex_engine") != "pdflatex":
            errors.append(
                "backend readiness: mathematics PDF engine is not the "
                "memory-safe production engine (expected pdflatex)"
            )
        gate = ready.get("access_gate")
        if not (isinstance(gate, dict) and gate.get("enforced") and gate.get("code_configured")):
            errors.append(f"backend readiness: access gate is not enforced ({gate!r})")

    for path in ("/", "/fag", "/norsk", "/matematikk", "/personvern"):
        page_status, _ = call(f"{FRONTEND}{path}")
        if page_status != 200:
            errors.append(f"frontend {path}: HTTP {page_status}")

    # Anonymous callers must be refused, never served and never a 5xx.
    for label, url, payload in (
        ("platform API", f"{BACKEND}/api/platform/jobs", None),
        ("Fag API", f"{BACKEND}/api/fag/health", None),
        ("mathematics proxy", f"{FRONTEND}/api/backend/estimate", ESTIMATE),
    ):
        refused, _ = call(url, payload=payload)
        if refused != 401:
            errors.append(f"{label} answered HTTP {refused} without an access code (expected 401)")
    return errors


def run_authorised(code: str, call: Call = request) -> list[str]:
    """Sign in once, then check the paths an authorised teacher uses.

    The login is deliberately never repeated after a 401/429: a stale CI secret
    must not hammer the throttled endpoint and lock every teacher out.
    """
    status, body = call(f"{BACKEND}/api/platform/access/login", payload={"code": code})
    token = body.get("token") if status == 200 and isinstance(body, dict) else None
    if not isinstance(token, str) or not token:
        return [f"access login with SMOKE_ACCESS_CODE: HTTP {status} {body}"]

    errors: list[str] = []
    for label, url, payload in (
        ("platform API", f"{BACKEND}/api/platform/jobs", None),
        ("protected mathematics proxy", f"{FRONTEND}/api/backend/estimate", ESTIMATE),
    ):
        got, detail = call(url, payload=payload, token=token)
        if got != 200:
            errors.append(f"{label} with a valid token: HTTP {got} {detail}")
    return errors


def main(
    call: Call = request,
    *,
    attempts: int = ATTEMPTS,
    delay: float = DELAY_SECONDS,
    code: str | None = None,
) -> int:
    code = os.getenv("SMOKE_ACCESS_CODE", "").strip() if code is None else code.strip()
    last_errors: list[str] = []
    for attempt in range(1, attempts + 1):
        last_errors = run_once(call)
        if not last_errors:
            print(f"Production smoke passed on attempt {attempt}.")
            break
        print(f"Attempt {attempt}/{attempts} failed: {'; '.join(last_errors)}")
        if attempt < attempts:
            time.sleep(delay)
    else:
        print("Production smoke failed after all retries.", file=sys.stderr)
        return 1

    if not code:
        print("NOTICE: SMOKE_ACCESS_CODE is not set, so the signed-in path was not exercised.")
        return 0

    for attempt in range(1, 4):
        errors = run_authorised(code, call)
        if not errors:
            print("Authorised smoke passed.")
            return 0
        print(f"Authorised attempt {attempt}/3 failed: {'; '.join(errors)}")
        # A rejected code is final; only transient server trouble is worth another try.
        if any("access login" in error and ("HTTP 401" in error or "HTTP 429" in error) for error in errors):
            break
        time.sleep(delay)
    print("Authorised smoke failed.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
