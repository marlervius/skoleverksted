"""Durable execution for compendium chapter repair.

The teacher-facing request only *registers* work. Everything that can hang —
two grounded model calls, the truth audit, the write-back — happens in a worker
that owns a durable job row, a leased chapter lock, a compare-and-swap token and
a forensic ledger. A dropped HTTP connection, a client timeout or a backend
restart therefore cannot decide the fate of a repair.
"""

from __future__ import annotations

import logging
import os
import threading
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from .compendium import repair_compendium_chapter, repair_preconditions
from .models import (
    REPAIR_JOB_KIND,
    Compendium,
    CompendiumChapter,
    Job,
    RepairJob,
    utc_now,
)
from .queue import get_durable_job_queue
from .store import StaleChapterWriteError, get_platform_store


logger = logging.getLogger(__name__)


def _lease_seconds() -> int:
    return max(120, min(3600, int(os.getenv("COMPENDIUM_REPAIR_LEASE_SECONDS", "900"))))


_MIRROR_STATUS: dict[str, tuple[str, int, bool]] = {
    # repair status -> (platform job status, progress, retryable)
    "queued": ("queued", 0, True),
    "running": ("generating", 20, True),
    "succeeded": ("completed", 100, False),
    "failed_retryable": ("needs_review", 100, True),
    "failed_terminal": ("failed", 100, False),
    "cancelled": ("cancelled", 100, True),
    "superseded": ("superseded", 100, False),
}


class RepairConflictError(RuntimeError):
    """Another repair already owns this chapter."""

    def __init__(self, job: RepairJob) -> None:
        super().__init__(
            f"En automatisk retting kjører allerede for dette kapittelet (jobb {job.id})."
        )
        self.job = job


class _Recorder:
    """Writes the forensic ledger and remembers what the model actually did."""

    def __init__(self, store: Any, job: RepairJob) -> None:
        self._store = store
        self._job = job
        self.repair_call_failed = False
        self.failure_reason = ""

    def __call__(self, stage: str, data: dict[str, Any]) -> None:
        if stage == "model_failed" and data.get("call") == "repair":
            self.repair_call_failed = True
            self.failure_reason = str(data.get("error") or data.get("error_type") or "")
        self.write(stage, **data)

    def write(self, stage: str, **data: Any) -> None:
        self._store.append_repair_event(self._job.id, self._job.operation_id, stage, data)


