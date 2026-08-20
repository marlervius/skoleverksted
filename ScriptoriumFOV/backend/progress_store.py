"""
Generation progress storage: in-memory by default, optional Redis for multi-instance.

Set REDIS_URL (e.g. redis://localhost:6379/0) to share progress across workers.
"""

from __future__ import annotations

import logging
import os
import pickle
import threading
import time
from typing import Any, Dict, Optional

if __package__:
    from .config import GENERATION_MAX_SECONDS, PROGRESS_TTL_SECONDS
else:
    from config import GENERATION_MAX_SECONDS, PROGRESS_TTL_SECONDS

logger = logging.getLogger(__name__)

TTL_SECONDS = PROGRESS_TTL_SECONDS

_MEMORY: Dict[str, Dict[str, Any]] = {}
_REDIS_CLIENT: Optional[Any] = None
_REDIS_TRIED = False
_LOCK = threading.RLock()

TERMINAL_STATUSES = frozenset(
    {"completed", "needs_teacher_review", "needs_user_action", "failed", "cancelled"}
)


def _get_redis():
    """Return Redis client or None (lazy init, fall back to memory on failure)."""
    global _REDIS_CLIENT, _REDIS_TRIED
    if _REDIS_TRIED:
        return _REDIS_CLIENT
    _REDIS_TRIED = True
    url = os.getenv("REDIS_URL", "").strip()
    if not url:
        return None
    try:
        import redis  # type: ignore

        r = redis.from_url(url, decode_responses=False, socket_connect_timeout=3)
        r.ping()
        _REDIS_CLIENT = r
        logger.info("Generation progress: using Redis (REDIS_URL)")
        return r
    except Exception as e:
        logger.warning(
            "REDIS_URL is set but Redis is unavailable (%s); using in-memory progress store",
            e,
        )
        _REDIS_CLIENT = None
        return None


def _mem_cleanup() -> None:
    now = time.time()
    for k, v in list(_MEMORY.items()):
        if now - v.get("timestamp", now) > TTL_SECONDS:
            _MEMORY.pop(k, None)


def _redis_key(generation_id: str) -> str:
    return f"fov:gen:{generation_id}"


def get_progress(generation_id: str) -> Optional[Dict[str, Any]]:
    with _LOCK:
        r = _get_redis()
        if r:
            data = r.get(_redis_key(generation_id))
            if not data:
                return None
            try:
                return pickle.loads(data)
            except Exception as e:
                logger.error("Corrupt progress for %s: %s", generation_id, e)
                return None
        state = _MEMORY.get(generation_id)
        return dict(state) if state is not None else None


def _save(generation_id: str, state: Dict[str, Any]) -> None:
    r = _get_redis()
    if r:
        r.setex(_redis_key(generation_id), TTL_SECONDS, pickle.dumps(state))
    else:
        _mem_cleanup()
        _MEMORY[generation_id] = dict(state)


def _append_event(
    state: Dict[str, Any],
    generation_id: str,
    event_type: str,
    *,
    status: str | None = None,
    artifact: dict | None = None,
    error_code: str | None = None,
    message: str | None = None,
    step_key: str | None = None,
    step_name: str | None = None,
) -> None:
    """Keep a bounded, JSON-safe event ledger for status recovery and support."""

    event = {
        "type": event_type,
        "job_id": generation_id,
        "request_id": state.get("request_id") or "unknown",
        "timestamp": time.time(),
    }
    if status:
        event["status"] = status
    if artifact:
        event["artifact"] = artifact
    if error_code:
        event["error_code"] = error_code
    if message:
        event["message"] = message
    if step_key:
        event["step_key"] = step_key
    if step_name:
        event["step_name"] = step_name
    events = list(state.get("events") or [])
    events.append(event)
    state["events"] = events[-50:]
    state["event_type"] = event_type
    state["last_event"] = event


def initialize_progress(
    generation_id: str,
    total_steps: int,
    message: str,
    *,
    request_id: str = "",
    request_summary: dict | None = None,
) -> None:
    """Create a job with an explicit non-terminal running status."""

    state: Dict[str, Any] = {
        "job_id": generation_id,
        "request_id": request_id,
        "step": 0,
        "total_steps": total_steps,
        "message": message,
        "job_status": "running",
        "status": "running",
        "terminal_status": None,
        "event_type": "progress",
        "timestamp": time.time(),
        "started_at": time.time(),
        "deadline_at": time.time() + GENERATION_MAX_SECONDS,
        "request_summary": dict(request_summary or {}),
        "events": [],
    }
    _append_event(state, generation_id, "progress", status="running")
    with _LOCK:
        _save(generation_id, state)


def initialize_progress_once(
    generation_id: str,
    total_steps: int,
    message: str,
    *,
    request_id: str = "",
    request_summary: dict | None = None,
) -> bool:
    """Atomically create a job unless an idempotent request already did so."""

    with _LOCK:
        if get_progress(generation_id) is not None:
            return False
        initialize_progress(
            generation_id,
            total_steps,
            message,
            request_id=request_id,
            request_summary=request_summary,
        )
        return True


