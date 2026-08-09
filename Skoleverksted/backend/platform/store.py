from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .models import (
    ACTIVE_REPAIR_STATUSES,
    Compendium,
    CompendiumChapter,
    CompendiumCreate,
    CompendiumUpdate,
    Feedback,
    FeedbackCreate,
    Job,
    Project,
    ProjectCreate,
    ProjectUpdate,
    RepairJob,
    RepairLedgerEntry,
    YearPlan,
    YearPlanCreate,
    YearPlanMaterial,
    YearPlanMaterialCreate,
    YearPlanMaterialUpdate,
    YearPlanPeriod,
    YearPlanPeriodUpdate,
    YearPlanUpdate,
    TeachingArtifact,
    TeachingArtifactFile,
    TeachingPackage,
    TeachingPackageUpdate,
    utc_now,
)


def _default_db_path() -> Path:
    configured = os.getenv("SKOLEVERKSTED_DB_PATH", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    output_dir = Path(os.getenv("OUTPUT_DIR", "./output"))
    return (output_dir / "platform" / "skoleverksted.sqlite3").resolve()


def _lease_deadline(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=max(30, seconds))).isoformat()


_SECRET_KEY_MARKERS = ("key", "token", "secret", "password", "authorization", "credential")
# Compare-and-swap tokens are content hashes, not credentials, and the incident
# cannot be reconstructed without them.
_LEDGER_KEY_ALLOWLIST = frozenset({
    "chapter_token",
    "result_token",
    "expected_token",
    "actual_token",
})
_LEDGER_TEXT_LIMIT = 400


def _ledger_safe(payload: dict[str, Any]) -> dict[str, Any]:
    """Keep the forensic ledger useful without turning it into a secret store.

    Anything that looks like a credential is dropped, and free text is capped.
    Callers are expected to pass hashes and counters, not prompts or responses.
    """
    safe: dict[str, Any] = {}
    for key, value in payload.items():
        lowered = str(key).casefold()
        if (
            any(marker in lowered for marker in _SECRET_KEY_MARKERS)
            and not lowered.endswith("_hash")
            and lowered not in _LEDGER_KEY_ALLOWLIST
        ):
            continue
        if isinstance(value, str):
            safe[key] = value[:_LEDGER_TEXT_LIMIT]
        elif isinstance(value, (int, float, bool)) or value is None:
            safe[key] = value
        elif isinstance(value, dict):
            safe[key] = _ledger_safe(value)
        elif isinstance(value, (list, tuple)):
            safe[key] = [
                item[:_LEDGER_TEXT_LIMIT] if isinstance(item, str) else item
                for item in list(value)[:20]
                if isinstance(item, (str, int, float, bool))
            ]
        else:
            safe[key] = str(value)[:_LEDGER_TEXT_LIMIT]
    return safe


class StaleChapterWriteError(RuntimeError):
    """The chapter changed after the worker read it."""

    def __init__(self, expected: str, actual: str) -> None:
        super().__init__("Kapittelet ble endret mens reparasjonen kjørte.")
        self.expected = expected
        self.actual = actual


class StaleTeachingArtifactError(RuntimeError):
    """Raised when a worker tries to write over newer teacher/package state."""

    def __init__(self, expected: str, actual: str) -> None:
        super().__init__("Artefaktet ble endret mens jobben kjørte.")
        self.expected = expected
        self.actual = actual


class ProjectedMaterialError(RuntimeError):
    """A derived teaching-package material cannot be edited as source data."""


class _PostgresConnection:
    """Small compatibility wrapper so the store keeps one SQL surface."""

    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def execute(self, query: str, params: Any = ()):
        return self._connection.execute(query.replace("?", "%s"), params)

    def executescript(self, script: str) -> None:
        for statement in script.split(";"):
            if statement.strip():
                self.execute(statement)

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        self._connection.close()


