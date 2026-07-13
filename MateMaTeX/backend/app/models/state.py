"""
Pipeline state model — the single source of truth flowing through the LangGraph.

Every node in the graph reads from and writes to this state.
Uses Pydantic v2 for strict validation.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class PipelineStatus(str, Enum):
    """Overall pipeline status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"


class AgentRole(str, Enum):
    """Every agent in the pipeline."""
    PEDAGOGUE = "pedagogue"
    AUTHOR = "author"
    CONTENT_QUALITY = "content_quality"
    MATH_VERIFIER = "math_verifier"
    TIKZ_VALIDATOR = "tikz_validator"
    TABLE_VALIDATOR = "table_validator"
    LATEX_VALIDATOR = "latex_validator"
    LATEX_FIXER = "latex_fixer"
    LATEX_FALLBACK = "latex_fallback"
    EDITOR = "editor"
    LAYOUT = "layout"


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------
class PdfStyle(BaseModel):
    """
    Visual + accessibility options for the generated PDF.

    All fields default to the classic look, so omitting this object reproduces
    the previous output exactly.
    """
    theme: str = Field(
        default="default",
        description="Color palette: default|calm|playful|highcontrast",
    )
    student_mode: bool = Field(
        default=False, description="Favour writing space (answer fields)"
    )
    accessible: bool = Field(
        default=False, description="Emit PDF language metadata / tagged-PDF mode"
    )
    dyslexia: bool = Field(
        default=False, description="Sans-serif body with generous leading"
    )
    high_contrast: bool = Field(
        default=False, description="Force the high-contrast palette"
    )


class GenerationRequest(BaseModel):
    """User's input to the pipeline."""
    grade: str = Field(description="Grade level, e.g. '10. trinn', 'VG2 R1'")
    topic: str = Field(description="Math topic", max_length=500)
    material_type: str = Field(
        default="arbeidsark",
        description="arbeidsark|kapittel|prøve|differensiert",
    )
    language_level: str = Field(default="standard", description="standard|b2|b1")
    num_exercises: int = Field(default=10, ge=1, le=50)
    difficulty: str = Field(default="Middels", description="Lett|Middels|Vanskelig")
    include_theory: bool = True
    include_examples: bool = True
    include_exercises: bool = True
    include_solutions: bool = True
    include_graphs: bool = True
    competency_goals: list[str] = Field(default_factory=list)
    extra_instructions: str = Field(default="", max_length=10_000)
    pdf_style: PdfStyle = Field(default_factory=PdfStyle)


class MathClaim(BaseModel):
    """A single mathematical claim extracted from the LaTeX for verification."""
    claim_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    latex_expression: str = Field(description="Raw LaTeX of the claim")
    claim_type: str = Field(description="equation|inequality|computation|solution")
    context: str = Field(default="", description="Surrounding text for context")
    sympy_expression: str = Field(default="", description="SymPy-parseable form")
    is_verified: bool = False
    is_correct: bool | None = None
    error_message: str = ""
    expected_result: str = ""
    actual_result: str = ""


class VerificationResult(BaseModel):
    """Result of the SymPy math verification pass."""
    claims_checked: int = 0
    claims_correct: int = 0
    claims_incorrect: int = 0
    claims_unparseable: int = 0
    errors: list[MathClaim] = Field(default_factory=list)
    unparseable_claims: list[MathClaim] = Field(default_factory=list)
    all_correct: bool = False
    summary: str = ""


class LayoutIssue(BaseModel):
    """A single layout problem detected in the compilation log."""
    kind: str = Field(description="overfull_hbox|underfull_hbox|overfull_vbox|oversized_float|undefined_reference|multiply_defined|missing_font")
    severity: str = Field(default="info", description="info|warning|error")
    detail: str = ""
    overflow_pt: float = 0.0
    page: int | None = None


class ContentQualityIssue(BaseModel):
    """A single pedagogical completeness problem."""

    code: str
    severity: str = Field(default="error", description="error|warning")
    message: str


