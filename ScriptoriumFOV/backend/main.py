from __future__ import annotations

import io
import json
import logging
import os
import re
import tempfile
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated, Literal, Optional, Dict
from urllib.parse import quote

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from Skoleverksted.backend.platform.images import (
    ImageResult,
    discover_commons_images,
    is_trusted_commons_image_url,
    normalize_image_mode,
    resolve_image,
)
from Skoleverksted.backend.platform.queue import JobCancelled, get_durable_job_queue
from Skoleverksted.backend.platform.models import utc_now
from Skoleverksted.backend.platform.quality_gate import (
    content_digest,
    require_export_ready,
    run_quality_pipeline,
    source_approval_reasons,
)
if __package__:
    from .agents import generate_lesson_content
    from .artifact import (
        ArtifactValidationError,
        ValidatedArtifact,
        validate_pdf_artifact,
        validate_zip_artifact,
    )
    from .config import ALLOWED_IMAGE_TYPES, MAX_IMAGE_BYTES, PDF_THREAD_POOL_WORKERS, RATE_LIMIT_PER_MINUTE
    from .errors import GeminiQuotaExceededError
    from .auth import app_password_configured, require_app_password, verify_password_plain
    from .pdf_service import create_lesson_pdf
    from .media_manager import image_processor
    from .progress_store import (
        cancel_progress, get_progress, initialize_progress, is_json_preview_ready, is_pdf_preview_ready,
        is_pdf_ready, is_zip_preview_ready, is_zip_ready,
        merge_progress, progress_backend_label, publish_event, update_progress,
    )
else:
    from agents import generate_lesson_content
    from artifact import (
        ArtifactValidationError,
        ValidatedArtifact,
        validate_pdf_artifact,
        validate_zip_artifact,
    )
    from config import ALLOWED_IMAGE_TYPES, MAX_IMAGE_BYTES, PDF_THREAD_POOL_WORKERS, RATE_LIMIT_PER_MINUTE
    from errors import GeminiQuotaExceededError
    from auth import app_password_configured, require_app_password, verify_password_plain
    from pdf_service import create_lesson_pdf
    from media_manager import image_processor
    from progress_store import (
        cancel_progress, get_progress, initialize_progress, is_json_preview_ready, is_pdf_preview_ready,
        is_pdf_ready, is_zip_preview_ready, is_zip_ready,
        merge_progress, progress_backend_label, publish_event, update_progress,
    )

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# User-visible error (never leak internal exception strings to clients)
USER_FACING_GENERATION_ERROR = (
    "Noe gikk galt under generering. Prøv igjen litt senere, eller kontakt support."
)


def _public_progress_error(exc: Exception) -> str:
    """Log a safe error code and return a user-facing progress message."""
    logger.error("Generation task failed error_type=%s", type(exc).__name__)
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


def _request_id(request: Request) -> str:
    """Use the platform correlation id when present, otherwise create one."""

    return (request.headers.get("x-request-id") or uuid.uuid4().hex[:12]).strip()[:80]


def _job_context(generation_id: str) -> tuple[str, str]:
    progress = get_progress(generation_id) or {}
    return str(progress.get("request_id") or "unknown"), generation_id


def _log_generation_event(
    event: str,
    generation_id: str,
    *,
    artifact_id: str = "",
    started_at: float | None = None,
    size_bytes: int | None = None,
    terminal_status: str = "running",
    error_code: str = "",
) -> None:
    request_id, job_id = _job_context(generation_id)
    duration_ms = round((time.perf_counter() - started_at) * 1000, 2) if started_at else None
    logger.info(
        "generation_event=%s request_id=%s job_id=%s artifact_id=%s duration_ms=%s "
        "size_bytes=%s terminal_status=%s error_code=%s",
        event,
        request_id,
        job_id,
        artifact_id or "-",
        duration_ms if duration_ms is not None else "-",
        size_bytes if size_bytes is not None else "-",
        terminal_status,
        error_code or "-",
    )


def _artifact_metadata(
    generation_id: str,
    artifact: ValidatedArtifact,
    *,
    draft: bool = False,
) -> dict:
    kind = f"draft_{artifact.kind}" if draft else artifact.kind
    artifact_id = f"{generation_id}:{kind}:{uuid.uuid4().hex[:12]}"
    base_url = f"/api/norsk"
    if artifact.content_type == "application/pdf":
        download_url = f"{base_url}/download-pdf/{generation_id}"
        preview_url = f"{download_url}?preview=true"
    else:
        download_url = f"{base_url}/download-zip/{generation_id}"
        preview_url = None
    return {
        "id": artifact_id,
        "job_id": generation_id,
        "kind": kind,
        "filename": ("UTKAST_" if draft else "") + artifact.filename,
        "content_type": artifact.content_type,
        "size_bytes": artifact.size_bytes,
        "preview_url": preview_url,
        "download_url": download_url,
        "draft": draft,
    }


