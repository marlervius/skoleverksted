from __future__ import annotations

import os


DEFAULT_PRODUCTION_FRONTEND_ORIGINS = (
    "https://skoleverksted.vercel.app",
    "https://skoleverksted-3npg.vercel.app",
)


def allowed_origins() -> list[str]:
    """Return explicit browser origins for local and hosted frontends."""
    raw = os.getenv("ALLOWED_ORIGINS") or os.getenv("FRONTEND_URL") or "http://localhost:3000"
    origins = [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]

    if os.getenv("ENVIRONMENT", "development").strip().lower() == "production":
        production_origins = [
            origin.strip().rstrip("/")
            for origin in os.getenv("SKOLEVERKSTED_PUBLIC_FRONTEND_URL", "").split(",")
            if origin.strip()
        ]
        for production_origin in (*DEFAULT_PRODUCTION_FRONTEND_ORIGINS, *production_origins):
            if production_origin and production_origin not in origins:
                origins.append(production_origin)

    return origins
