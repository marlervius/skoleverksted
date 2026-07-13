"""Centralised configuration for the VGS-Lærerassistent backend.

All tunable knobs live here so they can be adjusted via environment variables
without grepping through the codebase.
"""
import os
from typing import List


def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_list(key: str, default: List[str]) -> List[str]:
    raw = os.getenv(key, "")
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return parts or default


# ── Timeouts ─────────────────────────────────────────────────────────────────
AGENT_TIMEOUT_SECONDS: int = _env_int("AGENT_TIMEOUT_SECONDS", 300)
SSE_HEARTBEAT_SECONDS: int = _env_int("SSE_HEARTBEAT_SECONDS", 30)

# ── Cache ────────────────────────────────────────────────────────────────────
CACHE_TTL_SECONDS: int = _env_int("CACHE_TTL_SECONDS", 86400 * 7)  # 7 days
GREP_CACHE_TTL_SECONDS: int = _env_int("GREP_CACHE_TTL_SECONDS", 60 * 60 * 12)  # 12h

# ── Job store ────────────────────────────────────────────────────────────────
# Jobs older than this are removed by the periodic cleanup task.
JOB_TTL_SECONDS: int = _env_int("JOB_TTL_SECONDS", 60 * 60)  # 1 hour
JOB_CLEANUP_INTERVAL_SECONDS: int = _env_int("JOB_CLEANUP_INTERVAL_SECONDS", 5 * 60)

# ── Limits ───────────────────────────────────────────────────────────────────
MAX_IMAGE_BASE64_BYTES: int = _env_int("MAX_IMAGE_BASE64_BYTES", 7 * 1024 * 1024)
MAX_IMAGE_WIDTH_PX: int = _env_int("MAX_IMAGE_WIDTH_PX", 1200)

# ── CORS ─────────────────────────────────────────────────────────────────────
# Defaults to localhost:3000 for dev. Production MUST set ALLOWED_ORIGINS
# explicitly. We never default to ['*'] — that's a deliberate security choice.
#
# Two ways to add a production frontend URL:
#   ALLOWED_ORIGINS=https://your-app.vercel.app          (comma-separated list)
#   FRONTEND_URL=https://your-app.vercel.app              (single URL shorthand)
#   ALLOWED_ORIGIN_REGEX=https://your-app.*\.vercel\.app  (regex for previews)
ALLOWED_ORIGINS: List[str] = _env_list("ALLOWED_ORIGINS", ["http://localhost:3000"])

# Append FRONTEND_URL if set and not already present
_frontend_url = os.getenv("FRONTEND_URL", "").strip().rstrip("/")
if _frontend_url and _frontend_url not in ALLOWED_ORIGINS:
    ALLOWED_ORIGINS = [*ALLOWED_ORIGINS, _frontend_url]

# Optional regex pattern for dynamic origins (e.g. Vercel preview deployments)
ALLOWED_ORIGIN_REGEX: str = os.getenv("ALLOWED_ORIGIN_REGEX", "")

# ── Rate limiting ────────────────────────────────────────────────────────────
RATE_LIMIT_GENERATE: str = os.getenv("RATE_LIMIT_GENERATE", "5/minute")
RATE_LIMIT_GREP: str = os.getenv("RATE_LIMIT_GREP", "30/minute")

# ── Parallelism ──────────────────────────────────────────────────────────────
# How many independent dependent-tasks can run in parallel after the main
# fagtekst has been generated (worksheet, language exercises, faktarapport, etc.)
MAX_PARALLEL_AGENT_TASKS: int = _env_int("MAX_PARALLEL_AGENT_TASKS", 5)