def _publish_validated_artifact(
    generation_id: str,
    artifact: ValidatedArtifact,
    *,
    payload_key: str,
    total_steps: int,
    quality_documents: list[dict],
    ready_message: str,
    done_message: str = "Ferdig! PDF klar for nedlasting.",
    terminal_status: str = "completed",
    draft: bool = False,
    review_preview: dict | None = None,
) -> dict:
    """Store, verify and publish one idempotent terminal artefact transition.

    ``draft=True`` stores the bytes under a separate preview key and closes
    the job as ``needs_teacher_review``.  Such bytes can never satisfy the
    final export readiness predicate.
    """

    existing = get_progress(generation_id) or {}
    if existing.get("job_status") == "cancelled":
        raise JobCancelled("generation cancelled before artifact publication")
    if terminal_status not in {"completed", "needs_teacher_review"}:
        raise ValueError(f"Unsupported artifact terminal status: {terminal_status}")
    stored_payload_key = payload_key
    if draft:
        stored_payload_key = "preview_" + payload_key
    if (
        existing.get("job_status") == terminal_status
        and existing.get(stored_payload_key)
        and existing.get("artifact")
    ):
        return dict(existing["artifact"])

    started_at = time.perf_counter()
    metadata = _artifact_metadata(generation_id, artifact, draft=draft)
    merge_progress(
        generation_id,
        **{
            stored_payload_key: artifact.content,
            "filename": metadata["filename"],
            "artifact": metadata,
            "artifact_id": metadata["id"],
            "quality_documents": quality_documents,
            "quality_review": _quality_review_payload(quality_documents, artifact=metadata),
            "review_preview": review_preview,
        },
    )
    stored = get_progress(generation_id) or {}
    if stored.get(stored_payload_key) != artifact.content:
        raise ArtifactValidationError("artifact_storage_verification_failed")
    _log_generation_event(
        "pdf_storage_completed",
        generation_id,
        artifact_id=metadata["id"],
        started_at=started_at,
        size_bytes=artifact.size_bytes,
    )
    _log_generation_event(
        "artifact_metadata_created",
        generation_id,
        artifact_id=metadata["id"],
        size_bytes=artifact.size_bytes,
    )

    publish_event(
        generation_id,
        "artifact_ready",
        message=ready_message,
        artifact=metadata,
    )
    _log_generation_event(
        "artifact_ready_sent",
        generation_id,
        artifact_id=metadata["id"],
        size_bytes=artifact.size_bytes,
    )

    # A full progress bar is now true, but it is still not the terminal state.
    update_progress(
        generation_id,
        total_steps,
        total_steps,
        "Utkastet er klart for lærergjennomgang …" if draft else "Artefaktet er kontrollert. Fullfører jobben …",
        event_type="review_required" if draft else "progress",
        job_status=terminal_status,
    )
    publish_event(
        generation_id,
        "review_required" if draft else "done",
        message=ready_message if draft else done_message,
        job_status=terminal_status,
        artifact=metadata,
        error_code="quality_gate_review_required" if draft else None,
    )
    _log_generation_event(
        "terminal_event_sent",
        generation_id,
        artifact_id=metadata["id"],
        size_bytes=artifact.size_bytes,
        terminal_status=terminal_status,
    )
    return metadata


