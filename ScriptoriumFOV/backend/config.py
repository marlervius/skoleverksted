"""
Centralised runtime configuration for Scriptorium backend.

All environment variables and tuneable constants live here so they
can be imported instead of being scattered across modules.
"""

from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# AI / Gemini
# ---------------------------------------------------------------------------

GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_MODEL: str = os.getenv("GOOGLE_MODEL", "gemini-3.5-flash")

# ---------------------------------------------------------------------------
# Lesson generation cache
# ---------------------------------------------------------------------------

CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", str(3600 * 24)))  # 24 h

# ---------------------------------------------------------------------------
# Image processing
# ---------------------------------------------------------------------------

IMAGE_DOWNLOAD_TIMEOUT_SECONDS: int = int(os.getenv("IMAGE_DOWNLOAD_TIMEOUT", "30"))
IMAGE_MAX_DIMENSION: int = int(os.getenv("IMAGE_MAX_DIMENSION", "800"))
IMAGE_JPEG_QUALITY: int = int(os.getenv("IMAGE_JPEG_QUALITY", "85"))

# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

RATE_LIMIT_PER_MINUTE: str = os.getenv("RATE_LIMIT_PER_MINUTE", "5/minute")

# ---------------------------------------------------------------------------
# PDF / Typst
# ---------------------------------------------------------------------------

TYPST_COMPILE_TIMEOUT_SECONDS: int = int(os.getenv("TYPST_COMPILE_TIMEOUT", "60"))

# ---------------------------------------------------------------------------
# File upload
# ---------------------------------------------------------------------------

MAX_IMAGE_BYTES: int = 5 * 1024 * 1024  # 5 MB
ALLOWED_IMAGE_TYPES: frozenset[str] = frozenset(
    {"image/jpeg", "image/png", "image/webp"}
)

# ---------------------------------------------------------------------------
# Thread pool (parallel PDF generation)
# ---------------------------------------------------------------------------

PDF_THREAD_POOL_WORKERS: int = int(os.getenv("PDF_THREAD_POOL_WORKERS", "4"))

# ---------------------------------------------------------------------------
# Progress / Redis
# ---------------------------------------------------------------------------

REDIS_URL: str | None = os.getenv("REDIS_URL")
PROGRESS_TTL_SECONDS: int = int(os.getenv("PROGRESS_TTL_SECONDS", str(3600 * 2)))  # 2 h

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

APP_PASSWORD: str | None = os.getenv("APP_PASSWORD") or None
