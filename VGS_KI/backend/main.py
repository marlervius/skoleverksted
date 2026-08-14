"""FastAPI entrypoint for VGS-Lærerassistent.

Cleaned up: deduplicated job-running boilerplate, hardened CORS, leak-free
job store with TTL cleanup, race-condition-safe caching, structured errors
with request_id propagation.

The actual generation work happens in `agents.py`; PDF compilation in
`pdf_service.py`; per-endpoint orchestration delegates to `job_manager.py`.
"""
import asyncio
import json
import logging
import os
import re
import threading
import uuid
from typing import Any, Literal, Optional

import diskcache as dc
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field, field_validator
from pythonjsonlogger import jsonlogger
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from Skoleverksted.backend.platform.images import ImageResult, normalize_image_mode, resolve_image
from Skoleverksted.backend.platform.models import utc_now
from Skoleverksted.backend.platform.quality_gate import (
    content_digest as quality_content_digest,
    require_export_ready,
    run_quality_pipeline,
    source_approval_reasons,
    verify_teacher_export,
)

if __package__:
    from . import config
    from .agents import (
        generate_lesson_content,
        generate_prove_content,
        generate_sequence_content,
        validate_differentiated_variants,
    )
    from .tools import WikimediaImageSearchTool
    from .grep_api import get_competency_goals
    from .ndla_service import fetch_ndla_source
    from .docx_service import create_lesson_docx
    from .laeringsark_renderer import (
        build_faktarapport_doc, build_laeringsark_doc, collect_text_fields,
        make_image_observation_task, parse_oppgaver, structured_to_plain_text,
    )
    from .text_pipeline import lint_pdf
    from .pdf_service import (
        compile_typst, create_differentiated_pdf, create_lesson_pdf,
        create_prove_pdf, create_sequence_pdf, parse_worksheet_content,
    )
    from .media_manager import image_processor
    from .logging_utils import RequestLogger
    from .job_manager import (
        JobContext, compute_cache_key, fetch_image_with_retry, get_job,
        register_job, run_job_in_thread, safe_filename, start_cleanup_task,
        cancel_job,
    )
else:
    import config
    from agents import (
        generate_lesson_content,
        generate_prove_content,
        generate_sequence_content,
        validate_differentiated_variants,
    )
    from tools import WikimediaImageSearchTool
    from grep_api import get_competency_goals
    from ndla_service import fetch_ndla_source
    from docx_service import create_lesson_docx
    from laeringsark_renderer import (
        build_faktarapport_doc, build_laeringsark_doc, collect_text_fields,
        make_image_observation_task, parse_oppgaver, structured_to_plain_text,
    )
    from text_pipeline import lint_pdf
    from pdf_service import (
        compile_typst, create_differentiated_pdf, create_lesson_pdf,
        create_prove_pdf, create_sequence_pdf, parse_worksheet_content,
    )
    from media_manager import image_processor
    from logging_utils import RequestLogger
    from job_manager import (
        JobContext, compute_cache_key, fetch_image_with_retry, get_job,
        register_job, run_job_in_thread, safe_filename, start_cleanup_task,
        cancel_job,
    )

_wikimedia_tool = WikimediaImageSearchTool()


# ── Logging ──────────────────────────────────────────────────────────────────
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter(
    '%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s'
)
logHandler.setFormatter(formatter)
logging.basicConfig(level=logging.INFO, handlers=[logHandler], force=True)
logger = logging.getLogger(__name__)


def _materialize_pedagogical_image(
    *,
    image_mode: object,
    topic: str,
    subject: str,
    level: str,
    text: str,
    req_logger: RequestLogger,
    image_data: Optional[str] = None,
    image_url_override: Optional[str] = None,
) -> tuple[Optional[str], Optional[ImageResult], str, str]:
    """Resolve and optimise one image without making PDF generation depend on it."""
    if image_data:
        path = fetch_image_with_retry(None, image_data, req_logger)
        return path, None, "", "Bilde: lærerens eget opplastede bilde"
    if image_url_override:
        path = fetch_image_with_retry(image_url_override, None, req_logger)
        return path, None, "", "Kilde: Wikimedia Commons · valgt av læreren"

    mode = normalize_image_mode(image_mode)
    if mode == "none":
        return None, None, "", ""

    asset = resolve_image(
        mode,
        topic=topic,
        subject=subject,
        level=level,
        text=text,
    )
    if not asset:
        req_logger.warning("Bildecrewet fant ikke et faglig trygt bilde; fortsetter uten bilde")
        return None, None, "", ""

    path: Optional[str] = None
    if asset.local_path:
        raw_path = asset.local_path
        try:
            path = image_processor.process_image_from_path(raw_path)
        finally:
            try:
                os.unlink(raw_path)
            except OSError:
                pass
    elif asset.image_url:
        path = fetch_image_with_retry(asset.image_url, None, req_logger)

    if not path:
        req_logger.warning("Valgt bilde kunne ikke behandles; fortsetter uten bilde")
        return None, None, "", ""
    return path, asset, asset.caption, asset.credit


# ── Prompt-injection sanitisation ────────────────────────────────────────────
_INJECTION_PATTERNS = [
    re.compile(r'ignore (all |previous |above |prior )?instructions?', re.IGNORECASE),
    re.compile(r'(system|assistant|user)\s*prompt', re.IGNORECASE),
    re.compile(r'<\s*(system|assistant|instruction|prompt)[^>]*>', re.IGNORECASE),
    re.compile(r'\[INST\]|\[/INST\]|<\|im_start\|>|<\|im_end\|>', re.IGNORECASE),
    re.compile(r'you are now|act as|pretend (to be|you are)', re.IGNORECASE),
    re.compile(
        r'(disregard|forget|override) (your |all |previous )?(instructions?|rules?|guidelines?)',
        re.IGNORECASE,
    ),
]


def sanitize_description(text: str) -> str:
    """Strip common prompt-injection patterns from user-supplied free text."""
    for pattern in _INJECTION_PATTERNS:
        text = pattern.sub('', text)
    return text.strip()


# ── User-visible errors ──────────────────────────────────────────────────────
# Provider and compiler exceptions are English, noisy and sometimes carry
# internal service metadata. The full error goes to the log; the teacher gets a
# Norwegian message plus the request id that ties the two together.
USER_FACING_GENERATION_ERROR = (
    "Noe gikk galt under generering. Prøv igjen litt senere, eller kontakt "
    "support med referansen under."
)
USER_FACING_DOCUMENT_ERROR = (
    "Dokumentet kunne ikke bygges. Prøv igjen, eller kontakt support med "
    "referansen under."
)


# ── Cache backend (Redis if available, diskcache otherwise) ──────────────────

def _build_cache():
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        try:
            import redis as redis_lib

            class RedisCache:
                def __init__(self, url: str):
                    self._r = redis_lib.from_url(url, decode_responses=False)
                    self._r.ping()
                    logger.info(f"Redis cache connected: {url.split('@')[-1]}")

                def __contains__(self, key: str) -> bool:
                    return bool(self._r.exists(key))

                def get(self, key: str, default=None):
                    val = self._r.get(key)
                    if val is None:
                        return default
                    try:
                        return json.loads(val)
                    except Exception:
                        return val

                def set(self, key: str, value, expire: int = None):
                    payload = value if isinstance(value, (bytes, bytearray)) else json.dumps(value).encode()
                    if expire:
                        self._r.set(key, payload, ex=expire)
                    else:
                        self._r.set(key, payload)

            return RedisCache(redis_url)
        except Exception as e:
            logger.warning(f"Redis init failed, falling back to diskcache: {e}")
    cache_dir = os.getenv("DISK_CACHE_DIR", "./.cache")
    os.makedirs(cache_dir, exist_ok=True)
    logger.info(f"Diskcache initialised at {cache_dir}")
    return dc.Cache(cache_dir)


