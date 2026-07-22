from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .models import Feedback, FeedbackCreate, Job, Project, ProjectCreate, ProjectUpdate, utc_now


def _default_db_path() -> Path:
    configured = os.getenv("SKOLEVERKSTED_DB_PATH", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    output_dir = Path(os.getenv("OUTPUT_DIR", "./output"))
    return (output_dir / "platform" / "skoleverksted.sqlite3").resolve()


class PlatformStore:
    """Small durable platform store, deliberately independent of authentication.

    SQLite is the local/default backend. Its API is intentionally narrow so the
    implementation can later be replaced by PostgreSQL when school tenancy is
    introduced without changing the frontend contract.
    """

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path is not None else _default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @contextmanager
    def _connection(self):
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._lock, self._connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    module TEXT NOT NULL,
                    status TEXT NOT NULL,
                    project_id TEXT,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_projects_updated ON projects(updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_jobs_updated ON jobs(updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_jobs_project ON jobs(project_id);
                CREATE TABLE IF NOT EXISTS feedback (
                    id TEXT PRIMARY KEY,
                    module TEXT NOT NULL,
                    project_id TEXT,
                    rating TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_feedback_created ON feedback(created_at DESC);
                """
            )

    @staticmethod
    def _json(value: dict[str, Any]) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    def health(self) -> dict[str, Any]:
        with self._connection() as conn:
            conn.execute("SELECT 1").fetchone()
        return {"status": "healthy", "backend": "sqlite", "path": str(self.path)}

    def create_project(self, request: ProjectCreate, *, status: str = "draft") -> Project:
        project = Project(**request.model_dump(), status=status)
        payload = project.model_dump()
        with self._lock, self._connection() as conn:
            conn.execute(
                "INSERT INTO projects(id,payload,status,created_at,updated_at) VALUES(?,?,?,?,?)",
                (project.id, self._json(payload), project.status, project.created_at, project.updated_at),
            )
        return project

    def get_project(self, project_id: str) -> Project | None:
        with self._connection() as conn:
            row = conn.execute("SELECT payload FROM projects WHERE id=?", (project_id,)).fetchone()
        return Project.model_validate_json(row["payload"]) if row else None

    def list_projects(self, *, limit: int = 50, status: str | None = None) -> list[Project]:
        query = "SELECT payload FROM projects"
        params: list[Any] = []
        if status:
            query += " WHERE status=?"
            params.append(status)
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        with self._connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [Project.model_validate_json(row["payload"]) for row in rows]

    def update_project(self, project_id: str, request: ProjectUpdate) -> Project | None:
        current = self.get_project(project_id)
        if current is None:
            return None
        changes = request.model_dump(exclude_none=True)
        payload = current.model_dump()
        payload.update(changes)
        payload["updated_at"] = utc_now()
        project = Project.model_validate(payload)
        with self._lock, self._connection() as conn:
            conn.execute(
                "UPDATE projects SET payload=?,status=?,updated_at=? WHERE id=?",
                (self._json(project.model_dump()), project.status, project.updated_at, project_id),
            )
        return project

    def upsert_job(self, job: Job) -> Job:
        payload = job.model_dump()
        with self._lock, self._connection() as conn:
            conn.execute(
                """INSERT INTO jobs(id,module,status,project_id,payload,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                     module=excluded.module,status=excluded.status,project_id=excluded.project_id,
                     payload=excluded.payload,updated_at=excluded.updated_at""",
                (job.id, job.module, job.status, job.project_id, self._json(payload), job.created_at, job.updated_at),
            )
        return job

    def update_job_state(
        self,
        job_id: str,
        *,
        status: str,
        message: str = "",
        progress: int | None = None,
        retryable: bool | None = None,
    ) -> Job | None:
        current = self.get_job(job_id)
        if current is None:
            return None
        payload = current.model_dump()
        payload.update(status=status, message=message, updated_at=utc_now())
        if progress is not None:
            payload["progress"] = max(0, min(100, progress))
        if retryable is not None:
            payload["retryable"] = retryable
        if status != "queued":
            payload["queue_position"] = None
        return self.upsert_job(Job.model_validate(payload))

    def queue_position(self, job_id: str) -> int | None:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT created_at,status FROM jobs WHERE id=?",
                (job_id,),
            ).fetchone()
            if row is None or row["status"] != "queued":
                return None
            ahead = conn.execute(
                "SELECT COUNT(*) AS n FROM jobs WHERE status='queued' AND created_at<=?",
                (row["created_at"],),
            ).fetchone()["n"]
        return max(1, int(ahead))

    def recover_incomplete_jobs(self) -> int:
        """Mark work lost during a process restart as safely retryable."""
        active = ("queued", "planning", "generating", "verifying", "rendering")
        placeholders = ",".join("?" for _ in active)
        with self._lock, self._connection() as conn:
            rows = conn.execute(
                f"SELECT payload FROM jobs WHERE status IN ({placeholders})",
                active,
            ).fetchall()
            for row in rows:
                payload = json.loads(row["payload"])
                payload.update(
                    status="needs_review",
                    progress=0,
                    retryable=True,
                    queue_position=None,
                    message="Serveren startet på nytt før jobben var ferdig. Prøv igjen med samme utkast.",
                    updated_at=utc_now(),
                )
                conn.execute(
                    "UPDATE jobs SET payload=?,status=?,updated_at=? WHERE id=?",
                    (self._json(payload), "needs_review", payload["updated_at"], payload["id"]),
                )
        return len(rows)

    def get_job(self, job_id: str) -> Job | None:
        with self._connection() as conn:
            row = conn.execute("SELECT payload FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            return None
        job = Job.model_validate_json(row["payload"])
        if job.status == "queued":
            job.queue_position = self.queue_position(job.id)
        return job

    def list_jobs(self, *, limit: int = 100, project_id: str | None = None) -> list[Job]:
        query = "SELECT payload FROM jobs"
        params: list[Any] = []
        if project_id:
            query += " WHERE project_id=?"
            params.append(project_id)
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        with self._connection() as conn:
            rows = conn.execute(query, params).fetchall()
        jobs = [Job.model_validate_json(row["payload"]) for row in rows]
        for job in jobs:
            if job.status == "queued":
                job.queue_position = self.queue_position(job.id)
        return jobs

    def create_feedback(self, request: FeedbackCreate) -> Feedback:
        feedback = Feedback(**request.model_dump())
        with self._lock, self._connection() as conn:
            conn.execute(
                "INSERT INTO feedback(id,module,project_id,rating,payload,created_at) VALUES(?,?,?,?,?,?)",
                (feedback.id, feedback.module, feedback.project_id, feedback.rating, self._json(feedback.model_dump()), feedback.created_at),
            )
        return feedback

    def list_feedback(self, *, limit: int = 100) -> list[Feedback]:
        with self._connection() as conn:
            rows = conn.execute("SELECT payload FROM feedback ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [Feedback.model_validate_json(row["payload"]) for row in rows]


_store: PlatformStore | None = None
_store_lock = threading.Lock()


def get_platform_store() -> PlatformStore:
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = PlatformStore()
    return _store