def _mark_generation_failed(generation_id: str, exc: Exception, total_steps: int) -> None:
    error_code = f"{type(exc).__name__.lower()}"
    request_id, job_id = _job_context(generation_id)
    logger.error(
        "generation_failed request_id=%s job_id=%s error_type=%s",
        request_id,
        job_id,
        type(exc).__name__,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    update_progress(
        generation_id,
        -1,
        total_steps,
        _public_progress_error(exc),
        event_type="failed",
        job_status="failed",
        error_code=error_code,
    )
    _log_generation_event(
        "terminal_event_sent",
        generation_id,
        terminal_status="failed",
        error_code=error_code,
    )


def _log_download_failure(generation_id: str, error_code: str) -> None:
    _log_generation_event(
        "artifact_download_failed",
        generation_id,
        terminal_status=str((get_progress(generation_id) or {}).get("job_status") or "unknown"),
        error_code=error_code,
    )


def _content_quality_document(content: dict) -> dict:
    return {
        "content": content.get("verification_content", ""),
        "truth_passport": content.get("truth_passport") or {},
        "quarantine": content.get("quarantine") or [],
        "quality_rounds": content.get("quality_rounds") or [],
        "quality_stop_reason": content.get("quality_stop_reason", ""),
        "quality_status": content.get("quality_status", ""),
        "teacher_approved_at": None,
        "approved_digest": "",
    }


def _quality_result_document(quality: object) -> dict:
    """Convert a QualityGateResult into the storage contract used by exports."""
    return {
        "content": str(getattr(quality, "approved_content", "") or ""),
        "truth_passport": getattr(quality, "passport").model_dump(mode="json"),
        "quarantine": [item.model_dump(mode="json") for item in getattr(quality, "quarantine", [])],
        "quality_rounds": [item.model_dump(mode="json") for item in getattr(quality, "rounds", [])],
        "quality_stop_reason": str(getattr(quality, "stop_reason", "") or ""),
        "quality_status": str(getattr(quality, "quality_status", "needs_teacher_review") or "needs_teacher_review"),
        "teacher_approved_at": None,
        "approved_digest": "",
    }


def _quality_document_is_source_approved(document: dict) -> bool:
    passport = document.get("truth_passport") or {}
    reasons = source_approval_reasons(
        content=str(document.get("content") or ""),
        verification_status=str(passport.get("status") or "missing"),
        verified_revision=str(passport.get("content_revision") or ""),
        verification_version=str(passport.get("version") or ""),
        quarantined_texts=[
            str(item.get("original_text") or "")
            for item in document.get("quarantine") or []
        ],
    )
    return not reasons


def _quality_review_payload(
    documents: list[dict],
    *,
    artifact: dict | None = None,
) -> dict:
    """Public, teacher-facing quality data without exposing binary payloads."""
    return {
        "status": (
            "source_approved"
            if documents and all(_quality_document_is_source_approved(item) for item in documents)
            else "needs_teacher_review"
        ),
        "documents": [
            {
                "index": index,
                "truth_passport": document.get("truth_passport") or {},
                "quarantine": document.get("quarantine") or [],
                "quality_rounds": document.get("quality_rounds") or [],
                "quality_stop_reason": document.get("quality_stop_reason", ""),
                "content_revision": (document.get("truth_passport") or {}).get("content_revision", ""),
            }
            for index, document in enumerate(documents)
        ],
        "artifact": artifact,
    }


def _review_message(documents: list[dict]) -> str:
    unresolved = 0
    reasons: list[str] = []
    for document in documents:
        passport = document.get("truth_passport") or {}
        unresolved += max(
            0,
            int(passport.get("total_claims") or 0) - int(passport.get("verified_claims") or 0),
        )
        stop_reason = str(document.get("quality_stop_reason") or "").strip()
        if stop_reason and stop_reason not in reasons:
            reasons.append(stop_reason)
    claim_text = (
        f" Kvalitetskontrollen fant {unresolved} uavklart(e) påstand(er)."
        if unresolved
        else " Kvalitetskontrollen fant innhold som må vurderes av lærer."
    )
    reason_text = f" Stoppårsak: {'; '.join(reasons)}." if reasons else ""
    return (
        "Lærergjennomgang kreves før PDF kan godkjennes."
        + claim_text
        + reason_text
        + " Rediger eller fjern uavklart innhold, og kjør kildekontroll på nytt."
    )


def _lesson_preview_payload(content: dict) -> dict:
    """Build the JSON preview shape from generated content for review recovery."""
    return {
        "topic": content.get("topic", ""),
        "subject": content.get("subject", ""),
        "level": content.get("level", ""),
        "text": content.get("text", ""),
        "worksheet": content.get("worksheet", ""),
        "image_url": content.get("image_url"),
        "image_mode": content.get("image_mode", "none"),
        "image_caption": content.get("image_caption", ""),
        "image_credit": content.get("image_credit", ""),
        "image_source_page": content.get("image_source_page"),
        "language_exercises": content.get("language_exercises"),
        "source_grounded": content.get("source_grounded", False),
        "source_name": content.get("source_name"),
        "truth_passport": content.get("truth_passport"),
        "quarantine": content.get("quarantine") or [],
        "quality_rounds": content.get("quality_rounds") or [],
        "quality_stop_reason": content.get("quality_stop_reason", ""),
        "prompt_version": content.get("prompt_version"),
    }


def _require_norsk_documents(
    progress: dict,
    export_id: str,
    *,
    teacher: bool,
    preview: bool = False,
) -> None:
    """Enforce final export approval without blocking teacher-facing previews."""
    if preview:
        return
    documents = progress.get("quality_documents") or []
    if not documents:
        raise HTTPException(status_code=409, detail="Eksportporten er lukket: kvalitetsdata mangler.")
    for document in documents:
        passport = document.get("truth_passport") or {}
        content = str(document.get("content") or "")
        quarantined = [item.get("original_text", "") for item in document.get("quarantine", [])]
        if teacher:
            try:
                require_export_ready(
                    export_id=export_id,
                    content=content,
                    verification_status=passport.get("status", "missing"),
                    verified_revision=passport.get("content_revision", ""),
                    verification_version=passport.get("version", ""),
                    teacher_approved=bool(document.get("teacher_approved_at")),
                    approved_revision=str(document.get("approved_digest") or ""),
                    quarantined_texts=quarantined,
                )
            except PermissionError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
        else:
            reasons = source_approval_reasons(
                content=content,
                verification_status=passport.get("status", "missing"),
                verified_revision=passport.get("content_revision", ""),
                verification_version=passport.get("version", ""),
                quarantined_texts=quarantined,
            )
            if reasons:
                raise HTTPException(status_code=409, detail="Forhåndsvisning blokkert: " + "; ".join(reasons))


def _materialize_pedagogical_image(
    request: object,
    content: dict,
    *,
    pre_processed_image_path: Optional[str] = None,
) -> tuple[Optional[str], Optional[ImageResult], str, str]:
    """Resolve and optimise the selected image mode; fail safely to no image."""
    if pre_processed_image_path:
        return (
            pre_processed_image_path,
            None,
            "",
            "Bilde: lærerens eget opplastede bilde",
        )

    mode = normalize_image_mode(getattr(request, "image_mode", "none"))
    if mode == "none":
        return None, None, "", ""

    asset = resolve_image(
        mode,
        topic=str(getattr(request, "topic", "")),
        subject=str(getattr(request, "subject", "")),
        level=str(getattr(request, "level", "")),
        text=str(content.get("text", "")),
    )
    if not asset:
        logger.warning("Bildecrewet fant ikke et faglig trygt bilde; fortsetter uten bilde")
        return None, None, "", ""

    processed_path: Optional[str] = None
    if asset.local_path:
        raw_path = asset.local_path
        try:
            processed_path = image_processor.process_image_from_path(raw_path)
        finally:
            try:
                os.unlink(raw_path)
            except OSError:
                pass
    elif asset.image_url:
        processed_path = _process_image_for_content({"image_url": asset.image_url})

    if not processed_path:
        logger.warning("Valgt bilde kunne ikke behandles; fortsetter uten bilde")
        return None, None, "", ""
    return processed_path, asset, asset.caption, asset.credit


def generate_lesson_background(
    generation_id: str,
    request: "LessonRequest",
    pre_processed_image_path: str = None
):
    """Background task to generate the lesson PDF."""
    processed_image_path = pre_processed_image_path
    try:
        # Step 1: Generate lesson content using AI agents
        update_progress(generation_id, 1, 4, "Skriver pedagogisk tekst...")
        logger.info(f"Generating lesson: {request.topic} ({request.subject}, {request.level})")
        content = generate_lesson_content(
            topic=request.topic,
            subject=request.subject,
            level=request.level,
            options=request.options,
            difficulty_modifier=getattr(request, 'difficulty_modifier', None),
            special_instructions=getattr(request, 'special_instructions', None),
            series=getattr(request, 'series', None),
            source_text=getattr(request, 'source_text', None),
            source_name=getattr(request, 'source_name', None),
            request_id=str((get_progress(generation_id) or {}).get("request_id") or ""),
        )

        # Step 2: Process the image (skip if caller already provided a local path)
        image_mode = normalize_image_mode(getattr(request, "image_mode", "none"))
        update_progress(
            generation_id,
            2,
            4,
            (
                "Bildecrewet planlegger og kvalitetssikrer ett pedagogisk bilde..."
                if image_mode != "none" and not pre_processed_image_path
                else "Behandler bildevalg..."
            ),
        )
        processed_image_path, image_asset, image_caption, image_credit = _materialize_pedagogical_image(
            request,
            content,
            pre_processed_image_path=pre_processed_image_path,
        )

        # Step 3: Create PDF from the generated content
        update_progress(
            generation_id,
            3,
            4,
            "Bygger og kontrollerer PDF …",
            event_type="artifact_building",
        )
        _log_generation_event("pdf_build_started", generation_id)
        pdf_started_at = time.perf_counter()
        quality_document = _content_quality_document(content)
        source_approved = _quality_document_is_source_approved(quality_document)
        pdf_bytes = create_lesson_pdf(
            content_text=content["text"],
            worksheet_text=content["worksheet"],
            topic=request.topic,
            level=request.level,
            subject=request.subject,
            image_path=processed_image_path,
            image_caption=image_caption,
            image_credit=image_credit,
            language_exercises=content.get("language_exercises"),
            options=request.options,
            teacher_key_content=content.get("teacher_key_content", ""),
            series_header=content.get("series_header", ""),
            accessibility=getattr(request, 'accessibility', None),
            draft=not source_approved,
        )
        _log_generation_event(
            "pdf_build_completed",
            generation_id,
            started_at=pdf_started_at,
            size_bytes=len(pdf_bytes),
        )
        _log_generation_event("pdf_validation_started", generation_id, size_bytes=len(pdf_bytes))
        validated = validate_pdf_artifact(pdf_bytes, _safe_filename(request.topic) + ".pdf")
        _log_generation_event(
            "pdf_validation_completed",
            generation_id,
            size_bytes=validated.size_bytes,
        )

        # Step 4: Store PDF bytes in progress for retrieval
        image_warning = (
            " Ingen tilstrekkelig relevant og fritt tilgjengelig bilde ble funnet. "
            "PDF-en er laget uten bilde; prøv Commons-søket på nytt, velg KI-illustrasjon "
            "eller last opp et eget bilde."
            if image_mode != "none" and not processed_image_path
            else ""
        )
        _publish_validated_artifact(
            generation_id,
            validated,
            payload_key="pdf_bytes",
            total_steps=4,
            quality_documents=[quality_document],
            ready_message=(
                (
                    "Utkastet er bygget og validert. Lærergjennomgang kreves."
                    if not source_approved
                    else "PDF-en er bygget, validert og lagret. PDF klar for nedlasting."
                )
                + image_warning
            ),
            terminal_status="completed" if source_approved else "needs_teacher_review",
            draft=not source_approved,
            review_preview=None if source_approved else _lesson_preview_payload(content),
        )

        logger.info("PDF generated successfully: %s (%s bytes)", validated.filename, validated.size_bytes)

    except Exception as e:
        _mark_generation_failed(generation_id, e, 4)
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
    source_text: Optional[str] = Field(default=None, max_length=5000)
    source_name: Optional[str] = Field(default=None, max_length=160)
    image_mode: Literal["none", "commons", "ai"] = Field(
        "none",
        description="Ingen bilder, et fritt Wikimedia-bilde eller en KI-generert illustrasjon.",
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
    source_text: Optional[str] = Field(default=None, max_length=5000)
    source_name: Optional[str] = Field(default=None, max_length=160)
    image_mode: Literal["none", "commons", "ai"] = "none"

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
            "source_text": self.source_text,
            "source_name": self.source_name,
            "image_mode": self.image_mode,
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
    image_mode: Literal["none", "commons", "ai"] = "none"
    image_caption: str = Field("", max_length=160)
    image_credit: str = Field("", max_length=600)
    image_source_page: Optional[str] = Field(None, max_length=600)
    language_exercises: Optional[dict] = None
    options: dict[str, bool]
    accessibility: Optional[dict] = None
    provided_sources: list[dict] = Field(
        default_factory=list,
        max_length=50,
        description="Concrete sources retained from the preceding truth audit.",
    )


class ImageCandidateResponse(BaseModel):
    """A licence-checked Commons candidate shown for teacher review."""
    image_url: str
    thumbnail_url: str
    source_page_url: str
    title: str
    description: str = ""
    creator: str = ""
    license: str
    credit: str
    caption: str = ""
    alt_text: str = ""
    rationale: str = ""
    recommended: bool = False
    review_status: Literal["recommended", "teacher_review"] = "teacher_review"


class LessonResponse(BaseModel):
    """Response model for lesson content (JSON format)."""
    topic: str
    subject: str
    level: str
    text: str
    worksheet: str
    image_url: Optional[str] = None
    image_mode: Literal["none", "commons", "ai"] = "none"
    image_caption: str = ""
    image_credit: str = ""
    image_source_page: Optional[str] = None
    image_candidates: list[ImageCandidateResponse] = Field(default_factory=list)
    language_exercises: Optional[dict] = None
    source_grounded: bool = False
    source_name: Optional[str] = None
    truth_passport: Optional[dict] = None
    quarantine: list[dict] = Field(default_factory=list)
    quality_rounds: list[dict] = Field(default_factory=list)
    quality_stop_reason: str = ""
    prompt_version: Optional[str] = None


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
    # Exclude binary payloads and the internal quality-document storage. The
    # public contract exposes only teacher-review metadata and safe preview
    # content needed to recover from a terminal quality stop.
    return {
        k: v
        for k, v in progress.items()
        if not isinstance(v, bytes) and k not in {"quality_documents", "json_data"}
    }


@app.post("/generation/{generation_id}/cancel")
def cancel_generation(generation_id: str, _auth: AuthPasswordDep):
    """Cancel a running generation and make the terminal state durable."""
    progress = get_progress(generation_id)
    if progress is None:
        raise HTTPException(status_code=404, detail="Generation task not found")
    if progress.get("job_status") in {"completed", "needs_teacher_review", "failed", "cancelled"}:
        if progress.get("job_status") == "cancelled":
            return {"status": "cancelled"}
        raise HTTPException(status_code=409, detail="Genereringen har allerede avsluttet.")
    if not cancel_progress(generation_id):
        raise HTTPException(status_code=404, detail="Generation task not found")
    try:
        get_durable_job_queue().cancel(generation_id)
    except Exception:
        logger.warning("Could not update durable queue cancellation job_id=%s", generation_id, exc_info=True)
    return {"status": "cancelled"}


@app.get("/download-pdf/{generation_id}")
def download_pdf(generation_id: str, _auth: AuthPasswordDep, preview: bool = False):
    """
    Download the completed PDF for a generation task.

    Returns:
        PDF file download
    """
    progress = get_progress(generation_id)
    if progress is None:
        _log_download_failure(generation_id, "generation_not_found")
        raise HTTPException(status_code=404, detail="Generation task not found")

    if preview:
        ready = is_pdf_preview_ready(progress)
    else:
        ready = is_pdf_ready(progress)
        if not ready and progress.get("job_status") == "needs_teacher_review":
            _log_download_failure(generation_id, "quality_review_required")
            raise HTTPException(
                status_code=409,
                detail="Eksportporten er lukket: lærergjennomgang kreves før endelig PDF kan lastes ned.",
            )
    if not ready:
        _log_download_failure(generation_id, "pdf_not_ready")
        raise HTTPException(status_code=202, detail="PDF not ready yet")
    try:
        _require_norsk_documents(progress, "norsk.pdf", teacher=not preview, preview=preview)
    except HTTPException:
        _log_download_failure(generation_id, "quality_gate_blocked")
        raise

    is_draft_preview = progress.get("job_status") == "needs_teacher_review"
    pdf_bytes = progress.get("preview_pdf_bytes") if is_draft_preview else progress.get("pdf_bytes")
    filename = progress.get("filename", "lesson.pdf")

    if not pdf_bytes:
        _log_download_failure(generation_id, "pdf_bytes_missing")
        raise HTTPException(status_code=500, detail="PDF data not available")

    _log_generation_event(
        "artifact_download_requested",
        generation_id,
        artifact_id=(progress.get("artifact") or {}).get("id", ""),
        size_bytes=len(pdf_bytes),
        terminal_status=str(progress.get("job_status") or "running"),
    )
    _log_generation_event(
        "artifact_download_completed",
        generation_id,
        artifact_id=(progress.get("artifact") or {}).get("id", ""),
        size_bytes=len(pdf_bytes),
        terminal_status=str(progress.get("job_status") or "running"),
    )
    disposition = "inline" if preview else "attachment"
    headers = {
        "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(filename)}",
        "Content-Length": str(len(pdf_bytes)),
        "X-Artifact-ID": str((progress.get("artifact") or {}).get("id", "")),
        "X-Job-ID": generation_id,
    }
    if preview:
        headers.update({
            "Cache-Control": "no-store",
            "X-Preview-Draft": "true" if is_draft_preview else "false",
        })
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers=headers,
    )


@app.get("/download-zip/{generation_id}")
def download_zip(generation_id: str, _auth: AuthPasswordDep, preview: bool = False):
    """
    Download a ZIP archive containing two PDFs (dual-version generation).

    Returns:
        ZIP file download
    """
    progress = get_progress(generation_id)
    if progress is None:
        _log_download_failure(generation_id, "generation_not_found")
        raise HTTPException(status_code=404, detail="Generation task not found")

    if preview:
        ready = is_zip_preview_ready(progress)
    else:
        ready = is_zip_ready(progress)
        if not ready and progress.get("job_status") == "needs_teacher_review":
            _log_download_failure(generation_id, "quality_review_required")
            raise HTTPException(
                status_code=409,
                detail="Eksportporten er lukket: lærergjennomgang kreves før endelig ZIP kan lastes ned.",
            )
    if not ready:
        _log_download_failure(generation_id, "zip_not_ready")
        raise HTTPException(status_code=202, detail="ZIP not ready yet")
    try:
        _require_norsk_documents(progress, "norsk.zip", teacher=not preview, preview=preview)
    except HTTPException:
        _log_download_failure(generation_id, "quality_gate_blocked")
        raise

    is_draft_preview = progress.get("job_status") == "needs_teacher_review"
    zip_bytes = progress.get("preview_zip_bytes") if is_draft_preview else progress.get("zip_bytes")
    filename = progress.get("filename", "lessons.zip")

    if not zip_bytes:
        _log_download_failure(generation_id, "zip_bytes_missing")
        raise HTTPException(status_code=500, detail="ZIP data not available")

    _log_generation_event(
        "artifact_download_requested",
        generation_id,
        artifact_id=(progress.get("artifact") or {}).get("id", ""),
        size_bytes=len(zip_bytes),
        terminal_status=str(progress.get("job_status") or "running"),
    )
    _log_generation_event(
        "artifact_download_completed",
        generation_id,
        artifact_id=(progress.get("artifact") or {}).get("id", ""),
        size_bytes=len(zip_bytes),
        terminal_status=str(progress.get("job_status") or "running"),
    )
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
        "Content-Length": str(len(zip_bytes)),
        "X-Artifact-ID": str((progress.get("artifact") or {}).get("id", "")),
        "X-Job-ID": generation_id,
    }
    if preview:
        headers.update({
            "Cache-Control": "no-store",
            "X-Preview-Draft": "true" if is_draft_preview else "false",
        })
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers=headers,
    )


