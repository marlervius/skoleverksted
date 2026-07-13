from __future__ import annotations

import os
import shutil
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
        "typst": bool(which(typst_command)),
        "pdflatex": bool(which(pdflatex_command)),
    }
    missing = [name for name, available in checks.items() if not available]
    ready = not missing

    return ready, {
        "status": "ready" if ready else "degraded",
        "checks": checks,
        "missing": missing,
        "storage": dict(storage),
        "redis_configured": bool(env.get("REDIS_URL", "").strip()),
    }