cache = _build_cache()


# ── App + middleware ─────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="VGS-Lærerassistent API",
    description="Generer PDF-leksjoner og arbeidsark for videregående skole (VGS)",
    version="1.1.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS: never default to '*'. Production must set ALLOWED_ORIGINS explicitly;
# config.py defaults to localhost for dev convenience.
logger.info(f"CORS allowed origins: {config.ALLOWED_ORIGINS}")
if config.ALLOWED_ORIGIN_REGEX:
    logger.info(f"CORS allowed origin regex: {config.ALLOWED_ORIGIN_REGEX}")
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_origin_regex=config.ALLOWED_ORIGIN_REGEX or None,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.on_event("startup")
async def _on_startup():
    start_cleanup_task()


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down — cleaning up temporary files...")
    image_processor.cleanup_all()


# ── Pydantic request/response models ─────────────────────────────────────────

class LessonRequest(BaseModel):
    """Request model for lesson and differentiated generation."""
    topic: str = Field(..., min_length=1, max_length=200)
    subject: str = Field(..., min_length=1, max_length=100)
    level: str = Field("VGS")
    language_level: Optional[str] = Field(None)
    options: dict[str, bool] = Field(
        default_factory=lambda: {
            "deep_dive": False,
            "lang_tekst": False,
            "grammar_tasks": True,
            "vocabulary_tasks": True,
            "comprehension_tasks": True,
            "discussion_tasks": True,
            "teacher_key": True,
            "role_play": False,
            "image_description": False,
            "writing_frame": False,
            "cultural_comparison": False,
            "real_case": False,
            "faktarapport": True,
            "korrektur": True,
            "differensiering": False,
            "reading_friendly": False,
        }
    )
    image_data: Optional[str] = Field(None)
    description: Optional[str] = Field(None, max_length=2000)
    source_text: Optional[str] = Field(None, max_length=5000)
    use_ndla: bool = Field(True)
    interest: Optional[str] = Field(None, max_length=200)
    basis_text: Optional[str] = Field(None, max_length=10000)
    image_url_override: Optional[str] = Field(None, max_length=500)
    image_mode: Literal["none", "commons", "ai"] = Field(
        "none",
        description="Ingen bilder, et fritt Wikimedia-bilde eller en KI-generert illustrasjon.",
    )

    @field_validator('image_data')
    @classmethod
    def validate_image_size(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v.encode('utf-8')) > config.MAX_IMAGE_BASE64_BYTES:
            raise ValueError(
                f"Bildet er for stort. Maks {config.MAX_IMAGE_BASE64_BYTES // (1024*1024)} MB."
            )
        return v

    @field_validator('description', 'source_text', 'interest')
    @classmethod
    def sanitize_text_field(cls, v: Optional[str]) -> Optional[str]:
        return sanitize_description(v) if v else v


class ProveRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=200)
    subject: str = Field(..., min_length=1, max_length=100)
    level: str = Field("VGS")
    language_level: Optional[str] = Field(None)
    include_fasit: bool = Field(False)
    description: Optional[str] = Field(None, max_length=2000)
    source_text: Optional[str] = Field(None, max_length=5000)
    use_ndla: bool = Field(True)

    @field_validator('description', 'source_text')
    @classmethod
    def sanitize_description_field(cls, v: Optional[str]) -> Optional[str]:
        return sanitize_description(v) if v else v


class SequenceRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=200)
    subject: str = Field(..., min_length=1, max_length=100)
    level: str = Field("VG1")
    antall_uker: int = Field(3, ge=2, le=6)
    timer_per_uke: int = Field(2, ge=1, le=3)
    grep_goals: list[str] = Field(default_factory=list)
    description: Optional[str] = Field(None, max_length=2000)

    @field_validator('description')
    @classmethod
    def sanitize_description_field(cls, v: Optional[str]) -> Optional[str]:
        return sanitize_description(v) if v else v


class LessonResponse(BaseModel):
    topic: str
    subject: str
    level: str
    text: str
    worksheet: str
    image_url: Optional[str] = None
    language_exercises: Optional[dict] = None
    truth_passport: Optional[dict] = None


# ── Health ───────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {"message": "VGS-Lærerassistent API", "version": app.version}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# ── Generic SSE stream + download handlers ───────────────────────────────────

async def _stream_job(job_id: str, request: Request) -> StreamingResponse:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_gen():
        yield f"data: {json.dumps({'type': 'connected'})}\n\n"
        while True:
            if await request.is_disconnected():
                break
            try:
                msg = await asyncio.wait_for(
                    job.queue.get(),
                    timeout=config.SSE_HEARTBEAT_SECONDS,
                )
                yield f"data: {json.dumps(msg)}\n\n"
                if msg.get("type") in ("done", "needs_teacher_review", "failed", "cancelled", "error"):
                    break
            except asyncio.TimeoutError:
                current = get_job(job_id)
                heartbeat = {
                    "type": "heartbeat",
                    "status": current.status if current else "failed",
                    **(current.progress if current else {}),
                }
                yield f"data: {json.dumps(heartbeat)}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _download_job(job_id: str, default_filename: str = "dokument.pdf",
                        kind: str = "main", preview: bool = False) -> Response:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.done:
        raise HTTPException(status_code=202, detail="Generering pågår fortsatt")
    if job.status == "cancelled":
        raise HTTPException(status_code=409, detail="Genereringen er avbrutt.")
    if job.status == "failed":
        raise HTTPException(status_code=500, detail=job.error or "Genereringen feilet.")
    if job.status == "needs_teacher_review":
        passport = job.truth_passport or {}
        reason = job.quality_stop_reason or "truth_layer_unresolved_claims"
        raise HTTPException(
            status_code=409,
            detail={
                "code": "needs_teacher_review",
                "stop_reason": reason,
                "message": "PDF er blokkert til en lærer har kontrollert innholdet.",
                "truth_passport": passport,
                "quarantine": job.quarantine,
            },
        )
    if job.error:
        raise HTTPException(status_code=500, detail=job.error)

    if kind == "rapport":
        if not job.rapport_pdf:
            raise HTTPException(status_code=404, detail="Ingen faktarapport for denne jobben")
        pdf_bytes = job.rapport_pdf
        filename = job.rapport_filename or default_filename
    else:
        pdf_bytes = job.pdf
        filename = job.filename or default_filename

    if kind != "rapport":
        passport = job.truth_passport or {}
        quarantine = [
            str(item.get("original_text") or "")
            for item in job.quarantine
            if item.get("status", "withheld") == "withheld"
        ]
        if preview:
            reasons = source_approval_reasons(
                content=job.verification_content,
                verification_status=str(passport.get("status") or "missing"),
                verified_revision=str(passport.get("content_revision") or ""),
                verification_version=str(passport.get("version") or ""),
                quarantined_texts=quarantine,
            )
            if reasons:
                if passport:
                    raise HTTPException(
                        status_code=409,
                        detail={
                            "code": "needs_teacher_review",
                            "stop_reason": "truth_passport_mismatch",
                            "message": "Kildekontrollen krever ny lærer-gjennomgang før forhåndsvisning.",
                            "truth_passport": passport,
                            "reasons": reasons,
                        },
                    )
                raise HTTPException(status_code=409, detail="Forhåndsvisningen er blokkert: " + "; ".join(reasons))
        else:
            try:
                require_export_ready(
                    export_id="fag.pdf",
                    content=job.verification_content,
                    verification_status=str(passport.get("status") or "missing"),
                    verified_revision=str(passport.get("content_revision") or ""),
                    verification_version=str(passport.get("version") or ""),
                    teacher_approved=bool(job.teacher_approved_at),
                    approved_revision=job.approved_digest,
                    quarantined_texts=quarantine,
                )
            except PermissionError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc

    # The job is intentionally NOT popped here: a lesson job may have both a
    # student PDF and a teacher fact-report PDF that are downloaded separately.
    # TTL cleanup removes the job afterwards.
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'{"inline" if preview or kind == "rapport" else "attachment"}; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
            "X-Quality-Status": "review_only" if kind == "rapport" else ("source_approved" if preview else "export_ready"),
        },
    )