@app.post("/generation/{generation_id}/approve")
def approve_generation(generation_id: str, _auth: AuthPasswordDep):
    """Bind the teacher's approval to every exact verified document revision."""
    progress = get_progress(generation_id)
    if progress is None:
        raise HTTPException(status_code=404, detail="Generation task not found")
    export_id = "norsk.zip" if progress.get("zip_bytes") else "norsk.pdf"
    _require_norsk_documents(progress, export_id, teacher=False)
    approved_at = utc_now()
    documents = []
    for document in progress.get("quality_documents") or []:
        revised = dict(document)
        revised["teacher_approved_at"] = approved_at
        revised["approved_digest"] = content_digest(str(document.get("content") or ""))
        documents.append(revised)
    merge_progress(generation_id, quality_documents=documents)
    return {"status": "approved", "approved_at": approved_at, "documents": len(documents)}


# ---------------------------------------------------------------------------
# Main lesson generation endpoints
# ---------------------------------------------------------------------------

def _run_durable_fov_job(
    generation_id: str,
    kind: str,
    payload,
    project_id: str | None,
    target,
    *args,
) -> None:
    """Run every FOV background job through the shared durable capacity gate."""
    queue = None
    try:
        queue = get_durable_job_queue()
        queue.enqueue(generation_id, module="norsk", kind=kind, payload=payload, project_id=project_id)

        def announce(position: int) -> None:
            update_progress(generation_id, 0, 4, f"Venter i kø (plass {position}) …")

        def cancel_check() -> bool:
            return (get_progress(generation_id) or {}).get("job_status") == "cancelled"

        with queue.claim(
            generation_id,
            on_wait=announce,
            auto_complete=False,
            cancel_check=cancel_check,
        ):
            target(*args)
        progress = get_progress(generation_id) or {}
        if progress.get("job_status") == "cancelled":
            queue.cancel(generation_id)
        elif progress.get("job_status") == "failed" or int(progress.get("step", 0)) < 0:
            queue.fail(generation_id, str(progress.get("message") or "Genereringen feilet"))
        elif progress.get("job_status") in {"completed", "needs_teacher_review", "cancelled"}:
            queue.finish(generation_id)
        else:
            _mark_generation_failed(
                generation_id,
                RuntimeError("worker_returned_without_terminal_status"),
                int(progress.get("total_steps") or 4),
            )
            queue.fail(generation_id, "Genereringen avsluttet uten terminalstatus")
    except Exception as exc:
        progress = get_progress(generation_id) or {}
        if progress.get("job_status") == "cancelled" or isinstance(exc, JobCancelled):
            if progress.get("job_status") != "cancelled":
                cancel_progress(generation_id)
        elif progress.get("job_status") not in {"completed", "needs_teacher_review", "failed", "cancelled"}:
            _mark_generation_failed(generation_id, exc, int(progress.get("total_steps") or 4))
        if queue is not None:
            try:
                if progress.get("job_status") == "cancelled" or isinstance(exc, JobCancelled):
                    queue.cancel(generation_id)
                else:
                    queue.fail(generation_id, "Genereringen feilet")
            except Exception:
                logger.exception("Could not mark durable queue job as failed job_id=%s", generation_id)

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
    initialize_progress(
        generation_id,
        4,
        "Starter generering...",
        request_id=_request_id(request),
    )
    background_tasks.add_task(
        _run_durable_fov_job,
        generation_id, "lesson", lesson_request, request.headers.get("X-Skoleverksted-Project"), generate_lesson_background,
        generation_id, lesson_request,
    )

    return {"generation_id": generation_id}