def update_progress(
    generation_id: str,
    step: int,
    total_steps: int,
    message: str,
    *,
    request_id: str | None = None,
    event_type: str = "progress",
    job_status: str | None = None,
    error_code: str | None = None,
    step_key: str | None = None,
    step_name: str | None = None,
    attempt: int | None = None,
    service: str | None = None,
    model: str | None = None,
    duration_ms: float | None = None,
    error: dict | None = None,
    available_actions: list[str] | None = None,
) -> None:
    """Update progress without allowing numeric progress to imply completion."""

    with _LOCK:
        state = dict(get_progress(generation_id) or {})
        state.update(
            {
                "job_id": generation_id,
                "step": step,
                "total_steps": total_steps,
                "message": message,
                "timestamp": time.time(),
            }
        )
        if step_key:
            state["step_key"] = step_key
        if step_name:
            state["step_name"] = step_name
        if attempt is not None:
            state["attempt"] = attempt
        if service:
            state["service"] = service
        if model:
            state["model"] = model
        if duration_ms is not None:
            state["duration_ms"] = duration_ms
        if error is not None:
            state["error"] = dict(error)
        if available_actions is not None:
            state["available_actions"] = list(available_actions)
        if request_id:
            state["request_id"] = request_id
        if step == -1:
            job_status = "failed"
            event_type = "error"
            state["terminal_status"] = "failed"
            state.pop("pdf_bytes", None)
            state.pop("zip_bytes", None)
            state.pop("json_data", None)
            state.pop("artifact", None)
        if job_status:
            if job_status not in TERMINAL_STATUSES and job_status != "running":
                raise ValueError(f"Unsupported job status: {job_status}")
            state["job_status"] = job_status
            state["status"] = job_status
            if job_status in TERMINAL_STATUSES:
                state["terminal_status"] = job_status
        else:
            state.setdefault("job_status", "running")
        state["status"] = state.get("job_status", "running")
        _append_event(
            state,
            generation_id,
            event_type,
            status=state.get("job_status"),
            error_code=error_code,
            message=message,
            step_key=step_key or state.get("step_key"),
            step_name=step_name or state.get("step_name"),
        )
        _save(generation_id, state)


def merge_progress(generation_id: str, **fields: Any) -> None:
    """Merge fields (e.g. pdf_bytes, filename, json_data) without clearing step/message."""
    with _LOCK:
        state = dict(get_progress(generation_id) or {})
        for k, v in fields.items():
            if v is not None:
                state[k] = v
        _save(generation_id, state)


def publish_event(
    generation_id: str,
    event_type: str,
    *,
    message: str | None = None,
    job_status: str | None = None,
    artifact: dict | None = None,
    error_code: str | None = None,
    error: dict | None = None,
    available_actions: list[str] | None = None,
) -> None:
    """Publish a named lifecycle event and optionally its terminal job status."""

    if event_type not in {
        "progress",
        "artifact_building",
        "artifact_ready",
        "review_required",
        "user_action_required",
        "error",
        "failed",  # legacy readers
        "cancelled",
        "done",
    }:
        raise ValueError(f"Unsupported event type: {event_type}")
    with _LOCK:
        state = dict(get_progress(generation_id) or {})
        if message is not None:
            state["message"] = message
        if artifact is not None:
            state["artifact"] = artifact
        if error is not None:
            state["error"] = dict(error)
        if available_actions is not None:
            state["available_actions"] = list(available_actions)
        if job_status:
            if job_status not in TERMINAL_STATUSES and job_status != "running":
                raise ValueError(f"Unsupported job status: {job_status}")
            state["job_status"] = job_status
            state["status"] = job_status
            if job_status in TERMINAL_STATUSES:
                state["terminal_status"] = job_status
        state["timestamp"] = time.time()
        _append_event(
            state,
            generation_id,
            event_type,
            status=state.get("job_status"),
            artifact=artifact or state.get("artifact"),
            error_code=error_code,
            message=message,
            step_key=state.get("step_key"),
            step_name=state.get("step_name"),
        )
        _save(generation_id, state)


def progress_backend_label() -> str:
    """For health/debug: where generation progress is stored."""
    return "redis" if _get_redis() else "memory"


def clear_progress(generation_id: str) -> None:
    with _LOCK:
        r = _get_redis()
        if r:
            r.delete(_redis_key(generation_id))
        else:
            _MEMORY.pop(generation_id, None)


def list_events(generation_id: str, *, after: int = 0) -> list[Dict[str, Any]]:
    """Return JSON-safe lifecycle events after a zero-based cursor."""

    state = get_progress(generation_id) or {}
    events = list(state.get("events") or [])
    start = max(0, int(after))
    return [dict(event) for event in events[start:]]


def is_pdf_ready(progress: Optional[Dict[str, Any]]) -> bool:
    if not progress or progress.get("step") == -1:
        return False
    return (
        progress.get("step") == progress.get("total_steps")
        and progress.get("step", 0) > 0
        and bool(progress.get("pdf_bytes"))
        and progress.get("job_status", "completed") == "completed"
        and (progress.get("artifact") or {}).get("content_type") == "application/pdf"
    )


def is_zip_ready(progress: Optional[Dict[str, Any]]) -> bool:
    if not progress or progress.get("step") == -1:
        return False
    return (
        progress.get("step") == progress.get("total_steps")
        and progress.get("step", 0) > 0
        and bool(progress.get("zip_bytes"))
        and progress.get("job_status", "completed") == "completed"
        and (progress.get("artifact") or {}).get("content_type") == "application/zip"
    )


def is_json_preview_ready(progress: Optional[Dict[str, Any]]) -> bool:
    if not progress or progress.get("step") == -1:
        return False
    return (
        progress.get("step") == progress.get("total_steps")
        and progress.get("step", 0) > 0
        and bool(progress.get("json_data"))
        and progress.get("job_status", "completed") == "completed"
    )