class RepairService:
    """One durable repair pipeline, backed by the existing DurableJobGate."""

    def __init__(
        self,
        *,
        store: Any | None = None,
        spawn: Callable[[Callable[[], None]], None] | None = None,
        gate: Any | None = None,
    ) -> None:
        self._store = store or get_platform_store()
        self._spawn = spawn or _spawn_daemon
        self._gate = gate
        self._store.recover_incomplete_repair_jobs()

    @property
    def gate(self) -> Any:
        if self._gate is None:
            self._gate = get_durable_job_queue()
        return self._gate

    # -- registration -------------------------------------------------

    def submit(
        self,
        compendium: Compendium,
        chapter_id: str,
        *,
        operation_id: str,
    ) -> RepairJob:
        """Validate, reserve the chapter and persist the job — no model work.

        Raises `KeyError`/`ValueError` for a request that can never succeed and
        `RepairConflictError` when the chapter is already being repaired.
        """
        chapter, repair_notes = repair_preconditions(compendium, chapter_id)
        self._store.expire_stale_repair_leases()
        candidate = RepairJob(
            id=uuid4().hex,
            operation_id=operation_id,
            compendium_id=compendium.id,
            chapter_id=chapter_id,
            chapter_title=chapter.title[:180],
            status="queued",
            message="Reparasjonen er registrert og venter på ledig kapasitet …",
            chapter_token=self._store.chapter_content_token(chapter),
        )
        job, outcome = self._store.register_repair_job(candidate)
        if outcome == "conflict":
            raise RepairConflictError(job)
        if outcome == "idempotent":
            return job
        self._mirror(job)
        self._store.append_repair_event(
            job.id,
            job.operation_id,
            "registered",
            {
                "compendium_id": compendium.id,
                "chapter_id": chapter_id,
                "chapter_title": chapter.title,
                "note_count": len(repair_notes),
                "chapter_token": job.chapter_token,
                "attempt": job.attempt,
                "subject": compendium.subject,
                "level": compendium.level,
            },
        )
        self._spawn(lambda: self.execute(job.id))
        return job

    # -- execution ----------------------------------------------------

    def execute(self, job_id: str) -> RepairJob | None:
        """Run one registered repair to a terminal state.

        Safe to call from a worker thread; every exit path writes a durable
        status and releases the chapter lock.
        """
        job = self._store.claim_repair_job(job_id, lease_seconds=_lease_seconds())
        if job is None:
            # Cancelled, already claimed or released by recovery.
            return self._store.get_repair_job(job_id)
        self._mirror(job)
        recorder = _Recorder(self._store, job)
        recorder.write("claimed", attempt=job.attempt, lease_expires_at=job.lease_expires_at)

        heartbeat = _Heartbeat(self._store, job.id)
        try:
            with self.gate.claim(job.id, auto_complete=False):
                heartbeat.start()
                return self._run(job, recorder)
        except BaseException as exc:  # the gate must never own the outcome
            logger.exception("Reparasjonsjobb %s stoppet uventet", job.id)
            recorder.write("failed", error_type=type(exc).__name__, error=str(exc))
            return self._finish(
                job,
                "failed_retryable",
                f"Reparasjonen stoppet uventet ({type(exc).__name__}). Kapittelet er ikke endret.",
            )
        finally:
            heartbeat.stop()

    def _run(self, job: RepairJob, recorder: _Recorder) -> RepairJob | None:
        compendium = self._store.get_compendium(job.compendium_id)
        if compendium is None:
            recorder.write("failed", error_type="MissingCompendium")
            return self._finish(job, "failed_terminal", "Kompendiet finnes ikke lenger.")
        try:
            repair_preconditions(compendium, job.chapter_id)
        except KeyError as exc:
            recorder.write("failed", error_type="KeyError", error=str(exc))
            return self._finish(job, "failed_terminal", str(exc))
        except ValueError as exc:
            recorder.write("failed", error_type="ValueError", error=str(exc))
            return self._finish(job, "failed_terminal", str(exc))

        try:
            chapter = repair_compendium_chapter(
                compendium,
                job.chapter_id,
                observer=recorder,
            )
        except Exception as exc:
            recorder.write("failed", error_type=type(exc).__name__, error=str(exc))
            return self._finish(
                job,
                "failed_retryable",
                f"Reparasjonen feilet ({type(exc).__name__}). Kapittelet er ikke endret.",
            )

        current = self._store.get_repair_job(job.id)
        if current is not None and current.cancel_requested:
            recorder.write("cancelled", content_written=False)
            return self._finish(
                job,
                "cancelled",
                "Læreren avbrøt reparasjonen. Resultatet ble forkastet og kapittelet er uendret.",
                expected_statuses=("running", "cancelled"),
            )

        return self._write_back(job, chapter, recorder)

    def _write_back(
        self,
        job: RepairJob,
        chapter: CompendiumChapter,
        recorder: _Recorder,
    ) -> RepairJob | None:
        try:
            updated = self._store.replace_compendium_chapter_if_unchanged(
                job.compendium_id,
                chapter,
                job.chapter_token,
            )
        except StaleChapterWriteError as exc:
            recorder.write(
                "superseded",
                expected_token=exc.expected,
                actual_token=exc.actual,
                content_written=False,
            )
            return self._finish(
                job,
                "superseded",
                "Kapittelet ble redigert mens reparasjonen kjørte. "
                "Den nyere teksten er beholdt, og reparasjonsresultatet ble forkastet.",
            )
        except Exception as exc:
            recorder.write("failed", error_type=type(exc).__name__, error=str(exc), content_written=False)
            return self._finish(
                job,
                "failed_retryable",
                f"Lagringen av reparasjonen feilet ({type(exc).__name__}). Kapittelet er ikke endret.",
            )
        if updated is None:
            recorder.write("failed", error_type="MissingChapter", content_written=False)
            return self._finish(job, "failed_terminal", "Kapitlet finnes ikke lenger.")

        stored = next((item for item in updated.chapters if item.id == chapter.id), chapter)
        result_token = self._store.chapter_content_token(stored)
        recorder.write(
            "write_back",
            content_written=True,
            chapter_status=stored.status,
            revision_count=stored.revision_count,
            result_token=result_token,
        )
        if recorder.repair_call_failed:
            return self._finish(
                job,
                "failed_retryable",
                "Modellen klarte ikke å fullføre rettingen. Kapittelteksten er bevart "
                "uendret med oppdaterte kontrollmerknader; prøv igjen.",
                result_token=result_token,
                chapter_status=stored.status,
            )
        recorder.write("succeeded", chapter_status=stored.status)
        return self._finish(
            job,
            "succeeded",
            "Reparasjonen er fullført og kapittelet er oppdatert.",
            result_token=result_token,
            chapter_status=stored.status,
        )

    # -- cancellation --------------------------------------------------

    def cancel(self, job_id: str) -> RepairJob | None:
        job = self._store.request_repair_cancel(job_id)
        if job is None:
            return None
        self._store.append_repair_event(job.id, job.operation_id, "cancel_requested", {"status": job.status})
        self._mirror(job)
        return job

    # -- helpers -------------------------------------------------------

    def _finish(
        self,
        job: RepairJob,
        status: str,
        message: str,
        *,
        result_token: str = "",
        chapter_status: str | None = None,
        expected_statuses: tuple[str, ...] = ("queued", "running"),
    ) -> RepairJob | None:
        finished = self._store.finish_repair_job(
            job.id,
            status=status,
            message=message,
            result_token=result_token,
            chapter_status=chapter_status,
            expected_statuses=expected_statuses,
        )
        if finished is None:
            # Cancelled or recovered while we worked; that record wins.
            return self._store.get_repair_job(job.id)
        self._mirror(finished)
        return finished

    def _mirror(self, job: RepairJob) -> Job | None:
        """Keep the shared job ledger honest so /jobs and /queue stay usable."""
        status, progress, retryable = _MIRROR_STATUS[job.status]
        existing = self._store.get_job(job.id)
        mirrored = Job(
            id=job.id,
            module="platform",
            kind=REPAIR_JOB_KIND,
            status=status,  # type: ignore[arg-type]
            progress=progress,
            message=job.message,
            request_summary={
                "compendium_id": job.compendium_id,
                "chapter_id": job.chapter_id,
                "chapter_title": job.chapter_title,
                "operation_id": job.operation_id,
            },
            result_summary={
                "repair_status": job.status,
                "chapter_status": job.chapter_status or "",
                "status_url": job.status_url,
            },
            retryable=retryable,
            attempt=job.attempt,
            created_at=existing.created_at if existing else job.created_at,
            updated_at=utc_now(),
        )
        try:
            return self._store.upsert_job(mirrored)
        except Exception:
            logger.warning("Kunne ikke speile reparasjonsjobb %s i jobbledgeren", job.id, exc_info=True)
            return None


class _Heartbeat:
    """Renews the chapter lease while the model call is outstanding."""

    def __init__(self, store: Any, job_id: str) -> None:
        self._store = store
        self._job_id = job_id
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        interval = max(10, _lease_seconds() // 3)

        def beat() -> None:
            while not self._stop.wait(interval):
                try:
                    self._store.heartbeat_repair_job(self._job_id, lease_seconds=_lease_seconds())
                except Exception:
                    logger.warning("Kunne ikke fornye reparasjonslåsen", exc_info=True)

        self._thread = threading.Thread(target=beat, name=f"repair-lease-{self._job_id}", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()


def _spawn_daemon(work: Callable[[], None]) -> None:
    threading.Thread(target=work, name="compendium-repair-worker", daemon=True).start()


_service: RepairService | None = None
_service_lock = threading.Lock()


def get_repair_service() -> RepairService:
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                _service = RepairService()
    return _service


def reset_repair_service() -> None:
    """Test seam: drop the cached service so a fresh store is picked up."""
    global _service
    with _service_lock:
        _service = None