class ContentQualityReport(BaseModel):
    """Rule-based kapittel quality assessment before PDF compile."""

    passed: bool = False
    score: int = Field(default=0, ge=0, le=100)
    issues: list[ContentQualityIssue] = Field(default_factory=list)
    missing_subtopics: list[str] = Field(default_factory=list)
    section_count: int = 0
    example_count: int = 0
    graph_count: int = 0
    exercise_count: int = 0
    body_chars: int = 0
    semantic_score: int = Field(default=100, ge=0, le=100)
    semantic_summary: str = ""


class LayoutReport(BaseModel):
    """Structured quality assessment of the compiled document's layout."""
    score: int = 100
    issues: list[LayoutIssue] = Field(default_factory=list)
    overfull_count: int = 0
    underfull_count: int = 0
    max_overflow_pt: float = 0.0
    undefined_references: int = 0
    summary: str = ""


class LatexCompilationResult(BaseModel):
    """Result of actual pdflatex compilation check."""
    success: bool = False
    pdf_path: str = ""
    pdf_bytes: bytes | None = Field(
        default=None,
        exclude=True,
        description=(
            "Raw PDF bytes captured during compilation (not serialised). "
            "Used so we don't depend on temp-file paths that may have been cleaned up."
        ),
    )
    pdf_base64: str = ""
    used_fallback: bool = False
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    log_excerpt: str = ""


class AgentStep(BaseModel):
    """Observability record for a single agent execution."""
    agent: AgentRole
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: datetime | None = None
    duration_seconds: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    input_summary: str = ""
    output_summary: str = ""
    error: str = ""
    retries: int = 0


# ---------------------------------------------------------------------------
# Main pipeline state — flows through every node in the LangGraph
# ---------------------------------------------------------------------------
class PipelineState(BaseModel):
    """
    The single state object that flows through the entire LangGraph pipeline.

    LangGraph nodes read from and write to this state.
    Each field is updated by the responsible agent/node.
    """

    # --- Identifiers ---
    job_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    owner_id: str = ""
    created_at: datetime = Field(default_factory=datetime.now)
    status: PipelineStatus = PipelineStatus.PENDING

    # --- User input ---
    request: GenerationRequest = Field(default_factory=GenerationRequest)

    # --- Curriculum context (set by pedagogue) ---
    grade_boundaries: dict[str, Any] = Field(default_factory=dict)
    curriculum_context: str = ""

    # --- Agent outputs ---
    pedagogical_plan: str = ""
    raw_latex_body: str = ""
    verified_latex_body: str = ""
    edited_latex_body: str = ""
    final_latex_body: str = ""
    full_document: str = ""  # With preamble

    # --- Verification ---
    math_verification: VerificationResult = Field(default_factory=VerificationResult)
    math_verification_attempts: int = 0
    latex_compilation: LatexCompilationResult = Field(default_factory=LatexCompilationResult)
    latex_fix_attempts: int = 0
    layout_report: LayoutReport = Field(default_factory=LayoutReport)
    content_quality: ContentQualityReport = Field(default_factory=ContentQualityReport)
    content_quality_attempts: int = 0
    author_retry_reason: str = Field(
        default="",
        description="Set by graph routers before author: 'math' | 'quality'",
    )
    skip_editor_once: bool = Field(
        default=False,
        description="Skip the LLM editor pass once (after a quality retry author run)",
    )
    layout_fix_attempts: int = 0
    layout_fix_requested: bool = False

    # --- Observability ---
    steps: list[AgentStep] = Field(default_factory=list)
    total_tokens: int = 0
    total_duration_seconds: float = 0.0
    current_agent: AgentRole | None = None

    # --- Output ---
    pdf_path: str = ""
    pdf_base64: str = ""
    used_latex_fallback: bool = False
    from_cache: bool = False
    differentiated_basic: str = ""
    differentiated_advanced: str = ""
    error_message: str = ""
    warning_reason: str = Field(
        default="",
        description=(
            "Why status is completed_with_warnings: 'unparseable' | 'incorrect' | "
            "'fallback' | 'content_quality' (comma-separated)"
        ),
    )

    @field_validator("pdf_path", "pdf_base64", mode="before")
    @classmethod
    def normalize_nullable_pdf_fields(cls, value: Any) -> str:
        """Accept legacy snapshots that serialized absent PDF values as null."""
        return "" if value is None else value
