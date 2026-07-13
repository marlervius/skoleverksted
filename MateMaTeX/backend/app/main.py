"""
MateMaTeX 2.0 — FastAPI backend entry point.

Exposes:
- POST /generate              — Start a generation job
- GET  /generate/{id}/stream  — SSE stream of agent progress
- GET  /generate/{id}/result  — Get the final result
- POST /compile               — Compile LaTeX to PDF
- /exercises/*                — Exercise bank (CRUD, search, export)
- /editor/*                   — Interactive LaTeX editor (compile, AI actions)
- /differentiation/*          — Multi-level differentiation
- /export/*                   — PDF/Word/PowerPoint/QR export
- /sharing/*                  — Shareable links
- /school/*, /generations/*   — Collaboration (comments, versions, school bank)
"""

import asyncio
import base64
import json
import os
import re
import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Optional

import structlog
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel, Field
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.auth import get_current_user, require_stream_access
from app.config import get_config, get_settings
from app.job_store import cleanup_old_snapshots, evict_terminal_jobs, get_job_memory, persist_terminal_job, resolve_job
from app.pipeline.cancel import cancel_job, clear_cancel
from app.logging_config import configure_logging
from app.models.state import GenerationRequest, PipelineState, PipelineStatus
from app.rate_limit import limiter

configure_logging()
logger = structlog.get_logger()
settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.database_url:
        try:
            from app.db import get_pool
            await get_pool()
            logger.info("startup_complete", environment=settings.environment)
        except Exception as e:
            err_msg = str(e)
            logger.error("startup_database_failed", error=err_msg)
            raw = settings.database_url or ""
            if "pooler.supabase.com" in raw and ":6543" in raw:
                logger.error(
                    "database_supabase_transaction_pooler",
                    msg=(
                        "DATABASE_URL bruker Supabase transaction pooler (:6543). "
                        "Bytt til Direct URI eller fjern DATABASE_URL."
                    ),
                )
            logger.warning("startup_continuing_without_db", msg="DB features unavailable")
    else:
        logger.warning("startup_no_database", msg="DATABASE_URL not set — running without DB")

    # Do NOT hard-crash the process on missing auth config: a raise here means
    # uvicorn never binds the port, so the platform (Render) reports "no open
    # ports detected" and the deploy times out with an opaque error. The auth
    # layer already fails closed at request time (503 when no key is configured
    # in production), so we only warn loudly here and let the service boot.
    if settings.environment == "production" and not (
        settings.mate_api_key or settings.supabase_jwt_secret
    ):
        logger.critical(
            "startup_no_auth_configured",
            msg=(
                "Running in production without MATE_API_KEY or SUPABASE_JWT_SECRET. "
                "Protected endpoints will reject all requests with 503 until one is set."
            ),
        )

    cleanup_old_snapshots(max_age_days=7)
    evict_terminal_jobs(get_job_memory())
    from app.stores import collaboration_store, exercise_store
    from app.stores import sharing_store
    exercise_store._ensure_loaded()
    collaboration_store._ensure_loaded()
    sharing_store._ensure_loaded()
    yield

    _executor.shutdown(wait=False, cancel_futures=True)

    # The Postgres pool only exists when a DATABASE_URL was configured, and the
    # asyncpg driver is an optional dependency — never fail shutdown over it.
    if settings.database_url:
        try:
            from app.db import close_pool
            await close_pool()
        except ModuleNotFoundError:
            logger.warning("shutdown_db_driver_missing", msg="asyncpg not installed")
    logger.info("shutdown_complete")


