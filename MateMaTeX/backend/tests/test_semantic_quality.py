"""Exercise rubric rendering through the evaluator, without external model calls."""

from types import SimpleNamespace
from unittest.mock import Mock

from app.models.state import GenerationRequest
from app.verification.semantic_quality import evaluate_semantic_quality


def test_chapter_rubric_reaches_model_and_uses_actual_score(monkeypatch):
    model = Mock()
    model.invoke.return_value = '{"score": 61, "issues": [{"code": "thin_explanations", "message": "Mangler mellomregninger"}]}'
    monkeypatch.setattr("app.config.get_settings", lambda: SimpleNamespace(google_api_key="test-key"))
    monkeypatch.setattr("app.models.llm.LLMInterface", lambda **kw: model)
    request = GenerationRequest(grade="VG1 1T", topic="Funksjoner", material_type="kapittel")
    score, issues = evaluate_semantic_quality("Forklaring. " * 60, request)
    assert model.invoke.call_count == 1
    prompt = model.invoke.call_args.args[1]
    assert '{"score": 0-100, "issues": [{"code": "...", "message": "..."}]}' in prompt
    assert "passende for VG1 1T" in prompt
    assert score == 61
    assert issues[0].code == "thin_explanations"


def test_semantic_weaknesses_reach_content_gate(monkeypatch):
    from app.models.state import ContentQualityReport, PipelineState
    from app.pipeline.agents.content_quality import run_content_quality
    model = Mock()
    model.invoke.return_value = '{"score": 61, "issues": [{"code": "thin_explanations", "message": "Mangler mellomregninger"}]}'
    monkeypatch.setattr("app.config.get_settings", lambda: SimpleNamespace(google_api_key="test-key"))
    monkeypatch.setattr("app.models.llm.LLMInterface", lambda **kw: model)
    monkeypatch.setattr("app.pipeline.agents.content_quality.evaluate_content_quality",
                        lambda *a: ContentQualityReport(passed=True, score=100))
    state = PipelineState(
        request=GenerationRequest(grade="VG1 1T", topic="Funksjoner", material_type="kapittel"),
        edited_latex_body="Forklaring. " * 60,
    )
    result = run_content_quality(state)
    assert not result.content_quality.passed
    assert result.content_quality.semantic_score == 61
    assert result.content_quality.score == 61


def test_full_chapter_including_exercises_reaches_the_rubric(monkeypatch):
    model = Mock()
    model.invoke.return_value = '{"score": 85, "issues": []}'
    monkeypatch.setattr("app.config.get_settings", lambda: SimpleNamespace(google_api_key="test-key"))
    monkeypatch.setattr("app.models.llm.LLMInterface", lambda **kw: model)
    body = "Innledning. " * 1200 + r"\section{Logaritmereglene}\section{Oppgaver} Siste oppgave."
    evaluate_semantic_quality(body, GenerationRequest(grade="VG1 1T", topic="Funksjoner", material_type="kapittel"))
    assert model.invoke.call_args.args[1].endswith(body)