class PlatformStore:
    """Small durable platform store, deliberately independent of authentication.

    SQLite is the local/default backend. Its API is intentionally narrow so the
    implementation can later be replaced by PostgreSQL when school tenancy is
    introduced without changing the frontend contract.
    """

    def __init__(self, path: str | Path | None = None, files_dir: str | Path | None = None):
        self.database_url = os.getenv("DATABASE_URL", "").strip() if path is None else ""
        self.uses_postgres = self.database_url.startswith(("postgres://", "postgresql://"))
        self.path = Path(path) if path is not None else _default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if files_dir is not None:
            self.files_dir = Path(files_dir)
        elif path is not None:
            self.files_dir = self.path.parent / "year-plan-files"
        else:
            self.files_dir = Path(os.getenv("OUTPUT_DIR", "./output")) / "year-plans"
        self.files_dir.mkdir(parents=True, exist_ok=True)
        self.compendia_dir = (
            self.path.parent / "compendium-files"
            if path is not None
            else Path(os.getenv("OUTPUT_DIR", "./output")) / "compendia"
        )
        self.compendia_dir.mkdir(parents=True, exist_ok=True)
        self.teaching_packages_dir = (
            self.path.parent / "teaching-packages"
            if path is not None
            else Path(os.getenv("OUTPUT_DIR", "./output")) / "teaching-packages"
        )
        self.teaching_packages_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        if self.uses_postgres:
            try:
                import psycopg  # type: ignore
                from psycopg.rows import dict_row  # type: ignore
            except ImportError as exc:  # pragma: no cover - deployment configuration
                raise RuntimeError("DATABASE_URL er satt, men psycopg er ikke installert.") from exc
            connection = psycopg.connect(self.database_url, connect_timeout=8, row_factory=dict_row)
            return _PostgresConnection(connection)  # type: ignore[return-value]
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA synchronous=NORMAL")
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
                CREATE TABLE IF NOT EXISTS year_plans (
                    id TEXT PRIMARY KEY,
                    subject TEXT NOT NULL,
                    level TEXT NOT NULL,
                    school_year TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_year_plans_updated ON year_plans(updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_year_plans_subject ON year_plans(subject,level,school_year);
                CREATE TABLE IF NOT EXISTS teaching_packages (
                    id TEXT PRIMARY KEY,
                    year_plan_id TEXT NOT NULL,
                    period_id TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    level TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_teaching_packages_period
                    ON teaching_packages(year_plan_id,period_id,updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_teaching_packages_updated
                    ON teaching_packages(updated_at DESC);
                CREATE TABLE IF NOT EXISTS compendia (
                    id TEXT PRIMARY KEY,
                    subject TEXT NOT NULL,
                    level TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_compendia_updated ON compendia(updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_compendia_subject ON compendia(subject,level,kind);
                CREATE TABLE IF NOT EXISTS repair_jobs (
                    id TEXT PRIMARY KEY,
                    operation_id TEXT NOT NULL,
                    compendium_id TEXT NOT NULL,
                    chapter_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_repair_jobs_chapter
                    ON repair_jobs(compendium_id,chapter_id,created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_repair_jobs_status ON repair_jobs(status);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_repair_jobs_operation
                    ON repair_jobs(compendium_id,chapter_id,operation_id);
                CREATE TABLE IF NOT EXISTS repair_events (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    operation_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_repair_events_job ON repair_events(job_id,created_at);
                """
            )

    @staticmethod
    def _json(value: dict[str, Any]) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    def health(self) -> dict[str, Any]:
        with self._connection() as conn:
            conn.execute("SELECT 1").fetchone()
        return {
            "status": "healthy",
            "backend": "postgres" if self.uses_postgres else "sqlite",
            "path": "DATABASE_URL" if self.uses_postgres else str(self.path),
        }

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

    def update_job_result_summary(
        self,
        job_id: str,
        summary: dict[str, Any],
        *,
        quality_passport: dict[str, Any] | None = None,
    ) -> Job | None:
        current = self.get_job(job_id)
        if current is None:
            return None
        current.result_summary = dict(summary)
        if quality_passport is not None:
            current.quality_passport = dict(quality_passport)
        current.updated_at = utc_now()
        return self.upsert_job(current)

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

    def create_year_plan(self, request: YearPlanCreate, *, status: str = "draft") -> YearPlan:
        plan = YearPlan(**request.model_dump(), status=status)
        with self._lock, self._connection() as conn:
            conn.execute(
                """INSERT INTO year_plans(
                       id,subject,level,school_year,status,payload,created_at,updated_at
                   ) VALUES(?,?,?,?,?,?,?,?)""",
                (
                    plan.id,
                    plan.subject,
                    plan.level,
                    plan.school_year,
                    plan.status,
                    self._json(plan.model_dump()),
                    plan.created_at,
                    plan.updated_at,
                ),
            )
        return plan

    def get_year_plan(self, plan_id: str) -> YearPlan | None:
        with self._connection() as conn:
            row = conn.execute("SELECT payload FROM year_plans WHERE id=?", (plan_id,)).fetchone()
        return YearPlan.model_validate_json(row["payload"]) if row else None

    def list_year_plans(
        self,
        *,
        limit: int = 50,
        status: str | None = None,
        school_year: str | None = None,
    ) -> list[YearPlan]:
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status=?")
            params.append(status)
        if school_year:
            clauses.append("school_year=?")
            params.append(school_year)
        query = "SELECT payload FROM year_plans"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        with self._connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [YearPlan.model_validate_json(row["payload"]) for row in rows]

    def _save_year_plan(self, plan: YearPlan) -> YearPlan:
        with self._lock, self._connection() as conn:
            conn.execute(
                """UPDATE year_plans
                   SET subject=?,level=?,school_year=?,status=?,payload=?,updated_at=?
                   WHERE id=?""",
                (
                    plan.subject,
                    plan.level,
                    plan.school_year,
                    plan.status,
                    self._json(plan.model_dump()),
                    plan.updated_at,
                    plan.id,
                ),
            )
        return plan

    def update_year_plan(self, plan_id: str, request: YearPlanUpdate) -> YearPlan | None:
        current = self.get_year_plan(plan_id)
        if current is None:
            return None
        payload = current.model_dump()
        payload.update(request.model_dump(exclude_none=True))
        payload["updated_at"] = utc_now()
        return self._save_year_plan(YearPlan.model_validate(payload))

    def update_year_plan_period(
        self,
        plan_id: str,
        period_id: str,
        request: YearPlanPeriodUpdate,
    ) -> YearPlan | None:
        plan = self.get_year_plan(plan_id)
        if plan is None:
            return None
        changes = request.model_dump(exclude_none=True)
        found = False
        periods: list[YearPlanPeriod] = []
        for period in plan.periods:
            if period.id == period_id:
                payload = period.model_dump()
                payload.update(changes)
                period = YearPlanPeriod.model_validate(payload)
                found = True
            periods.append(period)
        if not found:
            return None
        payload = plan.model_dump()
        payload["periods"] = [period.model_dump() for period in periods]
        payload["updated_at"] = utc_now()
        return self._save_year_plan(YearPlan.model_validate(payload))

    def add_year_plan_material(
        self,
        plan_id: str,
        period_id: str,
        request: YearPlanMaterialCreate,
        content: bytes,
    ) -> tuple[YearPlan, YearPlanMaterial] | None:
        if not content or len(content) > 30_000_000:
            raise ValueError("Materialfilen må være mellom 1 byte og 30 MB.")
        plan = self.get_year_plan(plan_id)
        if plan is None:
            return None
        target = next((period for period in plan.periods if period.id == period_id), None)
        if target is None:
            return None
        versions = [item.version for item in target.materials if item.kind == request.kind]
        material = YearPlanMaterial(
            **request.model_dump(),
            version=(max(versions) + 1) if versions else 1,
            size_bytes=len(content),
        )
        plan_dir = self.files_dir / plan_id
        plan_dir.mkdir(parents=True, exist_ok=True)
        final_path = plan_dir / f"{material.id}.bin"
        temp_path = plan_dir / f".{material.id}.tmp"
        temp_path.write_bytes(content)
        temp_path.replace(final_path)
        try:
            target.materials.append(material)
            if request.status == "approved" and target.status == "not_started":
                target.status = "in_progress"
            payload = plan.model_dump()
            payload["updated_at"] = utc_now()
            saved = self._save_year_plan(YearPlan.model_validate(payload))
        except Exception:
            final_path.unlink(missing_ok=True)
            raise
        return saved, material

    def get_year_plan_material(
        self,
        plan_id: str,
        material_id: str,
    ) -> tuple[YearPlanMaterial, Path] | None:
        plan = self.get_year_plan(plan_id)
        if plan is None:
            return None
        for period in plan.periods:
            for material in period.materials:
                if material.id == material_id:
                    if (
                        material.source_kind == "teaching_package"
                        and material.teaching_package_id
                        and material.artifact_id
                    ):
                        package_result = self.teaching_artifact(material.teaching_package_id, material.artifact_id)
                        if package_result is None:
                            return None
                        _, artifact = package_result
                        primary = next((file for file in artifact.files if file.format == "pdf"), None) or (artifact.files[0] if artifact.files else None)
                        if primary is None:
                            return None
                        path = self.teaching_packages_dir / primary.storage_key
                    else:
                        path = self.files_dir / plan_id / f"{material.id}.bin"
                    return (material, path) if path.is_file() else None
        return None

    def update_year_plan_material(
        self,
        plan_id: str,
        period_id: str,
        material_id: str,
        request: YearPlanMaterialUpdate,
    ) -> tuple[YearPlan, YearPlanMaterial] | None:
        plan = self.get_year_plan(plan_id)
        if plan is None:
            return None
        changes = request.model_dump(exclude_none=True)
        updated: YearPlanMaterial | None = None
        for period in plan.periods:
            if period.id != period_id:
                continue
            for index, material in enumerate(period.materials):
                if material.id == material_id:
                    if material.source_kind == "teaching_package":
                        requested_status = changes.get("status")
                        if set(changes) - {"status"} or requested_status not in {None, "used"}:
                            raise ProjectedMaterialError(
                                "Dette læremiddelet styres av undervisningspakken. "
                                "Rediger pakken i stedet; bare «Brukt» kan markeres her."
                            )
                    payload = material.model_dump()
                    payload.update(changes)
                    payload["updated_at"] = utc_now()
                    updated = YearPlanMaterial.model_validate(payload)
                    period.materials[index] = updated
                    break
        if updated is None:
            return None
        payload = plan.model_dump()
        payload["updated_at"] = utc_now()
        return self._save_year_plan(YearPlan.model_validate(payload)), updated

    # ------------------------------------------------------------------
    # TeachingPackage canonical store
    # ------------------------------------------------------------------

    def create_teaching_package(self, package: TeachingPackage) -> TeachingPackage:
        with self._lock, self._connection() as conn:
            conn.execute(
                """INSERT INTO teaching_packages(
                       id,year_plan_id,period_id,subject,level,status,payload,created_at,updated_at
                   ) VALUES(?,?,?,?,?,?,?,?,?)""",
                (
                    package.id,
                    package.year_plan_id,
                    package.period_id,
                    package.subject,
                    package.level,
                    package.status,
                    self._json(package.model_dump(mode="json")),
                    package.created_at,
                    package.updated_at,
                ),
            )
        return package

    def get_teaching_package(self, package_id: str) -> TeachingPackage | None:
        with self._connection() as conn:
            row = conn.execute("SELECT payload FROM teaching_packages WHERE id=?", (package_id,)).fetchone()
        return TeachingPackage.model_validate_json(row["payload"]) if row else None

    def list_teaching_packages(
        self,
        *,
        limit: int = 50,
        year_plan_id: str | None = None,
        period_id: str | None = None,
        project_id: str | None = None,
    ) -> list[TeachingPackage]:
        clauses: list[str] = []
        params: list[Any] = []
        if year_plan_id:
            clauses.append("year_plan_id=?")
            params.append(year_plan_id)
        if period_id:
            clauses.append("period_id=?")
            params.append(period_id)
        query = "SELECT payload FROM teaching_packages"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        with self._connection() as conn:
            rows = conn.execute(query, params).fetchall()
        packages = [TeachingPackage.model_validate_json(row["payload"]) for row in rows]
        if project_id is not None:
            packages = [package for package in packages if package.project_id == project_id]
        return packages

    def save_teaching_package(self, package: TeachingPackage) -> TeachingPackage:
        package.updated_at = utc_now()
        with self._lock, self._connection() as conn:
            conn.execute(
                """UPDATE teaching_packages
                   SET year_plan_id=?,period_id=?,subject=?,level=?,status=?,payload=?,updated_at=?
                   WHERE id=?""",
                (
                    package.year_plan_id,
                    package.period_id,
                    package.subject,
                    package.level,
                    package.status,
                    self._json(package.model_dump(mode="json")),
                    package.updated_at,
                    package.id,
                ),
            )
        return package

    def teaching_artifact(
        self,
        package_id: str,
        artifact_id: str,
    ) -> tuple[TeachingPackage, TeachingArtifact] | None:
        package = self.get_teaching_package(package_id)
        if package is None:
            return None
        artifact = next((item for item in package.artifacts if item.id == artifact_id), None)
        return (package, artifact) if artifact is not None else None

    def cas_update_teaching_artifact(
        self,
        package_id: str,
        artifact_id: str,
        *,
        expected_generation_token: str,
        artifact: TeachingArtifact,
        rendered: dict[str, bytes],
        package_status: str,
    ) -> TeachingPackage:
        """Persist files and content only if the worker still owns the artifact."""
        from .teaching_package import with_revision_digest

        written: list[Path] = []
        with self._exclusive() as conn:
            row = conn.execute("SELECT payload FROM teaching_packages WHERE id=?", (package_id,)).fetchone()
            if row is None:
                raise KeyError("Undervisningspakken finnes ikke.")
            package = TeachingPackage.model_validate_json(row["payload"])
            current = next((item for item in package.artifacts if item.id == artifact_id), None)
            if current is None:
                raise KeyError("Artefaktet finnes ikke.")
            if current.generation_token != expected_generation_token:
                raise StaleTeachingArtifactError(expected_generation_token, current.generation_token or "")
            for file in artifact.files:
                content = rendered.get(file.format)
                if content is None:
                    raise ValueError(f"Rendret innhold mangler for {file.format}.")
                path = self.teaching_packages_dir / file.storage_key
                path.parent.mkdir(parents=True, exist_ok=True)
                temp = path.with_name(f".{path.name}.tmp")
                temp.write_bytes(content)
                temp.replace(path)
                written.append(path)
            index = package.artifacts.index(current)
            package.artifacts[index] = artifact
            package.status = package_status  # type: ignore[assignment]
            package.updated_at = utc_now()
            package = with_revision_digest(package)
            conn.execute(
                "UPDATE teaching_packages SET status=?,payload=?,updated_at=? WHERE id=?",
                (package.status, self._json(package.model_dump(mode="json")), package.updated_at, package.id),
            )
        return package

    def apply_teaching_package_projection(
        self,
        package: TeachingPackage,
        plan: YearPlan,
    ) -> tuple[TeachingPackage, YearPlan]:
        """Atomic package approval + derived period material projection."""
        with self._exclusive() as conn:
            package_row = conn.execute("SELECT payload FROM teaching_packages WHERE id=?", (package.id,)).fetchone()
            plan_row = conn.execute("SELECT payload FROM year_plans WHERE id=?", (plan.id,)).fetchone()
            if package_row is None or plan_row is None:
                raise KeyError("Pakken eller årsplanen finnes ikke.")
            stored_package = TeachingPackage.model_validate_json(package_row["payload"])
            stored_plan = YearPlan.model_validate_json(plan_row["payload"])
            target_period = next((period for period in stored_plan.periods if period.id == stored_package.period_id), None)
            if target_period is None:
                raise KeyError("Årsplanperioden finnes ikke.")
            artifact_ids = {artifact.id for artifact in stored_package.artifacts}
            for material in target_period.materials:
                if material.source_kind == "teaching_package" and material.teaching_package_id == stored_package.id:
                    if material.artifact_id not in artifact_ids:
                        material.artifact_status = "needs_revision"
                        material.status = "needs_revision"
                        material.updated_at = utc_now()
            for artifact in stored_package.artifacts:
                primary = next((file for file in artifact.files if file.format == "pdf"), None) or (artifact.files[0] if artifact.files else None)
                if artifact.status != "approved" or primary is None:
                    continue
                existing = next(
                    (
                        item for item in target_period.materials
                        if item.source_kind == "teaching_package"
                        and item.teaching_package_id == stored_package.id
                        and item.artifact_id == artifact.id
                    ),
                    None,
                )
                payload = {
                    "title": artifact.title,
                    "kind": artifact.artifact_type,
                    "status": "approved",
                    "version": existing.version if existing else 1,
                    "filename": primary.filename,
                    "mime_type": primary.mime_type,
                    "size_bytes": primary.size_bytes,
                    "notes": f"Undervisningspakke {stored_package.package_revision}. revisjon.",
                    "source_kind": "teaching_package",
                    "teaching_package_id": stored_package.id,
                    "artifact_id": artifact.id,
                    "artifact_type": artifact.artifact_type,
                    "artifact_version": artifact.artifact_version,
                    "artifact_status": "approved",
                    "projected_at": utc_now(),
                    "created_at": existing.created_at if existing else utc_now(),
                    "updated_at": utc_now(),
                }
                if existing:
                    payload["id"] = existing.id
                material = YearPlanMaterial.model_validate(payload)
                if existing:
                    target_period.materials[target_period.materials.index(existing)] = material
                else:
                    target_period.materials.append(material)
            stored_package.status = "approved"
            stored_package.approved_at = package.approved_at or utc_now()
            stored_package.approved_by = package.approved_by
            stored_package.updated_at = stored_package.approved_at
            stored_package.approved_revision = stored_package.package_revision
            stored_package.approved_digest = stored_package.revision_digest
            stored_package = self._with_package_digest(stored_package)
            stored_plan.updated_at = utc_now()
            conn.execute(
                "UPDATE teaching_packages SET status=?,payload=?,updated_at=? WHERE id=?",
                (stored_package.status, self._json(stored_package.model_dump(mode="json")), stored_package.updated_at, stored_package.id),
            )
            conn.execute(
                "UPDATE year_plans SET payload=?,updated_at=? WHERE id=?",
                (self._json(stored_plan.model_dump(mode="json")), stored_plan.updated_at, stored_plan.id),
            )
        return stored_package, stored_plan

    @staticmethod
    def _with_package_digest(package: TeachingPackage) -> TeachingPackage:
        from .teaching_package import with_revision_digest

        return with_revision_digest(package)

    def get_teaching_artifact_file(
        self,
        package_id: str,
        artifact_id: str,
        artifact_format: str,
    ) -> tuple[TeachingPackage, TeachingArtifact, TeachingArtifactFile, Path] | None:
        result = self.teaching_artifact(package_id, artifact_id)
        if result is None:
            return None
        package, artifact = result
        file = next((item for item in artifact.files if item.format == artifact_format), None)
        if file is None:
            return None
        path = self.teaching_packages_dir / file.storage_key
        return (package, artifact, file, path) if path.is_file() else None

    def create_compendium(self, request: CompendiumCreate) -> Compendium:
        compendium = Compendium(**request.model_dump())
        with self._lock, self._connection() as conn:
            conn.execute(
                """INSERT INTO compendia(
                       id,subject,level,kind,status,payload,created_at,updated_at
                   ) VALUES(?,?,?,?,?,?,?,?)""",
                (
                    compendium.id,
                    compendium.subject,
                    compendium.level,
                    compendium.kind,
                    compendium.status,
                    self._json(compendium.model_dump()),
                    compendium.created_at,
                    compendium.updated_at,
                ),
            )
        return compendium

    def get_compendium(self, compendium_id: str) -> Compendium | None:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT payload FROM compendia WHERE id=?",
                (compendium_id,),
            ).fetchone()
        return Compendium.model_validate_json(row["payload"]) if row else None

    def list_compendia(
        self,
        *,
        limit: int = 50,
        status: str | None = None,
    ) -> list[Compendium]:
        query = "SELECT payload FROM compendia"
        params: list[Any] = []
        if status:
            query += " WHERE status=?"
            params.append(status)
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        with self._connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [Compendium.model_validate_json(row["payload"]) for row in rows]

    def _save_compendium(self, compendium: Compendium) -> Compendium:
        with self._lock, self._connection() as conn:
            conn.execute(
                """UPDATE compendia
                   SET subject=?,level=?,kind=?,status=?,payload=?,updated_at=?
                   WHERE id=?""",
                (
                    compendium.subject,
                    compendium.level,
                    compendium.kind,
                    compendium.status,
                    self._json(compendium.model_dump()),
                    compendium.updated_at,
                    compendium.id,
                ),
            )
        return compendium

    def update_compendium(
        self,
        compendium_id: str,
        request: CompendiumUpdate,
    ) -> Compendium | None:
        current = self.get_compendium(compendium_id)
        if current is None:
            return None
        payload = current.model_dump()
        payload.update(request.model_dump(exclude_none=True))
        payload["updated_at"] = utc_now()
        return self._save_compendium(Compendium.model_validate(payload))

    def replace_compendium_chapter(
        self,
        compendium_id: str,
        chapter: CompendiumChapter,
    ) -> Compendium | None:
        compendium = self.get_compendium(compendium_id)
        if compendium is None:
            return None
        found = False
        for index, current in enumerate(compendium.chapters):
            if current.id == chapter.id:
                if (
                    current.content_markdown.strip()
                    and current.content_markdown != chapter.content_markdown
                ):
                    chapter.previous_content_markdown = current.content_markdown
                    chapter.revision_count = current.revision_count + 1
                else:
                    chapter.previous_content_markdown = current.previous_content_markdown
                    chapter.revision_count = current.revision_count
                chapter.content_revision = hashlib.sha256(
                    chapter.content_markdown.replace("\r\n", "\n").strip().encode("utf-8")
                ).hexdigest()
                if (
                    chapter.truth_passport is not None
                    and chapter.truth_passport.content_revision != chapter.content_revision
                ):
                    # A passport for another text revision is never carried
                    # forward. The next audit must earn a new passport.
                    chapter.truth_passport = None
                compendium.chapters[index] = chapter
                found = True
                break
        if not found:
            return None
        if chapter.content_markdown and compendium.status in {"outline", "review", "approved"}:
            compendium.status = "writing"
            compendium.approved_at = None
        compendium.updated_at = utc_now()
        return self._save_compendium(compendium)

    # ------------------------------------------------------------------
    # Durable chapter repair
    # ------------------------------------------------------------------

    @staticmethod
    def chapter_content_token(chapter: CompendiumChapter) -> str:
        """Compare-and-swap token for one chapter's teacher-visible text.

        Revision count is part of the token so that an edit that restores the
        previous text still invalidates an in-flight repair.
        """
        material = f"{chapter.revision_count}\x1f{chapter.content_markdown}"
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def compendium_chapter(
        self,
        compendium_id: str,
        chapter_id: str,
    ) -> CompendiumChapter | None:
        compendium = self.get_compendium(compendium_id)
        if compendium is None:
            return None
        return next((item for item in compendium.chapters if item.id == chapter_id), None)

    @contextmanager
    def _exclusive(self):
        """One writer transaction, so check-then-insert cannot interleave."""
        with self._lock, self._connection() as conn:
            if not self.uses_postgres:
                conn.execute("BEGIN IMMEDIATE")
            yield conn

    def _save_repair_job(self, conn: Any, job: RepairJob) -> RepairJob:
        conn.execute(
            """INSERT INTO repair_jobs(
                   id,operation_id,compendium_id,chapter_id,status,payload,created_at,updated_at
               ) VALUES(?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 status=excluded.status,payload=excluded.payload,updated_at=excluded.updated_at""",
            (
                job.id,
                job.operation_id,
                job.compendium_id,
                job.chapter_id,
                job.status,
                self._json(job.model_dump()),
                job.created_at,
                job.updated_at,
            ),
        )
        return job

    def _read_repair_job(self, conn: Any, job_id: str) -> RepairJob | None:
        row = conn.execute("SELECT payload FROM repair_jobs WHERE id=?", (job_id,)).fetchone()
        return RepairJob.model_validate_json(row["payload"]) if row else None

    def get_repair_job(self, job_id: str) -> RepairJob | None:
        with self._connection() as conn:
            return self._read_repair_job(conn, job_id)

    def active_repair_job(self, compendium_id: str, chapter_id: str) -> RepairJob | None:
        placeholders = ",".join("?" for _ in ACTIVE_REPAIR_STATUSES)
        with self._connection() as conn:
            row = conn.execute(
                f"""SELECT payload FROM repair_jobs
                    WHERE compendium_id=? AND chapter_id=? AND status IN ({placeholders})
                    ORDER BY created_at DESC LIMIT 1""",
                (compendium_id, chapter_id, *ACTIVE_REPAIR_STATUSES),
            ).fetchone()
        return RepairJob.model_validate_json(row["payload"]) if row else None

    def latest_repair_job(self, compendium_id: str, chapter_id: str) -> RepairJob | None:
        with self._connection() as conn:
            row = conn.execute(
                """SELECT payload FROM repair_jobs
                   WHERE compendium_id=? AND chapter_id=?
                   ORDER BY created_at DESC LIMIT 1""",
                (compendium_id, chapter_id),
            ).fetchone()
        return RepairJob.model_validate_json(row["payload"]) if row else None

    def register_repair_job(self, job: RepairJob) -> tuple[RepairJob, str]:
        """Reserve the chapter and persist the job before any work starts.

        Returns the stored job and one of `created`, `idempotent` (same
        operation replayed) or `conflict` (another repair owns the chapter).
        """
        placeholders = ",".join("?" for _ in ACTIVE_REPAIR_STATUSES)
        with self._exclusive() as conn:
            replay = conn.execute(
                """SELECT payload FROM repair_jobs
                   WHERE compendium_id=? AND chapter_id=? AND operation_id=?""",
                (job.compendium_id, job.chapter_id, job.operation_id),
            ).fetchone()
            if replay:
                return RepairJob.model_validate_json(replay["payload"]), "idempotent"
            blocking = conn.execute(
                f"""SELECT payload FROM repair_jobs
                    WHERE compendium_id=? AND chapter_id=? AND status IN ({placeholders})
                    ORDER BY created_at DESC LIMIT 1""",
                (job.compendium_id, job.chapter_id, *ACTIVE_REPAIR_STATUSES),
            ).fetchone()
            if blocking:
                return RepairJob.model_validate_json(blocking["payload"]), "conflict"
            attempts = conn.execute(
                "SELECT COUNT(*) AS n FROM repair_jobs WHERE compendium_id=? AND chapter_id=?",
                (job.compendium_id, job.chapter_id),
            ).fetchone()["n"]
            job.attempt = int(attempts) + 1
            return self._save_repair_job(conn, job), "created"

    def claim_repair_job(self, job_id: str, *, lease_seconds: int = 900) -> RepairJob | None:
        """Move `queued` to `running` exactly once."""
        with self._exclusive() as conn:
            job = self._read_repair_job(conn, job_id)
            if job is None or job.status != "queued":
                return None
            job.status = "running"
            job.message = "Reparasjonen kjører …"
            job.started_at = utc_now()
            job.updated_at = job.started_at
            job.lease_expires_at = _lease_deadline(lease_seconds)
            return self._save_repair_job(conn, job)

    def heartbeat_repair_job(self, job_id: str, *, lease_seconds: int = 900) -> RepairJob | None:
        with self._exclusive() as conn:
            job = self._read_repair_job(conn, job_id)
            if job is None or job.status != "running":
                return None
            job.lease_expires_at = _lease_deadline(lease_seconds)
            job.updated_at = utc_now()
            return self._save_repair_job(conn, job)

    def finish_repair_job(
        self,
        job_id: str,
        *,
        status: str,
        message: str = "",
        result_token: str = "",
        output_revision: str = "",
        chapter_status: str | None = None,
        repair_summary: Any | None = None,
        failure_reason: str = "",
        expected_statuses: tuple[str, ...] = ACTIVE_REPAIR_STATUSES,
        terminal_event: tuple[str, dict[str, Any]] | None = None,
    ) -> RepairJob | None:
        """Write a terminal status and release the chapter lock."""
        with self._exclusive() as conn:
            job = self._read_repair_job(conn, job_id)
            if job is None or job.status not in expected_statuses:
                return None
            job.status = status  # type: ignore[assignment]
            job.message = message[:400]
            job.result_token = result_token or job.result_token
            job.output_revision = output_revision or job.output_revision
            job.chapter_status = chapter_status  # type: ignore[assignment]
            if repair_summary is not None:
                job.repair_summary = repair_summary
            job.failure_reason = failure_reason[:400]
            job.lease_expires_at = ""
            job.finished_at = utc_now()
            job.updated_at = job.finished_at
            finished = self._save_repair_job(conn, job)
            if terminal_event is not None:
                stage, payload = terminal_event
                entry = RepairLedgerEntry(
                    job_id=job.id,
                    operation_id=job.operation_id,
                    stage=stage,
                    payload=_ledger_safe(payload),
                )
                conn.execute(
                    "INSERT INTO repair_events(id,job_id,operation_id,stage,payload,created_at) VALUES(?,?,?,?,?,?)",
                    (
                        entry.id,
                        entry.job_id,
                        entry.operation_id,
                        entry.stage,
                        self._json(entry.payload),
                        entry.created_at,
                    ),
                )
            return finished

    def request_repair_cancel(self, job_id: str) -> RepairJob | None:
        """Record the teacher's intent durably, whatever the model is doing."""
        with self._exclusive() as conn:
            job = self._read_repair_job(conn, job_id)
            if job is None:
                return None
            job.cancel_requested = True
            job.updated_at = utc_now()
            if job.status in ACTIVE_REPAIR_STATUSES:
                job.status = "cancelled"
                job.message = "Avbrutt av læreren."
                job.lease_expires_at = ""
                job.finished_at = job.updated_at
            return self._save_repair_job(conn, job)

    def recover_incomplete_repair_jobs(self) -> int:
        """A restart loses the model call, so never claim it finished."""
        return self._release_repair_jobs(
            "Serveren startet på nytt før reparasjonen var ferdig. "
            "Kapittelet er ikke endret; start reparasjonen på nytt.",
        )

    def expire_stale_repair_leases(self) -> int:
        """A crashed worker must not leave the chapter locked forever."""
        return self._release_repair_jobs(
            "Reparasjonen mistet kontakten med arbeideren. "
            "Kapittelet er ikke endret; start reparasjonen på nytt.",
            only_expired=True,
        )

    def _release_repair_jobs(self, message: str, *, only_expired: bool = False) -> int:
        placeholders = ",".join("?" for _ in ACTIVE_REPAIR_STATUSES)
        now = utc_now()
        released = 0
        recovered: list[RepairJob] = []
        with self._exclusive() as conn:
            rows = conn.execute(
                f"SELECT payload FROM repair_jobs WHERE status IN ({placeholders})",
                ACTIVE_REPAIR_STATUSES,
            ).fetchall()
            for row in rows:
                job = RepairJob.model_validate_json(row["payload"])
                if only_expired and not (job.lease_expires_at and job.lease_expires_at < now):
                    continue
                job.status = "failed_retryable"
                job.message = message[:400]
                job.lease_expires_at = ""
                job.finished_at = now
                job.updated_at = now
                self._save_repair_job(conn, job)
                recovered.append(job)
                released += 1
        for job in recovered:
            # Recovery happens before a RepairService instance may exist, so
            # write the durable event directly here rather than leaving a
            # status transition with no explanation in the ledger.
            self.append_repair_event(
                job.id,
                job.operation_id,
                "recovered",
                {"status": job.status, "message": message},
            )
        return released

    def append_repair_event(
        self,
        job_id: str,
        operation_id: str,
        stage: str,
        payload: dict[str, Any] | None = None,
    ) -> RepairLedgerEntry:
        entry = RepairLedgerEntry(
            job_id=job_id,
            operation_id=operation_id,
            stage=stage,
            payload=_ledger_safe(payload or {}),
        )
        with self._lock, self._connection() as conn:
            conn.execute(
                "INSERT INTO repair_events(id,job_id,operation_id,stage,payload,created_at) VALUES(?,?,?,?,?,?)",
                (
                    entry.id,
                    entry.job_id,
                    entry.operation_id,
                    entry.stage,
                    self._json(entry.payload),
                    entry.created_at,
                ),
            )
        return entry

    def list_repair_events(self, job_id: str, *, limit: int = 200) -> list[RepairLedgerEntry]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT id,job_id,operation_id,stage,payload,created_at FROM repair_events "
                "WHERE job_id=? ORDER BY created_at,id LIMIT ?",
                (job_id, limit),
            ).fetchall()
        return [
            RepairLedgerEntry(
                id=row["id"],
                job_id=row["job_id"],
                operation_id=row["operation_id"],
                stage=row["stage"],
                created_at=row["created_at"],
                payload=json.loads(row["payload"]),
            )
            for row in rows
        ]

    def replace_compendium_chapter_if_unchanged(
        self,
        compendium_id: str,
        chapter: CompendiumChapter,
        expected_token: str,
    ) -> Compendium | None:
        """Write back only while the teacher's text is still the one we read.

        Raises `StaleChapterWriteError` when the chapter moved on, so a late
        worker can never overwrite newer teacher work.
        """
        with self._lock:
            current = self.compendium_chapter(compendium_id, chapter.id)
            if current is None:
                return None
            actual_token = self.chapter_content_token(current)
            if actual_token != expected_token:
                raise StaleChapterWriteError(expected_token, actual_token)
            return self.replace_compendium_chapter(compendium_id, chapter)

    def store_compendium_artifacts(
        self,
        compendium_id: str,
        *,
        pdf: bytes,
        docx: bytes,
        pdf_filename: str,
        docx_filename: str,
    ) -> Compendium | None:
        if not pdf.startswith(b"%PDF") or not docx.startswith(b"PK"):
            raise ValueError("Dokumentbyggeren returnerte ugyldige filer.")
        compendium = self.get_compendium(compendium_id)
        if compendium is None:
            return None
        version = compendium.artifact_version + 1
        target_dir = self.compendia_dir / compendium.id
        target_dir.mkdir(parents=True, exist_ok=True)
        final_pdf = target_dir / f"v{version}.pdf"
        final_docx = target_dir / f"v{version}.docx"
        temp_pdf = target_dir / f".v{version}.pdf.tmp"
        temp_docx = target_dir / f".v{version}.docx.tmp"
        temp_pdf.write_bytes(pdf)
        temp_docx.write_bytes(docx)
        temp_pdf.replace(final_pdf)
        temp_docx.replace(final_docx)
        try:
            compendium.pdf_filename = pdf_filename
            compendium.pdf_size_bytes = len(pdf)
            compendium.docx_filename = docx_filename
            compendium.docx_size_bytes = len(docx)
            compendium.artifact_version = version
            compendium.status = "review"
            compendium.approved_at = None
            compendium.updated_at = utc_now()
            return self._save_compendium(compendium)
        except Exception:
            final_pdf.unlink(missing_ok=True)
            final_docx.unlink(missing_ok=True)
            raise

    def get_compendium_artifact(
        self,
        compendium_id: str,
        artifact_type: str,
    ) -> tuple[Compendium, Path] | None:
        compendium = self.get_compendium(compendium_id)
        if compendium is None or compendium.artifact_version < 1:
            return None
        suffix = "pdf" if artifact_type == "pdf" else "docx"
        path = self.compendia_dir / compendium.id / f"v{compendium.artifact_version}.{suffix}"
        return (compendium, path) if path.is_file() else None

    def approve_compendium(self, compendium_id: str) -> Compendium | None:
        compendium = self.get_compendium(compendium_id)
        if compendium is None:
            return None
        compendium.status = "approved"
        compendium.approved_at = utc_now()
        compendium.updated_at = compendium.approved_at
        return self._save_compendium(compendium)


_store: PlatformStore | None = None
_store_lock = threading.Lock()


def get_platform_store() -> PlatformStore:
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = PlatformStore()
    return _store
