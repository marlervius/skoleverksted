from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


ProjectStatus = Literal["draft", "ready", "generating", "completed", "archived"]
JobStatus = Literal["queued", "planning", "generating", "verifying", "rendering", "completed", "needs_review", "failed", "cancelled"]


class ProjectCreate(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    theme: str = Field(default="", max_length=240)
    subject: str = Field(default="", max_length=120)
    level: str = Field(default="", max_length=80)
    description: str = Field(default="", max_length=4000)
    competency_goals: list[str] = Field(default_factory=list, max_length=30)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=160)
    theme: str | None = Field(default=None, max_length=240)
    subject: str | None = Field(default=None, max_length=120)
    level: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=4000)
    competency_goals: list[str] | None = Field(default=None, max_length=30)
    status: ProjectStatus | None = None
    metadata: dict[str, Any] | None = None


class Project(ProjectCreate):
    id: str = Field(default_factory=lambda: uuid4().hex)
    status: ProjectStatus = "draft"
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


class Job(BaseModel):
    id: str
    module: Literal["fag", "norsk", "matematikk", "platform"]
    kind: str = "generation"
    status: JobStatus = "queued"
    progress: int = Field(default=0, ge=0, le=100)
    message: str = ""
    project_id: str | None = None
    request_summary: dict[str, Any] = Field(default_factory=dict)
    result_summary: dict[str, Any] = Field(default_factory=dict)
    quality_passport: dict[str, Any] = Field(default_factory=dict)
    queue_position: int | None = Field(default=None, ge=1)
    retryable: bool = False
    attempt: int = Field(default=1, ge=1)
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


class QualityCheck(BaseModel):
    code: str
    label: str
    status: Literal["passed", "warning", "failed", "not_applicable"]
    detail: str = ""
    deterministic: bool = True


class QualityPassport(BaseModel):
    version: str = "1.0"
    generated_at: str = Field(default_factory=utc_now)
    module: str
    title: str
    overall_status: Literal["passed", "needs_review", "failed"]
    score: int = Field(ge=0, le=100)
    checks: list[QualityCheck]
    sources: list[str] = Field(default_factory=list)
    competency_goals: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    prompt_version: str = "unknown"


class QualityPassportRequest(BaseModel):
    module: str = Field(min_length=2, max_length=40)
    title: str = Field(min_length=2, max_length=160)
    content: str = Field(default="", max_length=300_000)
    sources: list[str] = Field(default_factory=list, max_length=100)
    competency_goals: list[str] = Field(default_factory=list, max_length=30)
    has_answer_key: bool | None = None
    compiled: bool | None = None
    math_incorrect: int | None = Field(default=None, ge=0)
    math_unparseable: int | None = Field(default=None, ge=0)
    prompt_version: str = Field(default="unknown", max_length=80)


class ThemePackRequest(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    theme: str = Field(min_length=2, max_length=240)
    subject: str = Field(default="Naturfag", max_length=120)
    level: str = Field(default="VG1", max_length=80)
    norwegian_level: str = Field(default="B1", max_length=20)
    duration_lessons: int = Field(default=4, ge=1, le=30)
    description: str = Field(default="", max_length=4000)
    source_text: str = Field(default="", max_length=120_000)
    source_name: str = Field(default="", max_length=240)
    competency_goals: list[str] = Field(default_factory=list, max_length=30)
    include_assessment: bool = True
    include_teacher_guide: bool = True


class ThemePackTask(BaseModel):
    id: str
    module: Literal["fag", "norsk", "matematikk"]
    title: str
    brief: str
    href: str
    status: Literal["ready", "generated"] = "ready"


class ThemePack(BaseModel):
    id: str
    project: Project
    tasks: list[ThemePackTask]
    quality_passport: QualityPassport
    created_at: str = Field(default_factory=utc_now)


class FeedbackCreate(BaseModel):
    module: Literal["fag", "norsk", "matematikk", "platform"]
    artifact_id: str = Field(default="", max_length=120)
    project_id: str | None = Field(default=None, max_length=64)
    rating: Literal["up", "down"]
    reason: str = Field(default="", max_length=500)


class Feedback(FeedbackCreate):
    id: str = Field(default_factory=lambda: uuid4().hex)
    created_at: str = Field(default_factory=utc_now)
