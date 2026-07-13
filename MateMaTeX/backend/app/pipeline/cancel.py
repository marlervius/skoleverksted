"""Cooperative cancellation for in-flight generation jobs."""

from __future__ import annotations

import threading

_lock = threading.Lock()
_cancelled: set[str] = set()


def cancel_job(job_id: str) -> None:
    with _lock:
        _cancelled.add(job_id)


def is_cancelled(job_id: str) -> bool:
    with _lock:
        return job_id in _cancelled


def clear_cancel(job_id: str) -> None:
    with _lock:
        _cancelled.discard(job_id)
