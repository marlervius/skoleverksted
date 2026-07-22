from __future__ import annotations

import os
import shutil
import hashlib
from collections.abc import Callable, Mapping
from typing import Any


WhichCommand = Callable[[str], str | None]


def build_readiness(
    storage: Mapping[str, Any],
    *,
    environ: Mapping[str, str] | None = None,
    which: WhichCommand = shutil.which,
) -> tuple[bool, dict[str, Any]]:
    """Build a production-readiness report without exposing secret values."""
    env = os.environ if environ is None else environ
    typst_command = env.get("TYPST_PATH", "typst").strip() or "typst"
    pdflatex_command = env.get("PDFLATEX_PATH", "pdflatex").strip() or "pdflatex"

    checks = {
        "storage": storage.get("status") == "healthy",
        # Fag and Norsk currently depend on Gemini, so another provider alone
        # is not enough for the complete superapp to be ready.
        "google_ai": bool(env.get("GOOGLE_API_KEY", "").strip()),
        # Both are server-side secrets. Presence is reported, never the value.
        "matematikk_access": bool(env.get("MATE_API_KEY", "").strip()),
        "norsk_access": bool(env.get("APP_PASSWORD", "").strip()),
        "typst": bool(which(typst_command)),
        "pdflatex": bool(which(pdflatex_command)),
    }
    missing = [name for name, available in checks.items() if not available]
    ready = not missing

    release = (
        env.get("RENDER_GIT_COMMIT", "").strip()
        or env.get("VERCEL_GIT_COMMIT_SHA", "").strip()
        or env.get("COMMIT_SHA", "").strip()
        or "unknown"
    )
    prompt_version = env.get("PROMPT_VERSION", "unknown").strip() or "unknown"
    google_model = env.get("GOOGLE_MODEL", "unknown").strip() or "unknown"
    image_model = env.get("GOOGLE_IMAGE_MODEL", "unknown").strip() or "unknown"
    config_fingerprint = hashlib.sha256(
        f"{prompt_version}|{google_model}|{image_model}".encode("utf-8")
    ).hexdigest()[:12]

    return ready, {
        "status": "ready" if ready else "degraded",
        "checks": checks,
        "missing": missing,
        "storage": dict(storage),
        "redis_configured": bool(env.get("REDIS_URL", "").strip()),
        "release": release[:12],
        "runtime": {
            "environment": env.get("ENVIRONMENT", "development"),
            "prompt_version": prompt_version,
            "google_model": google_model,
            "image_model": image_model,
            "config_fingerprint": config_fingerprint,
        },
    }
