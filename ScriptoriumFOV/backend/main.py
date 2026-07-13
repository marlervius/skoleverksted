from __future__ import annotations

import io
import json
import logging
import os
import re
import tempfile
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated, Literal, Optional, Dict

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

if __package__:
    from .agents import generate_lesson_content
    from .config import ALLOWED_IMAGE_TYPES, MAX_IMAGE_BYTES, PDF_THREAD_POOL_WORKERS, RATE_LIMIT_PER_MINUTE
    from .errors import GeminiQuotaExceededError
    from .auth import app_password_configured, require_app_password, verify_password_plain
    from .pdf_service import create_lesson_pdf
    from .media_manager import image_processor
    from .progress_store import (
        get_progress, is_json_preview_ready, is_pdf_ready, is_zip_ready,
        merge_progress, progress_backend_label, update_progress,
    )
else:
    from agents import generate_lesson_content
    from config import ALLOWED_IMAGE_TYPES, MAX_IMAGE_BYTES, PDF_THREAD_POOL_WORKERS, RATE_LIMIT_PER_MINUTE
    from errors import GeminiQuotaExceededError
    from auth import app_password_configured, require_app_password, verify_password_plain
    from pdf_service import create_lesson_pdf
    from media_manager import image_processor
    from progress_store import (
        get_progress, is_json_preview_ready, is_pdf_ready, is_zip_ready,
        merge_progress, progress_backend_label, update_progress,
    )

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# User-visible error (never leak internal exception strings to clients)
USER_FACING_GENERATION_ERROR = (
    "Noe gikk galt under generering. Prøv igjen litt senere, eller kontakt support."
)


def _public_progress_error(exc: Exception) -> str:
    """Log full error; return safe message for progress JSON."""
    logger.exception("Generation task failed: %s", exc)
    if isinstance(exc, GeminiQuotaExceededError):
        return exc.user_message
    return USER_FACING_GENERATION_ERROR


# Thread pool for CPU-bound PDF generation tasks
_executor = ThreadPoolExecutor(max_workers=PDF_THREAD_POOL_WORKERS)

# Dependency: Bearer password when APP_PASSWORD is set
AuthPasswordDep = Annotated[None, Depends(require_app_password)]


def _safe_filename(topic: str) -> str:
    """Convert a topic string into a safe filename (no special chars)."""
    return "".join(
        c if c.isalnum() or c in (' ', '-', '_') else '_'
        for c in topic[:50]
    ).strip()


def _process_image_for_content(content: dict) -> Optional[str]:
    """Download and optimise the image URL found in content. Returns local path or None."""
    image_url = content.get("image_url")
    if not image_url:
        logger.info("No image URL found, proceeding without image")
        return None

    logger.info(f"Processing image from: {image_url[:100]}...")
    processed_path = image_processor.process_image(image_url)

    # If thumbnail failed, try the original full-size URL as fallback
    if not processed_path and '/thumb/' in image_url:
        original_pattern = (
            r'(https://upload\.wikimedia\.org/wikipedia/commons)'
            r'/thumb(/[a-f0-9]/[a-f0-9]{2}/[^/]+)/\d+px-[^/]+'
        )
        original_match = re.match(original_pattern, image_url, re.IGNORECASE)
        if original_match:
            original_url = original_match.group(1) + original_match.group(2)
            logger.info(f"Thumbnail failed, trying original: {original_url[:100]}...")
            processed_path = image_processor.process_image(original_url)

    if processed_path:
        logger.info(f"Image optimized: {processed_path}")
    else:
        logger.warning("Image processing failed, proceeding without image")
    return processed_path


def _cleanup_image(path: Optional[str]) -> None:
    """Remove a temporary image file if it exists."""
    if path and os.path.exists(path):
        try:
            os.remove(path)
            logger.info(f"Cleaned up temporary image: {path}")
        except Exception as e:
            logger.warning(f"Failed to clean up image {path}: {e}")


