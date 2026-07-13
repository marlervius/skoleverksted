"""
LangGraph pipeline definition — the heart of MateMaTeX 2.0.

Implements the multi-agent pipeline with verification loops:

    User Input
        ↓
    [Pedagogue] → Pedagogical plan
        ↓
    [Author] → LaTeX body content
        ↓
    [Math Verifier] → SymPy verification of all calculations
        ↓ ← ERRORS? → [Author] retries (max 3)
        ↓
    [Editor] → Quality control & cleanup
        ↓
    [LaTeX Validator] → Actual pdflatex compilation
        ↓ ← ERRORS? → [LaTeX Fixer] retries (max 3)
        ↓
    Final Document
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Literal

import structlog
from langgraph.graph import END, StateGraph

from app.config import get_config
from app.latex.preamble import inject_verification_banner, wrap_with_style
from app.models.state import (
    GenerationRequest,
    PipelineState,
    PipelineStatus,
)
from app.pipeline.agents.author import run_author
from app.pipeline.agents.content_quality import run_content_quality
from app.pipeline.agents.editor import run_editor
from app.pipeline.agents.latex_fallback import run_latex_fallback
from app.pipeline.agents.latex_fixer import run_latex_fixer
from app.pipeline.agents.latex_validator import run_latex_validator
from app.pipeline.agents.layout import run_layout
from app.pipeline.agents.math_verifier import run_final_math_verifier, run_math_verifier
from app.pipeline.agents.pedagogue import run_pedagogue
from app.pipeline.agents.table_validator import run_table_validator
from app.pipeline.agents.tikz_validator import run_tikz_validator
from app.pipeline.routing_helpers import (
    can_retry_content_quality,
    can_retry_math,
    over_time_budget,
)

logger = structlog.get_logger()

_ABORT_MESSAGE = "Avbrutt av bruker"


def try_restore_cached_pipeline(
    request: GenerationRequest,
    *,
    job_id: str,
    owner_id: str = "",
    created_at: datetime | None = None,
) -> PipelineState | None:
    """
    Return a completed PipelineState when an exact cache entry with a PDF exists.

    Used synchronously on POST /generate (instant response for cache hits) and
    inside run_pipeline (background thread path).
    """
    try:
        from app.cache import get_cache

        cached_json = get_cache().get_full_result(request)
        data = json.loads(cached_json) if cached_json else None
        if data is None:
            return None
        if not data.get("pdf_base64"):
            pdf_path = data.get("pdf_path") or ""
            if not (pdf_path and Path(pdf_path).is_file()):
                logger.info("pipeline_cache_ignored_no_pdf", job_id=job_id)
                return None

        restored = PipelineState(**data)
        restored.job_id = job_id
        if created_at is not None:
            restored.created_at = created_at
        restored.from_cache = True
        if owner_id and not restored.owner_id:
            restored.owner_id = owner_id
        restored.status = (
            PipelineStatus.COMPLETED_WITH_WARNINGS
            if (
                restored.math_verification.claims_unparseable > 0
                or (
                    get_config().verification_fail_open
                    and restored.math_verification.claims_incorrect > 0
                )
                or (
                    not restored.content_quality.passed
                    and (
                        restored.content_quality.score > 0
                        or bool(restored.content_quality.issues)
                    )
                )
            )
            else PipelineStatus.COMPLETED
        )
        if (
            restored.math_verification.claims_incorrect > 0
            and not get_config().verification_fail_open
        ):
            logger.info(
                "pipeline_cache_ignored_incorrect_fasit",
                job_id=job_id,
                incorrect=restored.math_verification.claims_incorrect,
            )
            return None
        logger.info("pipeline_cache_hit", job_id=restored.job_id)
        return restored
    except Exception as e:
        logger.warning("pipeline_cache_restore_failed", error=str(e))
        return None


# ---------------------------------------------------------------------------
# Routing functions (conditional edges)
# ---------------------------------------------------------------------------

from app.pipeline.cancel import clear_cancel, is_cancelled


def _should_skip_editor(state: PipelineState) -> bool:
    """Skip the slow LLM editor for worksheets/exams (saves ~3–5 min per job)."""
    config = get_config()
    if config.skip_editor:
        return True
    fast_types = {
        t.strip()
        for t in config.skip_editor_material_types.split(",")
        if t.strip()
    }
    return state.request.material_type in fast_types


def should_retry_content(
    state: PipelineState,
) -> Literal["author", "tikz_validator"]:
    """
    After content quality gate: retry author if kapittel fails standards.
    """
    if state.request.material_type != "kapittel":
        if not state.content_quality.passed:
            state.warning_reason = (
                f"{state.warning_reason},content_quality"
                if state.warning_reason
                else "content_quality"
            )
        return "tikz_validator"

    if state.content_quality.passed:
        return "tikz_validator"

    if can_retry_content_quality(state, state.content_quality):
        logger.info(
            "content_quality_retry",
            job_id=state.job_id,
            attempt=state.content_quality_attempts + 1,
            score=state.content_quality.score,
            issues=len(state.content_quality.issues),
            author_retry_reason=state.author_retry_reason,
        )
        return "author"

    if over_time_budget(state):
        logger.warning(
            "pipeline_time_budget_exceeded",
            job_id=state.job_id,
            elapsed=round((datetime.now() - state.created_at).total_seconds(), 1),
            budget=get_config().pipeline_max_seconds,
        )

    logger.warning(
        "content_quality_proceed_with_gaps",
        job_id=state.job_id,
        score=state.content_quality.score,
        issues=len(state.content_quality.issues),
    )
    if state.content_quality.score < 70:
        state.warning_reason = (
            (state.warning_reason + ",content_quality")
            if state.warning_reason
            else "content_quality"
        )
    return "tikz_validator"


def should_retry_math(
    state: PipelineState,
) -> Literal["author", "editor", "content_quality", "math_blocked"]:
    """
    After math verification: retry author if errors found and retries remain.
    SymPy-confirmed incorrect fasit blocks delivery (grunnlov §1) unless
    verification_fail_open is enabled. Unparseable claims may proceed with
    a «lærer kontroll anbefales» marker in finalize.
    """
    config = get_config()
    incorrect = state.math_verification.claims_incorrect

    if can_retry_math(state):
        logger.info(
            "math_retry_decision",
            decision="retry",
            attempt=state.math_verification_attempts,
            max_retries=config.max_verification_retries,
            errors=incorrect,
            author_retry_reason=state.author_retry_reason,
        )
        return "author"

    if incorrect > 0 and not config.verification_fail_open:
        logger.warning(
            "math_retry_decision",
            decision="blocked",
            errors=incorrect,
            attempts=state.math_verification_attempts,
        )
        return "math_blocked"

    if not state.math_verification.all_correct:
        logger.warning(
            "math_retry_decision",
            decision="proceed_with_unparseable_only",
            unparseable=state.math_verification.claims_unparseable,
        )

    if _should_skip_editor(state) or state.skip_editor_once:
        if state.skip_editor_once:
            state.skip_editor_once = False
        logger.info(
            "editor_skip_decision",
            material_type=state.request.material_type,
            job_id=state.job_id,
        )
        state.edited_latex_body = state.verified_latex_body
        return "content_quality"

    return "editor"


def route_final_math(
    state: PipelineState,
) -> Literal["content_quality", "math_blocked"]:
    """Fail closed if the editor introduced an incorrect or unverifiable fasit."""
    config = get_config()
    if state.error_message.startswith("Endelig fasitkontroll feilet"):
        return "math_blocked"
    if (
        state.math_verification.claims_incorrect > 0
        and not config.verification_fail_open
    ):
        return "math_blocked"
    return "content_quality"


def run_math_blocked(state: PipelineState) -> PipelineState:
    """Terminal node when SymPy confirms incorrect fasit (grunnlov §1)."""
    incorrect = state.math_verification.claims_incorrect
    error_details = []
    for claim in state.math_verification.errors[:3]:
        expression = claim.latex_expression.strip()
        detail = claim.error_message.strip()
        if expression:
            error_details.append(
                f"{expression}: {detail}" if detail else expression
            )
    details_suffix = (
        " Kontroller: " + " | ".join(error_details) if error_details else ""
    )
    state.status = PipelineStatus.FAILED
    if not state.error_message.startswith("Endelig fasitkontroll feilet"):
        state.error_message = (
            f"SymPy fant {incorrect} feil i fasiten etter "
            f"{state.math_verification_attempts} kontrollrunder. "
            "Materialet leveres ikke — fasiten er hellig (MateMaTeX grunnlov §1)."
            f"{details_suffix}"
        )
    state.warning_reason = "incorrect"
    state.pdf_base64 = ""
    state.pdf_path = ""
    state.current_agent = None
    state.total_duration_seconds = sum(s.duration_seconds for s in state.steps)
    state.total_tokens = sum(s.total_tokens for s in state.steps)
    logger.warning(
        "pipeline_math_blocked",
        job_id=state.job_id,
        incorrect=incorrect,
        attempts=state.math_verification_attempts,
    )
    return state


def should_retry_latex(state: PipelineState) -> Literal["latex_fixer", "latex_fallback", "finalize"]:
    """
    After LaTeX validation: retry with fixer if compilation failed and retries remain.
    If max retries reached and still failing, go to fallback.
    """
    config = get_config()
    max_retries = config.max_verification_retries

    if state.latex_compilation.success:
        return "finalize"

    if over_time_budget(state):
        logger.warning(
            "latex_retry_decision",
            decision="fallback",
            msg="Time budget exceeded. Using fallback document.",
        )
        return "latex_fallback"

    if state.latex_fix_attempts < max_retries:
        logger.info(
            "latex_retry_decision",
            decision="retry",
            attempt=state.latex_fix_attempts,
            max_retries=max_retries,
        )
        return "latex_fixer"
    else:
        logger.warning(
            "latex_retry_decision",
            decision="fallback",
            msg="Max retries reached. Using fallback document.",
        )
        return "latex_fallback"


# ---------------------------------------------------------------------------
# Terminal nodes
# ---------------------------------------------------------------------------

def _apply_differentiation(state: PipelineState) -> None:
    """Build a three-level document when material_type is differensiert."""
    from app.differentiation.generator import differentiate_content_sync

    body = (
        state.final_latex_body
        or state.edited_latex_body
        or state.verified_latex_body
        or state.raw_latex_body
    )
    if not body.strip():
        return

    logger.info("differentiation_pipeline_start", job_id=state.job_id)
    output = differentiate_content_sync(
        body,
        topic=state.request.topic,
        grade=state.request.grade,
    )
    state.differentiated_basic = output.basic_latex
    state.differentiated_advanced = output.advanced_latex

    combined_body = (
        "\\section*{Grunnleggende}\n"
        + (output.basic_latex or body)
        + "\n\n\\section*{Standard}\n"
        + (output.standard_latex or body)
        + "\n\n\\section*{Avansert}\n"
        + (output.advanced_latex or body)
    )
    state.final_latex_body = combined_body
    state.full_document = wrap_with_style(combined_body, state.request.pdf_style)


def should_route_after_layout(state: PipelineState) -> Literal["latex_fixer", "finalize"]:
    """One layout-driven fix pass before delivery (resize floats / overfull boxes)."""
    if state.layout_fix_requested and state.layout_fix_attempts < 1:
        state.layout_fix_attempts += 1
        state.layout_fix_requested = False
        hints = [
            i.detail
            for i in state.layout_report.issues
            if i.kind in ("oversized_float", "overfull_hbox")
        ][:6]
        state.latex_compilation.errors = [
            "Layout-problemer — reduser figur/tabell-bredde med \\resizebox eller mindre axis width:",
            *hints,
        ]
        logger.info("layout_route_to_fixer", job_id=state.job_id, hints=len(hints))
        return "latex_fixer"
    return "finalize"


def finalize(state: PipelineState) -> PipelineState:
    """
    Final node: assemble the complete document and compute summary stats.
    """
    config = get_config()
    mv = state.math_verification

    # Safety net: never mark completed when SymPy confirmed wrong answers.
    if mv.claims_incorrect > 0 and not config.verification_fail_open:
        state.status = PipelineStatus.FAILED
        state.error_message = (
            f"SymPy fant {mv.claims_incorrect} feil i fasiten. "
            "Materialet leveres ikke (MateMaTeX grunnlov §1)."
        )
        state.warning_reason = "incorrect"
        state.pdf_base64 = ""
        state.pdf_path = ""
        state.total_duration_seconds = sum(s.duration_seconds for s in state.steps)
        state.total_tokens = sum(s.total_tokens for s in state.steps)
        state.current_agent = None
        logger.warning("finalize_blocked_incorrect_fasit", job_id=state.job_id)
        return state

    body = (
        state.final_latex_body
        or state.edited_latex_body
        or state.verified_latex_body
        or state.raw_latex_body
    )

    verified_banner = (
        mv.claims_checked > 0
        and mv.claims_incorrect == 0
        and mv.claims_unparseable == 0
    )
    needs_review = mv.claims_unparseable > 0
    if body.strip() and (verified_banner or needs_review):
        body = inject_verification_banner(
            body,
            verified=verified_banner,
            needs_teacher_review=needs_review,
        )
        if state.final_latex_body:
            state.final_latex_body = body
        elif state.edited_latex_body:
            state.edited_latex_body = body
        elif state.verified_latex_body:
            state.verified_latex_body = body
        else:
            state.raw_latex_body = body

    if state.request.material_type == "differensiert":
        _apply_differentiation(state)
        try:
            from app.verification.latex_checker import LatexChecker

            checker = LatexChecker(pdflatex_path=config.pdflatex_path)
            compile_result = checker.check(state.full_document)
            state.latex_compilation = compile_result
            if compile_result.pdf_base64:
                state.pdf_base64 = compile_result.pdf_base64
        except Exception as e:
            logger.warning(
                "differentiation_recompile_failed",
                error=str(e),
                job_id=state.job_id,
            )
    elif not state.full_document:
        state.full_document = wrap_with_style(body, state.request.pdf_style)
    elif state.final_latex_body and state.full_document:
        state.full_document = wrap_with_style(state.final_latex_body, state.request.pdf_style)

    if not state.pdf_base64 and state.latex_compilation.pdf_base64:
        state.pdf_base64 = state.latex_compilation.pdf_base64

    state.used_latex_fallback = (
        state.used_latex_fallback or state.latex_compilation.used_fallback
    )

    # Compute totals
    state.total_duration_seconds = sum(s.duration_seconds for s in state.steps)
    state.total_tokens = sum(s.total_tokens for s in state.steps)
    state.current_agent = None

    has_unparseable = mv.claims_unparseable > 0
    has_fail_open_incorrect = mv.claims_incorrect > 0 and config.verification_fail_open
    reasons: list[str] = []
    if (
        not state.content_quality.passed
        and (state.content_quality.score > 0 or bool(state.content_quality.issues))
    ):
        reasons.append("content_quality")
    if has_unparseable:
        reasons.append("unparseable")
    if has_fail_open_incorrect:
        reasons.append("incorrect")
    if state.used_latex_fallback:
        reasons.append("fallback")

    if reasons:
        state.warning_reason = ",".join(reasons)
        state.status = PipelineStatus.COMPLETED_WITH_WARNINGS
    else:
        state.warning_reason = ""
        state.status = PipelineStatus.COMPLETED

    # Only cache a full result that actually carries a usable PDF. Caching a
    # PDF-less "completed" state would make later cache hits return a document
    # the UI can never render (the result view just spins), which looks like a
    # hang to the user.
    has_pdf_file = bool(state.pdf_path) and Path(state.pdf_path).is_file()
    if state.pdf_base64 or has_pdf_file:
        try:
            from app.cache import get_cache
            from app.job_store import dump_state_compact

            get_cache().set_full_result(state.request, dump_state_compact(state))
        except Exception as e:
            logger.warning("cache_full_result_failed", error=str(e), job_id=state.job_id)
    else:
        logger.info("cache_full_result_skipped_no_pdf", job_id=state.job_id)

    logger.info(
        "pipeline_complete",
        job_id=state.job_id,
        status=state.status.value,
        total_steps=len(state.steps),
        total_duration=round(state.total_duration_seconds, 1),
        math_verification_attempts=state.math_verification_attempts,
        latex_fix_attempts=state.latex_fix_attempts,
        latex_compiled=state.latex_compilation.success,
        used_fallback=state.used_latex_fallback,
    )

    return state


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def create_pipeline() -> StateGraph:
    """
    Build the LangGraph pipeline.

    Graph topology:

        pedagogue → author → math_verifier
                        ↑           |
                        |    (retry if errors)
                        +-----------+
                                    |
                                    ↓
                              editor → tikz_validator → table_validator → latex_validator
                                                                                  ↑         |
                                                                                  |  (retry if errors)
                                                                                  +---------+
                                                                                            |
                                                                                            ↓
                                                                                        finalize → END
    """
    # Define the graph with PipelineState
    graph = StateGraph(PipelineState)

    # Add nodes
    graph.add_node("pedagogue", run_pedagogue)
    graph.add_node("author", run_author)
    graph.add_node("math_verifier", run_math_verifier)
    graph.add_node("editor", run_editor)
    graph.add_node("final_math_verifier", run_final_math_verifier)
    graph.add_node("content_quality", run_content_quality)
    graph.add_node("tikz_validator", run_tikz_validator)    # Rule-based figure fixer
    graph.add_node("table_validator", run_table_validator)  # Rule-based table fixer
    graph.add_node("latex_validator", run_latex_validator)
    graph.add_node("latex_fixer", run_latex_fixer)
    graph.add_node("latex_fallback", run_latex_fallback)
    graph.add_node("math_blocked", run_math_blocked)
    graph.add_node("layout", run_layout)  # Track E: non-destructive layout QA
    graph.add_node("finalize", finalize)

    # Set entry point
    graph.set_entry_point("pedagogue")

    # Linear edges
    graph.add_edge("pedagogue", "author")
    graph.add_edge("author", "math_verifier")

    # Conditional: math verification → retry author OR content quality OR skip editor
    graph.add_conditional_edges(
        "math_verifier",
        should_retry_math,
        {
            "author": "author",
            "editor": "editor",
            "content_quality": "content_quality",
            "math_blocked": "math_blocked",
        },
    )

    graph.add_edge("editor", "final_math_verifier")
    graph.add_conditional_edges(
        "final_math_verifier",
        route_final_math,
        {
            "content_quality": "content_quality",
            "math_blocked": "math_blocked",
        },
    )

    graph.add_conditional_edges(
        "content_quality",
        should_retry_content,
        {
            "author": "author",
            "tikz_validator": "tikz_validator",
        },
    )

    graph.add_edge("math_blocked", END)

    # Linear: tikz → table → latex validation
    graph.add_edge("tikz_validator", "table_validator")
    graph.add_edge("table_validator", "latex_validator")

    # Conditional: latex validation → retry with fixer OR fallback OR finalize
    graph.add_conditional_edges(
        "latex_validator",
        should_retry_latex,
        {
            "latex_fixer": "latex_fixer",
            "latex_fallback": "latex_fallback",
            "finalize": "layout",
        },
    )

    # LaTeX fixer goes back to validation
    graph.add_edge("latex_fixer", "latex_validator")

    # Fallback runs layout QA too, then finalize
    graph.add_edge("latex_fallback", "layout")

    # Layout QA → optional fixer → finalize → END
    graph.add_conditional_edges(
        "layout",
        should_route_after_layout,
        {
            "latex_fixer": "latex_fixer",
            "finalize": "finalize",
        },
    )
    graph.add_edge("finalize", END)

    return graph


# ---------------------------------------------------------------------------
# Convenience runner
# ---------------------------------------------------------------------------

def _coerce_state(value: object) -> PipelineState:
    """LangGraph may yield a dict or a PipelineState — normalise to PipelineState."""
    if isinstance(value, PipelineState):
        return value
    if isinstance(value, dict):
        return PipelineState(**value)
    raise TypeError(f"Unexpected pipeline state type: {type(value)!r}")


def run_pipeline(
    request: GenerationRequest,
    *,
    job_id: str | None = None,
    owner_id: str = "",
    on_progress: Callable[[PipelineState], None] | None = None,
) -> PipelineState:
    """
    Run the full pipeline synchronously.

    Args:
        request: The generation request from the user.
        job_id: Reuse this job id (so the API and SSE clients can track the same
            job). When omitted a fresh id is generated.
        owner_id: User id that owns this job (for authorization checks).
        on_progress: Optional callback invoked with the latest state after every
            graph super-step, enabling live SSE progress streaming.

    Returns:
        Final PipelineState with all outputs and observability data.
    """
    logger.info(
        "pipeline_start",
        grade=request.grade,
        topic=request.topic,
        material_type=request.material_type,
        job_id=job_id,
    )

    # Build initial state, reusing the caller's job id so persistence and
    # streaming all key off a single, stable id.
    state = PipelineState(
        request=request,
        status=PipelineStatus.RUNNING,
        owner_id=owner_id,
    )
    if job_id:
        state.job_id = job_id

    restored = try_restore_cached_pipeline(
        request,
        job_id=state.job_id,
        owner_id=owner_id,
        created_at=state.created_at,
    )
    if restored is not None:
        if on_progress:
            on_progress(restored)
        return restored

    graph = create_pipeline()
    compiled = graph.compile()

    # Run, streaming intermediate state so the SSE endpoint sees live progress.
    final_state = state
    try:
        # stream_mode="values" yields the full accumulated state after each
        # node, so we can publish incremental progress to SSE clients.
        for chunk in compiled.stream(state, stream_mode="values"):
            if job_id and is_cancelled(job_id):
                final_state = _coerce_state(chunk)
                if job_id:
                    final_state.job_id = job_id
                final_state.status = PipelineStatus.FAILED
                final_state.error_message = _ABORT_MESSAGE
                logger.info("pipeline_cancelled", job_id=job_id)
                clear_cancel(job_id)
                return final_state

            final_state = _coerce_state(chunk)
            # job_id/owner_id are not mutated by nodes, but re-assert to be safe.
            if job_id:
                final_state.job_id = job_id
            if owner_id and not final_state.owner_id:
                final_state.owner_id = owner_id
            if on_progress is not None:
                try:
                    on_progress(final_state)
                except Exception as cb_err:  # never let a callback kill the run
                    logger.warning("pipeline_progress_callback_failed", error=str(cb_err))

        return final_state

    except Exception as e:
        final_state.status = PipelineStatus.FAILED
        final_state.error_message = str(e)
        if job_id:
            final_state.job_id = job_id
        logger.error("pipeline_failed", error=str(e), job_id=final_state.job_id)
        return final_state