@app.delete("/generate/{job_id}")
async def cancel_generation(job_id: str):
    """Cancel a generation and publish an idempotent terminal SSE event."""
    job = cancel_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"success": True, "status": job.status, "message": "Genereringen er avbrutt."}


@app.get("/generation/{job_id}/review")
def generation_review(job_id: str):
    """Return a teacher-facing control view for a blocked generation.

    This is intentionally separate from the PDF route: a blocked artifact is
    inspectable and editable, but never downloadable as an approved document.
    """
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "needs_teacher_review":
        raise HTTPException(status_code=409, detail="Jobben har ikke en aktiv lærerkontroll.")
    passport = job.truth_passport or {}
    claims = (passport.get("claims") or []) if isinstance(passport, dict) else []
    return {
        "job_id": job_id,
        "status": job.status,
        "quality_stop_reason": job.quality_stop_reason or "truth_layer_unresolved_claims",
        "content": job.review_payload,
        "verification_content": job.verification_content,
        "truth_passport": passport,
        "sources": passport.get("sources", []) if isinstance(passport, dict) else [],
        "verified_claims": [item for item in claims if item.get("status") == "verified"],
        "quarantine": job.quarantine,
        "variant_issues": job.variant_issues,
        "claims_for_review": [
            item for item in claims if item.get("status") != "verified"
        ],
        "actions": {
            "rerun": f"/generation/{job_id}/review/rerun",
            "remove_claim": f"/generation/{job_id}/review/remove",
            "cancel": f"/generate/{job_id}",
        },
    }


class GenerationReviewPatch(BaseModel):
    """Editable fields returned by the teacher control view."""

    canonical: dict[str, Any] | str | None = None
    variants: dict[str, str] | None = None
    worksheet: str | None = Field(default=None, max_length=20_000)
    language_exercises: dict[str, Any] | None = None


def _review_payload(job: Any) -> dict[str, Any]:
    if job.review_payload:
        return json.loads(json.dumps(job.review_payload, ensure_ascii=False))
    try:
        parsed = json.loads(job.verification_content or "{}")
    except json.JSONDecodeError:
        parsed = {}
    return parsed if isinstance(parsed, dict) else {}


def _replace_claim_once(value: Any, exact_text: str, state: dict[str, bool]) -> Any:
    if state["removed"]:
        return value
    if isinstance(value, str) and exact_text and exact_text in value:
        state["removed"] = True
        return value.replace(exact_text, "", 1)
    if isinstance(value, list):
        return [_replace_claim_once(item, exact_text, state) for item in value]
    if isinstance(value, dict):
        return {key: _replace_claim_once(item, exact_text, state) for key, item in value.items()}
    return value


async def _rerun_review(job_id: str, job: Any, payload: dict[str, Any]) -> dict[str, Any]:
    source_payload = (job.truth_passport or {}).get("sources", [])
    result = await asyncio.to_thread(
        run_quality_pipeline,
        generator_id="fag.differentiated",
        content=json.dumps(payload, ensure_ascii=False),
        topic=getattr(job.request_payload, "topic", "Norsk"),
        subject=getattr(job.request_payload, "subject", "Norsklæring"),
        level=getattr(job.request_payload, "level", "A2"),
        provided_sources=source_payload,
        request_id=job_id,
    )
    job.filename = safe_filename(
        "kontroll",
        getattr(job.request_payload, "topic", "differensiert"),
        getattr(job.request_payload, "level", ""),
    )
    job.variant_issues = []
    try:
        approved_payload = json.loads(result.approved_content)
    except (TypeError, json.JSONDecodeError):
        approved_payload = None
    if not isinstance(approved_payload, dict):
        job.review_payload = payload
        job.verification_content = result.approved_content
        job.truth_passport = result.passport.model_dump(mode="json")
        job.quarantine = [item.model_dump(mode="json") for item in result.quarantine]
        job.quality_rounds = [item.model_dump(mode="json") for item in result.rounds]
        job.quality_stop_reason = "review_payload_invalid_after_quality_gate"
        job.teacher_approved_at = ""
        job.approved_digest = ""
        job.pdf = None
        job.status = "needs_teacher_review"
        job.done = True
        return {
            "job_id": job_id,
            "status": job.status,
            "quality_stop_reason": job.quality_stop_reason,
            "truth_passport": job.truth_passport,
            "quarantine": job.quarantine,
            "review_payload": job.review_payload,
            "variant_issues": job.variant_issues,
            "pdf_ready": False,
            "filename": job.filename,
        }
    payload = approved_payload
    job.review_payload = payload
    job.verification_content = result.approved_content
    job.truth_passport = result.passport.model_dump(mode="json")
    job.quarantine = [item.model_dump(mode="json") for item in result.quarantine]
    job.quality_rounds = [item.model_dump(mode="json") for item in result.rounds]
    job.quality_stop_reason = result.stop_reason
    job.teacher_approved_at = ""
    job.approved_digest = ""
    job.pdf = None
    job.status = "needs_teacher_review"
    if result.source_approved:
        canonical = payload.get("canonical")
        if isinstance(canonical, dict):
            canonical_text = structured_to_plain_text(canonical) if canonical.get("seksjoner") else str(canonical.get("text") or "")
        else:
            canonical_text = str(canonical or "")
        variants = payload.get("variants") if isinstance(payload.get("variants"), dict) else {}
        differentiation = {
            "stoette": str(variants.get("støtte", variants.get("stoette", "")) or ""),
            "fordypning": str(variants.get("fordypning", "") or ""),
        }
        variant_issues = validate_differentiated_variants(
            canonical_text=canonical_text,
            differensiering=differentiation,
        )
        job.variant_issues = variant_issues
        if not variant_issues:
            request_payload = job.request_payload
            job.pdf = await asyncio.to_thread(
                create_differentiated_pdf,
                standard_text=canonical_text,
                stoette_text=differentiation["stoette"],
                fordypning_text=differentiation["fordypning"],
                topic=getattr(request_payload, "topic", "Norsk"),
                level=getattr(request_payload, "level", "VGS"),
                subject=getattr(request_payload, "subject", "Norsklæring"),
                worksheet_text=str(payload.get("worksheet") or ""),
                language_exercises=payload.get("language_exercises"),
                options=getattr(request_payload, "options", {}) or {},
            )
            job.filename = safe_filename(
                "differensiert",
                getattr(request_payload, "topic", "differensiert"),
                getattr(request_payload, "level", ""),
            )
            job.status = "source_approved"
        else:
            job.quality_stop_reason = "differentiation_contract_failed"
    job.done = True
    return {
        "job_id": job_id,
        "status": job.status,
        "quality_stop_reason": job.quality_stop_reason,
        "truth_passport": job.truth_passport,
        "quarantine": job.quarantine,
        "review_payload": job.review_payload,
        "variant_issues": job.variant_issues,
        "pdf_ready": bool(job.pdf),
        "filename": job.filename,
    }