def generate_lesson_background(
    generation_id: str,
    request: "LessonRequest",
    pre_processed_image_path: str = None
):
    """Background task to generate the lesson PDF."""
    processed_image_path = pre_processed_image_path
    try:
        # Step 1: Generate lesson content using AI agents
        update_progress(generation_id, 1, 4, "Skriver pedagogisk tekst og finner relevant bilde...")
        logger.info(f"Generating lesson: {request.topic} ({request.subject}, {request.level})")
        content = generate_lesson_content(
            topic=request.topic,
            subject=request.subject,
            level=request.level,
            options=request.options,
            difficulty_modifier=getattr(request, 'difficulty_modifier', None),
            special_instructions=getattr(request, 'special_instructions', None),
            series=getattr(request, 'series', None),
        )

        # Step 2: Process the image (skip if caller already provided a local path)
        update_progress(generation_id, 2, 4, "Behandler og optimaliserer bilde...")
        if not processed_image_path:
            processed_image_path = _process_image_for_content(content)

        # Step 3: Create PDF from the generated content
        update_progress(generation_id, 3, 4, "Formaterer og kompilerer PDF...")
        pdf_bytes = create_lesson_pdf(
            content_text=content["text"],
            worksheet_text=content["worksheet"],
            topic=request.topic,
            level=request.level,
            subject=request.subject,
            image_path=processed_image_path,
            language_exercises=content.get("language_exercises"),
            options=request.options,
            teacher_key_content=content.get("teacher_key_content", ""),
            series_header=content.get("series_header", ""),
            accessibility=getattr(request, 'accessibility', None),
        )

        # Step 4: Store PDF bytes in progress for retrieval
        update_progress(generation_id, 4, 4, "Ferdig! PDF klar for nedlasting.")
        fname = _safe_filename(request.topic) + ".pdf"
        merge_progress(generation_id, pdf_bytes=pdf_bytes, filename=fname)

        logger.info(f"PDF generated successfully: {fname} ({len(pdf_bytes)} bytes)")

    except Exception as e:
        update_progress(generation_id, -1, 4, _public_progress_error(e))
    finally:
        _cleanup_image(processed_image_path)


limiter = Limiter(key_func=get_remote_address, default_limits=[RATE_LIMIT_PER_MINUTE])

app = FastAPI(
    title="Scriptorium API",
    description="Scriptorium — PDF lesson plans for adult immigrants learning Norwegian (CEFR levels)",
    version="1.0.0"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS for frontend communication
# Use ALLOWED_ORIGINS env var (comma-separated) to define allowed origins.
# Defaults to localhost for local development. Never use "*" in production.
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
if allowed_origins_env.strip() == "*":
    logger.warning(
        "CORS is configured with wildcard '*'. "
        "This is insecure — set ALLOWED_ORIGINS to specific domain(s) in production."
    )
    allowed_origins = ["*"]
    allow_credentials = False
else:
    allowed_origins = [origin.strip() for origin in allowed_origins_env.split(",") if origin.strip()]
    allow_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LessonRequest(BaseModel):
    """Request model for lesson generation."""
    topic: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="The topic for the lesson (e.g., 'Kildesortering', 'Norsk arbeidsliv')",
        examples=["Kildesortering og resirkulering"]
    )
    subject: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="The subject area (e.g., 'Samfunnsfag', 'Naturfag', 'Norsk')",
        examples=["Samfunnsfag"]
    )
    level: Literal["A1.1", "A1.2", "A2.1", "A2.2", "B1.1", "B1.2", "B2.1", "B2.2"] = Field(
        ...,
        description="CEFR language level with sub-levels",
        examples=["A2.1"]
    )
    difficulty_modifier: Optional[int] = Field(
        default=None,
        ge=-2,
        le=2,
        description="Optional difficulty modifier (-2 to +2) to fine-tune content complexity within the selected level",
        examples=[-1]
    )
    options: dict[str, bool] = Field(
        default_factory=lambda: {
            "deep_dive": False,
            "grammar_tasks": True,
            "vocabulary_tasks": True,
            "comprehension_tasks": True,
            "discussion_tasks": True,
            "teacher_key": False,
            # Advanced modules
            "role_play": False,
            "image_description": False,
            "writing_frame": False,
            "cultural_comparison": False,
            "real_case": False
        },
        description="Modular options for lesson generation including advanced modules"
    )
    special_instructions: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional free-text instructions from the teacher (max 500 characters)"
    )
    series: Optional[dict] = Field(
        default=None,
        description="Optional series info: {lesson_number, total_lessons, series_theme}"
    )
    accessibility: Optional[dict] = Field(
        default=None,
        description="Optional accessibility options: {dyslexia_font, high_contrast, large_print}"
    )


