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
from typing import Optional

import diskcache as dc
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field, field_validator
from pythonjsonlogger import jsonlogger
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

if __package__:
    from . import config
    from .agents import generate_lesson_content, generate_prove_content, generate_sequence_content
    from .tools import WikimediaImageSearchTool
    from .grep_api import get_competency_goals
    from .ndla_service import fetch_ndla_source
    from .docx_service import create_lesson_docx
    from .laeringsark_renderer import (
        build_faktarapport_doc, build_laeringsark_doc, collect_text_fields, parse_oppgaver,
    )
    from .text_pipeline import lint_pdf
    from .pdf_service import (
        compile_typst, create_differentiated_pdf, create_lesson_pdf,
        create_prove_pdf, create_sequence_pdf, parse_worksheet_content,
    )
    from .media_manager import image_processor
    from .job_manager import (
        JobContext, compute_cache_key, fetch_image_with_retry, get_job,
        register_job, run_job_in_thread, safe_filename, start_cleanup_task,
    )
else:
    import config
    from agents import generate_lesson_content, generate_prove_content, generate_sequence_content
    from tools import WikimediaImageSearchTool
    from grep_api import get_competency_goals
    from ndla_service import fetch_ndla_source
    from docx_service import create_lesson_docx
    from laeringsark_renderer import (
        build_faktarapport_doc, build_laeringsark_doc, collect_text_fields, parse_oppgaver,
    )
    from text_pipeline import lint_pdf
    from pdf_service import (
        compile_typst, create_differentiated_pdf, create_lesson_pdf,
        create_prove_pdf, create_sequence_pdf, parse_worksheet_content,
    )
    from media_manager import image_processor
    from job_manager import (
        JobContext, compute_cache_key, fetch_image_with_retry, get_job,
        register_job, run_job_in_thread, safe_filename, start_cleanup_task,
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


class RequestLogger(logging.LoggerAdapter):
    """Logger adapter that injects request_id into every log record."""
    def process(self, msg, kwargs):
        kwargs.setdefault('extra', {})['request_id'] = self.extra.get('request_id', '-')
        return msg, kwargs


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
            "teacher_key": False,
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
                if msg.get("type") in ("done", "error"):
                    break
            except asyncio.TimeoutError:
                yield "data: {\"type\":\"heartbeat\"}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _download_job(job_id: str, default_filename: str = "dokument.pdf",
                        kind: str = "main") -> Response:
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.done:
        raise HTTPException(status_code=202, detail="Generering pågår fortsatt")
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

    # The job is intentionally NOT popped here: a lesson job may have both a
    # student PDF and a teacher fact-report PDF that are downloaded separately.
    # TTL cleanup removes the job afterwards.
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )


# ── Source resolution (teacher-provided or NDLA) ─────────────────────────────

def _resolve_source(req, ctx: "JobContext") -> tuple[Optional[str], Optional[str]]:
    """Determine the grounding source for a generation job.

    Teacher-pasted material always wins. Otherwise, if NDLA grounding is
    enabled, search NDLA's open learning resources for a relevant article.
    Returns (source_text, source_name); both None when no source is available.
    """
    if req.source_text:
        return req.source_text, "lærerens kildemateriale"
    if getattr(req, "use_ndla", False):
        ctx.push("Søker etter kildegrunnlag på NDLA...")
        language = "en" if req.subject.lower() == "engelsk" else "nb"
        ndla = fetch_ndla_source(req.topic, language=language)
        if ndla:
            ctx.push(f"Kildeforankrer i NDLA: {ndla['title']}")
            return ndla["text"], f"NDLA: {ndla['title']}"
        ctx.push("Fant ingen passende NDLA-kilde — fortsetter uten kildeforankring.")
    return None, None


# ── Worker: standard læringsark ───────────────────────────────────────────────