app = FastAPI(
    title="MateMaTeX 2.0 API",
    version="2.0.0",
    description="AI-powered math education content generator for Norwegian schools",
    docs_url="/docs" if settings.environment == "development" else None,
    redoc_url="/redoc" if settings.environment == "development" else None,
    lifespan=lifespan,
    openapi_tags=[
        {"name": "generation", "description": "AI content generation pipeline"},
        {"name": "exercises", "description": "Exercise bank — CRUD, search, export"},
        {"name": "editor", "description": "Interactive LaTeX editor — compile, AI actions"},
        {"name": "differentiation", "description": "Multi-level differentiation and hints"},
        {"name": "export", "description": "PDF, Word, PowerPoint, QR export"},
        {"name": "sharing", "description": "Shareable links with password/expiry"},
        {"name": "collaboration", "description": "School bank, comments, version history"},
    ],
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ---------------------------------------------------------------------------
# CORS — restrict in production
# ---------------------------------------------------------------------------
allowed_origins = [settings.frontend_url]
if settings.environment == "development":
    allowed_origins.append("http://localhost:3000")

# Vercel preview URLs share the production project slug prefix only
# e.g. https://mate-ma-tex-abc123-user.vercel.app when FRONTEND_URL is mate-ma-tex.vercel.app
_vercel_origin_regex: str | None = None
_frontend = (settings.frontend_url or "").rstrip("/")
if ".vercel.app" in _frontend:
    _slug_match = re.match(r"https://([a-zA-Z0-9-]+)", _frontend)
    if _slug_match:
        _slug = re.escape(_slug_match.group(1))
        _vercel_origin_regex = rf"https://{_slug}.*\.vercel\.app"

logger.info("cors_origins", origins=allowed_origins, vercel_regex=_vercel_origin_regex)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=_vercel_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Mount sub-routers (Fase 2 modules)
# ---------------------------------------------------------------------------
from app.exercises.router import router as exercises_router
from app.editor.compiler import router as editor_compile_router
from app.editor.ai_actions import router as editor_ai_router
from app.differentiation.generator import router as diff_router
from app.differentiation.hint_engine import router as hint_router
from app.export.router import router as export_router
from app.export.qr import router as qr_router
from app.sharing.router import router as sharing_router
from app.collaboration.router import router as collab_router
from app.m1.router import router as m1_router

app.include_router(exercises_router)
app.include_router(editor_compile_router)
app.include_router(editor_ai_router)
app.include_router(diff_router)
app.include_router(hint_router)
app.include_router(export_router)
app.include_router(qr_router)
app.include_router(sharing_router)
app.include_router(collab_router)
app.include_router(m1_router)

_jobs = get_job_memory()
_executor = ThreadPoolExecutor(max_workers=get_settings().max_concurrent_jobs)
_ABORT_MESSAGE = "Avbrutt av bruker"
_MAX_STREAM_SECONDS = 3600  # 1 hour — prevent infinite SSE if job stalls


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class GenerateResponse(BaseModel):
    job_id: str
    status: str
    message: str
    from_cache: bool = False


class CompileRequest(BaseModel):
    latex_content: str = Field(..., max_length=500_000)
    filename: str = Field(default="document", max_length=64)


class CompileResponse(BaseModel):
    success: bool
    pdf_path: Optional[str] = None
    errors: list[str] = []


class VerifyLatexRequest(BaseModel):
    latex_content: str = Field(..., min_length=1, max_length=500_000)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/", tags=["meta"])
async def root():
    """Root — avoids 404 when someone opens the service URL in a browser."""
    return {
        "service": "MateMaTeX API",
        "version": "2.0.0",
        "health": "/health",
        "hint": "Frontend kaller POST /generate m.m. Se /health for driftstatus.",
    }


@app.head("/")
async def root_head():
    """So HEAD / succeeds (some uptime checks use HEAD)."""
    return Response(status_code=200)


@app.post("/generate", response_model=GenerateResponse)
@limiter.limit("30/minute")
async def start_generation(
    request: Request,
    generation_request: GenerationRequest,
    user_id: str = Depends(get_current_user),
) -> GenerateResponse:
    """Start an asynchronous generation job."""
    from app.pipeline.graph import try_restore_cached_pipeline

    state = PipelineState(
        request=generation_request,
        status=PipelineStatus.PENDING,
        owner_id=user_id,
    )

    # Cache hit: return immediately so the client never depends on SSE for a
    # job that finished in milliseconds (SSE through Vercel/Render often stalls).
    cached = try_restore_cached_pipeline(
        generation_request,
        job_id=state.job_id,
        owner_id=user_id,
        created_at=state.created_at,
    )
    if cached is not None:
        _jobs[state.job_id] = cached
        persist_terminal_job(cached)
        logger.info(
            "generation_cache_hit_sync",
            job_id=state.job_id,
            topic=generation_request.topic,
        )
        return GenerateResponse(
            job_id=state.job_id,
            status=cached.status.value,
            from_cache=True,
            message="Ferdig (hentet fra hurtigbuffer).",
        )

    _jobs[state.job_id] = state

    loop = asyncio.get_event_loop()
    loop.run_in_executor(_executor, _run_job, state.job_id, generation_request, user_id)

    logger.info("generation_started", job_id=state.job_id, topic=generation_request.topic)

    return GenerateResponse(
        job_id=state.job_id,
        status="pending",
        message="Generering startet. Bruk /generate/{id}/stream for fremdrift.",
    )


@app.get("/generate/{job_id}/stream")
async def stream_progress(
    job_id: str,
    user_id: str = Depends(require_stream_access),
) -> StreamingResponse:
    """Stream agent progress via Server-Sent Events."""

    initial_state = resolve_job(job_id, _jobs)
    if initial_state is not None:
        _authorize_job(initial_state, user_id)

    async def event_generator() -> AsyncGenerator[str, None]:
        import time as _time
        last_step_count = 0
        last_heartbeat = _time.monotonic()
        stream_started = _time.monotonic()
        _HEARTBEAT_INTERVAL = 15  # seconds

        while True:
            if _time.monotonic() - stream_started > _MAX_STREAM_SECONDS:
                yield _sse_event("error", {"message": "Stream timeout — job may still be running"})
                break

            state = resolve_job(job_id, _jobs)
            if state is None:
                yield _sse_event("error", {"message": "Job not found"})
                break

            while last_step_count < len(state.steps):
                step = state.steps[last_step_count]
                yield _sse_event("step", {
                    "agent": step.agent.value,
                    "started_at": step.started_at.isoformat(),
                    "completed_at": step.completed_at.isoformat() if step.completed_at else None,
                    "duration_seconds": step.duration_seconds,
                    "output_summary": step.output_summary,
                    "error": step.error,
                    "retries": step.retries,
                })
                last_step_count += 1
                last_heartbeat = _time.monotonic()

            if state.current_agent:
                yield _sse_event("current_agent", {
                    "agent": state.current_agent.value,
                })
                last_heartbeat = _time.monotonic()

            if state.status in (
                PipelineStatus.COMPLETED,
                PipelineStatus.COMPLETED_WITH_WARNINGS,
                PipelineStatus.FAILED,
            ):
                yield _sse_event("complete", {
                    "status": state.status.value,
                    "total_duration": state.total_duration_seconds,
                    "total_steps": len(state.steps),
                    "math_checks": state.math_verification.claims_checked,
                    "math_correct": state.math_verification.claims_correct,
                    "latex_compiled": state.latex_compilation.success,
                    "error": state.error_message,
                })
                break

            # Send SSE comment heartbeat to prevent proxy/Vercel from closing idle connections
            now = _time.monotonic()
            if now - last_heartbeat >= _HEARTBEAT_INTERVAL:
                yield ": heartbeat\n\n"
                last_heartbeat = now

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Disable proxy buffering (nginx/Render) so events flush immediately
            # instead of being held until the connection closes.
            "X-Accel-Buffering": "no",
        },
    )