CefrLevel = Literal["A1.1", "A1.2", "A2.1", "A2.2", "B1.1", "B1.2", "B2.1", "B2.2"]


class MultiLevelLessonRequest(BaseModel):
    """Same as lesson generation, but 2–3 CEFR levels at once (one PDF per level, delivered as ZIP)."""

    topic: str = Field(..., min_length=1, max_length=200)
    subject: str = Field(..., min_length=1, max_length=100)
    levels: list[CefrLevel] = Field(
        ...,
        min_length=2,
        max_length=3,
        description="Two or three distinct CEFR sub-levels for the same topic",
    )
    difficulty_modifier: Optional[int] = Field(default=None, ge=-2, le=2)
    options: dict[str, bool] = Field(default_factory=dict)
    special_instructions: Optional[str] = Field(default=None, max_length=500)
    series: Optional[dict] = Field(default=None)
    accessibility: Optional[dict] = Field(default=None)

    @field_validator("levels")
    @classmethod
    def levels_unique(cls, v: list[str]) -> list[str]:
        if len(set(v)) != len(v):
            raise ValueError("Nivåer må være ulike (ingen duplikater).")
        return v

    def to_base_lesson_request(self, level: CefrLevel) -> "LessonRequest":
        """Build a single-level request (for helpers that expect LessonRequest)."""
        kwargs: dict = {
            "topic": self.topic,
            "subject": self.subject,
            "level": level,
            "difficulty_modifier": self.difficulty_modifier,
            "special_instructions": self.special_instructions,
            "series": self.series,
            "accessibility": self.accessibility,
        }
        if self.options:
            kwargs["options"] = self.options
        return LessonRequest(**kwargs)


class SeriesInfo(BaseModel):
    lesson_number: int = Field(..., ge=1, le=20)
    total_lessons: int = Field(..., ge=2, le=20)
    series_theme: str = Field(..., max_length=100)


class PreviewPDFRequest(BaseModel):
    """Request model for converting preview JSON to PDF."""
    topic: str
    subject: str
    level: str
    text: str
    worksheet: str
    image_url: Optional[str] = None
    language_exercises: Optional[dict] = None
    options: dict[str, bool]
    accessibility: Optional[dict] = None

class LessonResponse(BaseModel):
    """Response model for lesson content (JSON format)."""
    topic: str
    subject: str
    level: str
    text: str
    worksheet: str
    image_url: Optional[str] = None
    language_exercises: Optional[dict] = None


class PasswordVerifyBody(BaseModel):
    password: str = Field(..., min_length=1, max_length=500)


# ---------------------------------------------------------------------------
# Health / utility endpoints
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    """Health check endpoint."""
    return {"message": "Hello World - Scriptorium API is running!"}


@app.get("/health")
async def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "progress_store": progress_backend_label(),
        "password_required": app_password_configured(),
    }


@app.get("/auth/config")
async def auth_config():
    """Tell the frontend whether a password is required (without revealing it)."""
    return {"password_required": app_password_configured()}


@app.post("/auth/verify")
async def auth_verify(body: PasswordVerifyBody):
    """Check password before the client stores it (e.g. sessionStorage)."""
    if not app_password_configured():
        return {"ok": True, "password_required": False}
    if verify_password_plain(body.password):
        return {"ok": True, "password_required": True}
    raise HTTPException(status_code=401, detail="Feil passord.")


# ---------------------------------------------------------------------------
# Progress / download endpoints
# ---------------------------------------------------------------------------

@app.get("/generation-status/{generation_id}")
def get_generation_status(generation_id: str, _auth: AuthPasswordDep):
    """
    Get the progress status of a PDF generation task.

    Returns:
        JSON with step, total_steps, message, and timestamp
    """
    progress = get_progress(generation_id)
    if progress is None:
        raise HTTPException(status_code=404, detail="Generation task not found")
    # Exclude binary fields (pdf_bytes, zip_bytes) — not JSON-serializable
    return {k: v for k, v in progress.items() if not isinstance(v, bytes)}


