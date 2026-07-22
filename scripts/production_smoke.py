"""Post-deploy smoke tests for the complete public Skoleverksted path.

The protected mathematics estimate call deliberately goes through Vercel. It
therefore verifies both deployments, the shared server-side secret and Render's
mounted mathematics app without exposing the secret to CI.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request


FRONTEND = os.getenv("SMOKE_FRONTEND_URL", "https://skoleverksted.vercel.app").rstrip("/")
BACKEND = os.getenv("SMOKE_BACKEND_URL", "https://skoleverksted-api.onrender.com").rstrip("/")
ATTEMPTS = int(os.getenv("SMOKE_ATTEMPTS", "24"))
DELAY_SECONDS = float(os.getenv("SMOKE_DELAY_SECONDS", "10"))


def request(url: str, *, payload: dict | None = None) -> tuple[int, dict | str]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "skoleverksted-smoke/1.0"},
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
        raw = exc.read().decode("utf-8", errors="replace")
        return exc.code, raw[:300]


def run_once() -> list[str]:
    errors: list[str] = []
    status, ready = request(f"{BACKEND}/health/ready")
    if status != 200 or not isinstance(ready, dict) or ready.get("status") != "ready":
        errors.append(f"backend readiness: HTTP {status} {ready}")

    for path in ("/", "/fag", "/norsk", "/matematikk"):
        page_status, _ = request(f"{FRONTEND}{path}")
        if page_status != 200:
            errors.append(f"frontend {path}: HTTP {page_status}")

    estimate = {
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
    auth_status, auth_body = request(f"{FRONTEND}/api/backend/estimate", payload=estimate)
    if auth_status != 200:
        errors.append(f"protected mathematics proxy: HTTP {auth_status} {auth_body}")
    return errors


def main() -> int:
    last_errors: list[str] = []
    for attempt in range(1, ATTEMPTS + 1):
        last_errors = run_once()
        if not last_errors:
            print(f"Production smoke passed on attempt {attempt}.")
            return 0
        print(f"Attempt {attempt}/{ATTEMPTS} failed: {'; '.join(last_errors)}")
        if attempt < ATTEMPTS:
            time.sleep(DELAY_SECONDS)
    print("Production smoke failed after all retries.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
