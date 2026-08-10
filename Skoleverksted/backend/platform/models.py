from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


ProjectStatus = Literal["draft", "ready", "generating", "completed", "archived"]
JobStatus = Literal[
    "queued",
    "planning",
    "generating",
    "verifying",
    "rendering",
    "completed",
    "needs_review",
    "failed",
    "cancelled",
    "superseded",
]
YearPlanStatus = Literal["draft", "active", "completed", "archived"]
YearPlanPeriodStatus = Literal["not_started", "in_progress", "ready", "completed", "needs_revision"]
MaterialStatus = Literal["draft", "approved", "used", "needs_revision"]
MaterialKind = Literal[
    "learning_sheet",
    "student_sheet",
    "worksheet",
    "exercise_sheet",
    "answer_key",
    "teacher_guide",
    "lesson_sequence",
    "assessment",
    "presentation",
    "source_task",
    "differentiated",
    "compendium",
    "other",
]

TeachingArtifactType = Literal[
    "presentation",
    "student_sheet",
    "exercise_sheet",
    "answer_key",
    "teacher_guide",
]
TeachingArtifactStatus = Literal[
    "planned",
    "generating",
    "generated",
    "needs_review",
    "needs_revision",
    "reviewed_with_issues",
    "approved",
    "generation_incomplete",
    "parse_failure",
    "language_quality_failed",
    "source_grounding_failed",
    "verification_failed",
    "superseded",
    "cancelled",
]
TeachingPackageStatus = Literal[
    "draft",
    "planning",
    "generating",
    "needs_review",
    "needs_revision",
    "reviewed_with_issues",
    "approved",
    "user_approved_with_exceptions",
    "archived",
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
TruthContentType = Literal[
    "fact",
    "quote",
    "number",
    "mathematics",
    "user_input",
    "instruction",
    "creative",
    "interpretation",
]


class TruthSource(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    url: str = Field(min_length=8, max_length=1000)
    publisher: str = Field(default="", max_length=180)
    source_tier: Literal["primary", "authoritative", "editorial", "other"] = "other"
    published_at: str = Field(default="", max_length=80)
    retrieved_at: str = Field(default_factory=utc_now)
    origin: Literal["teacher", "grounding", "model"] = "model"
    fetch_status: Literal["provided", "grounded", "model_reported", "fetched", "source_unavailable"] = "model_reported"


class TruthSourceAttempt(BaseModel):
    """A source lookup recorded for one claim, never an approval by itself."""

    title: str = Field(default="", max_length=300)
    url: str = Field(default="", max_length=1000)
    publisher: str = Field(default="", max_length=180)
    published_at: str = Field(default="", max_length=80)
    retrieved_at: str = Field(default_factory=utc_now)
    status: Literal["supported", "not_supported", "unavailable", "not_evaluated"] = "not_evaluated"
    supports_claim: str = Field(default="", max_length=1600)
    evidence: str = Field(default="", max_length=1600)


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
    content_type: TruthContentType = "fact"
    location: str = Field(default="", max_length=300)
    source_attempts: list[TruthSourceAttempt] = Field(default_factory=list, max_length=20)


class TruthPassport(BaseModel):
    version: str = "1.0"
    generated_at: str = Field(default_factory=utc_now)
    # A passport is only valid for the exact text revision it audited.  The
    # empty default keeps old persisted compendia readable; new audits always
    # populate this value before they can be considered green.
    content_revision: str = Field(default="", max_length=128)
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


RepairActionKind = Literal[
    "keep",
    "qualify",
    "replace",
    "remove",
    "source_required",
    "manual_review",
]


class RepairIssue(BaseModel):
    issue_id: str = Field(min_length=1, max_length=80)
    claim_id: str = Field(default="", max_length=80)
    category: str = Field(default="factual", max_length=80)
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    original_text: str = Field(default="", max_length=1600)
    evidence: str = Field(default="", max_length=1600)
    source_refs: list[str] = Field(default_factory=list, max_length=12)
    recommended_action: RepairActionKind = "manual_review"


class RepairAction(BaseModel):
    issue_id: str = Field(min_length=1, max_length=80)
    action: RepairActionKind
    target_text: str = Field(default="", max_length=1600)
    replacement_text: str = Field(default="", max_length=1600)
    justification: str = Field(default="", max_length=1600)
    source_refs: list[str] = Field(default_factory=list, max_length=12)


class RepairPlan(BaseModel):
    chapter_id: str = Field(min_length=1, max_length=80)
    source_revision: str = Field(min_length=1, max_length=128)
    issues: list[RepairIssue] = Field(default_factory=list, max_length=80)
    proposed_actions: list[RepairAction] = Field(default_factory=list, max_length=80)
    expected_result: str = Field(default="", max_length=1600)


class RepairChange(BaseModel):
    issue_id: str = Field(min_length=1, max_length=80)
    action: RepairActionKind
    result: Literal["applied", "unresolved", "manual_review", "skipped"]
    before: str = Field(default="", max_length=1600)
    after: str = Field(default="", max_length=1600)
    reason: str = Field(default="", max_length=1600)
    source_refs: list[str] = Field(default_factory=list, max_length=12)


class RepairMetrics(BaseModel):
    verified_claims: int = Field(default=0, ge=0)
    total_claims: int = Field(default=0, ge=0)
    coverage: int = Field(default=0, ge=0, le=100)
    unresolved: int = Field(default=0, ge=0)
    source_grounding_failures: int = Field(default=0, ge=0)
    language_failures: int = Field(default=0, ge=0)


class RepairSummary(BaseModel):
    before: RepairMetrics = Field(default_factory=RepairMetrics)
    after: RepairMetrics = Field(default_factory=RepairMetrics)
    changes: list[RepairChange] = Field(default_factory=list, max_length=80)
    found_count: int = Field(default=0, ge=0)
    repaired_count: int = Field(default=0, ge=0)
    qualified_count: int = Field(default=0, ge=0)
    replaced_count: int = Field(default=0, ge=0)
    removed_count: int = Field(default=0, ge=0)
    unresolved_count: int = Field(default=0, ge=0)
    manual_review_count: int = Field(default=0, ge=0)
    pass_count: int = Field(default=1, ge=1, le=3)
    stop_reason: str = Field(default="", max_length=240)


class QualityRevisionRound(BaseModel):
    """Durable audit record for one AI repair and re-check round."""

    round_number: int = Field(ge=1, le=20)
    started_at: str = Field(default_factory=utc_now)
    completed_at: str = Field(default_factory=utc_now)
    before_revision: str = Field(default="", max_length=128)
    after_revision: str = Field(default="", max_length=128)
    claims_found: int = Field(default=0, ge=0)
    claims_verified: int = Field(default=0, ge=0)
    corrected_count: int = Field(default=0, ge=0)
    unresolved_count: int = Field(default=0, ge=0)
    changed: bool = False
    status: Literal["completed", "no_progress", "max_rounds", "failed"] = "completed"
    summary: str = Field(default="", max_length=1600)
    changes: list[RepairChange] = Field(default_factory=list, max_length=120)


class QualityQuarantineItem(BaseModel):
    """Content withheld from approved text while remaining visible to the teacher."""

    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    claim_id: str = Field(default="", max_length=80)
    content_type: TruthContentType = "fact"
    original_text: str = Field(min_length=1, max_length=2400)
    location: str = Field(default="Ukjent seksjon", max_length=300)
    reason: str = Field(default="Påstanden mangler tilstrekkelig dokumentasjon.", max_length=1600)
    source_attempts: list[TruthSourceAttempt] = Field(default_factory=list, max_length=20)
    suggested_replacement: str = Field(default="", max_length=2400)
    omission_consequence: str = Field(default="", max_length=1600)
    status: Literal["withheld", "replaced", "removed", "resolved"] = "withheld"
    created_at: str = Field(default_factory=utc_now)


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
    truth_passport: TruthPassport | None = None
    quality_rounds: list[QualityRevisionRound] = Field(default_factory=list)
    quarantine: list[QualityQuarantineItem] = Field(default_factory=list)
    quality_stop_reason: str = ""
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
    source_kind: Literal["manual", "teaching_package"] = "manual"
    teaching_package_id: str | None = Field(default=None, max_length=64)
    artifact_id: str | None = Field(default=None, max_length=64)
    artifact_type: MaterialKind | None = None
    artifact_version: int = Field(default=0, ge=0)
    artifact_status: str = Field(default="approved", max_length=40)
    projected_at: str = ""
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
    truth_passport: TruthPassport | None = None
    quality_rounds: list[QualityRevisionRound] = Field(default_factory=list)
    quarantine: list[QualityQuarantineItem] = Field(default_factory=list)
    quality_stop_reason: str = ""
    content_revision: str = Field(default="", max_length=128)
    approved_at: str | None = None
    approved_revision: str = Field(default="", max_length=128)


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


class ArtifactSpec(BaseModel):
    artifact_type: TeachingArtifactType
    title: str = Field(min_length=2, max_length=180)
    required: bool = True
    order: int = Field(default=0, ge=0, le=20)


class TeachingPackagePlan(BaseModel):
    theme: str = Field(min_length=2, max_length=240)
    period_title: str = Field(min_length=2, max_length=180)
    subject: str = Field(min_length=2, max_length=120)
    level: str = Field(min_length=1, max_length=80)
    audience: str = Field(default="Elever", max_length=180)
    lesson_count: int = Field(default=1, ge=1, le=120)
    lesson_minutes: int = Field(default=45, ge=1, le=240)
    duration_weeks: int = Field(default=1, ge=1, le=12)
    competency_goals: list[str] = Field(default_factory=list, max_length=30)
    learning_goals: list[str] = Field(default_factory=list, max_length=20)
    key_concepts: list[str] = Field(default_factory=list, max_length=30)
    suggested_activities: list[str] = Field(default_factory=list, max_length=20)
    assessment: str = Field(default="", max_length=1600)
    teacher_notes: str = Field(default="", max_length=3000)
    overview: str = Field(default="", max_length=4000)
    source_brief: str = Field(default="", max_length=40_000)
    sources: list[TruthSource] = Field(default_factory=list, max_length=50)
    artifact_specs: list[ArtifactSpec] = Field(min_length=1, max_length=10)
    period_snapshot: dict[str, Any] = Field(default_factory=dict)


class TeachingArtifactFile(BaseModel):
    format: Literal["pdf", "docx", "pptx"]
    filename: str = Field(min_length=1, max_length=240)
    mime_type: str = Field(min_length=3, max_length=180)
    size_bytes: int = Field(default=0, ge=0, le=100_000_000)
    digest: str = Field(min_length=32, max_length=128)
    storage_key: str = Field(min_length=1, max_length=240)
    package_revision: int = Field(default=1, ge=1)


class TeachingArtifact(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    package_id: str
    artifact_type: TeachingArtifactType
    required: bool = True
    title: str = Field(min_length=2, max_length=180)
    order: int = Field(default=0, ge=0, le=20)
    content_markdown: str = Field(default="", max_length=120_000)
    content_revision: str = Field(default="", max_length=128)
    package_revision: int = Field(default=1, ge=1)
    sources: list[TruthSource] = Field(default_factory=list, max_length=50)
    truth_passport: TruthPassport | None = None
    quality_passport: QualityPassport | None = None
    verification_notes: list[str] = Field(default_factory=list, max_length=40)
    source_quality_notes: list[str] = Field(default_factory=list, max_length=30)
    quality_rounds: list[QualityRevisionRound] = Field(default_factory=list, max_length=20)
    quarantine: list[QualityQuarantineItem] = Field(default_factory=list, max_length=120)
    quality_run_count: int = Field(default=0, ge=0, le=100)
    quality_stop_reason: str = Field(default="", max_length=240)
    status: TeachingArtifactStatus = "planned"
    generation_token: str | None = Field(default=None, max_length=160)
    artifact_job_id: str | None = Field(default=None, max_length=160)
    revision_count: int = Field(default=0, ge=0, le=1000)
    previous_content_markdown: str = Field(default="", max_length=120_000)
    files: list[TeachingArtifactFile] = Field(default_factory=list, max_length=10)
    artifact_version: int = Field(default=0, ge=0)
    approved_at: str | None = None
    approved_by: str = Field(default="", max_length=180)
    approved_revision: str = Field(default="", max_length=128)
    approved_digest: str = Field(default="", max_length=128)
    updated_at: str = Field(default_factory=utc_now)

    def model_post_init(self, __context: Any) -> None:
        if not self.content_revision:
            self.content_revision = hashlib.sha256(
                self.content_markdown.replace("\r\n", "\n").strip().encode("utf-8")
            ).hexdigest()


class TeachingPackageCreate(BaseModel):
    year_plan_id: str = Field(min_length=1, max_length=64)
    period_id: str = Field(min_length=1, max_length=64)
    artifact_types: list[TeachingArtifactType] = Field(default_factory=lambda: [
        "presentation", "student_sheet", "exercise_sheet", "answer_key", "teacher_guide",
    ], min_length=1, max_length=10)
    audience: str = Field(default="Elever", max_length=180)
    source_brief: str = Field(default="", max_length=40_000)
    sources: list[TruthSource] = Field(default_factory=list, max_length=50)
    title: str | None = Field(default=None, min_length=2, max_length=180)
    project_id: str | None = Field(default=None, max_length=64)


class TeachingPackageUpdate(BaseModel):
    artifact_types: list[TeachingArtifactType] | None = Field(default=None, min_length=1, max_length=10)
    audience: str | None = Field(default=None, max_length=180)
    source_brief: str | None = Field(default=None, max_length=40_000)
    sources: list[TruthSource] | None = Field(default=None, max_length=50)


class TeachingArtifactUpdate(BaseModel):
    content_markdown: str | None = Field(default=None, max_length=120_000)
    status: Literal["needs_revision", "reviewed_with_issues"] | None = None


class TeachingApprovalRecord(BaseModel):
    """Audit trail for a final teacher decision and later revocation."""

    action: Literal["approved", "approved_with_exceptions", "revoked"]
    teacher: str = Field(default="", max_length=180)
    at: str = Field(default_factory=utc_now)
    package_revision: int = Field(default=1, ge=1)
    artifact_versions: dict[str, int] = Field(default_factory=dict)
    content_hashes: dict[str, str] = Field(default_factory=dict)
    verification_statuses: dict[str, str] = Field(default_factory=dict)
    source_urls: list[str] = Field(default_factory=list, max_length=200)
    omitted_claims: list[str] = Field(default_factory=list, max_length=120)
    unresolved_claims: list[str] = Field(default_factory=list, max_length=120)
    reason: str = Field(default="", max_length=1600)


class TeachingPackage(TeachingPackageCreate):
    id: str = Field(default_factory=lambda: uuid4().hex)
    title: str = Field(default="Undervisningspakke", min_length=2, max_length=180)
    subject: str = Field(default="", max_length=120)
    level: str = Field(default="", max_length=80)
    status: TeachingPackageStatus = "draft"
    plan: TeachingPackagePlan
    artifacts: list[TeachingArtifact] = Field(default_factory=list, max_length=10)
    package_job_id: str | None = Field(default=None, max_length=160)
    package_revision: int = Field(default=1, ge=1)
    revision_digest: str = Field(default="", max_length=128)
    planning_source: Literal["ai", "fallback", "manual"] = "manual"
    approved_at: str | None = None
    approved_by: str = Field(default="", max_length=180)
    approved_revision: int = 0
    approved_digest: str = Field(default="", max_length=128)
    approval_history: list[TeachingApprovalRecord] = Field(default_factory=list, max_length=50)
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


class TeachingApprovalRequest(BaseModel):
    teacher: str = Field(default="local-teacher", min_length=1, max_length=180)
    confirm: bool = False
    reason: str = Field(default="", max_length=1600)


class TeachingPackageJobAccepted(BaseModel):
    package_job_id: str
    artifact_job_ids: list[str]
    status: str
    status_url: str


class TeachingArtifactJobAccepted(BaseModel):
    job_id: str
    artifact_id: str
    status: str
    status_url: str


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
    content_revision: str = Field(default="", max_length=128)
    revision_summary: list[str] = Field(default_factory=list, max_length=30)
    repair_summary: RepairSummary | None = None
    quality_rounds: list[QualityRevisionRound] = Field(default_factory=list, max_length=20)
    quarantine: list[QualityQuarantineItem] = Field(default_factory=list, max_length=120)
    quality_stop_reason: str = Field(default="", max_length=240)
    previous_content_markdown: str = Field(default="", max_length=80_000)
    revision_count: int = Field(default=0, ge=0, le=1000)
    status: CompendiumChapterStatus = "planned"
    updated_at: str = Field(default_factory=utc_now)

    def model_post_init(self, __context: Any) -> None:
        if not self.content_revision:
            self.content_revision = hashlib.sha256(
                self.content_markdown.replace("\r\n", "\n").strip().encode("utf-8")
            ).hexdigest()


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
    confirm_omissions: bool = False


class CompendiumCompileResult(BaseModel):
    compendium: Compendium
    pdf_download_url: str
    docx_download_url: str


RepairJobStatus = Literal[
    "queued",
    "running",
    "succeeded",
    "failed_retryable",
    "failed_terminal",
    "cancelled",
    "superseded",
]

ACTIVE_REPAIR_STATUSES: tuple[str, ...] = ("queued", "running")

REPAIR_JOB_KIND = "compendium_repair"


class RepairJob(BaseModel):
    """Durable identity for one teacher-initiated chapter repair.

    The status here describes the *job*, never the chapter. A job that stores a
    chapter with `source_grounding_failed` is a succeeded job with a content
    result the teacher must read.
    """

    id: str
    operation_id: str = Field(min_length=1, max_length=120)
    compendium_id: str
    chapter_id: str
    chapter_title: str = Field(default="", max_length=180)
    status: RepairJobStatus = "queued"
    message: str = Field(default="", max_length=400)
    chapter_token: str = Field(default="", max_length=80)
    result_token: str = Field(default="", max_length=80)
    source_revision: str = Field(default="", max_length=128)
    output_revision: str = Field(default="", max_length=128)
    chapter_status: CompendiumChapterStatus | None = None
    repair_summary: RepairSummary | None = None
    failure_reason: str = Field(default="", max_length=400)
    attempt: int = Field(default=1, ge=1)
    cancel_requested: bool = False
    lease_expires_at: str = ""
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)
    started_at: str = ""
    finished_at: str = ""

    @property
    def active(self) -> bool:
        return self.status in ACTIVE_REPAIR_STATUSES

    @property
    def status_url(self) -> str:
        return f"/api/platform/repair-jobs/{self.id}"


class RepairJobAccepted(BaseModel):
    job_id: str
    operation_id: str
    compendium_id: str
    chapter_id: str
    status: RepairJobStatus
    status_url: str


class RepairLedgerEntry(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    job_id: str
    operation_id: str
    stage: str = Field(max_length=60)
    created_at: str = Field(default_factory=utc_now)
    payload: dict[str, Any] = Field(default_factory=dict)