@app.delete("/generate/{job_id}")
async def abort_generation(job_id: str, user_id: str = Depends(get_current_user)):
    """Cancel a running generation job."""
    state = resolve_job(job_id, _jobs)
    if state is None:
        raise HTTPException(status_code=404, detail="Job not found")
    _authorize_job(state, user_id)

    if state.status == PipelineStatus.RUNNING or state.status == PipelineStatus.PENDING:
        cancel_job(job_id)
        state.status = PipelineStatus.FAILED
        state.error_message = _ABORT_MESSAGE
        _jobs[job_id] = state
        persist_terminal_job(state)
        logger.info("generation_aborted", job_id=job_id, user_id=user_id)
        return {"success": True, "message": "Job cancelled"}
    else:
        return {"success": False, "message": "Job already finished"}

@app.get("/generate/{job_id}/status")
async def get_job_status(job_id: str, user_id: str = Depends(get_current_user)):
    """
    Lightweight job status for client polling.

    Returns a tiny JSON payload so the frontend can detect completion without
    downloading the full LaTeX body on every poll (which stalled some proxies).
    """
    state = resolve_job(job_id, _jobs)
    if state is None:
        logger.warning("job_status_not_found", job_id=job_id)
        raise HTTPException(status_code=404, detail="Job not found")
    _authorize_job(state, user_id)

    if state.status in (PipelineStatus.RUNNING, PipelineStatus.PENDING):
        return {
            "job_id": state.job_id,
            "status": state.status.value,
            "ready": False,
            "latex_compiled": state.latex_compilation.success,
            "total_duration_seconds": state.total_duration_seconds,
            "error": "",
        }

    return {
        "job_id": state.job_id,
        "status": state.status.value,
        "ready": True,
        "latex_compiled": state.latex_compilation.success,
        "total_duration_seconds": state.total_duration_seconds,
        "error": state.error_message,
    }