def _lesson_worker(ctx: JobContext) -> tuple[bytes, str]:
    req = ctx.request_payload  # LessonRequest
    # When regenerating from an existing text the main text is reused as-is,
    # so fetching a new source would have no effect.
    if req.basis_text:
        source_text, source_name = req.source_text, ("lærerens kildemateriale" if req.source_text else None)
    else:
        source_text, source_name = _resolve_source(req, ctx)
    ctx.push("Genererer fagtekst og søker etter bilde..." if not req.basis_text else "Bruker eksisterende fagtekst, regenererer oppgaver...")
    content = generate_lesson_content(
        topic=req.topic,
        subject=req.subject,
        level=req.level,
        language_level=req.language_level,
        options=req.options,
        description=req.description,
        source_text=source_text,
        interest=req.interest,
        basis_text=req.basis_text,
        progress_callback=ctx.push,
    )

    if ctx.set_meta:
        ctx.set_meta("basis_text", content.get("text"))
        ctx.set_meta("image_url", content.get("image_url") or req.image_url_override)
        ctx.set_meta("worksheet_text", content.get("worksheet"))
        ctx.set_meta("faktarapport_text", content.get("faktarapport"))
        ctx.set_meta("language_exercises", content.get("language_exercises"))
        ctx.set_meta("warnings", content.get("warnings"))
        ctx.set_meta("source_grounded", content.get("source_grounded"))
        ctx.set_meta("source_name", source_name)
        ctx.set_meta("prompt_version", content.get("prompt_version"))

    ctx.push("Henter og optimaliserer bilde...")
    image_path = fetch_image_with_retry(
        req.image_url_override or content.get("image_url"),
        req.image_data,
        ctx.req_logger,
    )

    structured = content.get("structured")
    rapport_payload = content.get("faktarapport_structured") or content.get("faktarapport")

    try:
        ctx.push("Kompilerer PDF...")
        if structured:
            # Redesigned layout (SPEC_laeringsark_redesign DEL 2): margin
            # terms, numbered colour-stripe sections, purple task boxes.
            sections = parse_worksheet_content(content.get("worksheet") or "")
            oppgaver = parse_oppgaver(sections["comprehension"], sections["discussion"])
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
                har_k_markorer="[K]" in collect_text_fields(structured),
                laeringsmaal=sections.get("learning_goals", ""),
                oppgaver=oppgaver,
                image_filename=os.path.basename(image_path) if image_path else None,
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

    # ── Separate teacher fact-report PDF (spec 2.8) ──
    if rapport_payload:
        try:
            ctx.push("Kompilerer faktarapport (egen PDF til læreren)...")
            rapport_doc = build_faktarapport_doc(
                rapport_payload, fag=req.subject, tema=req.topic, kilde=source_name,
            )
            rapport_pdf = compile_typst(rapport_doc)
            if ctx.set_meta:
                ctx.set_meta("rapport_pdf", rapport_pdf)
                ctx.set_meta("rapport_filename",
                             safe_filename("faktarapport", req.topic, req.level))
        except Exception as e:
            ctx.req_logger.error(f"Faktarapport PDF failed: {e}", exc_info=True)
            ctx.push("⚠ Faktarapporten kunne ikke kompileres som egen PDF.")

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

    source_text, source_name = _resolve_source(req, ctx)
    ctx.push("Genererer fagtekst og søker etter bilde...")
    content = generate_lesson_content(
        topic=req.topic,
        subject=req.subject,
        level=req.level,
        language_level=req.language_level,
        options=options,
        description=req.description,
        source_text=source_text,
        interest=req.interest,
        progress_callback=ctx.push,
    )

    if ctx.set_meta:
        ctx.set_meta("source_grounded", content.get("source_grounded"))
        ctx.set_meta("source_name", source_name)
        ctx.set_meta("prompt_version", content.get("prompt_version"))

    ctx.push("Henter og optimaliserer bilde...")
    image_path = fetch_image_with_retry(
        content.get("image_url"),
        req.image_data,
        ctx.req_logger,
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
    source_text, source_name = _resolve_source(req, ctx)
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

    ctx.push("Henter og optimaliserer bilde...")
    image_path = fetch_image_with_retry(content.get("image_url"), None, ctx.req_logger)

    try:
        ctx.push("Kompilerer prøve-PDF...")
        prove_json = content.get("prove_json") or {}
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

    ctx.push("Kompilerer sekvensplan-PDF...")
    pdf_bytes = create_sequence_pdf(
        sequence_json=content.get("sequence_json", {}),
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
                      cache_key=cache_key, cache=cache)
    return {"job_id": job_id}


@app.get("/generate-lesson-stream/{job_id}")
async def lesson_stream(job_id: str, request: Request):
    return await _stream_job(job_id, request)


@app.get("/generate-lesson-download/{job_id}")
async def download_lesson(job_id: str):
    return await _download_job(job_id, "leksjon.pdf")


@app.get("/generate-lesson-download-rapport/{job_id}")
async def download_lesson_rapport(job_id: str):
    """Separate teacher fact-report PDF (never part of the student PDF)."""
    return await _download_job(job_id, "faktarapport.pdf", kind="rapport")


# ── Endpoints: differensiert ──────────────────────────────────────────────────

@app.post("/generate-differentiated-start")
@limiter.limit(config.RATE_LIMIT_GENERATE)
async def start_differentiated_generation(request: Request, lesson_request: LessonRequest):
    job_id, queue = register_job()
    # Differensiering varies enough that we don't share PDF cache with standard lesson.
    cache_key = compute_cache_key("pdf_diff", lesson_request)
    run_job_in_thread(job_id, queue, lesson_request, _differentiated_worker,
                      cache_key=cache_key, cache=cache)
    return {"job_id": job_id}


# ── Endpoints: prøve ──────────────────────────────────────────────────────────

@app.post("/generate-prove-start")
@limiter.limit(config.RATE_LIMIT_GENERATE)
async def start_prove_generation(request: Request, prove_request: ProveRequest):
    job_id, queue = register_job()
    cache_key = compute_cache_key("pdf_prove", prove_request)
    run_job_in_thread(job_id, queue, prove_request, _prove_worker,
                      cache_key=cache_key, cache=cache)
    return {"job_id": job_id}


@app.get("/generate-prove-stream/{job_id}")
async def prove_stream(job_id: str, request: Request):
    return await _stream_job(job_id, request)


@app.get("/generate-prove-download/{job_id}")
async def download_prove(job_id: str):
    return await _download_job(job_id, "prove.pdf")


# ── Endpoints: sekvensplan ────────────────────────────────────────────────────

@app.post("/generate-sequence-start")
@limiter.limit(config.RATE_LIMIT_GENERATE)
async def start_sequence_generation(request: Request, seq_request: SequenceRequest):
    job_id, queue = register_job()
    cache_key = compute_cache_key("pdf_sequence", seq_request)
    run_job_in_thread(job_id, queue, seq_request, _sequence_worker,
                      cache_key=cache_key, cache=cache)
    return {"job_id": job_id}


@app.get("/generate-sequence-stream/{job_id}")
async def sequence_stream(job_id: str, request: Request):
    return await _stream_job(job_id, request)


@app.get("/generate-sequence-download/{job_id}")
async def download_sequence(job_id: str):
    return await _download_job(job_id, "sekvensplan.pdf")


# ── Legacy synchronous endpoints (kept for backwards-compat callers) ─────────

@app.post("/generate-lesson", response_class=Response)
@limiter.limit(config.RATE_LIMIT_GENERATE)
async def generate_lesson_sync(request: Request, lesson_request: LessonRequest):
    """Synchronous lesson generation. Prefer /generate-lesson-start for UX."""
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
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e} (request_id={request_id})")

    image_path = fetch_image_with_retry(
        content.get("image_url"), lesson_request.image_data, req_logger,
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
            language_exercises=content.get("language_exercises"),
            options=lesson_request.options,
            faktarapport=content.get("faktarapport"),
        )
    except Exception as e:
        req_logger.error(f"PDF compile failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"PDF-feil: {e} (request_id={request_id})")
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
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e} (request_id={request_id})")

    response_data = {
        "topic": content["topic"],
        "subject": content["subject"],
        "level": content["level"],
        "text": content["text"],
        "worksheet": content.get("worksheet", ""),
        "image_url": content.get("image_url"),
        "language_exercises": content.get("language_exercises"),
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


@app.post("/recompile-lesson")
@limiter.limit("20/minute")
async def recompile_lesson(request: Request, req: RecompileRequest):
    """Recompile a lesson PDF from raw text without running agents. Fast (~3 sec)."""
    request_id = str(uuid.uuid4())[:8]
    req_logger = RequestLogger(logger, {'request_id': request_id})
    req_logger.info(f"Recompile request: topic={req.topic!r} level={req.level}")

    def _compile() -> bytes:
        img_path = fetch_image_with_retry(req.image_url, None, req_logger)
        try:
            return create_lesson_pdf(
                content_text=req.text,
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
        raise HTTPException(status_code=500, detail=f"PDF-feil: {e} (request_id={request_id})")

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


@app.post("/generate-docx")
@limiter.limit("20/minute")
async def generate_docx(request: Request, req: DocxRequest):
    """Convert lesson text to a .docx Word document. Fast (~1 sec)."""
    request_id = str(uuid.uuid4())[:8]
    req_logger = RequestLogger(logger, {'request_id': request_id})
    req_logger.info(f"Docx request: topic={req.topic!r} level={req.level}")

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
        raise HTTPException(status_code=500, detail=f"Docx-feil: {e} (request_id={request_id})")

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