@app.post("/generation/{job_id}/review/rerun")
async def rerun_generation_review(job_id: str, patch: GenerationReviewPatch):
    """Apply teacher edits and run only the bounded quality gate again."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    payload = _review_payload(job)
    changes = patch.model_dump(exclude_none=True)
    payload.update(changes)
    result = await _rerun_review(job_id, job, payload)
    result["job_id"] = job_id
    return result


class GenerationReviewRemove(BaseModel):
    claim_id: str = Field(min_length=1, max_length=80)


@app.post("/generation/{job_id}/review/remove")
async def remove_generation_claim(job_id: str, request: GenerationReviewRemove):
    """Remove one explicitly selected claim, then re-run the gate."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    passport = job.truth_passport or {}
    claims = passport.get("claims", []) if isinstance(passport, dict) else []
    claim = next((item for item in claims if item.get("id") == request.claim_id), None)
    if not claim:
        raise HTTPException(status_code=404, detail="Påstanden finnes ikke i kontrollbildet.")
    exact_text = str(claim.get("exact_text") or claim.get("claim") or "")
    payload = _review_payload(job)
    state = {"removed": False}
    payload = _replace_claim_once(payload, exact_text, state)
    if not state["removed"]:
        raise HTTPException(status_code=409, detail="Påstanden kunne ikke fjernes sikkert. Rediger feltet i stedet.")
    result = await _rerun_review(job_id, job, payload)
    result["job_id"] = job_id
    return result


@app.post("/generation/{job_id}/approve")
def approve_generation(job_id: str):
    """Record explicit teacher approval for the exact verified job text."""
    job = get_job(job_id)
    if not job or not job.done:
        raise HTTPException(status_code=404, detail="Det ferdige dokumentet finnes ikke.")
    passport = job.truth_passport or {}
    reasons = source_approval_reasons(
        content=job.verification_content,
        verification_status=str(passport.get("status") or "missing"),
        verified_revision=str(passport.get("content_revision") or ""),
        verification_version=str(passport.get("version") or ""),
        quarantined_texts=[
            str(item.get("original_text") or "") for item in job.quarantine
            if item.get("status", "withheld") == "withheld"
        ],
    )
    if reasons:
        raise HTTPException(status_code=409, detail="Dokumentet kan ikke lærer-godkjennes: " + "; ".join(reasons))
    job.teacher_approved_at = utc_now()
    job.approved_digest = quality_content_digest(job.verification_content)
    return {"status": "teacher_approved", "approved_at": job.teacher_approved_at, "content_revision": job.approved_digest, "quarantined_count": len(job.quarantine)}


# ── Source resolution (teacher-provided or NDLA) ─────────────────────────────

def _resolve_source(req, ctx: "JobContext") -> tuple[Optional[str], Optional[str], Optional[dict]]:
    """Determine the grounding source for a generation job.

    Teacher-pasted material always wins. Otherwise, if NDLA grounding is
    enabled, search NDLA's open learning resources for a relevant article.
    Returns (source_text, source_name, source_metadata).  The metadata follows
    the generated text into the independent truth layer so a fetched NDLA page
    is not silently discarded before claim verification.
    """
    if req.source_text:
        return req.source_text, "lærerens kildemateriale", None
    if getattr(req, "use_ndla", False):
        ctx.push("Søker etter kildegrunnlag på NDLA...")
        language = "en" if req.subject.lower() == "engelsk" else "nb"
        ndla = fetch_ndla_source(req.topic, language=language)
        if ndla:
            ctx.push(f"Kildeforankrer i NDLA: {ndla['title']}")
            return ndla["text"], f"NDLA: {ndla['title']}", {
                "title": ndla["title"],
                "url": ndla["url"],
                "publisher": "NDLA",
                "origin": "grounding",
                "fetch_status": "fetched",
            }
        ctx.push("Fant ingen passende NDLA-kilde — fortsetter uten kildeforankring.")
    return None, None, None