@app.get("/download-pdf/{generation_id}")
def download_pdf(generation_id: str, _auth: AuthPasswordDep):
    """
    Download the completed PDF for a generation task.

    Returns:
        PDF file download
    """
    progress = get_progress(generation_id)
    if progress is None:
        raise HTTPException(status_code=404, detail="Generation task not found")

    if not is_pdf_ready(progress):
        raise HTTPException(status_code=202, detail="PDF not ready yet")

    pdf_bytes = progress.get("pdf_bytes")
    filename = progress.get("filename", "lesson.pdf")

    if not pdf_bytes:
        raise HTTPException(status_code=500, detail="PDF data not available")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
            "Content-Length": str(len(pdf_bytes))
        }
    )


@app.get("/download-zip/{generation_id}")
def download_zip(generation_id: str, _auth: AuthPasswordDep):
    """
    Download a ZIP archive containing two PDFs (dual-version generation).

    Returns:
        ZIP file download
    """
    progress = get_progress(generation_id)
    if progress is None:
        raise HTTPException(status_code=404, detail="Generation task not found")

    if not is_zip_ready(progress):
        raise HTTPException(status_code=202, detail="ZIP not ready yet")

    zip_bytes = progress.get("zip_bytes")
    filename = progress.get("filename", "lessons.zip")

    if not zip_bytes:
        raise HTTPException(status_code=500, detail="ZIP data not available")

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
            "Content-Length": str(len(zip_bytes))
        }
    )


# ---------------------------------------------------------------------------
# Main lesson generation endpoints
# ---------------------------------------------------------------------------

@app.post("/generate-lesson")
@limiter.limit("5/minute")
async def generate_lesson(
    lesson_request: "LessonRequest",
    request: Request,
    background_tasks: BackgroundTasks,
    _auth: AuthPasswordDep,
):
    """
    Start PDF lesson plan generation based on the provided topic, subject, and CEFR level.

    Returns:
        JSON with generation_id for tracking progress via /generation-status/{id}
    """
    generation_id = str(uuid.uuid4())
    update_progress(generation_id, 0, 4, "Starter generering...")
    background_tasks.add_task(generate_lesson_background, generation_id, lesson_request)

    return {"generation_id": generation_id}


def generate_lesson_json_background(
    generation_id: str,
    lesson_request: "LessonRequest"
):
    """Background task to generate JSON preview."""
    try:
        update_progress(generation_id, 1, 2, "Skriver pedagogisk tekst og finner bilde...")
        
        content = generate_lesson_content(
            topic=lesson_request.topic,
            subject=lesson_request.subject,
            level=lesson_request.level,
            options=lesson_request.options,
            difficulty_modifier=lesson_request.difficulty_modifier,
            special_instructions=lesson_request.special_instructions,
            series=lesson_request.series,
        )
        
        update_progress(generation_id, 2, 2, "Forhåndsvisning er klar!")
        merge_progress(
            generation_id,
            json_data={
                "topic": content["topic"],
                "subject": content["subject"],
                "level": content["level"],
                "text": content["text"],
                "worksheet": content["worksheet"],
                "image_url": content.get("image_url"),
                "language_exercises": content.get("language_exercises"),
            },
        )

    except Exception as e:
        update_progress(generation_id, -1, 2, _public_progress_error(e))

@app.post("/generate-lesson-json")
@limiter.limit("5/minute")
async def generate_lesson_json(
    lesson_request: "LessonRequest",
    request: Request,
    background_tasks: BackgroundTasks,
    _auth: AuthPasswordDep,
):
    """
    Start JSON preview generation in the background.

    Returns:
        JSON with generation_id for tracking progress via /generation-status/{id}
    """
    generation_id = str(uuid.uuid4())
    update_progress(generation_id, 0, 2, "Starter forhåndsvisning...")
    background_tasks.add_task(generate_lesson_json_background, generation_id, lesson_request)

    return {"generation_id": generation_id}