@app.get("/generate/{job_id}/result")
async def get_result(
    job_id: str,
    include_pdf_base64: bool = False,
    user_id: str = Depends(get_current_user),
):
    """Get the result of a completed generation job."""

    state = resolve_job(job_id, _jobs)
    if state is None:
        raise HTTPException(status_code=404, detail="Job not found")
    _authorize_job(state, user_id)

    if state.status in (PipelineStatus.RUNNING, PipelineStatus.PENDING):
        raise HTTPException(status_code=202, detail="Job still running")

    pdf_available = bool(state.pdf_path) and os.path.isfile(state.pdf_path)
    if not pdf_available and state.pdf_base64:
        pdf_available = True

    return {
        "job_id": state.job_id,
        "status": state.status.value,
        "full_document": state.full_document,
        "pdf_path": state.pdf_path,
        "pdf_available": pdf_available,
        # PDF bytes are large (~300KB+ base64). Clients should use GET
        # /generate/{id}/pdf for preview/download; omit by default so /result
        # stays small and reliable through Vercel's serverless proxy.
        "pdf_base64": state.pdf_base64 if include_pdf_base64 else "",
        "used_latex_fallback": state.used_latex_fallback,
        "from_cache": state.from_cache,
        "differentiated_basic": state.differentiated_basic,
        "differentiated_advanced": state.differentiated_advanced,
        "warning_reason": state.warning_reason,
        "math_verification": state.math_verification.model_dump(),
        "content_quality": state.content_quality.model_dump(),
        "latex_compilation": state.latex_compilation.model_dump(),
        "layout_report": state.layout_report.model_dump(),
        "layout_fix_attempts": state.layout_fix_attempts,
        "steps": [s.model_dump() for s in state.steps],
        "total_duration_seconds": state.total_duration_seconds,
        "total_tokens": state.total_tokens,
        "error": state.error_message,
    }


@app.get("/generate/{job_id}/pdf")
async def get_job_pdf(job_id: str, user_id: str = Depends(get_current_user)):
    """
    Return the compiled PDF for a completed job.

    Uses the cached PDF written by the LaTeX validator. Avoids re-compilation
    for the common case of "show me the PDF I just generated".
    """
    state = resolve_job(job_id, _jobs)
    if state is None:
        raise HTTPException(status_code=404, detail="Job not found")
    _authorize_job(state, user_id)
    if state.status in (PipelineStatus.RUNNING, PipelineStatus.PENDING):
        raise HTTPException(status_code=202, detail="Job still running")

    if state.pdf_base64:
        try:
            pdf_bytes = base64.b64decode(state.pdf_base64)
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={"Cache-Control": "private, max-age=0, must-revalidate"},
            )
        except Exception:
            raise HTTPException(status_code=500, detail="Invalid PDF data")

    if not state.pdf_path or not os.path.isfile(state.pdf_path):
        # Fall back to compiling the stored full_document on demand.
        if state.full_document:
            from app.latex.compiler import compile_to_pdf
            config = get_config()
            output_dir = Path(settings.output_dir) / "pipeline_pdfs"
            output_dir.mkdir(parents=True, exist_ok=True)
            target = output_dir / f"{state.job_id}.pdf"
            pdf_path = await asyncio.to_thread(
                compile_to_pdf,
                latex_content=state.full_document,
                output_path=str(target),
                pdflatex_path=config.pdflatex_path,
            )
            if pdf_path and os.path.isfile(pdf_path):
                state.pdf_path = pdf_path
                persist_terminal_job(state)
            else:
                raise HTTPException(
                    status_code=410,
                    detail="PDF could not be regenerated from stored LaTeX",
                )
        else:
            raise HTTPException(
                status_code=404,
                detail="No PDF or LaTeX available for this job",
            )

    return FileResponse(
        state.pdf_path,
        media_type="application/pdf",
        filename=f"matematex_{job_id[:8]}.pdf",
        headers={"Cache-Control": "private, max-age=0, must-revalidate"},
    )


@app.post("/verify-latex")
@limiter.limit("30/minute")
async def verify_latex(
    request: Request,
    body: VerifyLatexRequest,
    user_id: str = Depends(get_current_user),
):
    """Re-run the deterministic fasit check after manual or AI editing."""
    from app.verification.math_checker import MathChecker

    result = await asyncio.to_thread(MathChecker().verify, body.latex_content)
    return result.model_dump()


@app.post("/compile", response_model=CompileResponse)
@limiter.limit("20/minute")
async def compile_latex(
    request: Request,
    body: CompileRequest,
    user_id: str = Depends(get_current_user),
) -> CompileResponse:
    """Compile LaTeX content to PDF."""
    from app.latex.compiler import compile_to_pdf
    from app.latex.preamble import wrap_with_preamble

    content = body.latex_content
    if r"\documentclass" not in content:
        content = wrap_with_preamble(content)

    config = get_config()
    safe_name = _safe_filename(body.filename)
    out_dir = Path(config.output_dir) / "compile_cache"
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = await asyncio.to_thread(
        compile_to_pdf,
        latex_content=content,
        output_path=str(out_dir / f"{uuid.uuid4().hex}.pdf"),
        pdflatex_path=config.pdflatex_path,
    )

    if pdf_path:
        return CompileResponse(success=True, pdf_path=pdf_path)
    else:
        return CompileResponse(success=False, errors=["Compilation failed"])


