"""
Generation progress storage: in-memory by default, optional Redis for multi-instance.

Set REDIS_URL (e.g. redis://localhost:6379/0) to share progress across workers.
"""

from __future__ import annotations

import logging
import os
import pickle
import time
from typing import Any, Dict, Optional

if __package__:
    from .config import PROGRESS_TTL_SECONDS
else:
    from config import PROGRESS_TTL_SECONDS

logger = logging.getLogger(__name__)

TTL_SECONDS = PROGRESS_TTL_SECONDS

_MEMORY: Dict[str, Dict[str, Any]] = {}
_REDIS_CLIENT: Optional[Any] = None
_REDIS_TRIED = False


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
    return _MEMORY.get(generation_id)


def _save(generation_id: str, state: Dict[str, Any]) -> None:
    r = _get_redis()
    if r:
        r.setex(_redis_key(generation_id), TTL_SECONDS, pickle.dumps(state))
    else:
        _mem_cleanup()
        _MEMORY[generation_id] = state


def update_progress(generation_id: str, step: int, total_steps: int, message: str) -> None:
    state = dict(get_progress(generation_id) or {})
    state.update(
        {
            "step": step,
            "total_steps": total_steps,
            "message": message,
            "timestamp": time.time(),
        }
    )
    if step == -1:
        state.pop("pdf_bytes", None)
        state.pop("zip_bytes", None)
        state.pop("json_data", None)
    _save(generation_id, state)


def merge_progress(generation_id: str, **fields: Any) -> None:
    """Merge fields (e.g. pdf_bytes, filename, json_data) without clearing step/message."""
    state = dict(get_progress(generation_id) or {})
    for k, v in fields.items():
        if v is not None:
            state[k] = v
    _save(generation_id, state)


def progress_backend_label() -> str:
    """For health/debug: where generation progress is stored."""
    return "redis" if _get_redis() else "memory"


def clear_progress(generation_id: str) -> None:
    r = _get_redis()
    if r:
        r.delete(_redis_key(generation_id))
    else:
        _MEMORY.pop(generation_id, None)


def is_pdf_ready(progress: Optional[Dict[str, Any]]) -> bool:
    if not progress or progress.get("step") == -1:
        return False
    return (
        progress.get("step") == progress.get("total_steps")
        and progress.get("step", 0) > 0
        and bool(progress.get("pdf_bytes"))
    )


def is_zip_ready(progress: Optional[Dict[str, Any]]) -> bool:
    if not progress or progress.get("step") == -1:
        return False
    return (
        progress.get("step") == progress.get("total_steps")
        and progress.get("step", 0) > 0
        and bool(progress.get("zip_bytes"))
    )


def is_json_preview_ready(progress: Optional[Dict[str, Any]]) -> bool:
    if not progress or progress.get("step") == -1:
        return False
    return (
        progress.get("step") == progress.get("total_steps")
        and progress.get("step", 0) > 0
        and bool(progress.get("json_data"))
    )
