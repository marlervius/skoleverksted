"""
Persist terminal pipeline jobs to disk so results survive process restarts (single instance).

Running jobs exist only in memory; completed/failed jobs are written as JSON under
output_dir/job_snapshots/.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path

import structlog

from app.config import get_settings
from app.models.state import PipelineState, PipelineStatus
from app.stores.fs_utils import atomic_write_text

logger = structlog.get_logger()

# Central in-memory job registry (single-worker deployments)
_memory_jobs: dict[str, PipelineState] = {}
_shared_resources: dict[str, dict] = {}

# A job is "terminal" once it has finished — including when it finished with
# warnings (e.g. unparseable math). Terminal jobs must be persisted so results
# survive a process restart / Render free-plan spin-down; otherwise the client
# polling /result after the instance recycles gets a 404 and appears to hang.
TERMINAL_STATUSES = (
    PipelineStatus.COMPLETED,
    PipelineStatus.COMPLETED_WITH_WARNINGS,
    PipelineStatus.FAILED,
)

# Job IDs are uuid4().hex (32 hex chars). Anything else is rejected before any
# filesystem access to prevent path traversal via crafted IDs (e.g. "../../x").
_JOB_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def is_safe_job_id(job_id: str) -> bool:
    """Reject IDs containing path separators or traversal sequences."""
    return bool(job_id) and bool(_JOB_ID_RE.match(job_id))


def get_job_memory() -> dict[str, PipelineState]:
    return _memory_jobs


def _snapshots_dir() -> Path:
    s = get_settings()
    d = Path(s.output_dir) / "job_snapshots"
    d.mkdir(parents=True, exist_ok=True)
    return d


def dump_state_compact(state: PipelineState, indent: int | None = None) -> str:
    """
    Serialize a PipelineState, omitting base64 PDF blobs when the PDF already
    exists on disk. Base64 doubles snapshot size (~300KB-1MB per job) and the
    /pdf endpoint reads from pdf_path or recompiles from full_document anyway.
    """
    exclude = None
    if state.pdf_path and Path(state.pdf_path).is_file():
        exclude = {"pdf_base64": True, "latex_compilation": {"pdf_base64"}}
    return state.model_dump_json(indent=indent, exclude=exclude)


def persist_terminal_job(state: PipelineState) -> None:
    """Write terminal jobs (completed / completed-with-warnings / failed) to disk."""
    if state.status not in TERMINAL_STATUSES:
        return
    try:
        path = _snapshots_dir() / f"{state.job_id}.json"
        atomic_write_text(path, dump_state_compact(state, indent=2))
        logger.debug("job_persisted", job_id=state.job_id, status=state.status.value)
    except OSError as e:
        logger.warning("job_persist_failed", job_id=state.job_id, error=str(e))


def load_job_from_disk(job_id: str) -> PipelineState | None:
    if not is_safe_job_id(job_id):
        logger.warning("job_load_rejected_unsafe_id", job_id=job_id)
        return None
    path = _snapshots_dir() / f"{job_id}.json"
    if not path.is_file():
        return None
    try:
        return PipelineState.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        logger.warning("job_load_failed", job_id=job_id, error=str(e))
        return None


def resolve_job(job_id: str, memory: dict[str, PipelineState] | None = None) -> PipelineState | None:
    """Prefer in-memory state; otherwise load from disk and warm the cache."""
    store = memory if memory is not None else _memory_jobs
    if job_id in store:
        return store[job_id]
    loaded = load_job_from_disk(job_id)
    if loaded is not None:
        store[job_id] = loaded
    return loaded


def get_resource_snapshot(resource_type: str, resource_id: str) -> dict | None:
    """Build a shareable content snapshot for a resource."""
    if resource_type == "generation":
        state = resolve_job(resource_id)
        if state is None:
            return None
        return {
            "full_document": state.full_document,
            "topic": state.request.topic,
            "grade": state.request.grade,
            "material_type": state.request.material_type,
            "job_id": state.job_id,
            "status": state.status.value,
        }
    return _shared_resources.get(resource_id)


def store_shared_resource(resource_id: str, content: dict) -> None:
    _shared_resources[resource_id] = content


def cleanup_old_snapshots(max_age_days: int = 7) -> int:
    """Remove job snapshot files older than max_age_days."""
    cutoff = datetime.now() - timedelta(days=max_age_days)
    removed = 0
    for path in _snapshots_dir().glob("*.json"):
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
            if mtime < cutoff:
                path.unlink(missing_ok=True)
                removed += 1
        except OSError:
            continue
    if removed:
        logger.info("job_snapshots_cleaned", removed=removed)
    return removed


def evict_terminal_jobs(
    memory: dict[str, PipelineState] | None = None,
    *,
    max_age_hours: int = 24,
    max_count: int = 200,
) -> int:
    """Drop completed/failed jobs from memory to prevent unbounded growth."""
    store = memory if memory is not None else _memory_jobs
    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    evicted = 0

    terminal = [
        (jid, st)
        for jid, st in store.items()
        if st.status in TERMINAL_STATUSES
    ]
    terminal.sort(key=lambda x: x[1].created_at)

    for jid, st in terminal:
        too_old = st.created_at < cutoff
        over_cap = len(store) > max_count
        if too_old or over_cap:
            store.pop(jid, None)
            evicted += 1

    if evicted:
        logger.info("jobs_evicted_from_memory", count=evicted)
    return evicted
