from __future__ import annotations

import os
import threading
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any, Iterator

from .models import Job
from .store import get_platform_store


def _safe_summary(payload: Any) -> dict[str, Any]:
    """Keep useful queue context without persisting sources or free text."""
    fields = ("topic", "theme", "subject", "level", "grade", "material_type")
    return {
        field: str(getattr(payload, field, ""))[:160]
        for field in fields
        if getattr(payload, field, None)
    }


class DurableJobGate:
    """One process-wide capacity gate backed by a durable SQLite ledger."""

    def __init__(self) -> None:
        limit = max(1, int(os.getenv("MAX_CONCURRENT_JOBS", "1")))
        self._gate = threading.BoundedSemaphore(limit)
        self._store = get_platform_store()
        self._store.recover_incomplete_jobs()

    def enqueue(
        self,
        job_id: str,
        *,
        module: str,
        kind: str,
        payload: Any = None,
        project_id: str | None = None,
    ) -> Job:
        existing = self._store.get_job(job_id)
        attempt = (existing.attempt + 1) if existing else 1
        job = Job(
            id=job_id,
            module=module,  # type: ignore[arg-type]
            kind=kind,
            status="queued",
            progress=0,
            message="Venter på ledig kapasitet …",
            project_id=project_id,
            request_summary=_safe_summary(payload),
            retryable=True,
            attempt=attempt,
        )
        self._store.upsert_job(job)
        job.queue_position = self._store.queue_position(job_id)
        return job

    @contextmanager
    def claim(
        self,
        job_id: str,
        *,
        on_wait: Callable[[int], None] | None = None,
        auto_complete: bool = True,
    ) -> Iterator[None]:
        position = self._store.queue_position(job_id) or 1
        if on_wait:
            on_wait(position)
        self._gate.acquire()
        try:
            self._store.update_job_state(
                job_id,
                status="generating",
                message="Generering pågår …",
                progress=5,
                retryable=True,
            )
            yield
        except BaseException as exc:
            self._store.update_job_state(
                job_id,
                status="failed",
                message=f"{type(exc).__name__}: {str(exc)[:240]}",
                progress=100,
                retryable=True,
            )
            raise
        else:
            if not auto_complete:
                return
            self._store.update_job_state(
                job_id,
                status="completed",
                message="Ferdig",
                progress=100,
                retryable=False,
            )
        finally:
            self._gate.release()

    def finish(self, job_id: str, *, message: str = "Ferdig") -> Job | None:
        return self._store.update_job_state(
            job_id,
            status="completed",
            message=message,
            progress=100,
            retryable=False,
        )

    def fail(self, job_id: str, message: str) -> Job | None:
        return self._store.update_job_state(
            job_id,
            status="failed",
            message=message[:280],
            progress=100,
            retryable=True,
        )

    def cancel(self, job_id: str) -> Job | None:
        return self._store.update_job_state(
            job_id,
            status="cancelled",
            message="Avbrutt av bruker",
            progress=100,
            retryable=True,
        )


_queue: DurableJobGate | None = None
_lock = threading.Lock()


def get_durable_job_queue() -> DurableJobGate:
    global _queue
    if _queue is None:
        with _lock:
            if _queue is None:
                _queue = DurableJobGate()
    return _queue
