from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


ProjectStatus = Literal["draft", "ready", "generating", "completed", "archived"]
JobStatus = Literal["queued", "planning", "generating", "verifying", "rendering", "completed", "needs_review", "failed", "cancelled"]
YearPlanStatus = Literal["draft", "active", "completed", "archived"]
YearPlanPeriodStatus = Literal["not_started", "in_progress", "ready", "completed", "needs_revision"]
MaterialStatus = Literal["draft", "approved", "used", "needs_revision"]
MaterialKind = Literal[
    "learning_sheet",
    "worksheet",
    "lesson_sequence",
    "assessment",
    "presentation",
    "source_task",
    "differentiated",
    "compendium",
    "other",
]


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


TruthClaimStatus = Literal[
    "verified",
    "interpretation",
    "disputed",
    "time_sensitive",
    "unsupported",
    "verification_failed",
    "source_unavailable",
    "not_evaluated",
]
TruthAction = Literal["keep", "qualify", "remove"]


class TruthSource(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    url: str = Field(min_length=8, max_length=1000)
    publisher: str = Field(default="", max_length=180)
    source_tier: Literal["primary", "authoritative", "editorial", "other"] = "other"
    retrieved_at: str = Field(default_factory=utc_now)
    origin: Literal["teacher", "grounding", "model"] = "model"
    fetch_status: Literal["provided", "grounded", "model_reported", "fetched", "source_unavailable"] = "model_reported"


class TruthClaim(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    claim: str = Field(min_length=1, max_length=1200)
    exact_text: str = Field(default="", max_length=1200)
    status: TruthClaimStatus
    action: TruthAction = "keep"
    replacement: str = Field(default="", max_length=1600)
    source_urls: list[str] = Field(default_factory=list, max_length=8)
    evidence: str = Field(default="", max_length=1200)
    confidence: float = Field(default=0, ge=0, le=1)


class TruthPassport(BaseModel):
    version: str = "1.0"
    generated_at: str = Field(default_factory=utc_now)
    status: Literal[
        "verified",
        "needs_review",
        "blocked",
        "verification_failed",
        "source_unavailable",
        "not_evaluated",
    ]
    topic: str = Field(default="", max_length=300)
    subject: str = Field(default="", max_length=120)
    coverage_percent: int = Field(default=0, ge=0, le=100)
    verified_claims: int = Field(default=0, ge=0)
    total_claims: int = Field(default=0, ge=0)
    claims: list[TruthClaim] = Field(default_factory=list, max_length=120)
    sources: list[TruthSource] = Field(default_factory=list, max_length=50)
    removed_claims: list[str] = Field(default_factory=list, max_length=50)
    limitations: list[str] = Field(default_factory=list, max_length=30)
    summary: str = Field(default="", max_length=1200)


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


class YearPlanMaterial(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    title: str = Field(min_length=2, max_length=180)
    kind: MaterialKind = "learning_sheet"
    status: MaterialStatus = "approved"
    version: int = Field(default=1, ge=1)
    filename: str = Field(min_length=1, max_length=240)
    mime_type: str = Field(default="application/pdf", max_length=120)
    size_bytes: int = Field(default=0, ge=0, le=30_000_000)
    notes: str = Field(default="", max_length=1200)
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


class YearPlanPeriod(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    order: int = Field(default=0, ge=0, le=100)
    title: str = Field(min_length=2, max_length=180)
    theme: str = Field(default="", max_length=240)
    week_start: str = Field(default="", max_length=20)
    week_end: str = Field(default="", max_length=20)
    duration_weeks: int = Field(default=3, ge=1, le=12)
    lesson_count: int = Field(default=6, ge=1, le=120)
    overview: str = Field(default="", max_length=3000)
    learning_goals: list[str] = Field(default_factory=list, max_length=12)
    competency_goals: list[str] = Field(default_factory=list, max_length=30)
    key_concepts: list[str] = Field(default_factory=list, max_length=20)
    suggested_activities: list[str] = Field(default_factory=list, max_length=15)
    assessment: str = Field(default="", max_length=1200)
    teacher_notes: str = Field(default="", max_length=3000)
    status: YearPlanPeriodStatus = "not_started"
    materials: list[YearPlanMaterial] = Field(default_factory=list, max_length=100)


class YearPlanGenerateRequest(BaseModel):
    title: str = Field(default="", max_length=180)
    subject: str = Field(min_length=2, max_length=120)
    level: str = Field(min_length=1, max_length=80)
    school_year: str = Field(min_length=4, max_length=20)
    lessons_per_week: int = Field(default=2, ge=1, le=15)
    lesson_minutes: int = Field(default=45, ge=30, le=180)
    teaching_weeks: int = Field(default=38, ge=20, le=45)
    number_of_periods: int = Field(default=9, ge=4, le=16)
    competency_goals: list[str] = Field(default_factory=list, max_length=80)
    constraints: str = Field(default="", max_length=4000)
    use_ai: bool = True


class YearPlanCreate(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    subject: str = Field(min_length=2, max_length=120)
    level: str = Field(min_length=1, max_length=80)
    school_year: str = Field(min_length=4, max_length=20)
    lessons_per_week: int = Field(default=2, ge=1, le=15)
    lesson_minutes: int = Field(default=45, ge=30, le=180)
    teaching_weeks: int = Field(default=38, ge=20, le=45)
    competency_goals: list[str] = Field(default_factory=list, max_length=80)
    periods: list[YearPlanPeriod] = Field(default_factory=list, max_length=30)
    notes: str = Field(default="", max_length=4000)
    planning_source: Literal["ai", "fallback", "manual"] = "manual"


class YearPlan(YearPlanCreate):
    id: str = Field(default_factory=lambda: uuid4().hex)
    status: YearPlanStatus = "draft"
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


class YearPlanUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=180)
    lessons_per_week: int | None = Field(default=None, ge=1, le=15)
    lesson_minutes: int | None = Field(default=None, ge=30, le=180)
    teaching_weeks: int | None = Field(default=None, ge=20, le=45)
    competency_goals: list[str] | None = Field(default=None, max_length=80)
    periods: list[YearPlanPeriod] | None = Field(default=None, max_length=30)
    notes: str | None = Field(default=None, max_length=4000)
    status: YearPlanStatus | None = None


class YearPlanPeriodUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=180)
    theme: str | None = Field(default=None, max_length=240)
    week_start: str | None = Field(default=None, max_length=20)
    week_end: str | None = Field(default=None, max_length=20)
    duration_weeks: int | None = Field(default=None, ge=1, le=12)
    lesson_count: int | None = Field(default=None, ge=1, le=120)
    overview: str | None = Field(default=None, max_length=3000)
    learning_goals: list[str] | None = Field(default=None, max_length=12)
    competency_goals: list[str] | None = Field(default=None, max_length=30)
    key_concepts: list[str] | None = Field(default=None, max_length=20)
    suggested_activities: list[str] | None = Field(default=None, max_length=15)
    assessment: str | None = Field(default=None, max_length=1200)
    teacher_notes: str | None = Field(default=None, max_length=3000)
    status: YearPlanPeriodStatus | None = None


class YearPlanMaterialCreate(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    kind: MaterialKind = "learning_sheet"
    status: MaterialStatus = "approved"
    filename: str = Field(min_length=1, max_length=240)
    mime_type: str = Field(default="application/pdf", max_length=120)
    notes: str = Field(default="", max_length=1200)


class YearPlanMaterialUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=180)
    status: MaterialStatus | None = None
    notes: str | None = Field(default=None, max_length=1200)


CompendiumType = Literal[
    "thematic",
    "chronological",
    "reference",
    "comparative",
    "source_collection",
    "appendix",
]
CompendiumStatus = Literal["outline", "writing", "review", "approved", "archived"]
CompendiumChapterStatus = Literal[
    "planned",
    "generated",
    "approved",
    "needs_revision",
    "generation_incomplete",
    "parse_failure",
    "language_quality_failed",
    "source_grounding_failed",
    "verification_failed",
]
CompendiumImageMode = Literal["none", "commons", "ai"]


class CompendiumSource(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    url: str = Field(default="", max_length=1000)
    publisher: str = Field(default="", max_length=180)
    origin: Literal["teacher", "grounding", "model"] = "model"
    fetch_status: Literal["provided", "grounded", "model_reported", "fetched", "source_unavailable"] = "model_reported"


class ScopeContract(BaseModel):
    reference_date: str = Field(default="", max_length=160)
    geography: str = Field(default="", max_length=300)
    inclusion_criteria: list[str] = Field(default_factory=list, max_length=20)
    exclusions: list[str] = Field(default_factory=list, max_length=20)
    completeness_label: Literal["complete", "documented", "selected"] = "selected"
    completeness_note: str = Field(default="", max_length=1500)


class CompendiumChapter(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    order: int = Field(default=0, ge=0, le=100)
    title: str = Field(min_length=2, max_length=180)
    purpose: str = Field(default="", max_length=1200)
    guiding_questions: list[str] = Field(default_factory=list, max_length=12)
    content_markdown: str = Field(default="", max_length=80_000)
    key_facts: list[str] = Field(default_factory=list, max_length=30)
    glossary: list[str] = Field(default_factory=list, max_length=30)
    sources: list[CompendiumSource] = Field(default_factory=list, max_length=50)
    verification_notes: list[str] = Field(default_factory=list, max_length=30)
    truth_passport: TruthPassport | None = None
    revision_summary: list[str] = Field(default_factory=list, max_length=30)
    previous_content_markdown: str = Field(default="", max_length=80_000)
    revision_count: int = Field(default=0, ge=0, le=1000)
    status: CompendiumChapterStatus = "planned"
    updated_at: str = Field(default_factory=utc_now)


class CompendiumPlanRequest(BaseModel):
    title: str = Field(default="", max_length=180)
    topic: str = Field(min_length=2, max_length=300)
    subject: str = Field(default="Historie", min_length=2, max_length=120)
    level: str = Field(default="VG2", min_length=1, max_length=80)
    kind: CompendiumType = "thematic"
    purpose: str = Field(default="", max_length=4000)
    audience: str = Field(default="Elever", max_length=180)
    target_pages: int = Field(default=16, ge=4, le=60)
    chapter_count: int = Field(default=6, ge=2, le=14)
    competency_goals: list[str] = Field(default_factory=list, max_length=40)
    source_brief: str = Field(default="", max_length=40_000)
    include_timeline: bool = True
    include_tables: bool = True
    include_glossary: bool = True
    include_reflection_tasks: bool = True
    image_mode: CompendiumImageMode = "none"
    year_plan_id: str | None = Field(default=None, max_length=64)
    period_ids: list[str] = Field(default_factory=list, max_length=10)
    use_ai: bool = True


class CompendiumCreate(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    topic: str = Field(min_length=2, max_length=300)
    subject: str = Field(default="Historie", max_length=120)
    level: str = Field(default="VG2", max_length=80)
    kind: CompendiumType = "thematic"
    purpose: str = Field(default="", max_length=4000)
    audience: str = Field(default="Elever", max_length=180)
    target_pages: int = Field(default=16, ge=4, le=60)
    competency_goals: list[str] = Field(default_factory=list, max_length=40)
    source_brief: str = Field(default="", max_length=40_000)
    scope_contract: ScopeContract = Field(default_factory=ScopeContract)
    chapters: list[CompendiumChapter] = Field(default_factory=list, max_length=20)
    include_timeline: bool = True
    include_tables: bool = True
    include_glossary: bool = True
    include_reflection_tasks: bool = True
    image_mode: CompendiumImageMode = "none"
    year_plan_id: str | None = Field(default=None, max_length=64)
    period_ids: list[str] = Field(default_factory=list, max_length=10)
    planning_source: Literal["ai", "fallback", "manual"] = "manual"


class Compendium(CompendiumCreate):
    id: str = Field(default_factory=lambda: uuid4().hex)
    status: CompendiumStatus = "outline"
    pdf_filename: str = Field(default="", max_length=240)
    pdf_size_bytes: int = Field(default=0, ge=0, le=100_000_000)
    docx_filename: str = Field(default="", max_length=240)
    docx_size_bytes: int = Field(default=0, ge=0, le=100_000_000)
    artifact_version: int = Field(default=0, ge=0)
    approved_at: str | None = None
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


class CompendiumUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=180)
    purpose: str | None = Field(default=None, max_length=4000)
    audience: str | None = Field(default=None, max_length=180)
    target_pages: int | None = Field(default=None, ge=4, le=60)
    competency_goals: list[str] | None = Field(default=None, max_length=40)
    source_brief: str | None = Field(default=None, max_length=40_000)
    scope_contract: ScopeContract | None = None
    include_timeline: bool | None = None
    include_tables: bool | None = None
    include_glossary: bool | None = None
    include_reflection_tasks: bool | None = None
    image_mode: CompendiumImageMode | None = None
    year_plan_id: str | None = Field(default=None, max_length=64)
    period_ids: list[str] | None = Field(default=None, max_length=10)
    status: CompendiumStatus | None = None


class CompendiumChapterUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=180)
    purpose: str | None = Field(default=None, max_length=1200)
    guiding_questions: list[str] | None = Field(default=None, max_length=12)
    content_markdown: str | None = Field(default=None, max_length=80_000)
    key_facts: list[str] | None = Field(default=None, max_length=30)
    glossary: list[str] | None = Field(default=None, max_length=30)
    sources: list[CompendiumSource] | None = Field(default=None, max_length=50)
    verification_notes: list[str] | None = Field(default=None, max_length=30)
    status: CompendiumChapterStatus | None = None


class CompendiumCompileResult(BaseModel):
    compendium: Compendium
    pdf_download_url: str
    docx_download_url: str