def generate_lesson_json_background(
    generation_id: str,
    lesson_request: "LessonRequest"
):
    """Background task to generate JSON preview."""
    try:
        update_progress(generation_id, 1, 3, "Skriver pedagogisk tekst...")
        
        content = generate_lesson_content(
            topic=lesson_request.topic,
            subject=lesson_request.subject,
            level=lesson_request.level,
            options=lesson_request.options,
            difficulty_modifier=lesson_request.difficulty_modifier,
            special_instructions=lesson_request.special_instructions,
            series=lesson_request.series,
            source_text=lesson_request.source_text,
            source_name=lesson_request.source_name,
            request_id=str((get_progress(generation_id) or {}).get("request_id") or ""),
        )
        
        image_candidates: list[dict] = []
        selected_candidate: Optional[dict] = None
        if normalize_image_mode(lesson_request.image_mode) == "commons":
            update_progress(
                generation_id,
                2,
                3,
                "Bildecrewet finner og rangerer frie bildeforslag...",
            )
            image_candidates = discover_commons_images(
                topic=lesson_request.topic,
                subject=lesson_request.subject,
                level=lesson_request.level,
                text=content.get("text", ""),
            )
            selected_candidate = next(
                (
                    candidate
                    for candidate in image_candidates
                    if candidate.get("recommended") is True
                ),
                None,
            )

        merge_progress(
            generation_id,
            json_data={
                "topic": content["topic"],
                "subject": content["subject"],
                "level": content["level"],
                "text": content["text"],
                "worksheet": content["worksheet"],
                "image_url": selected_candidate.get("image_url") if selected_candidate else None,
                # If the critic recommends nothing, the PDF must remain without
                # an image until the teacher deliberately selects a candidate.
                "image_mode": (
                    "commons"
                    if selected_candidate
                    else "none"
                    if normalize_image_mode(lesson_request.image_mode) == "commons"
                    else lesson_request.image_mode
                ),
                "image_caption": selected_candidate.get("caption", "") if selected_candidate else "",
                "image_credit": selected_candidate.get("credit", "") if selected_candidate else "",
                "image_source_page": (
                    selected_candidate.get("source_page_url") if selected_candidate else None
                ),
                "image_candidates": image_candidates,
                "language_exercises": content.get("language_exercises"),
                "source_grounded": content.get("source_grounded", False),
                "source_name": content.get("source_name"),
                "truth_passport": content.get("truth_passport"),
                "quarantine": content.get("quarantine", []),
                "quality_rounds": content.get("quality_rounds", []),
                "quality_stop_reason": content.get("quality_stop_reason", ""),
                "quality_status": content.get("quality_status", ""),
                "prompt_version": content.get("prompt_version"),
            },
            quality_documents=[_content_quality_document(content)],
            review_preview=_lesson_preview_payload(content),
        )
        quality_document = _content_quality_document(content)
        source_approved = _quality_document_is_source_approved(quality_document)
        terminal_status = "completed" if source_approved else "needs_teacher_review"
        terminal_message = (
            "Forhåndsvisning er klar!"
            if source_approved
            else _review_message([quality_document])
        )
        # Publish the completed step only after json_data is persisted. This
        # prevents clients from observing "ready" in the tiny interval before
        # the preview payload exists.
        update_progress(
            generation_id,
            3,
            3,
            terminal_message,
            event_type="progress" if source_approved else "review_required",
            job_status=terminal_status,
        )
        publish_event(
            generation_id,
            "done" if source_approved else "review_required",
            message=terminal_message,
            job_status=terminal_status,
        )
        _log_generation_event("terminal_event_sent", generation_id, terminal_status=terminal_status)

    except Exception as e:
        _mark_generation_failed(generation_id, e, 3)

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
    initialize_progress(
        generation_id,
        3,
        "Starter forhåndsvisning...",
        request_id=_request_id(request),
    )
    background_tasks.add_task(
        _run_durable_fov_job,
        generation_id, "preview", lesson_request, request.headers.get("X-Skoleverksted-Project"), generate_lesson_json_background,
        generation_id, lesson_request,
    )

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
        verification_document = json.dumps(
            {
                "text": request.text,
                "worksheet": request.worksheet,
                "language_exercises": request.language_exercises,
            },
            ensure_ascii=False,
        )
        request_id = str((get_progress(generation_id) or {}).get("request_id") or "")
        quality = run_quality_pipeline(
            generator_id="norsk.preview_pdf",
            content=verification_document,
            topic=request.topic,
            subject=request.subject,
            level=request.level,
            provided_sources=request.provided_sources,
            request_id=request_id,
        )
        quality_document = _quality_result_document(quality)
        source_approved = _quality_document_is_source_approved(quality_document)
        original_text = request.text
        original_worksheet = request.worksheet
        original_language_exercises = request.language_exercises
        try:
            revised_document = json.loads(quality.approved_content)
            if not isinstance(revised_document, dict):
                raise ValueError("kontrollert innhold er ikke et objekt")
            revised_text = revised_document.get("text")
            revised_worksheet = revised_document.get("worksheet")
            revised_language = revised_document.get("language_exercises")
            if not isinstance(revised_text, str) or not isinstance(revised_worksheet, str):
                raise ValueError("kontrollerte tekstfelt mangler")
            if revised_language is not None and not isinstance(revised_language, dict):
                raise ValueError("språkoppgavene er ikke et objekt")
            request.text = revised_text
            request.worksheet = revised_worksheet
            request.language_exercises = revised_language
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            if source_approved:
                raise ValueError("Kontrollert innhold kunne ikke deles trygt tilbake i PDF-feltene.") from exc
            # A review draft must remain visible even if the controller could
            # not safely parse a revised structured payload. It is explicitly
            # watermarked and can never be served by the final export route.
            request.text = original_text
            request.worksheet = original_worksheet
            request.language_exercises = original_language_exercises
        update_progress(generation_id, 1, 3, "Behandler og optimaliserer bilde...")
        
        image_asset: Optional[ImageResult] = None
        image_caption = request.image_caption
        image_credit = request.image_credit

        # A Commons image may already have been selected during preview.
        if not processed_image_path and request.image_url:
            if not is_trusted_commons_image_url(request.image_url):
                logger.warning("Avviser ikke-verifisert Commons-URL fra forhåndsvisningen")
            else:
                content_dict = {"image_url": request.image_url}
                processed_image_path = _process_image_for_content(content_dict)
        elif not processed_image_path and normalize_image_mode(request.image_mode) != "none":
            processed_image_path, image_asset, image_caption, image_credit = _materialize_pedagogical_image(
                request,
                {"text": request.text},
            )
            
        update_progress(
            generation_id,
            2,
            3,
            "Bygger og kontrollerer PDF …",
            event_type="artifact_building",
        )
        _log_generation_event("pdf_build_started", generation_id)
        pdf_started_at = time.perf_counter()
        pdf_bytes = create_lesson_pdf(
            content_text=request.text,
            worksheet_text=request.worksheet,
            topic=request.topic,
            level=request.level,
            subject=request.subject,
            image_path=processed_image_path,
            image_caption=image_caption,
            image_credit=image_credit,
            language_exercises=request.language_exercises,
            options=request.options,
            accessibility=getattr(request, "accessibility", None),
            draft=not source_approved,
        )
        _log_generation_event(
            "pdf_build_completed",
            generation_id,
            started_at=pdf_started_at,
            size_bytes=len(pdf_bytes),
        )
        _log_generation_event("pdf_validation_started", generation_id, size_bytes=len(pdf_bytes))
        validated = validate_pdf_artifact(pdf_bytes, _safe_filename(request.topic) + ".pdf")
        _log_generation_event(
            "pdf_validation_completed",
            generation_id,
            size_bytes=validated.size_bytes,
        )

        # Store PDF
        requested_image = normalize_image_mode(request.image_mode) != "none"
        image_warning = (
            " Ingen tilstrekkelig relevant og fritt tilgjengelig bilde ble funnet. "
            "PDF-en er laget uten bilde; prøv Commons-søket på nytt, velg KI-illustrasjon "
            "eller last opp et eget bilde."
            if requested_image and not processed_image_path
            else ""
        )
        _publish_validated_artifact(
            generation_id,
            validated,
            payload_key="pdf_bytes",
            total_steps=3,
            quality_documents=[quality_document],
            ready_message=(
                (
                    "Utkastet er bygget og validert. " + _review_message([quality_document])
                    if not source_approved
                    else "PDF-en er bygget, validert og lagret. PDF klar for nedlasting."
                )
                + image_warning
            ),
            terminal_status="completed" if source_approved else "needs_teacher_review",
            draft=not source_approved,
            review_preview={
                "topic": request.topic,
                "subject": request.subject,
                "level": request.level,
                "text": request.text,
                "worksheet": request.worksheet,
                "image_url": request.image_url,
                "image_mode": request.image_mode,
                "image_caption": request.image_caption,
                "image_credit": request.image_credit,
                "image_source_page": request.image_source_page,
                "language_exercises": request.language_exercises,
                "truth_passport": quality_document.get("truth_passport"),
                "quarantine": quality_document.get("quarantine", []),
                "quality_rounds": quality_document.get("quality_rounds", []),
                "quality_stop_reason": quality_document.get("quality_stop_reason", ""),
                "provided_sources": (
                    quality_document.get("truth_passport") or {}
                ).get("sources", []),
            },
        )

    except Exception as e:
        _mark_generation_failed(generation_id, e, 3)
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
    initialize_progress(
        generation_id,
        3,
        "Starter PDF-generering...",
        request_id=_request_id(request),
    )
    background_tasks.add_task(
        _run_durable_fov_job,
        generation_id, "preview_pdf", preview_request, request.headers.get("X-Skoleverksted-Project"), generate_pdf_from_json_background,
        generation_id, preview_request,
    )
    
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