def _verify_structured_output(
    ctx: "JobContext",
    *,
    generator_id: str,
    payload: dict,
    topic: str,
    subject: str,
    level: str,
    provided_sources: tuple[dict, ...] = (),
) -> dict:
    """Route assessment and sequence JSON through the shared quality engine."""
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True)

    def _quality_progress(event: dict[str, object]) -> None:
        details = dict(event)
        message = str(details.pop("message", "Sannhetslaget arbeider..."))
        ctx.push(message, **details)

    result = run_quality_pipeline(
        generator_id=generator_id,
        content=canonical,
        topic=topic,
        subject=subject,
        level=level,
        provided_sources=provided_sources,
        cancel_check=ctx.cancel_check,
        request_id=ctx.job_id,
        progress_callback=_quality_progress,
    )
    try:
        verified_payload = json.loads(result.approved_content)
    except (TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Kvalitetskontrollen kunne ikke bevare dokumentstrukturen.") from exc
    if not isinstance(verified_payload, dict):
        raise RuntimeError("Kvalitetskontrollen returnerte ikke et gyldig dokumentobjekt.")
    if ctx.set_meta:
        ctx.set_meta("verification_content", result.approved_content)
        ctx.set_meta("truth_passport", result.passport.model_dump(mode="json"))
        ctx.set_meta("quarantine", [item.model_dump(mode="json") for item in result.quarantine])
        ctx.set_meta("quality_rounds", [item.model_dump(mode="json") for item in result.rounds])
        ctx.set_meta("quality_stop_reason", result.stop_reason)
        ctx.set_meta("quality_status", result.quality_status)
    return verified_payload


# ── Worker: standard læringsark ───────────────────────────────────────────────

def _lesson_worker(ctx: JobContext) -> tuple[bytes, str]:
    req = ctx.request_payload  # LessonRequest
    # Existing text is reused as-is, but its source provenance must still be
    # available to the independent verifier (for example when only the image
    # or exercises are regenerated).
    if req.basis_text and not (getattr(req, "use_ndla", False) and not req.source_text):
        source_text, source_name, source_metadata = (
            req.source_text,
            "lærerens kildemateriale" if req.source_text else None,
            None,
        )
    else:
        source_text, source_name, source_metadata = _resolve_source(req, ctx)
    provided_sources = (
        (source_metadata,)
        if source_metadata else ()
    )
    ctx.push("Genererer fagtekst..." if not req.basis_text else "Bruker eksisterende fagtekst, regenererer oppgaver...")
    content = generate_lesson_content(
        topic=req.topic,
        subject=req.subject,
        level=req.level,
        language_level=req.language_level,
        options=req.options,
        description=req.description,
        source_text=source_text,
        source_metadata=source_metadata,
        interest=req.interest,
        basis_text=req.basis_text,
        progress_callback=ctx.push,
        cancel_check=ctx.cancel_check,
        request_id=ctx.job_id,
        provided_sources=provided_sources,
    )

    if ctx.set_meta:
        ctx.set_meta("basis_text", content.get("text"))
        ctx.set_meta("worksheet_text", content.get("worksheet"))
        ctx.set_meta("faktarapport_text", content.get("faktarapport"))
        ctx.set_meta("language_exercises", content.get("language_exercises"))
        ctx.set_meta("warnings", content.get("warnings"))
        ctx.set_meta("source_grounded", content.get("source_grounded"))
        ctx.set_meta("source_name", source_name)
        ctx.set_meta("source_url", (source_metadata or {}).get("url"))
        ctx.set_meta("truth_passport", content.get("truth_passport"))
        ctx.set_meta("verification_content", content.get("verification_content"))
        ctx.set_meta("quarantine", content.get("quarantine"))
        ctx.set_meta("quality_rounds", content.get("quality_rounds"))
        ctx.set_meta("quality_stop_reason", content.get("quality_stop_reason"))
        ctx.set_meta("quality_status", content.get("quality_status", "needs_teacher_review"))
        ctx.set_meta("prompt_version", content.get("prompt_version"))

    if content.get("quality_status") != "source_approved":
        ctx.push(
            "Kildekontrollen er ferdig – rediger innholdet før PDF kan frigis.",
            revision_round=len(content.get("quality_rounds") or []),
            claims_checked=sum(int(round_item.get("claims_found", 0)) for round_item in content.get("quality_rounds") or []),
            claims_verified=sum(int(round_item.get("claims_verified", 0)) for round_item in content.get("quality_rounds") or []),
            claims_quarantined=len(content.get("quarantine") or []),
            stop_reason=content.get("quality_stop_reason") or "truth_layer_unresolved_claims",
        )
        return b"", safe_filename("kontroll", req.topic, req.level)

    if normalize_image_mode(req.image_mode) != "none" and not req.image_data and not req.image_url_override:
        ctx.push("Bildecrewet planlegger og kvalitetssikrer ett pedagogisk bilde...")
    else:
        ctx.push("Behandler bildevalg...")
    image_path, image_asset, image_caption, image_credit = _materialize_pedagogical_image(
        image_mode=req.image_mode,
        topic=req.topic,
        subject=req.subject,
        level=req.level,
        text=content.get("text", ""),
        req_logger=ctx.req_logger,
        image_data=req.image_data,
        image_url_override=req.image_url_override,
    )
    if ctx.set_meta:
        ctx.set_meta("image_url", image_asset.image_url if image_asset else req.image_url_override)
        ctx.set_meta("image_metadata", image_asset.public_metadata() if image_asset else None)
        if normalize_image_mode(req.image_mode) != "none" and not image_path and not req.image_data:
            ctx.set_meta(
                "warnings",
                list(content.get("warnings") or [])
                + [
                    "Ingen tilstrekkelig relevant og fritt tilgjengelig bilde ble funnet. "
                    "PDF-en ble laget uten bilde. Du kan prøve Commons-søket på nytt, "
                    "velge en KI-illustrasjon eller laste opp et eget bilde."
                ],
            )

    structured = content.get("structured")
    rapport_payload = content.get("faktarapport_structured") or content.get("faktarapport")
    worksheet_sections = parse_worksheet_content(content.get("worksheet") or "")
    image_assessment_note = ""

    try:
        ctx.push("Kompilerer PDF...")
        if structured:
            # Redesigned layout (SPEC_laeringsark_redesign DEL 2): margin
            # terms, numbered colour-stripe sections, purple task boxes.
            oppgaver = parse_oppgaver(
                worksheet_sections["comprehension"],
                worksheet_sections["discussion"],
            )
            if image_path:
                image_task = make_image_observation_task(
                    caption=image_caption,
                    rationale=image_asset.rationale if image_asset else req.topic,
                    source=image_asset.source if image_asset else "teacher",
                    subject=req.subject,
                )
                oppgaver.append(image_task)
                if req.subject.strip().lower() == "engelsk":
                    image_assessment_note = (
                        "Image task: The student should identify two visible details, connect "
                        "both to the lesson content, and distinguish observation from interpretation. "
                        "For an AI image, credit explicit awareness that it is not documentary evidence."
                    )
                else:
                    image_assessment_note = (
                        "Bildeoppgave: Eleven bør peke på to synlige detaljer, koble begge til "
                        "fagstoffet og skille observasjon fra tolkning. For KI-bilder skal eleven "
                        "forstå at illustrasjonen ikke er dokumentarisk bevis."
                    )
            modus = ("Fordypning"
                     if (req.options or {}).get("deep_dive") or (req.options or {}).get("lang_tekst")
                     else "Standard")
            doc = build_laeringsark_doc(
                structured,
                fag=req.subject,
                tema=req.topic,
                niva=req.level,
                modus=modus,
                kilde=source_name,
                har_k_markorer=bool(
                    source_name and "[K]" in collect_text_fields(structured)
                ),
                laeringsmaal=worksheet_sections.get("learning_goals", ""),
                oppgaver=oppgaver,
                image_filename=os.path.basename(image_path) if image_path else None,
                image_caption=image_caption,
                image_credit=image_credit,
            )
            pdf_bytes = compile_typst(doc, image_path=image_path)
        else:
            # Legacy fallback when the writer's JSON could not be parsed.
            # The fact report is no longer appended to the student PDF — it
            # is delivered as its own document below (spec 2.8).
            pdf_bytes = create_lesson_pdf(
                content_text=content["text"],
                worksheet_text=content["worksheet"],
                topic=req.topic,
                level=req.level,
                subject=req.subject,
                language_level=req.language_level,
                image_path=image_path,
                image_caption=image_caption,
                image_credit=image_credit,
                language_exercises=content.get("language_exercises"),
                options=req.options,
                faktarapport=None,
                source_name=source_name,
            )
    finally:
        if image_path:
            try:
                image_processor.cleanup_image(image_path)
            except Exception as e:
                ctx.req_logger.warning(f"Image cleanup failed: {e}")

    # ── Separate teacher guide: fact review + answer guidance ──
    teacher_key = worksheet_sections.get("teacher_key", "")
    if image_assessment_note:
        teacher_key = "\n\n".join(
            part for part in (teacher_key.strip(), image_assessment_note) if part
        )
    if rapport_payload or teacher_key:
        try:
            ctx.push("Kompilerer lærerveiledning med faktasjekk og fasit...")
            rapport_doc = build_faktarapport_doc(
                rapport_payload or {},
                fag=req.subject,
                tema=req.topic,
                kilde=source_name,
                teacher_key=teacher_key,
            )
            rapport_pdf = compile_typst(rapport_doc)
            if ctx.set_meta:
                ctx.set_meta("rapport_pdf", rapport_pdf)
                ctx.set_meta("rapport_filename",
                             safe_filename("laererveiledning", req.topic, req.level))
        except Exception as e:
            ctx.req_logger.error(f"Lærerveiledning PDF failed: {e}", exc_info=True)
            ctx.push("⚠ Lærerveiledningen kunne ikke kompileres som egen PDF.")

    # ── PDF lint: last gate before delivery (spec 1.5) ──
    try:
        whitelist = tuple(content.get("verk") or [])
        issues = lint_pdf(pdf_bytes, whitelist)
        if req.subject.lower() == "engelsk":
            issues = [i for i in issues if not i.startswith("engelske ord")]
        if issues:
            ctx.req_logger.warning(f"PDF lint issues: {issues}")
            if ctx.set_meta:
                ctx.set_meta("lint_issues", issues)
            ctx.push(f"⚠ Kvalitetssjekk fant {len(issues)} mulige problem(er) i PDF-en.")
    except Exception as e:
        ctx.req_logger.warning(f"PDF lint failed: {e}")

    return pdf_bytes, safe_filename("leksjon", req.topic, req.level)


# ── Worker: differensiert ─────────────────────────────────────────────────────

def _differentiated_worker(ctx: JobContext) -> tuple[bytes, str]:
    req = ctx.request_payload
    options = dict(req.options)
    options["differensiering"] = True

    source_text, source_name, source_metadata = _resolve_source(req, ctx)
    provided_sources = (
        (source_metadata,)
        if source_metadata else ()
    )
    ctx.push("Genererer fagtekst...")
    content = generate_lesson_content(
        topic=req.topic,
        subject=req.subject,
        level=req.level,
        language_level=req.language_level,
        options=options,
        description=req.description,
        source_text=source_text,
        source_metadata=source_metadata,
        interest=req.interest,
        progress_callback=ctx.push,
        quality_generator_id="fag.differentiated",
        cancel_check=ctx.cancel_check,
        request_id=ctx.job_id,
        provided_sources=provided_sources,
    )

    if ctx.set_meta:
        ctx.set_meta("source_grounded", content.get("source_grounded"))
        ctx.set_meta("source_name", source_name)
        ctx.set_meta("source_url", (source_metadata or {}).get("url"))
        ctx.set_meta("prompt_version", content.get("prompt_version"))
        ctx.set_meta("truth_passport", content.get("truth_passport"))
        ctx.set_meta("verification_content", content.get("verification_content"))
        ctx.set_meta("quarantine", content.get("quarantine"))
        ctx.set_meta("quality_rounds", content.get("quality_rounds"))
        ctx.set_meta("quality_stop_reason", content.get("quality_stop_reason"))
        ctx.set_meta("quality_status", content.get("quality_status", "needs_teacher_review"))
        ctx.set_meta("review_payload", content.get("review_payload"))

    if content.get("quality_status") != "source_approved":
        ctx.push("Kildekontrollen er ferdig – rediger innholdet før PDF kan frigis.")
        return b"", safe_filename("kontroll", req.topic, req.level)

    variant_issues = validate_differentiated_variants(
        canonical_text=content.get("canonical_content") or content.get("text", ""),
        differensiering=content.get("differensiering"),
    )
    if variant_issues:
        if ctx.set_meta:
            ctx.set_meta("quality_status", "needs_teacher_review")
            ctx.set_meta("quality_stop_reason", "differentiation_contract_failed")
            ctx.set_meta("variant_issues", variant_issues)
        ctx.push("Differensieringen mangler en gyldig variant – lærergjennomgang kreves.")
        return b"", safe_filename("kontroll", req.topic, req.level)

    ctx.push(
        "Bildecrewet planlegger og kvalitetssikrer ett pedagogisk bilde..."
        if normalize_image_mode(req.image_mode) != "none" and not req.image_data
        else "Behandler bildevalg..."
    )
    image_path, image_asset, image_caption, image_credit = _materialize_pedagogical_image(
        image_mode=req.image_mode,
        topic=req.topic,
        subject=req.subject,
        level=req.level,
        text=content.get("text", ""),
        req_logger=ctx.req_logger,
        image_data=req.image_data,
    )
    if ctx.set_meta:
        ctx.set_meta("image_url", image_asset.image_url if image_asset else None)
        ctx.set_meta("image_metadata", image_asset.public_metadata() if image_asset else None)
        if normalize_image_mode(req.image_mode) != "none" and not image_path and not req.image_data:
            ctx.set_meta(
                "warnings",
                list(content.get("warnings") or [])
                + [
                    "Ingen tilstrekkelig relevant og fritt tilgjengelig bilde ble funnet. "
                    "PDF-en ble laget uten bilde. Du kan prøve Commons-søket på nytt, "
                    "velge en KI-illustrasjon eller laste opp et eget bilde."
                ],
            )

    try:
        ctx.push("Kompilerer differensiert PDF...")
        diff = content.get("differensiering") or {}
        pdf_bytes = create_differentiated_pdf(
            standard_text=content["text"],
            stoette_text=diff.get("stoette", ""),
            fordypning_text=diff.get("fordypning", ""),
            topic=req.topic,
            level=req.level,
            subject=req.subject,
            image_path=image_path,
            image_caption=image_caption,
            image_credit=image_credit,
            worksheet_text=content.get("worksheet", ""),
            language_exercises=content.get("language_exercises"),
            options=options,
        )
    finally:
        if image_path:
            try:
                image_processor.cleanup_image(image_path)
            except Exception as e:
                ctx.req_logger.warning(f"Image cleanup failed: {e}")

    return pdf_bytes, safe_filename("differensiert", req.topic, req.level)


# ── Worker: prøve ─────────────────────────────────────────────────────────────

def _prove_worker(ctx: JobContext) -> tuple[bytes, str]:
    req = ctx.request_payload  # ProveRequest
    source_text, source_name, source_metadata = _resolve_source(req, ctx)
    ctx.push("Genererer prøveoppgaver...")
    content = generate_prove_content(
        topic=req.topic,
        subject=req.subject,
        level=req.level,
        description=req.description,
        language_level=req.language_level,
        source_text=source_text,
        progress_callback=ctx.push,
    )

    if ctx.set_meta:
        ctx.set_meta("source_grounded", bool(source_text))
        ctx.set_meta("source_name", source_name)
        ctx.set_meta("source_url", (source_metadata or {}).get("url"))

    ctx.push("Henter og optimaliserer bilde...")
    image_path = fetch_image_with_retry(content.get("image_url"), None, ctx.req_logger)

    try:
        ctx.push("Kompilerer prøve-PDF...")
        prove_json = _verify_structured_output(
            ctx,
            generator_id="fag.assessment",
            payload=content.get("prove_json") or {},
            topic=req.topic,
            subject=req.subject,
            level=req.level,
            provided_sources=(source_metadata,) if source_metadata else (),
        )
        if ctx.cancel_check and ctx.cancel_check():
            return b"", safe_filename("kontroll", req.topic, req.level)
        if (ctx.meta or {}).get("quality_status") != "source_approved":
            return b"", safe_filename("kontroll", req.topic, req.level)
        pdf_bytes = create_prove_pdf(
            prove_json=prove_json,
            topic=req.topic,
            level=req.level,
            subject=req.subject,
            include_fasit=req.include_fasit,
        )
    finally:
        if image_path:
            try:
                image_processor.cleanup_image(image_path)
            except Exception as e:
                ctx.req_logger.warning(f"Image cleanup failed: {e}")

    return pdf_bytes, safe_filename("prove", req.topic, req.level)


# ── Worker: sekvensplan ───────────────────────────────────────────────────────

def _sequence_worker(ctx: JobContext) -> tuple[bytes, str]:
    req = ctx.request_payload  # SequenceRequest
    ctx.push("Planlegger undervisningssekvens...")
    content = generate_sequence_content(
        topic=req.topic,
        subject=req.subject,
        level=req.level,
        antall_uker=req.antall_uker,
        timer_per_uke=req.timer_per_uke,
        description=req.description,
        grep_goals=req.grep_goals or [],
        progress_callback=ctx.push,
    )

    sequence_json = _verify_structured_output(
        ctx,
        generator_id="fag.lesson_sequence",
        payload=content.get("sequence_json") or {},
        topic=req.topic,
        subject=req.subject,
        level=req.level,
    )
    if (ctx.meta or {}).get("quality_status") != "source_approved":
        return b"", safe_filename("kontroll", req.topic, req.level)
    ctx.push("Kompilerer sekvensplan-PDF...")
    pdf_bytes = create_sequence_pdf(
        sequence_json=sequence_json,
        topic=req.topic,
        level=req.level,
        subject=req.subject,
    )
    return pdf_bytes, safe_filename("sekvensplan", req.topic, f"{req.level}_{req.antall_uker}uker")


# ── Endpoints: læringsark ─────────────────────────────────────────────────────

@app.post("/generate-lesson-start")
@limiter.limit(config.RATE_LIMIT_GENERATE)
async def start_lesson_generation(request: Request, lesson_request: LessonRequest):
    job_id, queue = register_job()
    cache_key = compute_cache_key("pdf_lesson", lesson_request)
    run_job_in_thread(job_id, queue, lesson_request, _lesson_worker,
                      cache_key=cache_key, cache=cache,
                      project_id=request.headers.get("X-Skoleverksted-Project"))
    return {"job_id": job_id}


@app.get("/generate-lesson-stream/{job_id}")
async def lesson_stream(job_id: str, request: Request):
    return await _stream_job(job_id, request)


@app.get("/generate-lesson-download/{job_id}")
async def download_lesson(job_id: str, preview: bool = False):
    return await _download_job(job_id, "leksjon.pdf", preview=preview)


@app.get("/generate-lesson-download-rapport/{job_id}")
async def download_lesson_rapport(job_id: str):
    """Separate teacher guide (never part of the student PDF)."""
    return await _download_job(job_id, "laererveiledning.pdf", kind="rapport")


# ── Endpoints: differensiert ──────────────────────────────────────────────────

@app.post("/generate-differentiated-start")
@limiter.limit(config.RATE_LIMIT_GENERATE)
async def start_differentiated_generation(request: Request, lesson_request: LessonRequest):
    job_id, queue = register_job()
    # Differensiering varies enough that we don't share PDF cache with standard lesson.
    cache_key = compute_cache_key("pdf_diff", lesson_request)
    run_job_in_thread(job_id, queue, lesson_request, _differentiated_worker,
                      cache_key=cache_key, cache=cache,
                      project_id=request.headers.get("X-Skoleverksted-Project"))
    return {"job_id": job_id}


# ── Endpoints: prøve ──────────────────────────────────────────────────────────

@app.post("/generate-prove-start")
@limiter.limit(config.RATE_LIMIT_GENERATE)
async def start_prove_generation(request: Request, prove_request: ProveRequest):
    job_id, queue = register_job()
    cache_key = compute_cache_key("pdf_prove", prove_request)
    run_job_in_thread(job_id, queue, prove_request, _prove_worker,
                      cache_key=cache_key, cache=cache,
                      project_id=request.headers.get("X-Skoleverksted-Project"))
    return {"job_id": job_id}


@app.get("/generate-prove-stream/{job_id}")
async def prove_stream(job_id: str, request: Request):
    return await _stream_job(job_id, request)


@app.get("/generate-prove-download/{job_id}")
async def download_prove(job_id: str, preview: bool = False):
    return await _download_job(job_id, "prove.pdf", preview=preview)


# ── Endpoints: sekvensplan ────────────────────────────────────────────────────

@app.post("/generate-sequence-start")
@limiter.limit(config.RATE_LIMIT_GENERATE)
async def start_sequence_generation(request: Request, seq_request: SequenceRequest):
    job_id, queue = register_job()
    cache_key = compute_cache_key("pdf_sequence", seq_request)
    run_job_in_thread(job_id, queue, seq_request, _sequence_worker,
                      cache_key=cache_key, cache=cache,
                      project_id=request.headers.get("X-Skoleverksted-Project"))
    return {"job_id": job_id}


@app.get("/generate-sequence-stream/{job_id}")
async def sequence_stream(job_id: str, request: Request):
    return await _stream_job(job_id, request)


@app.get("/generate-sequence-download/{job_id}")
async def download_sequence(job_id: str, preview: bool = False):
    return await _download_job(job_id, "sekvensplan.pdf", preview=preview)


# ── Legacy synchronous endpoints (kept for backwards-compat callers) ─────────

@app.post("/generate-lesson", response_class=Response)
@limiter.limit(config.RATE_LIMIT_GENERATE)
async def generate_lesson_sync(request: Request, lesson_request: LessonRequest):
    """Synchronous lesson generation. Prefer /generate-lesson-start for UX."""
    raise HTTPException(
        status_code=409,
        detail="Denne eldre direkteruten er stengt av kvalitetsporten. Bruk start/forhåndsvis/godkjenn-flyten.",
    )
    request_id = str(uuid.uuid4())[:8]
    req_logger = RequestLogger(logger, {'request_id': request_id})

    cache_key = compute_cache_key("pdf_lesson", lesson_request)
    if cache_key in cache:
        req_logger.info(f"Cache hit: {cache_key[:24]}…")
        cached_pdf = cache.get(cache_key)
        filename = safe_filename("leksjon", lesson_request.topic, lesson_request.level)
        return Response(
            content=cached_pdf,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(cached_pdf)),
            },
        )

    try:
        loop = asyncio.get_event_loop()
        content = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: generate_lesson_content(
                    topic=lesson_request.topic,
                    subject=lesson_request.subject,
                    level=lesson_request.level,
                    language_level=lesson_request.language_level,
                    options=lesson_request.options,
                    description=lesson_request.description,
                    source_text=lesson_request.source_text,
                    interest=lesson_request.interest,
                ),
            ),
            timeout=config.AGENT_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        req_logger.error(f"Agent execution timed out (request_id={request_id})")
        raise HTTPException(
            status_code=504,
            detail=f"Generering tok for lang tid (over {config.AGENT_TIMEOUT_SECONDS // 60} minutter). request_id={request_id}",
        )
    except Exception as e:
        req_logger.error(f"Generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"{USER_FACING_GENERATION_ERROR} (request_id={request_id})")

    image_path, _image_asset, image_caption, image_credit = _materialize_pedagogical_image(
        image_mode=lesson_request.image_mode,
        topic=lesson_request.topic,
        subject=lesson_request.subject,
        level=lesson_request.level,
        text=content.get("text", ""),
        req_logger=req_logger,
        image_data=lesson_request.image_data,
        image_url_override=lesson_request.image_url_override,
    )

    try:
        pdf_bytes = create_lesson_pdf(
            content_text=content["text"],
            worksheet_text=content["worksheet"],
            topic=lesson_request.topic,
            level=lesson_request.level,
            subject=lesson_request.subject,
            language_level=lesson_request.language_level,
            image_path=image_path,
            image_caption=image_caption,
            image_credit=image_credit,
            language_exercises=content.get("language_exercises"),
            options=lesson_request.options,
            faktarapport=content.get("faktarapport"),
        )
    except Exception as e:
        req_logger.error(f"PDF compile failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"{USER_FACING_DOCUMENT_ERROR} (request_id={request_id})")
    finally:
        if image_path:
            try:
                image_processor.cleanup_image(image_path)
            except Exception:
                pass

    cache.set(cache_key, pdf_bytes, expire=config.CACHE_TTL_SECONDS)
    filename = safe_filename("leksjon", lesson_request.topic, lesson_request.level)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )


@app.post("/generate-lesson-json", response_model=LessonResponse)
@limiter.limit(config.RATE_LIMIT_GENERATE)
async def generate_lesson_json(request: Request, lesson_request: LessonRequest):
    request_id = str(uuid.uuid4())[:8]
    req_logger = RequestLogger(logger, {'request_id': request_id})

    cache_key = compute_cache_key("json_lesson", lesson_request)
    if cache_key in cache:
        req_logger.info(f"JSON cache hit: {cache_key[:24]}…")
        return LessonResponse(**cache.get(cache_key))

    try:
        content = generate_lesson_content(
            topic=lesson_request.topic,
            subject=lesson_request.subject,
            level=lesson_request.level,
            language_level=lesson_request.language_level,
            options=lesson_request.options,
            description=lesson_request.description,
            source_text=lesson_request.source_text,
            interest=lesson_request.interest,
        )
    except Exception as e:
        req_logger.error(f"JSON generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"{USER_FACING_GENERATION_ERROR} (request_id={request_id})")

    response_data = {
        "topic": content["topic"],
        "subject": content["subject"],
        "level": content["level"],
        "text": content["text"],
        "worksheet": content.get("worksheet", ""),
        "image_url": content.get("image_url"),
        "language_exercises": content.get("language_exercises"),
        "truth_passport": content.get("truth_passport"),
    }
    cache.set(cache_key, response_data, expire=config.CACHE_TTL_SECONDS)
    return LessonResponse(**response_data)


# ── Recompile PDF without re-running agents ───────────────────────────────────

class RecompileRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=20000)
    worksheet: str = Field("", max_length=20000)
    faktarapport: Optional[str] = Field(None, max_length=5000)
    topic: str = Field(..., min_length=1, max_length=200)
    subject: str = Field(..., min_length=1, max_length=100)
    level: str = Field("VGS")
    language_level: Optional[str] = Field(None)
    options: dict[str, bool] = Field(default_factory=dict)
    image_url: Optional[str] = Field(None, max_length=500)
    language_exercises: Optional[dict] = Field(None)
    truth_verified: bool = False


@app.post("/recompile-lesson")
@limiter.limit("20/minute")
async def recompile_lesson(request: Request, req: RecompileRequest):
    """Recompile a lesson PDF from raw text without running agents. Fast (~3 sec)."""
    request_id = str(uuid.uuid4())[:8]
    req_logger = RequestLogger(logger, {'request_id': request_id})
    req_logger.info(f"Recompile request: topic={req.topic!r} level={req.level}")

    separator = "\n\n<<<SKOLEVERKSTED_OPPGAVER>>>\n\n"
    quality = await asyncio.to_thread(
        run_quality_pipeline,
        generator_id="fag.learning_sheet",
        content=f"{req.text}{separator}{req.worksheet}",
        topic=req.topic,
        subject=req.subject,
        level=req.level,
    )
    if not quality.source_approved or separator not in quality.approved_content:
        raise HTTPException(status_code=409, detail="Forhåndsvisningen ble blokkert av kvalitetskontrollen.")
    req.text, req.worksheet = quality.approved_content.split(separator, 1)
    req.truth_verified = True

    def _compile() -> bytes:
        img_path = fetch_image_with_retry(req.image_url, None, req_logger)
        content_text = req.text
        if not req.truth_verified:
            content_text = (
                "FAKTASTATUS: Innholdet er redigert etter siste faktakontroll. "
                "Kontroller opplysningene før materialet deles med elever.\n\n"
                f"{content_text}"
            )
        try:
            return create_lesson_pdf(
                content_text=content_text,
                worksheet_text=req.worksheet,
                topic=req.topic,
                level=req.level,
                subject=req.subject,
                language_level=req.language_level,
                image_path=img_path,
                language_exercises=req.language_exercises,
                options=req.options,
                faktarapport=req.faktarapport,
            )
        finally:
            if img_path:
                try:
                    image_processor.cleanup_image(img_path)
                except Exception:
                    pass

    try:
        pdf_bytes = await asyncio.to_thread(_compile)
    except Exception as e:
        req_logger.error(f"Recompile failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"{USER_FACING_DOCUMENT_ERROR} (request_id={request_id})")

    filename = safe_filename("rediger", req.topic, req.level)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )


# ── Generate .docx from existing text ────────────────────────────────────────

class DocxRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=20000)
    worksheet: str = Field("", max_length=20000)
    faktarapport: Optional[str] = Field(None, max_length=5000)
    topic: str = Field(..., min_length=1, max_length=200)
    subject: str = Field(..., min_length=1, max_length=100)
    level: str = Field("VGS")
    teacher_approved: bool = False