@app.get("/download-json/{generation_id}", response_model=LessonResponse)
def download_json(generation_id: str, _auth: AuthPasswordDep):
    """Get the completed JSON preview."""
    progress = get_progress(generation_id)
    if progress is None:
        raise HTTPException(status_code=404, detail="Generation task not found")

    if not is_json_preview_ready(progress):
        raise HTTPException(status_code=202, detail="JSON not ready yet")

    json_data = progress.get("json_data")
    if not json_data:
        raise HTTPException(status_code=500, detail="JSON data not available")
        
    return json_data


def generate_pdf_from_json_background(
    generation_id: str,
    request: PreviewPDFRequest,
    processed_image_path: str = None
):
    """Background task to generate PDF directly from JSON (skipping AI steps)."""
    try:
        update_progress(generation_id, 1, 3, "Behandler og optimaliserer bilde...")
        
        # Process image if needed
        if not processed_image_path and request.image_url:
            content_dict = {"image_url": request.image_url}
            processed_image_path = _process_image_for_content(content_dict)
            
        update_progress(generation_id, 2, 3, "Formaterer og kompilerer PDF...")
        
        pdf_bytes = create_lesson_pdf(
            content_text=request.text,
            worksheet_text=request.worksheet,
            topic=request.topic,
            level=request.level,
            subject=request.subject,
            image_path=processed_image_path,
            language_exercises=request.language_exercises,
            options=request.options,
            accessibility=getattr(request, "accessibility", None),
        )

        # Store PDF
        update_progress(generation_id, 3, 3, "Ferdig! PDF klar for nedlasting.")
        merge_progress(
            generation_id,
            pdf_bytes=pdf_bytes,
            filename=_safe_filename(request.topic) + ".pdf",
        )

    except Exception as e:
        update_progress(generation_id, -1, 3, _public_progress_error(e))
    finally:
        _cleanup_image(processed_image_path)

@app.post("/generate-pdf-from-json")
@limiter.limit("5/minute")
async def generate_pdf_from_json(
    preview_request: PreviewPDFRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    _auth: AuthPasswordDep,
):
    """Generate PDF directly from preview content."""
    generation_id = str(uuid.uuid4())
    update_progress(generation_id, 0, 3, "Starter PDF-generering...")
    background_tasks.add_task(generate_pdf_from_json_background, generation_id, preview_request)
    
    return {"generation_id": generation_id}

# ---------------------------------------------------------------------------
# #3 Dual-version generation
# ---------------------------------------------------------------------------

# Adjacent level map for dual generation
_ADJACENT_LEVELS: Dict[str, tuple] = {
    "A1.1": ("A1.1", "A1.2"),
    "A1.2": ("A1.1", "A1.2"),
    "A2.1": ("A2.1", "A2.2"),
    "A2.2": ("A2.1", "A2.2"),
    "B1.1": ("B1.1", "B1.2"),
    "B1.2": ("B1.1", "B1.2"),
    "B2.1": ("B2.1", "B2.2"),
    "B2.2": ("B2.1", "B2.2"),
}


def _generate_single_pdf(request: "LessonRequest", level_override: str) -> tuple[bytes, str]:
    """
    Synchronous helper that generates one complete PDF for a given level.
    Returns (pdf_bytes, filename).
    """
    import copy
    req = copy.copy(request)
    # Override level on a plain dict so we don't need to recreate the Pydantic model
    content = generate_lesson_content(
        topic=req.topic,
        subject=req.subject,
        level=level_override,
        options=req.options,
        difficulty_modifier=req.difficulty_modifier,
        special_instructions=req.special_instructions,
        series=req.series,
    )

    processed_image_path = _process_image_for_content(content)
    try:
        pdf_bytes = create_lesson_pdf(
            content_text=content["text"],
            worksheet_text=content["worksheet"],
            topic=req.topic,
            level=level_override,
            subject=req.subject,
            image_path=processed_image_path,
            language_exercises=content.get("language_exercises"),
            options=req.options,
            teacher_key_content=content.get("teacher_key_content", ""),
            series_header=content.get("series_header", ""),
            accessibility=req.accessibility,
        )
    finally:
        _cleanup_image(processed_image_path)

    filename = _safe_filename(req.topic) + f"_{level_override}.pdf"
    return pdf_bytes, filename


