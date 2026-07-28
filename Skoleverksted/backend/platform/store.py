from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .models import (
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
    YearPlan,
    YearPlanCreate,
    YearPlanMaterial,
    YearPlanMaterialCreate,
    YearPlanMaterialUpdate,
    YearPlanPeriod,
    YearPlanPeriodUpdate,
    YearPlanUpdate,
    utc_now,
)


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

    def __init__(self, path: str | Path | None = None, files_dir: str | Path | None = None):
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
