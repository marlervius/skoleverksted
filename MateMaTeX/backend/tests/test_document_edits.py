import json
from unittest.mock import Mock

import pytest

from app.models.llm import TruncatedResponseError
from app.models.state import GenerationRequest, PipelineState
from app.pipeline.document_edits import apply_edits, edit_prompt
from app.pipeline.partitioned_author import generate_in_parts


def test_edits_preserve_unaffected_document_and_use_original_coordinates():
    body = "Innledning\n$2+2=5$\nOppgave\n$3+3=7$\nSlutt"
    response = json.dumps({"edits": [
        {"before": "$2+2=5$", "after": "$2+2=4$ og kontroll"},
        {"before": "$3+3=7$", "after": "$3+3=6$"},
    ]})
    assert apply_edits(body, response) == "Innledning\n$2+2=4$ og kontroll\nOppgave\n$3+3=6$\nSlutt"
    assert "Ikke returner hele dokumentet" in edit_prompt(body, "Rett fasit")


@pytest.mark.parametrize("response", [
    "ufullstendig JSON", '{"edits":[', '"helt dokument"',
    json.dumps({"edits": [{"before": "ukjent", "after": "ny"}]}),
    json.dumps({"edits": [{"before": "tekst", "after": ""}]}),
    json.dumps({"edits": [{"before": "tekst", "after": r"\end{document}"}]}),
    json.dumps({"edits": [{"before": "tekst", "after": "x" * 1501}]}),
    json.dumps({"edits": [{"before": "tekst", "after": "ny"}] * 9}),
])
def test_invalid_edits_fail_without_producing_a_partial_document(response):
    with pytest.raises(ValueError):
        apply_edits("tekst", response)


def test_duplicate_and_overlapping_anchors_are_rejected():
    with pytest.raises(ValueError):
        apply_edits("tekst tekst", '{"edits":[{"before":"tekst","after":"ny"}]}')
    with pytest.raises(ValueError):
        apply_edits("abcdef", json.dumps({"edits": [
            {"before": "abcd", "after": "ny"}, {"before": "cdef", "after": "ny"},
        ]}))


def test_partitioning_preserves_requested_exercise_count_and_context():
    state = PipelineState(request=GenerationRequest(grade="VG1 1T", topic="Algebra", num_exercises=12))
    model = Mock()
    model.invoke.side_effect = ["Innledning", "Eksempler", "Oppgave1-5", "Oppgave6-10", "Oppgave11-12"]
    result = generate_in_parts(model, "system", "originale krav", state)
    assert result == "Innledning\n\nEksempler\n\nOppgave1-5\n\nOppgave6-10\n\nOppgave11-12"
    prompts = [call.args[1] for call in model.invoke.call_args_list]
    assert "Bare oppgave 1 til 5" in prompts[2]
    assert "Bare oppgave 6 til 10" in prompts[3]
    assert "Bare oppgave 11 til 12" in prompts[4]
    assert "Oppgave6-10" in prompts[4]
    assert all("originale krav" in prompt for prompt in prompts)


def test_truncated_part_never_returns_partial_assembly():
    state = PipelineState(request=GenerationRequest(grade="VG1 1T", topic="Algebra"))
    model = Mock()
    model.invoke.side_effect = ["ferdig innledning", TruncatedResponseError("ufullstendig")]
    with pytest.raises(TruncatedResponseError):
        generate_in_parts(model, "system", "krav", state)
    assert model.invoke.call_count == 2
    assert not state.raw_latex_body


def test_partitioning_stops_before_another_call_after_cancellation(monkeypatch):
    from app.pipeline import partitioned_author
    state = PipelineState(request=GenerationRequest(grade="VG1 1T", topic="Algebra"))
    model = Mock()
    monkeypatch.setattr(partitioned_author, "is_cancelled", lambda job_id: True)
    with pytest.raises(RuntimeError):
        generate_in_parts(model, "system", "krav", state)
    model.invoke.assert_not_called()


def test_author_recovers_from_truncation_without_using_partial_text(monkeypatch):
    from app.pipeline.agents import author
    model = Mock()
    model.invoke.side_effect = [TruncatedResponseError("ufullstendig"), "innledning", "eksempler", "oppgaver og fasit"]
    monkeypatch.setattr(author, "LLMInterface", lambda **kwargs: model)
    state = PipelineState(request=GenerationRequest(grade="VG1 1T", topic="Algebra", num_exercises=3))
    author.run_author(state)
    assert state.raw_latex_body == "innledning\n\neksempler\n\noppgaver og fasit"
    assert not state.steps[-1].error