@app.post("/estimate")
async def estimate_cost(request: GenerationRequest, user_id: str = Depends(get_current_user)):
    """Estimate token cost BEFORE generation."""
    from app.cache import get_cache
    cache = get_cache()
    tokens = cache.estimate_tokens(request)
    similar = cache.find_similar(request)

    return {
        **tokens,
        "similar_cached": len(similar),
        "cache_available": len(similar) > 0,
    }


@app.get("/cache/stats")
async def cache_stats(user_id: str = Depends(get_current_user)):
    """Get cache statistics."""
    from app.cache import get_cache
    return get_cache().stats()


@app.delete("/cache")
async def clear_cache(user_id: str = Depends(get_current_user)):
    """Clear the semantic cache (development only)."""
    if settings.environment == "production":
        raise HTTPException(status_code=403, detail="Cache clear disabled in production")
    from app.cache import get_cache
    count = get_cache().clear()
    return {"cleared": count}


@app.get("/health")
async def health():
    """Liveness check for Render."""
    return {
        "status": "ok",
        "version": "2.0.0",
        "environment": settings.environment,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/health/ready")
async def health_ready():
    """Readiness check — verifies dependencies."""
    checks: dict[str, str] = {"api_key": "ok" if settings.mate_api_key or settings.environment != "production" else "missing"}

    if settings.database_url:
        try:
            from app.db import get_pool
            pool = await get_pool()
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            checks["database"] = "ok"
        except Exception as e:
            checks["database"] = f"error: {e}"
    else:
        checks["database"] = "not_configured"

    checks["pdflatex"] = "ok" if shutil.which(settings.pdflatex_path) else "missing"

    all_ok = all(v == "ok" or v == "not_configured" for v in checks.values())
    return {
        "status": "ready" if all_ok else "degraded",
        "checks": checks,
        "timestamp": datetime.now().isoformat(),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _run_job(job_id: str, request: GenerationRequest, owner_id: str = "") -> None:
    """Run a generation job in a background thread."""
    from app.pipeline.graph import run_pipeline

    def _is_aborted() -> bool:
        existing = _jobs.get(job_id)
        return bool(
            existing
            and existing.status == PipelineStatus.FAILED
            and existing.error_message == _ABORT_MESSAGE
        )

    def _publish(state: PipelineState) -> None:
        # Live progress: keep the registry object SSE watches in sync after each
        # super-step. Never resurrect a job the user already aborted.
        if _is_aborted():
            return
        _jobs[job_id] = state

    try:
        _jobs[job_id].status = PipelineStatus.RUNNING
        result = run_pipeline(
            request,
            job_id=job_id,
            owner_id=owner_id,
            on_progress=_publish,
        )
        if _is_aborted():
            logger.info("job_aborted_skipping_overwrite", job_id=job_id)
            clear_cancel(job_id)
            return
        result.job_id = job_id
        _jobs[job_id] = result
        persist_terminal_job(result)
        evict_terminal_jobs(_jobs)
        clear_cancel(job_id)
    except Exception as e:
        state = _jobs.get(job_id)
        if state:
            state.status = PipelineStatus.FAILED
            state.error_message = str(e)
            persist_terminal_job(state)
        logger.error("job_failed", job_id=job_id, error=str(e))


def _authorize_job(state: PipelineState, user_id: str) -> None:
    """
    Raise 403 if the job belongs to a different user.

    Legacy jobs without an owner (owner_id == "") stay accessible, as does any
    job in the no-auth or shared-key modes where every caller resolves to the
    same identity ("anonymous" / "api-user").
    """
    if state.owner_id and user_id and state.owner_id != user_id:
        logger.warning(
            "job_access_denied",
            job_id=state.job_id,
            owner=state.owner_id,
            requester=user_id,
        )
        raise HTTPException(status_code=403, detail="Not authorized for this job")


def _safe_filename(name: str) -> str:
    """Sanitize user-provided filename for filesystem paths."""
    safe = re.sub(r"[^\w\-]", "_", name.strip())[:64]
    return safe or "document"


def _sse_event(event_type: str, data: dict) -> str:
    """Format a Server-Sent Event."""
    return f"event: {event_type}\ndata: {json.dumps(data, default=str)}\n\n"
