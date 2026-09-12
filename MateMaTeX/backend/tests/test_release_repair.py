"""Final repair must fix the rendered revision without releasing unchecked PDFs."""
from unittest.mock import Mock

import pytest

from app.models.state import GenerationRequest, PipelineState, PipelineStatus
from app.pipeline.agents import release_repair


@pytest.fixture
def state():
    return PipelineState(
        request=GenerationRequest(grade="VG1 1T", topic="Algebra",
                                  include_exercises=False, include_theory=False),
        raw_latex_body=r"$2+2=4$",
        final_latex_body=r"$2+2=4$",
        full_document=r"\documentclass{article}\begin{document}$2+2=5$\end{document}",
        pdf_base64="stale", pdf_path="stale.pdf",
        source_approved=True, teacher_approved_at="old", approved_digest="old",
        release_manifest={"file_hash": "old"},
    )


def test_repairs_actual_rendered_body_and_verifies_replacement(monkeypatch, state):
    model = Mock()
    model.invoke.return_value = r"$2+2=4$"
    monkeypatch.setattr(release_repair, "LLMInterface", lambda **kw: model)
    assert release_repair.prepare_release(state)
    assert "$2+2=5$" in model.invoke.call_args.args[1]
    assert state.final_latex_body == r"$2+2=4$"
    assert state.math_verification.all_correct
    assert state.math_verification.claims_incorrect == 0


def test_no_progress_terminates_and_clears_stale_release(monkeypatch, state):
    model = Mock()
    model.invoke.return_value = r"$2+2=5$"
    monkeypatch.setattr(release_repair, "LLMInterface", lambda **kw: model)
    assert not release_repair.prepare_release(state)
    assert model.invoke.call_count == 1
    assert state.status == PipelineStatus.FAILED
    assert not state.pdf_base64 and not state.pdf_path
    assert not state.source_approved and not state.teacher_approved_at
    assert not state.release_manifest and not state.approved_digest


def test_verified_candidate_never_calls_model(monkeypatch, state):
    state.full_document = r"\begin{document}$2+2=4$\end{document}"
    monkeypatch.setattr(release_repair, "LLMInterface", Mock(side_effect=AssertionError("unexpected model")))
    assert release_repair.prepare_release(state)


def test_empty_repair_is_not_approved(monkeypatch, state):
    model = Mock()
    model.invoke.return_value = ""
    monkeypatch.setattr(release_repair, "LLMInterface", lambda **kw: model)
    assert not release_repair.prepare_release(state)
    assert state.status == PipelineStatus.FAILED


def test_provider_timeout_is_terminal(monkeypatch, state):
    monkeypatch.setattr(release_repair, "run_bounded_sync", Mock(side_effect=TimeoutError("timeout")))
    assert not release_repair.prepare_release(state)
    assert state.current_agent is None
    assert state.steps[-1].completed_at is not None
    assert not state.pdf_base64


def test_repair_budget_is_two_attempts(monkeypatch, state):
    model = Mock()
    model.invoke.side_effect = [r"$2+2=6$", r"$2+2=7$"]
    monkeypatch.setattr(release_repair, "LLMInterface", lambda **kw: model)
    assert not release_repair.prepare_release(state)
    assert model.invoke.call_count == 2
    assert state.status == PipelineStatus.FAILED


def test_finalize_compiles_the_repaired_revision(monkeypatch, state):
    import base64
    import hashlib
    from app.models.state import LatexCompilationResult
    from app.pipeline.graph import finalize
    from app.verification.latex_checker import LatexChecker
    model = Mock()
    model.invoke.return_value = r"$2+2=4$"
    monkeypatch.setattr(release_repair, "LLMInterface", lambda **kw: model)
    compiled = []
    def compile_repaired(self, document):
        assert "$2+2=4$" in document
        assert "$2+2=5$" not in document
        compiled.append(document)
        return LatexCompilationResult(success=True, pdf_base64=base64.b64encode(b"new-pdf").decode())
    monkeypatch.setattr(LatexChecker, "check", compile_repaired)
    state.latex_compilation = LatexCompilationResult(success=True)
    result = finalize(state)
    assert result.status == PipelineStatus.COMPLETED
    assert compiled == [result.full_document]
    assert result.source_approved
    assert result.release_manifest["file_hash"] == hashlib.sha256(b"new-pdf").hexdigest()
    assert "$2+2=4$" in result.verification_content
    assert not result.teacher_approved_at