def _generate_single_pdf(
    request: "LessonRequest",
    level_override: str,
    quality_generator_id: str,
) -> tuple[bytes, str, dict]:
    """
    Synchronous helper that generates one complete PDF for a given level.
    Returns (pdf_bytes, filename, quality_document).
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
        source_text=req.source_text,
        source_name=req.source_name,
        quality_generator_id=quality_generator_id,
        request_id="",
    )

    req.level = level_override
    processed_image_path, _image_asset, image_caption, image_credit = _materialize_pedagogical_image(
        req,
        content,
    )
    quality_document = _content_quality_document(content)
    source_approved = _quality_document_is_source_approved(quality_document)
    try:
        pdf_bytes = create_lesson_pdf(
            content_text=content["text"],
            worksheet_text=content["worksheet"],
            topic=req.topic,
            level=level_override,
            subject=req.subject,
            image_path=processed_image_path,
            image_caption=image_caption,
            image_credit=image_credit,
            language_exercises=content.get("language_exercises"),
            options=req.options,
            teacher_key_content=content.get("teacher_key_content", ""),
            series_header=content.get("series_header", ""),
            accessibility=req.accessibility,
            draft=not source_approved,
        )
    finally:
        _cleanup_image(processed_image_path)

    filename = _safe_filename(req.topic) + f"_{level_override}.pdf"
    return pdf_bytes, filename, quality_document


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

        fut_a = _executor.submit(_generate_single_pdf, lesson_req, level_a, "norsk.dual_level")
        fut_b = _executor.submit(_generate_single_pdf, lesson_req, level_b, "norsk.dual_level")
        pdf_a, name_a, quality_a = fut_a.result()
        pdf_b, name_b, quality_b = fut_b.result()

        update_progress(
            generation_id,
            3,
            4,
            "Bygger og kontrollerer ZIP-artefakt …",
            event_type="artifact_building",
        )
        _log_generation_event("pdf_build_started", generation_id)
        artifact_started_at = time.perf_counter()
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(name_a, pdf_a)
            zf.writestr(name_b, pdf_b)
        zip_bytes = zip_buffer.getvalue()
        _log_generation_event(
            "pdf_build_completed",
            generation_id,
            started_at=artifact_started_at,
            size_bytes=len(zip_bytes),
        )
        _log_generation_event("pdf_validation_started", generation_id, size_bytes=len(zip_bytes))
        validated = validate_zip_artifact(
            zip_bytes,
            _safe_filename(lesson_req.topic) + "_dual.zip",
        )
        _log_generation_event(
            "pdf_validation_completed",
            generation_id,
            size_bytes=validated.size_bytes,
        )

        all_source_approved = all(
            _quality_document_is_source_approved(document)
            for document in (quality_a, quality_b)
        )
        _publish_validated_artifact(
            generation_id,
            validated,
            payload_key="zip_bytes",
            total_steps=4,
            quality_documents=[quality_a, quality_b],
            ready_message=(
                "ZIP-utkastet er bygget og validert. " + _review_message([quality_a, quality_b])
                if not all_source_approved
                else "ZIP-artefaktet er bygget, validert og lagret."
            ),
            done_message="Ferdig! ZIP klar for nedlasting.",
            terminal_status="completed" if all_source_approved else "needs_teacher_review",
            draft=not all_source_approved,
        )
        logger.info("Dual PDF ZIP generated: %s bytes", validated.size_bytes)

    except Exception as e:
        _mark_generation_failed(generation_id, e, 4)


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
    initialize_progress(
        generation_id,
        4,
        "Starter dual generering...",
        request_id=_request_id(request),
    )
    background_tasks.add_task(
        _run_durable_fov_job,
        generation_id, "dual_lesson", lesson_request, request.headers.get("X-Skoleverksted-Project"), _generate_dual_background,
        generation_id, lesson_request,
    )

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
        futures = [_executor.submit(_generate_single_pdf, base, lvl, "norsk.multi_level") for lvl in levels]
        zip_parts: list[tuple[bytes, str, dict]] = []
        for fut in futures:
            zip_parts.append(fut.result())

        update_progress(
            generation_id,
            3,
            4,
            "Bygger og kontrollerer ZIP-artefakt …",
            event_type="artifact_building",
        )
        _log_generation_event("pdf_build_started", generation_id)
        artifact_started_at = time.perf_counter()
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for pdf_bytes, name, _quality in zip_parts:
                zf.writestr(name, pdf_bytes)
        zip_bytes = zip_buffer.getvalue()
        _log_generation_event(
            "pdf_build_completed",
            generation_id,
            started_at=artifact_started_at,
            size_bytes=len(zip_bytes),
        )
        _log_generation_event("pdf_validation_started", generation_id, size_bytes=len(zip_bytes))
        validated = validate_zip_artifact(
            zip_bytes,
            _safe_filename(lesson_req.topic) + "_flerniva.zip",
        )
        _log_generation_event(
            "pdf_validation_completed",
            generation_id,
            size_bytes=validated.size_bytes,
        )

        all_source_approved = all(
            _quality_document_is_source_approved(document)
            for _pdf, _name, document in zip_parts
        )
        quality_documents = [quality for _pdf, _name, quality in zip_parts]
        _publish_validated_artifact(
            generation_id,
            validated,
            payload_key="zip_bytes",
            total_steps=4,
            quality_documents=quality_documents,
            ready_message=(
                "ZIP-utkastet er bygget og validert. " + _review_message(quality_documents)
                if not all_source_approved
                else "ZIP-artefaktet er bygget, validert og lagret."
            ),
            done_message="Ferdig! ZIP klar for nedlasting.",
            terminal_status="completed" if all_source_approved else "needs_teacher_review",
            draft=not all_source_approved,
        )
        logger.info("Multi-level PDF ZIP generated: %s bytes (%s levels)", validated.size_bytes, n)

    except Exception as e:
        _mark_generation_failed(generation_id, e, 4)


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
    initialize_progress(
        generation_id,
        4,
        "Starter flernivå-generering...",
        request_id=_request_id(request),
    )
    background_tasks.add_task(
        _run_durable_fov_job,
        generation_id, "multi_lesson", lesson_request, request.headers.get("X-Skoleverksted-Project"), _generate_multi_level_background,
        generation_id, lesson_request,
    )

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
    source_text: Optional[str] = Form(default=None, max_length=5000),
    source_name: Optional[str] = Form(default=None, max_length=160),
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
        source_text=source_text,
        source_name=source_name,
    )

    generation_id = str(uuid.uuid4())
    initialize_progress(
        generation_id,
        4,
        "Starter generering med opplastet bilde...",
        request_id=_request_id(request),
    )

    # Pass the pre-processed image path so background task skips URL download
    background_tasks.add_task(
        _run_durable_fov_job,
        generation_id,
        "lesson_with_image",
        lesson_request,
        request.headers.get("X-Skoleverksted-Project"),
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