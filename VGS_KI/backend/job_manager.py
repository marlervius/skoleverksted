"""Job manager: shared async-job infrastructure for all generation endpoints.

Replaces the duplicated `run_job()` boilerplate that previously lived in
each `/generate-*-start` endpoint. Centralises:

- Job store with TTL cleanup (no more memory leaks)
- Cache-key locking (no more race-condition double-generation)
- SSE progress queue
- Image fetch + retry with explicit logging
- Uniform error reporting with request_id
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from Skoleverksted.backend.platform.queue import JobCancelled, get_durable_job_queue

if __package__:
    from .media_manager import image_processor
    from . import config
    from .logging_utils import RequestLogger
else:
    from media_manager import image_processor
    import config
    from logging_utils import RequestLogger

logger = logging.getLogger(__name__)


class GenerationCancelled(RuntimeError):
    """Internal signal used to finish a user-cancelled job exactly once."""


TERMINAL_JOB_STATUSES = frozenset({
    "source_approved",
    "needs_teacher_review",
    "failed",
    "cancelled",
})


# ── Job store ─────────────────────────────────────────────────────────────────

@dataclass
class Job:
    queue: asyncio.Queue
    loop: Optional[asyncio.AbstractEventLoop] = None
    request_payload: Any = None
    created_at: float = field(default_factory=time.time)
    pdf: Optional[bytes] = None
    filename: Optional[str] = None
    # Separate teacher guide with fact review and answer guidance: never
    # appended to the student PDF.
    rapport_pdf: Optional[bytes] = None
    rapport_filename: Optional[str] = None
    error: Optional[str] = None
    done: bool = False
    status: str = "queued"
    cancel_event: threading.Event = field(default_factory=threading.Event)
    terminal_event_sent: bool = False
    progress: dict[str, Any] = field(default_factory=dict)
    verification_content: str = ""
    truth_passport: dict[str, Any] = field(default_factory=dict)
    quarantine: list[dict[str, Any]] = field(default_factory=list)
    quality_rounds: list[dict[str, Any]] = field(default_factory=list)
    quality_stop_reason: str = ""
    review_payload: dict[str, Any] = field(default_factory=dict)
    variant_issues: list[str] = field(default_factory=list)
    teacher_approved_at: str = ""
    approved_digest: str = ""


_jobs: dict[str, Job] = {}
_jobs_lock = threading.Lock()

# Per-cache-key locks to prevent two identical requests from generating twice.
_cache_key_locks: dict[str, threading.Lock] = {}
_cache_key_locks_lock = threading.Lock()


def _get_cache_key_lock(cache_key: str) -> threading.Lock:
    """Return (creating if necessary) a lock dedicated to one cache key."""
    with _cache_key_locks_lock:
        lock = _cache_key_locks.get(cache_key)
        if lock is None:
            lock = threading.Lock()
            _cache_key_locks[cache_key] = lock
        return lock


def cleanup_stale_jobs() -> int:
    """Remove jobs older than JOB_TTL_SECONDS. Returns the count removed."""
    cutoff = time.time() - config.JOB_TTL_SECONDS
    removed = 0
    with _jobs_lock:
        stale = [jid for jid, j in _jobs.items() if j.created_at < cutoff]
        for jid in stale:
            _jobs.pop(jid, None)
            removed += 1
    if removed:
        logger.info(f"Cleaned up {removed} stale job(s) older than {config.JOB_TTL_SECONDS}s")
    return removed


def start_cleanup_task() -> None:
    """Spawn a background daemon that periodically cleans stale jobs."""
    def _loop():
        while True:
            time.sleep(config.JOB_CLEANUP_INTERVAL_SECONDS)
            try:
                cleanup_stale_jobs()
            except Exception as e:
                logger.error(f"Job cleanup loop error: {e}", exc_info=True)
    threading.Thread(target=_loop, daemon=True, name="job-cleanup").start()
    logger.info(
        f"Started job cleanup loop "
        f"(interval={config.JOB_CLEANUP_INTERVAL_SECONDS}s, ttl={config.JOB_TTL_SECONDS}s)"
    )


def register_job() -> tuple[str, asyncio.Queue]:
    """Create a new job, return its id and queue."""
    job_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue()
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    with _jobs_lock:
        _jobs[job_id] = Job(queue=queue, loop=loop)
    return job_id, queue


def get_job(job_id: str) -> Optional[Job]:
    with _jobs_lock:
        return _jobs.get(job_id)


def pop_job(job_id: str) -> Optional[Job]:
    with _jobs_lock:
        return _jobs.pop(job_id, None)


def is_job_cancelled(job_id: str) -> bool:
    job = get_job(job_id)
    return bool(job and (job.cancel_event.is_set() or job.status == "cancelled"))


def cancel_job(job_id: str) -> Optional[Job]:
    """Mark a job cancelled immediately; repeated calls are idempotent."""
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            return None
        if job.status in TERMINAL_JOB_STATUSES:
            return job
        job.cancel_event.set()
        job.status = "cancelled"
        job.done = True
        job.pdf = None
        job.rapport_pdf = None
        if not job.terminal_event_sent:
            job.terminal_event_sent = True
            event = {"type": "cancelled", "status": "cancelled", "message": "Genereringen er avbrutt."}
            if job.loop and not job.loop.is_closed():
                job.loop.call_soon_threadsafe(job.queue.put_nowait, event)
            else:
                job.queue.put_nowait(event)
    logger.info("job_cancelled", extra={"job_id": job_id})
    return job


# ── Image fetch with explicit retry logging ───────────────────────────────────

def fetch_image_with_retry(
    image_url: Optional[str],
    image_data: Optional[str],
    req_logger: logging.LoggerAdapter,
) -> Optional[str]:
    """Fetch and optimise an image, logging every retry and failure explicitly.

    Returns the local processed image path, or None if everything failed.
    """
    # 1. Try user-uploaded base64 image first
    if image_data:
        path = image_processor.process_base64_image(image_data)
        if path:
            req_logger.info("Custom user image processed successfully")
            return path
        req_logger.warning("Custom user image processing failed; falling back to AI image")

    if not image_url:
        req_logger.info("No image URL available — proceeding without image")
        return None

    # 2. Try the AI-suggested URL directly
    path = image_processor.process_image(image_url)
    if path:
        req_logger.info(f"Image fetched on first attempt: {image_url[:80]}")
        return path

    # 3. Wikimedia thumb-URL retry — log explicitly when this kicks in
    if 'wikimedia.org' in image_url and '/commons/' in image_url and '/thumb/' not in image_url:
        thumb_url = (
            image_url.replace('/commons/', '/commons/thumb/')
            + '/800px-' + image_url.split('/')[-1]
        )
        req_logger.warning(
            f"Direct Wikimedia URL failed, retrying with thumb variant: {thumb_url[:80]}"
        )
        path = image_processor.process_image(thumb_url)
        if path:
            req_logger.info("Thumb-variant retry succeeded")
            return path
        req_logger.error(
            f"Both direct and thumb URLs failed for: {image_url[:80]} — proceeding without image"
        )
        return None

    req_logger.error(f"Image fetch failed (no retry possible): {image_url[:80]}")
    return None


# ── Job factory ───────────────────────────────────────────────────────────────

@dataclass
class JobContext:
    """Everything a worker function needs to do its job."""
    job_id: str
    queue: asyncio.Queue
    loop: asyncio.AbstractEventLoop
    push: Callable[[str], None]
    req_logger: logging.LoggerAdapter
    request_payload: Any
    cache_key: Optional[str] = None
    set_meta: Optional[Callable[[str, Any], None]] = None
    cancel_check: Optional[Callable[[], bool]] = None
    meta: Optional[dict[str, Any]] = None


def compute_cache_key(prefix: str, payload: Any) -> str:
    """Compute a stable cache key that changes with the prompt contract."""
    value = payload.model_dump() if hasattr(payload, 'model_dump') else payload
    blob = json.dumps(
        {
            "prompt_version": os.getenv("PROMPT_VERSION", "fag-v3-quality-gates"),
            "payload": value,
        },
        sort_keys=True,
        default=str,
    ).encode()
    return f"{prefix}_{hashlib.md5(blob).hexdigest()}"


def run_job_in_thread(
    job_id: str,
    queue: asyncio.Queue,
    request_payload: Any,
    worker: Callable[[JobContext], tuple[bytes, str]],
    cache_key: Optional[str] = None,
    cache=None,
    project_id: str | None = None,
) -> None:
    """Spawn a background thread that runs `worker(ctx)` and manages job state.

    `worker` is the per-endpoint function that generates content + PDF and
    returns `(pdf_bytes, filename)`. It receives a JobContext with everything
    it needs, including a `push(msg)` for SSE progress updates.

    Cache-locking: if `cache_key` and `cache` are provided, this function:
    - Checks the cache first; on hit, skips worker.
    - Holds a per-cache-key lock so two simultaneous identical requests
      do not both invoke the (expensive) worker.
    """
    job = get_job(job_id)
    loop = job.loop if job and job.loop else asyncio.get_event_loop()

    req_logger = RequestLogger(logger, {'request_id': job_id[:8]})
    durable_queue = get_durable_job_queue()
    payload_kind = type(request_payload).__name__.replace("Request", "").lower() or "generation"
    durable_queue.enqueue(
        job_id,
        module="fag",
        kind=payload_kind,
        payload=request_payload,
        project_id=project_id,
    )

    def schedule_event(event: dict) -> None:
        """Best-effort SSE delivery; clients/tests may close their loop first."""
        try:
            if not loop.is_closed():
                loop.call_soon_threadsafe(queue.put_nowait, event)
        except RuntimeError:
            pass

    def push(msg: str, **details: Any) -> None:
        with _jobs_lock:
            current_job = _jobs.get(job_id)
            if current_job:
                current_job.progress = dict(details)
        schedule_event({"type": "progress", "message": msg, **details})

    def thread_main() -> None:
        job_start = time.time()
        try:
            if is_job_cancelled(job_id):
                raise GenerationCancelled("job cancelled before worker start")
            with _jobs_lock:
                current_job = _jobs.get(job_id)
                if current_job:
                    current_job.status = "generating"
            pdf_bytes: Optional[bytes] = None
            filename: Optional[str] = None
            job_meta: dict = {}
            worker_duration: float = 0.0
            with _jobs_lock:
                current_job = _jobs.get(job_id)
                if current_job:
                    current_job.request_payload = request_payload

            def set_meta_fn(key: str, value: Any) -> None:
                job_meta[key] = value

            def _unpack_cached(value) -> Optional[bytes]:
                """Cache values are either raw pdf bytes (legacy) or a dict
                that also carries the separate fact-report PDF."""
                nonlocal filename
                if isinstance(value, dict):
                    if value.get("rapport_pdf"):
                        job_meta["rapport_pdf"] = value["rapport_pdf"]
                        job_meta["rapport_filename"] = value.get("rapport_filename")
                    if value.get("filename"):
                        filename = value["filename"]
                    for key in (
                        "verification_content", "truth_passport", "quarantine",
                        "quality_rounds", "quality_stop_reason", "quality_status",
                        "review_payload", "variant_issues",
                    ):
                        if key in value:
                            job_meta[key] = value[key]
                    return value.get("pdf")
                return value

            def _cache_value() -> dict:
                return {
                    "pdf": pdf_bytes,
                    "filename": filename,
                    "rapport_pdf": job_meta.get("rapport_pdf"),
                    "rapport_filename": job_meta.get("rapport_filename"),
                    "verification_content": job_meta.get("verification_content", ""),
                    "truth_passport": job_meta.get("truth_passport", {}),
                    "quarantine": job_meta.get("quarantine", []),
                    "quality_rounds": job_meta.get("quality_rounds", []),
                    "quality_stop_reason": job_meta.get("quality_stop_reason", ""),
                    "quality_status": job_meta.get("quality_status", "needs_teacher_review"),
                    "review_payload": job_meta.get("review_payload", {}),
                    "variant_issues": job_meta.get("variant_issues", []),
                }

            # ── Cache check / lock ──
            if cache_key and cache is not None:
                if cache_key in cache:
                    req_logger.info(f"Cache hit: {cache_key[:24]}…")
                    pdf_bytes = _unpack_cached(cache.get(cache_key))
                else:
                    lock = _get_cache_key_lock(cache_key)
                    with lock:
                        # Re-check inside the lock (another thread may have populated it)
                        if cache_key in cache:
                            req_logger.info(f"Cache hit after wait: {cache_key[:24]}…")
                            pdf_bytes = _unpack_cached(cache.get(cache_key))
                        else:
                            ctx = JobContext(
                                job_id=job_id, queue=queue, loop=loop,
                                push=push, req_logger=req_logger,
                                request_payload=request_payload, cache_key=cache_key,
                                set_meta=set_meta_fn,
                                cancel_check=lambda: is_job_cancelled(job_id),
                                meta=job_meta,
                            )
                            _t = time.time()
                            pdf_bytes, filename = worker(ctx)
                            worker_duration = time.time() - _t
                            if is_job_cancelled(job_id):
                                raise GenerationCancelled("job cancelled during worker")
                            try:
                                if job_meta.get("quality_status", "needs_teacher_review") == "source_approved":
                                    cache.set(cache_key, _cache_value(), expire=config.CACHE_TTL_SECONDS)
                            except Exception as e:
                                req_logger.warning(f"Failed to write cache: {e}")
            else:
                ctx = JobContext(
                    job_id=job_id, queue=queue, loop=loop,
                    push=push, req_logger=req_logger,
                    request_payload=request_payload, cache_key=None,
                    set_meta=set_meta_fn,
                    cancel_check=lambda: is_job_cancelled(job_id),
                    meta=job_meta,
                )
                _t = time.time()
                pdf_bytes, filename = worker(ctx)
                worker_duration = time.time() - _t

            if is_job_cancelled(job_id):
                raise GenerationCancelled("job cancelled after worker")

            if filename is None:
                # Cache hit: derive filename from request payload's topic
                topic = getattr(request_payload, 'topic', 'document')
                level = getattr(request_payload, 'level', '')
                safe = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_'
                               for c in str(topic)).strip()[:50]
                filename = f"{safe}_{level}.pdf" if level else f"{safe}.pdf"

            quality_status = str(job_meta.get("quality_status") or "needs_teacher_review")
            if quality_status not in {"source_approved", "needs_teacher_review"}:
                # Unknown states must never fall through to an approved PDF.
                quality_status = "needs_teacher_review"
            with _jobs_lock:
                job = _jobs.get(job_id)
                if job:
                    job.pdf = pdf_bytes if quality_status == "source_approved" else None
                    job.filename = filename
                    job.rapport_pdf = job_meta.get("rapport_pdf")
                    job.rapport_filename = job_meta.get("rapport_filename")
                    job.verification_content = str(job_meta.get("verification_content") or "")
                    job.truth_passport = dict(job_meta.get("truth_passport") or {})
                    job.quarantine = list(job_meta.get("quarantine") or [])
                    job.quality_rounds = list(job_meta.get("quality_rounds") or [])
                    job.quality_stop_reason = str(job_meta.get("quality_stop_reason") or "")
                    job.review_payload = dict(job_meta.get("review_payload") or {})
                    job.variant_issues = list(job_meta.get("variant_issues") or [])
                    job.status = quality_status
                    job.done = True

            total_duration = time.time() - job_start
            req_logger.info(
                f"Job done in {total_duration:.1f}s (worker {worker_duration:.1f}s)",
                extra={
                    "worker_duration_s": round(worker_duration, 2),
                    "total_duration_s": round(total_duration, 2),
                    "payload_type": type(request_payload).__name__,
                },
            )

            done_event: dict = {
                "type": "done" if quality_status == "source_approved" else "needs_teacher_review",
                "status": quality_status,
                "job_id": job_id,
                "filename": filename,
            }
            for field in ("basis_text", "image_url", "image_metadata", "worksheet_text",
                          "faktarapport_text", "language_exercises", "warnings",
                          "truth_passport",
                          "quarantine", "quality_rounds", "quality_stop_reason",
                          "source_name", "prompt_version", "lint_issues",
                          "review_payload", "variant_issues"):
                if job_meta.get(field):
                    done_event[field] = job_meta[field]
            # Boolean flags must be forwarded even when False, so the UI can
            # distinguish "ungrounded" from "unknown".
            if "source_grounded" in job_meta:
                done_event["source_grounded"] = bool(job_meta["source_grounded"])
            # Tell the UI a separate teacher guide exists (bytes
            # themselves never go over SSE).
            done_event["has_faktarapport"] = bool(job_meta.get("rapport_pdf"))
            done_event["quality_status"] = quality_status
            if quality_status == "needs_teacher_review":
                done_event["review_url"] = f"/generation/{job_id}/review"
            schedule_event(done_event)
            with _jobs_lock:
                job = _jobs.get(job_id)
                if job:
                    job.terminal_event_sent = True
            logger.info(
                "job_completed",
                extra={"job_id": job_id, "status": quality_status, "duration_s": round(total_duration, 2)},
            )
            logger.info(
                "package_completed",
                extra={"job_id": job_id, "status": quality_status, "duration_s": round(total_duration, 2)},
            )

        except GenerationCancelled:
            with _jobs_lock:
                job = _jobs.get(job_id)
                already_sent = bool(job and job.terminal_event_sent)
                if job:
                    job.cancel_event.set()
                    job.status = "cancelled"
                    job.done = True
            if not already_sent:
                schedule_event({"type": "cancelled", "status": "cancelled", "message": "Genereringen er avbrutt."})
            logger.info("job_cancelled", extra={"job_id": job_id})
        except Exception as e:
            # A provider cancellation exception must not be translated into a
            # failed job after the API has already marked it cancelled.
            if is_job_cancelled(job_id):
                with _jobs_lock:
                    job = _jobs.get(job_id)
                    already_sent = bool(job and job.terminal_event_sent)
                    if job:
                        job.status = "cancelled"
                        job.done = True
                if not already_sent:
                    schedule_event({"type": "cancelled", "status": "cancelled", "message": "Genereringen er avbrutt."})
                logger.info("job_cancelled", extra={"job_id": job_id, "stage": "provider"})
                return
            err_str = str(e)
            # Friendly message for Gemini quota exhaustion (429)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                import re as _re
                m = _re.search(r'retry in (\d+)', err_str, _re.IGNORECASE)
                wait = m.group(1) if m else "60"
                err_msg = (
                    f"API-kvoten er midlertidig brukt opp. "
                    f"Prøv igjen om {wait} sekunder."
                )
                req_logger.warning(f"Job {job_id[:8]} hit rate limit (429): retry in {wait}s")
            elif "API_KEY_INVALID" in err_str or "API key not valid" in err_str:
                err_msg = (
                    "Tjenesten mangler en gyldig API-nøkkel. Kontakt den som "
                    "drifter Skoleverksted."
                )
                req_logger.error(
                    f"Job {job_id[:8]} failed: invalid provider API key (req_id={job_id[:8]})",
                    exc_info=True,
                )
            else:
                # Log everything, show nothing internal: provider errors contain
                # English stack text and service metadata that only confuses a
                # teacher. The request id is enough to find the real cause.
                err_msg = (
                    "Noe gikk galt under generering. Prøv igjen litt senere, "
                    "eller kontakt support med referansen under."
                )
                req_logger.error(
                    f"Job {job_id[:8]} failed: {type(e).__name__}: {e} (req_id={job_id[:8]})",
                    exc_info=True,
                )
            with _jobs_lock:
                job = _jobs.get(job_id)
                if job:
                    job.error = f"{err_msg} (request_id: {job_id[:8]})"
                    job.status = "failed"
                    job.done = True
                    job.terminal_event_sent = True
            logger.error(
                "job_failed",
                extra={"job_id": job_id, "error_type": type(e).__name__},
            )
            schedule_event({
                "type": "error",
                "status": "failed",
                "message": f"{err_msg} (request_id: {job_id[:8]})",
            })

    def queued_thread_main() -> None:
        def announce(position: int) -> None:
            push(f"Venter i kø (plass {position}) …")

        try:
            with durable_queue.claim(
                job_id,
                on_wait=announce,
                auto_complete=False,
                cancel_check=lambda: is_job_cancelled(job_id),
            ):
                thread_main()
        except JobCancelled:
            durable_queue.cancel(job_id)
            logger.info("job_cancelled", extra={"job_id": job_id, "stage": "queue"})
            return
        job = get_job(job_id)
        if job and job.error:
            durable_queue.fail(job_id, job.error)
        elif job and job.status == "cancelled":
            durable_queue.cancel(job_id)
        elif job and job.status == "needs_teacher_review":
            durable_queue.finish(job_id, message="Krever lærergjennomgang")
        elif job and job.done:
            durable_queue.finish(job_id)

    threading.Thread(target=queued_thread_main, daemon=True, name=f"job-{job_id[:8]}").start()


# ── Helper for sanitising filenames ───────────────────────────────────────────

def safe_filename(prefix: str, topic: str, suffix: str) -> str:
    safe = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in topic).strip()[:50]
    return f"{prefix}_{safe}_{suffix}.pdf"
