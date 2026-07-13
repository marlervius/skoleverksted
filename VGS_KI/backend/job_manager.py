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
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

if __package__:
    from .media_manager import image_processor
    from . import config
else:
    from media_manager import image_processor
    import config

logger = logging.getLogger(__name__)


# ── Job store ─────────────────────────────────────────────────────────────────

@dataclass
class Job:
    queue: asyncio.Queue
    created_at: float = field(default_factory=time.time)
    pdf: Optional[bytes] = None
    filename: Optional[str] = None
    # Separate teacher fact-report PDF (spec 2.8): never appended to the
    # student PDF, downloaded through its own endpoint.
    rapport_pdf: Optional[bytes] = None
    rapport_filename: Optional[str] = None
    error: Optional[str] = None
    done: bool = False


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
    with _jobs_lock:
        _jobs[job_id] = Job(queue=queue)
    return job_id, queue


def get_job(job_id: str) -> Optional[Job]:
    with _jobs_lock:
        return _jobs.get(job_id)


def pop_job(job_id: str) -> Optional[Job]:
    with _jobs_lock:
        return _jobs.pop(job_id, None)


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


def compute_cache_key(prefix: str, payload: Any) -> str:
    """Compute a stable cache key from a Pydantic model dump."""
    blob = json.dumps(payload.model_dump() if hasattr(payload, 'model_dump') else payload,
                      sort_keys=True, default=str).encode()
    return f"{prefix}_{hashlib.md5(blob).hexdigest()}"


def run_job_in_thread(
    job_id: str,
    queue: asyncio.Queue,
    request_payload: Any,
    worker: Callable[[JobContext], tuple[bytes, str]],
    cache_key: Optional[str] = None,
    cache=None,
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
    loop = asyncio.get_event_loop()

    from main import RequestLogger  # avoid circular import at module load
    req_logger = RequestLogger(logger, {'request_id': job_id[:8]})

    def push(msg: str) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, {"type": "progress", "message": msg})

    def thread_main() -> None:
        job_start = time.time()
        try:
            pdf_bytes: Optional[bytes] = None
            filename: Optional[str] = None
            job_meta: dict = {}
            worker_duration: float = 0.0

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
                    return value.get("pdf")
                return value

            def _cache_value() -> dict:
                return {
                    "pdf": pdf_bytes,
                    "filename": filename,
                    "rapport_pdf": job_meta.get("rapport_pdf"),
                    "rapport_filename": job_meta.get("rapport_filename"),
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
                            )
                            _t = time.time()
                            pdf_bytes, filename = worker(ctx)
                            worker_duration = time.time() - _t
                            try:
                                cache.set(cache_key, _cache_value(), expire=config.CACHE_TTL_SECONDS)
                            except Exception as e:
                                req_logger.warning(f"Failed to write cache: {e}")
            else:
                ctx = JobContext(
                    job_id=job_id, queue=queue, loop=loop,
                    push=push, req_logger=req_logger,
                    request_payload=request_payload, cache_key=None,
                    set_meta=set_meta_fn,
                )
                _t = time.time()
                pdf_bytes, filename = worker(ctx)
                worker_duration = time.time() - _t

            if filename is None:
                # Cache hit: derive filename from request payload's topic
                topic = getattr(request_payload, 'topic', 'document')
                level = getattr(request_payload, 'level', '')
                safe = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_'
                               for c in str(topic)).strip()[:50]
                filename = f"{safe}_{level}.pdf" if level else f"{safe}.pdf"

            with _jobs_lock:
                job = _jobs.get(job_id)
                if job:
                    job.pdf = pdf_bytes
                    job.filename = filename
                    job.rapport_pdf = job_meta.get("rapport_pdf")
                    job.rapport_filename = job_meta.get("rapport_filename")
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

            done_event: dict = {"type": "done", "filename": filename}
            for field in ("basis_text", "image_url", "worksheet_text",
                          "faktarapport_text", "language_exercises", "warnings",
                          "source_name", "lint_issues"):
                if job_meta.get(field):
                    done_event[field] = job_meta[field]
            # Boolean flags must be forwarded even when False, so the UI can
            # distinguish "ungrounded" from "unknown".
            if "source_grounded" in job_meta:
                done_event["source_grounded"] = bool(job_meta["source_grounded"])
            # Tell the UI a separate teacher fact-report PDF exists (bytes
            # themselves never go over SSE).
            done_event["has_faktarapport"] = bool(job_meta.get("rapport_pdf"))
            loop.call_soon_threadsafe(queue.put_nowait, done_event)

        except Exception as e:
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
            else:
                err_msg = f"{type(e).__name__}: {e}"
                req_logger.error(
                    f"Job {job_id[:8]} failed: {err_msg} (req_id={job_id[:8]})",
                    exc_info=True,
                )
            with _jobs_lock:
                job = _jobs.get(job_id)
                if job:
                    job.error = f"{err_msg} (request_id: {job_id[:8]})"
                    job.done = True
            loop.call_soon_threadsafe(
                queue.put_nowait,
                {"type": "error", "message": f"{err_msg} (request_id: {job_id[:8]})"},
            )

    threading.Thread(target=thread_main, daemon=True, name=f"job-{job_id[:8]}").start()


# ── Helper for sanitising filenames ───────────────────────────────────────────

def safe_filename(prefix: str, topic: str, suffix: str) -> str:
    safe = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in topic).strip()[:50]
    return f"{prefix}_{safe}_{suffix}.pdf"
