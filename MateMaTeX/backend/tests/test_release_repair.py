"""Final repair must fix the rendered revision without releasing unchecked PDFs."""
import json
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
    model.invoke.return_value = json.dumps({"edits": [{"before": "$2+2=5$", "after": "$2+2=4$"}]})
    monkeypatch.setattr(release_repair, "LLMInterface", lambda **kw: model)
    assert release_repair.prepare_release(state)
    assert "$2+2=5$" in model.invoke.call_args.args[1]
    assert state.final_latex_body == r"$2+2=4$"
    assert state.math_verification.all_correct
    assert state.math_verification.claims_incorrect == 0


def test_no_progress_terminates_and_clears_stale_release(monkeypatch, state):
    model = Mock()
    model.invoke.return_value = '{"edits": []}'
    monkeypatch.setattr(release_repair, "LLMInterface", lambda **kw: model)
    assert not release_repair.prepare_release(state)
    assert model.invoke.call_count == 2
    assert state.status == PipelineStatus.FAILED
    assert not state.pdf_base64 and not state.pdf_path
    assert not state.source_approved and not state.teacher_approved_at
    assert not state.release_manifest and not state.approved_digest


def test_verified_candidate_never_calls_model(monkeypatch, state):
    state.full_document = r"\begin{document}$2+2=4$\end{document}"
    monkeypatch.setattr(release_repair, "LLMInterface", Mock(side_effect=AssertionError("unexpected model")))
    assert release_repair.prepare_release(state)


@pytest.mark.parametrize("rejected", [
    "not JSON", '{"edits": []}',
    '{"edits": [{"before": "missing anchor", "after": "replacement"}]}',
])
def test_rejected_edit_gets_bounded_retry_against_unchanged_candidate(monkeypatch, state, rejected):
    model = Mock()
    model.invoke.side_effect = [rejected, json.dumps({"edits": [
        {"before": "$2+2=5$", "after": "$2+2=4$"},
    ]})]
    monkeypatch.setattr(release_repair, "LLMInterface", lambda **kw: model)
    assert release_repair.prepare_release(state)
    assert model.invoke.call_count == 2
    retry_prompt = model.invoke.call_args.args[1]
    assert "Forrige endringsliste ble avvist" in retry_prompt
    assert "$2+2=5$" in retry_prompt
    assert "og returner hele dokumentet med korreksjoner" not in retry_prompt
    assert state.final_latex_body == "$2+2=4$"
    assert state.math_verification.claims_incorrect == 0
    assert state.steps[-1].retries == 2


def test_release_failure_retains_safe_diagnostic_and_logs_counts(monkeypatch, state):
    from app.public_errors import RELEASE_VERIFICATION_ERROR, public_generation_error
    model = Mock()
    model.invoke.return_value = '{"edits": []}'
    monkeypatch.setattr(release_repair, "LLMInterface", lambda **kw: model)
    log = Mock()
    monkeypatch.setattr(release_repair, "logger", log)
    assert not release_repair.prepare_release(state)
    assert public_generation_error(state.error_message) == RELEASE_VERIFICATION_ERROR
    log.warning.assert_any_call(
        "release_verification_failed", job_id=state.job_id,
        error="Sluttkandidaten bestod ikke alle kontrollene", error_type="_ReviewRequired",
        repairs=2, incorrect=1, unparseable=0,
    )


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


def test_two_stalled_repairs_stop_even_when_model_changes_text(monkeypatch, state):
    model = Mock()
    model.invoke.side_effect = [json.dumps({"edits": [{"before": f"$2+2={before}$", "after": f"$2+2={after}$"}]}) for before, after in [(5, 6), (6, 7)]]
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
    model.invoke.return_value = json.dumps({"edits": [{"before": "$2+2=5$", "after": "$2+2=4$"}]})
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


def test_large_chapter_repairs_39_expressions_in_verified_batches(monkeypatch, state):
    from app.verification.math_checker import MathChecker

    original = [rf"${i}\cdot{{2+1}}={i*3}$" for i in range(1, 40)]
    replacements = [rf"${i}\cdot(2+1)={i*3}$" for i in range(1, 40)]
    body = "Innledning som skal bevares.\n" + "\n".join(original)
    state.full_document = r"\begin{document}" + body + r"\end{document}"
    assert MathChecker().verify(body).claims_unparseable == 39
    model = Mock()
    model.invoke.side_effect = [json.dumps({"edits": [
        {"before": before, "after": after}
        for before, after in zip(original[start:start+6], replacements[start:start+6])
    ]}) for start in range(0, 39, 6)]
    monkeypatch.setattr(release_repair, "LLMInterface", lambda **kw: model)

    assert release_repair.prepare_release(state)
    assert model.invoke.call_count == 7
    assert state.math_verification.claims_checked == state.math_verification.claims_correct == 39
    assert not state.math_verification.claims_unparseable
    assert state.final_latex_body == "Innledning som skal bevares.\n" + "\n".join(replacements)
    first_prompt = model.invoke.call_args_list[0].args[1]
    feedback = first_prompt.split("DOKUMENT:")[0]
    assert "UVISS 6:" in feedback and "UVISS 7:" not in feedback
    assert "33 øvrige uttrykk" in feedback
    assert "Kontekst:" in feedback


def test_language_warning_is_repaired_even_when_overall_score_passes(monkeypatch, state):
    from app.models.state import ContentQualityIssue, ContentQualityReport

    state.full_document = r"\begin{document}Finn negasymptoten. $2+2=4$\end{document}"
    def check_quality(body, request):
        issues = ([ContentQualityIssue(code="language", severity="warning",
                   message="Rett skrivefeilen negasymptoten til asymptoten.")]
                  if "negasymptoten" in body else [])
        return ContentQualityReport(passed=True, score=95, issues=issues)
    monkeypatch.setattr(release_repair, "evaluate_content_quality", check_quality)
    model = Mock()
    model.invoke.return_value = json.dumps({"edits": [
        {"before": "negasymptoten", "after": "asymptoten"},
    ]})
    monkeypatch.setattr(release_repair, "LLMInterface", lambda **kw: model)
    assert release_repair.prepare_release(state)
    assert "SPRÅKFEIL SOM MÅ RETTES" in model.invoke.call_args.args[1]
    assert "negasymptoten" not in state.final_latex_body
    assert not state.content_quality.issues


def test_progress_does_not_remove_the_total_repair_limit(monkeypatch, state):
    original = [f"${i}+1={i+2}$" for i in range(1, 13)]
    state.full_document = r"\begin{document}" + "\n".join(original) + r"\end{document}"
    model = Mock()
    model.invoke.side_effect = [json.dumps({"edits": [
        {"before": original[i-1], "after": f"${i}+1={i+1}$"},
    ]}) for i in range(1, 13)]
    monkeypatch.setattr(release_repair, "LLMInterface", lambda **kw: model)
    assert not release_repair.prepare_release(state)
    assert model.invoke.call_count == 10
    assert state.math_verification.claims_incorrect == 2
    assert state.status == PipelineStatus.FAILED
    assert not state.source_approved and not state.pdf_base64
