"""Exercise real LangGraph transitions: router mutations are not persisted."""
from datetime import datetime, timedelta

import pytest

from app.models.state import (
    AgentRole, GenerationRequest, LatexCompilationResult, PipelineState, PipelineStatus,
)
from app.pipeline import graph
from app.pipeline.agents.layout import run_layout


OVERFLOW = "\n".join(
    f"Overfull \\hbox (40.0pt too wide) in paragraph at lines {i}--{i + 1}"
    for i in range(10, 14)
)


@pytest.mark.parametrize("via_fallback", [False, True])
def test_layout_loop_terminates_and_publishes_active_node_before_work(monkeypatch, via_fallback):
    observed = []
    fixes = []
    def noop(state):
        return state
    for name in ("run_pedagogue", "run_author", "run_math_verifier",
                 "run_content_quality", "run_tikz_validator", "run_table_validator"):
        monkeypatch.setattr(graph, name, noop)
    monkeypatch.setattr(graph, "_should_skip_editor", lambda _s: True)
    def compile_doc(state):
        assert observed[-1] == AgentRole.LATEX_VALIDATOR
        if via_fallback and state.latex_fix_attempts == 0:
            state.latex_compilation = LatexCompilationResult(errors=["PGF Math Error"])
            state.latex_fix_attempts = 3
            return state
        state.latex_compilation = LatexCompilationResult(success=True, log_excerpt=OVERFLOW)
        state.latex_fix_attempts += 1
        return state
    def fallback(state):
        state.latex_compilation = LatexCompilationResult(success=True, log_excerpt=OVERFLOW)
        state.used_latex_fallback = True
        return state
    def fix(state):
        assert observed[-1] == AgentRole.LATEX_FIXER
        fixes.append(state.layout_fix_attempts)
        assert "Layout-problemer" in state.latex_compilation.errors[0]
        return state
    def finish(state):
        state.status = PipelineStatus.COMPLETED
        return state
    monkeypatch.setattr(graph, "run_latex_validator", compile_doc)
    monkeypatch.setattr(graph, "run_latex_fallback", fallback)
    monkeypatch.setattr(graph, "run_latex_fixer", fix)
    monkeypatch.setattr(graph, "finalize", finish)
    state = PipelineState(request=GenerationRequest(grade="8. trinn", topic="Grafer"))
    result = graph.create_pipeline(
        on_progress=lambda state: observed.append(state.current_agent),
    ).compile().invoke(state, config={"recursion_limit": 25})
    assert result["status"] == PipelineStatus.COMPLETED
    assert result["layout_fix_attempts"] == 1
    assert result["layout_fix_requested"] is False
    assert fixes == [1]
    assert result["latex_fix_attempts"] == (4 if via_fallback else 2)
    assert result["used_latex_fallback"] is via_fallback


@pytest.mark.parametrize("expired,success", [(True, True), (False, False)])
def test_no_layout_repair_after_budget_or_failed_compilation(expired, success):
    state = PipelineState(
        request=GenerationRequest(grade="8. trinn", topic="Grafer"),
        latex_compilation=LatexCompilationResult(success=success, log_excerpt=OVERFLOW),
        created_at=datetime.now() - timedelta(days=1) if expired else datetime.now(),
    )
    run_layout(state)
    assert state.layout_fix_attempts == 0
    assert graph.should_route_after_layout(state) == "finalize"


def test_layout_fixer_receives_overflow_diagnostics(monkeypatch):
    from app.pipeline.agents.latex_fixer import run_latex_fixer
    document = r"\documentclass{article}\begin{document}Test\end{document}"
    state = PipelineState(
        request=GenerationRequest(grade="8. trinn", topic="Grafer"),
        full_document=document,
        latex_compilation=LatexCompilationResult(success=True, log_excerpt=OVERFLOW),
    )
    run_layout(state)
    prompts = []
    class FakeLLM:
        def __init__(self, **kwargs):
            pass
        def invoke(self, system, prompt):
            prompts.append(prompt)
            return document
    monkeypatch.setattr("app.pipeline.agents.latex_fixer.LLMInterface", FakeLLM)
    run_latex_fixer(state)
    assert "40.0" in prompts[0]
    assert "Layout-problemer" in prompts[0]


def test_status_poll_exposes_current_work_without_document(monkeypatch):
    import asyncio
    from app import main
    state = PipelineState(
        request=GenerationRequest(grade="8. trinn", topic="Grafer"),
        status=PipelineStatus.RUNNING, current_agent=AgentRole.LATEX_VALIDATOR,
    )
    monkeypatch.setattr(main, "resolve_job", lambda *_a: state)
    status = asyncio.run(main.get_job_status(state.job_id, user_id="anonymous"))
    assert status["current_agent"] == "latex_validator"
    assert not status["ready"]
    assert "full_document" not in status
    state.status = PipelineStatus.FAILED
    status = asyncio.run(main.get_job_status(state.job_id, user_id="anonymous"))
    assert status["ready"]
    assert status["current_agent"] is None
