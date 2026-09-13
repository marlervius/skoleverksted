"""
Layout QA node (Track E).

Runs after LaTeX validation/fallback. It inspects the compilation log captured
by the validator and produces a structured :class:`LayoutReport`. It is
non-destructive (no recompilation, no document edits), so it adds negligible
latency and can never break a document that already compiled.
"""

from __future__ import annotations

from datetime import datetime

import structlog

from app.latex.layout_report import analyze_log
from app.models.state import AgentRole, AgentStep, PipelineState
from app.pipeline.routing_helpers import over_time_budget

logger = structlog.get_logger()


def run_layout(state: PipelineState) -> PipelineState:
    """Analyze the compile log and attach a layout-quality report to the state."""
    step = AgentStep(agent=AgentRole.LAYOUT, started_at=datetime.now())
    state.current_agent = AgentRole.LAYOUT
    state.layout_fix_requested = False

    try:
        report = analyze_log(
            state.latex_compilation.log_excerpt,
            state.latex_compilation.warnings,
        )
        state.layout_report = report
        step.output_summary = f"Layout-score {report.score}/100 — {report.summary}"
        bad = [
            i
            for i in report.issues
            if i.kind in ("oversized_float", "overfull_hbox") and i.severity != "info"
        ]
        if (state.latex_compilation.success and report.score < 75 and bad
                and state.layout_fix_attempts < 1 and not over_time_budget(state)):
            # LangGraph persists node outputs, not mutations inside conditional
            # routers. Charge the attempt here so a low score cannot loop forever.
            state.layout_fix_attempts += 1
            state.layout_fix_requested = True
            state.latex_compilation.errors = [
                "Layout-problemer — reduser figur/tabell-bredde med \\resizebox eller mindre axis width:",
                *[issue.detail for issue in bad[:6]],
            ]
            logger.info(
                "layout_fix_scheduled",
                job_id=state.job_id,
                score=report.score,
                issues=len(bad),
            )
        logger.info(
            "layout_qa",
            job_id=state.job_id,
            score=report.score,
            overfull=report.overfull_count,
            undefined_refs=report.undefined_references,
        )
    except Exception as e:  # never let QA break the pipeline
        step.error = str(e)
        logger.warning("layout_qa_failed", job_id=state.job_id, error=str(e))

    step.completed_at = datetime.now()
    step.duration_seconds = (step.completed_at - step.started_at).total_seconds()
    state.steps.append(step)
    state.current_agent = None
    return state
