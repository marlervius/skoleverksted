from __future__ import annotations

import os
import threading
import time
import uuid
import logging
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any, Iterator

from .models import Job
from .store import get_platform_store


logger = logging.getLogger(__name__)


class _RedisJobLease:
    """Best-effort distributed capacity lease for multi-instance deployments."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.client: Any | None = None
        self.key = os.getenv("REDIS_JOB_LEASE_KEY", "skoleverksted:jobs:active")
        self.lease_seconds = max(600, int(os.getenv("REDIS_JOB_LEASE_SECONDS", "3600")))
        url = os.getenv("REDIS_URL", "").strip()
        if not url:
            return
        try:
            import redis  # type: ignore

            client = redis.from_url(url, decode_responses=True, socket_connect_timeout=3)
            client.ping()
            self.client = client
            logger.info("Jobbkø: bruker distribuert Redis-kapasitetslås")
        except Exception as exc:
            logger.warning("REDIS_URL er satt, men Redis er utilgjengelig: %s", exc)

    @property
    def configured(self) -> bool:
        return self.client is not None

    def _try_acquire(self, token: str) -> bool:
        if self.client is None:
            return True
        now = time.time()
        script = (
            "redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', ARGV[1]); "
            "if redis.call('ZCARD', KEYS[1]) < tonumber(ARGV[2]) then "
            "redis.call('ZADD', KEYS[1], ARGV[3], ARGV[4]); return 1; end; return 0"
        )
        return bool(self.client.eval(script, 1, self.key, now, self.limit, now + self.lease_seconds, token))

    def _release(self, token: str) -> None:
        if self.client is not None:
            try:
                self.client.zrem(self.key, token)
            except Exception:
                logger.warning("Kunne ikke frigjøre Redis-jobblås", exc_info=True)

    @contextmanager
    def claim(self, job_id: str) -> Iterator[None]:
        if self.client is None:
            yield
            return
        token = f"{os.getpid()}:{threading.get_ident()}:{job_id}:{uuid.uuid4().hex}"
        try:
            while not self._try_acquire(token):
                time.sleep(0.5)
        except Exception as exc:
            # A Redis outage must not strand a teacher's job indefinitely. The
            # durable SQLite state remains authoritative and the local gate is
            # still active for this process.
            logger.warning("Redis-jobblåsen feilet; fortsetter lokalt: %s", exc)
            self.client = None
            yield
            return
        try:
            yield
        finally:
            self._release(token)


def _safe_summary(payload: Any) -> dict[str, Any]:
    """Keep useful queue context without persisting sources or free text."""
    fields = (
        "topic", "theme", "subject", "level", "grade", "material_type",
        "package_id", "artifact_id", "artifact_type", "package_revision",
        "school_year", "number_of_periods",
    )

    def value(field: str) -> Any:
        if isinstance(payload, dict):
            return payload.get(field)
        return getattr(payload, field, None)

    return {field: str(value(field))[:160] for field in fields if value(field) is not None}


class DurableJobGate:
    """One process-wide capacity gate backed by a durable SQLite ledger."""

    def __init__(self) -> None:
        limit = max(1, int(os.getenv("MAX_CONCURRENT_JOBS", "1")))
        self._gate = threading.BoundedSemaphore(limit)
        self._distributed = _RedisJobLease(limit)
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
            with self._distributed.claim(job_id):
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