def _generate_dual_background(generation_id: str, lesson_req: "LessonRequest"):
    """Background task: generate two adjacent-level PDFs and zip them."""
    try:
        level_a, level_b = _ADJACENT_LEVELS.get(
            lesson_req.level, (lesson_req.level, lesson_req.level)
        )
        update_progress(
            generation_id,
            1,
            4,
            f"Genererer versjoner for {level_a} og {level_b} (parallelt)...",
        )

        fut_a = _executor.submit(_generate_single_pdf, lesson_req, level_a)
        fut_b = _executor.submit(_generate_single_pdf, lesson_req, level_b)
        pdf_a, name_a = fut_a.result()
        pdf_b, name_b = fut_b.result()

        update_progress(generation_id, 3, 4, "Pakker PDF-er til ZIP...")
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(name_a, pdf_a)
            zf.writestr(name_b, pdf_b)
        zip_bytes = zip_buffer.getvalue()

        update_progress(generation_id, 4, 4, "Ferdig! ZIP klar for nedlasting.")
        merge_progress(
            generation_id,
            zip_bytes=zip_bytes,
            filename=_safe_filename(lesson_req.topic) + "_dual.zip",
        )
        logger.info(f"Dual PDF ZIP generated: {len(zip_bytes)} bytes")

    except Exception as e:
        update_progress(generation_id, -1, 4, _public_progress_error(e))


@app.post("/generate-dual-lesson")
@limiter.limit("5/minute")
async def generate_dual_lesson(
    lesson_request: "LessonRequest",
    request: Request,
    background_tasks: BackgroundTasks,
    _auth: AuthPasswordDep,
):
    """
    Generate two PDF lesson plans for adjacent sub-levels (e.g. A2.1 + A2.2).

    Returns a generation_id; poll /generation-status/{id} then download the ZIP from /download-zip/{id}.
    """
    generation_id = str(uuid.uuid4())
    update_progress(generation_id, 0, 4, "Starter dual generering...")
    background_tasks.add_task(_generate_dual_background, generation_id, lesson_request)

    return {"generation_id": generation_id, "dual": True}


def _generate_multi_level_background(generation_id: str, lesson_req: "MultiLevelLessonRequest"):
    """Background task: generate 2–3 PDFs for different CEFR levels (same topic) and zip them."""
    try:
        levels = list(lesson_req.levels)
        n = len(levels)
        update_progress(
            generation_id,
            1,
            4,
            f"Genererer {n} PDF-er for {', '.join(levels)} (parallelt)...",
        )

        base = lesson_req.to_base_lesson_request(levels[0])
        futures = [_executor.submit(_generate_single_pdf, base, lvl) for lvl in levels]
        zip_parts: list[tuple[bytes, str]] = []
        for fut in futures:
            zip_parts.append(fut.result())

        update_progress(generation_id, 3, 4, "Pakker PDF-er til ZIP...")
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for pdf_bytes, name in zip_parts:
                zf.writestr(name, pdf_bytes)
        zip_bytes = zip_buffer.getvalue()

        update_progress(generation_id, 4, 4, "Ferdig! ZIP klar for nedlasting.")
        merge_progress(
            generation_id,
            zip_bytes=zip_bytes,
            filename=_safe_filename(lesson_req.topic) + "_flerniva.zip",
        )
        logger.info("Multi-level PDF ZIP generated: %s bytes (%s levels)", len(zip_bytes), n)

    except Exception as e:
        update_progress(generation_id, -1, 4, _public_progress_error(e))


@app.post("/generate-multi-lesson")
@limiter.limit("5/minute")
async def generate_multi_lesson(
    lesson_request: MultiLevelLessonRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    _auth: AuthPasswordDep,
):
    """
    Generate 2–3 PDF lesson plans for the same topic at different CEFR sub-levels.

    Returns generation_id; poll /generation-status/{id} then download ZIP from /download-zip/{id}.
    """
    generation_id = str(uuid.uuid4())
    update_progress(generation_id, 0, 4, "Starter flernivå-generering...")
    background_tasks.add_task(_generate_multi_level_background, generation_id, lesson_request)

    return {"generation_id": generation_id, "zip_download": True}


