from __future__ import annotations

import os


DEFAULT_PRODUCTION_FRONTEND_ORIGIN = "https://skoleverksted-3npg.vercel.app"


def allowed_origins() -> list[str]:
    """Return explicit browser origins for local and hosted frontends."""
    raw = os.getenv("ALLOWED_ORIGINS") or os.getenv("FRONTEND_URL") or "http://localhost:3000"
    origins = [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]

    if os.getenv("ENVIRONMENT", "development").strip().lower() == "production":
        production_origin = os.getenv(
            "SKOLEVERKSTED_PUBLIC_FRONTEND_URL",
            DEFAULT_PRODUCTION_FRONTEND_ORIGIN,
        ).strip().rstrip("/")
        if production_origin and production_origin not in origins:
            origins.append(production_origin)

    return origins