@app.post("/generate-docx")
@limiter.limit("20/minute")
async def generate_docx(request: Request, req: DocxRequest):
    """Convert lesson text to a .docx Word document. Fast (~1 sec)."""
    request_id = str(uuid.uuid4())[:8]
    req_logger = RequestLogger(logger, {'request_id': request_id})
    req_logger.info(f"Docx request: topic={req.topic!r} level={req.level}")

    export_content = f"{req.text}\n\n<<<SKOLEVERKSTED_OPPGAVER>>>\n\n{req.worksheet}"
    try:
        await asyncio.to_thread(
            verify_teacher_export,
            generator_id="fag.docx",
            export_id="fag.docx",
            content=export_content,
            topic=req.topic,
            subject=req.subject,
            level=req.level,
            teacher_approved=req.teacher_approved,
        )
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    try:
        docx_bytes = await asyncio.to_thread(
            lambda: create_lesson_docx(
                content_text=req.text,
                worksheet_text=req.worksheet,
                topic=req.topic,
                level=req.level,
                subject=req.subject,
                faktarapport=req.faktarapport,
            )
        )
    except Exception as e:
        req_logger.error(f"Docx generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"{USER_FACING_DOCUMENT_ERROR} (request_id={request_id})")

    filename = safe_filename("leksjon", req.topic, req.level).replace(".pdf", ".docx")
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(docx_bytes)),
        },
    )