# ---------------------------------------------------------------------------
# #5 Custom image upload
# ---------------------------------------------------------------------------

# Image upload constraints (from config)
_ALLOWED_IMAGE_TYPES = ALLOWED_IMAGE_TYPES
_MAX_IMAGE_BYTES = MAX_IMAGE_BYTES


@app.post("/generate-lesson-with-image")
@limiter.limit("5/minute")
async def generate_lesson_with_image(
    request: Request,
    background_tasks: BackgroundTasks,
    _auth: AuthPasswordDep,
    topic: str = Form(..., min_length=1, max_length=200),
    subject: str = Form(..., min_length=1, max_length=100),
    level: str = Form(...),
    difficulty_modifier: Optional[int] = Form(default=None),
    options: Optional[str] = Form(default=None, description="JSON string of options dict"),
    special_instructions: Optional[str] = Form(default=None, max_length=500),
    series: Optional[str] = Form(default=None, description="JSON string of series dict"),
    accessibility: Optional[str] = Form(default=None, description="JSON string of accessibility dict"),
    image: UploadFile = File(..., description="Custom image (JPEG/PNG/WebP, max 5 MB)"),
):
    """
    Generate a PDF lesson plan using a teacher-supplied image instead of a Wikimedia image.

    Send as multipart/form-data. The `options`, `series`, and `accessibility` fields
    are JSON-encoded strings.

    Returns:
        JSON with generation_id for tracking progress
    """
    # --- Validate level ---
    valid_levels = {"A1.1", "A1.2", "A2.1", "A2.2", "B1.1", "B1.2", "B2.1", "B2.2"}
    if level not in valid_levels:
        raise HTTPException(status_code=422, detail=f"Invalid level: {level}")

    # --- Validate uploaded image ---
    content_type = image.content_type or ""
    if content_type not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported image type '{content_type}'. Allowed: JPEG, PNG, WebP."
        )

    image_data = await image.read()
    if len(image_data) > _MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image too large. Maximum size is 5 MB.")
    if not image_data:
        raise HTTPException(status_code=400, detail="Uploaded image is empty.")

    # --- Save image to a temporary file ---
    suffix = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }.get(content_type, ".jpg")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        tmp.write(image_data)
        tmp.flush()
        tmp_path = tmp.name
    finally:
        tmp.close()

    # --- Optimise the uploaded image via the media manager ---
    processed_image_path = image_processor.process_image_from_path(tmp_path)
    try:
        os.remove(tmp_path)
    except OSError:
        pass

    if not processed_image_path:
        raise HTTPException(
            status_code=422,
            detail="Could not process the uploaded image. Please try a different file."
        )

    # --- Parse JSON form fields ---
    try:
        parsed_options = json.loads(options) if options else {}
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="'options' must be valid JSON.")
    try:
        parsed_series = json.loads(series) if series else None
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="'series' must be valid JSON.")
    try:
        parsed_accessibility = json.loads(accessibility) if accessibility else None
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="'accessibility' must be valid JSON.")

    lesson_request = LessonRequest(
        topic=topic,
        subject=subject,
        level=level,  # type: ignore[arg-type]
        difficulty_modifier=difficulty_modifier,
        options=parsed_options if parsed_options else {
            "deep_dive": False,
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
        },
        special_instructions=special_instructions,
        series=parsed_series,
        accessibility=parsed_accessibility,
    )

    generation_id = str(uuid.uuid4())
    update_progress(generation_id, 0, 4, "Starter generering med opplastet bilde...")

    # Pass the pre-processed image path so background task skips URL download
    background_tasks.add_task(
        generate_lesson_background,
        generation_id,
        lesson_request,
        processed_image_path,
    )

    return {"generation_id": generation_id, "custom_image": True}


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup_log_auth_mode():
    if app_password_configured():
        logger.info("APP_PASSWORD is set — generation endpoints require Bearer auth.")
    else:
        logger.warning(
            "APP_PASSWORD is not set — generation endpoints are open. "
            "Set APP_PASSWORD in production."
        )


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up all temporary files on application shutdown."""
    logger.info("Shutting down - cleaning up temporary files...")
    image_processor.cleanup_all()
    _executor.shutdown(wait=False)
