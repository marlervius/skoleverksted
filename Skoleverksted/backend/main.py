"""One FastAPI entrypoint for all three Skoleverksted workspaces.

The domain apps remain isolated behind stable prefixes. This prevents route,
job-store and model collisions while still giving deployment, CORS, health
checks and documentation one public backend address.
"""

from __future__ import annotations

import os
import sys
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .platform.router import router as platform_router
from .platform.store import get_platform_store
from .platform.telemetry import JobTelemetryMiddleware


REPO_ROOT = Path(__file__).resolve().parents[2]
MATE_BACKEND = REPO_ROOT / "MateMaTeX" / "backend"
if str(MATE_BACKEND) not in sys.path:
    sys.path.insert(0, str(MATE_BACKEND))

from VGS_KI.backend.main import app as fag_app  # noqa: E402
from ScriptoriumFOV.backend.main import app as norsk_app  # noqa: E402
from app.main import app as matematikk_app  # noqa: E402


DOMAIN_APPS = (fag_app, norsk_app, matematikk_app)


def _allowed_origins() -> list[str]:
    raw = os.getenv("ALLOWED_ORIGINS") or os.getenv("FRONTEND_URL") or "http://localhost:3000"
    return [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Run startup and shutdown hooks belonging to every mounted app."""
    async with AsyncExitStack() as stack:
        for domain_app in DOMAIN_APPS:
            await stack.enter_async_context(domain_app.router.lifespan_context(domain_app))
        yield


app = FastAPI(
    title="Skoleverksted API",
    description="Felles API-inngang for fagmateriell, norskopplæring og matematikk.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(JobTelemetryMiddleware)
app.include_router(platform_router, prefix="/api/platform")


@app.get("/", tags=["platform"])
async def platform_info() -> dict:
    return {
        "name": "Skoleverksted",
        "status": "ok",
        "modules": {
            "fag": "/api/fag/docs",
            "norsk": "/api/norsk/docs",
            "matematikk": "/api/matematikk/docs",
        },
    }


@app.get("/health", tags=["platform"])
async def health() -> dict:
    store_health = get_platform_store().health()
    return {
        "status": "healthy",
        "modules": {
            "fag": "loaded",
            "norsk": "loaded",
            "matematikk": "loaded",
        },
        "storage": store_health,
    }


@app.get("/health/ready", tags=["platform"])
async def readiness() -> dict:
    """Readiness details without performing slow external provider calls."""
    return {
        "status": "ready",
        "storage": get_platform_store().health(),
        "ai_provider_configured": bool(os.getenv("GOOGLE_API_KEY") or os.getenv("OPENAI_API_KEY")),
        "redis_configured": bool(os.getenv("REDIS_URL")),
        "pdf_engines": {
            "typst": bool(os.getenv("TYPST_PATH")) or "PATH",
            "pdflatex": bool(os.getenv("PDFLATEX_PATH")) or "PATH",
        },
    }


app.mount("/api/fag", fag_app, name="fag")
app.mount("/api/norsk", norsk_app, name="norsk")
app.mount("/api/matematikk", matematikk_app, name="matematikk")