# ── Wikimedia image search for image picker UI ───────────────────────────────

@app.get("/search-images")
@limiter.limit("30/minute")
async def search_images(request: Request, topic: str, subject: str = "", limit: int = 5):
    """Return up to `limit` Wikimedia image candidates for the image picker UI."""
    if not topic or len(topic) > 200:
        raise HTTPException(status_code=400, detail="Ugyldig tema")
    limit = min(max(limit, 1), 8)

    def _search():
        query = f"{topic} {subject}".strip()
        return _wikimedia_tool.search_candidates(query, subject=subject, limit=limit)

    candidates = await asyncio.to_thread(_search)
    return {
        "candidates": [
            {
                "url": c.image_url,
                "thumb_url": c.thumbnail_url or c.image_url,
                "title": c.title,
                "attribution": c.attribution,
            }
            for c in candidates
            if c.image_url
        ]
    }


# ── LK20 Grep proxy ───────────────────────────────────────────────────────────

@app.get("/grep/goals")
@limiter.limit(config.RATE_LIMIT_GREP)
async def grep_goals(request: Request, subject: str, level: str = "VGS"):
    if not subject or len(subject) > 100:
        raise HTTPException(status_code=400, detail="Ugyldig fagparameter")
    goals = get_competency_goals(subject=subject, level=level)
    return {"subject": subject, "level": level, "goals": goals, "count": len(goals)}
