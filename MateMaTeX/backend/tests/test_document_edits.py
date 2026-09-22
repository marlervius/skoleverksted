import json
from unittest.mock import Mock

import pytest

from app.models.llm import TruncatedResponseError
from app.models.state import GenerationRequest, PipelineState
from app.pipeline.document_edits import apply_edits, apply_edits_report, edit_prompt
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
    # An overlapping edit is dropped; it never lands on text another edit wrote.
    content, rejected = apply_edits_report("abcdef", json.dumps({"edits": [
        {"before": "abcd", "after": "ny"}, {"before": "cdef", "after": "ny"},
    ]}))
    assert content == "nyef"
    assert rejected and "overlapper" in rejected[0]


def test_one_unanchored_edit_does_not_discard_the_valid_repairs():
    """Production regression: one bad anchor failed the whole generation."""
    body = "Oppgave 1: $2+2=5$\nOppgave 2: $3+3=7$"
    content, rejected = apply_edits_report(body, json.dumps({"edits": [
        {"before": "$2+2=5$", "after": "$2+2=4$"},
        {"before": "tekst som ikke finnes", "after": "ny"},
        {"before": "$3+3=7$", "after": "$3+3=6$"},
    ]}))
    assert content == "Oppgave 1: $2+2=4$\nOppgave 2: $3+3=6$"
    assert len(rejected) == 1 and "finnes ikke" in rejected[0]


def test_unescaped_latex_backslashes_in_json_are_understood():
    body = r"Svar: $x = \frac{1}{2}$ og $y \neq 3$ med \textbf{fasit}."
    # Models often write LaTeX without doubling backslashes: \f and \n are
    # then valid JSON escapes that would silently corrupt the anchor, and \t
    # in \textbf would become a tab.
    response = '{"edits":[{"before":"$x = \\frac{1}{2}$","after":"$x = \\frac{1}{3}$"},' \
               '{"before":"\\textbf{fasit}","after":"\\textbf{løsning}"}]}'
    assert apply_edits(body, response) == r"Svar: $x = \frac{1}{3}$ og $y \neq 3$ med \textbf{løsning}."
    invalid_json = '{"edits":[{"before":"$y \\neq 3$","after":"$y \\leq 3$"}]}'
    assert apply_edits(body, invalid_json) == r"Svar: $x = \frac{1}{2}$ og $y \leq 3$ med \textbf{fasit}."


def test_whitespace_differences_in_an_anchor_are_tolerated_when_unique():
    body = "Løs likningen\n  $2x + 3 = 7$.\nSvar: $x = 5$"
    response = json.dumps({"edits": [{"before": "Svar:  $x = 5$", "after": "Svar: $x = 2$"}]})
    assert apply_edits(body, response) == "Løs likningen\n  $2x + 3 = 7$.\nSvar: $x = 2$"


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


def test_an_unusable_math_repair_keeps_the_draft_instead_of_failing_the_job(monkeypatch):
    """Production regression: a rejected repair ended in "KI-genereringen feilet"."""
    from app.models.state import VerificationResult
    from app.pipeline.agents import author
    model = Mock()
    model.invoke.side_effect = [
        '{"edits":[{"before":"finnes ikke","after":"ny"}]}',
        TimeoutError("Modellen svarte ikke"),
        '{"edits":[]}',
    ]
    monkeypatch.setattr(author, "LLMInterface", lambda **kwargs: model)
    state = PipelineState(request=GenerationRequest(grade="VG1 1T", topic="Algebra"),
                          raw_latex_body="$2+2=5$", author_retry_reason="math",
                          math_verification=VerificationResult(claims_checked=1, claims_incorrect=1))
    author.run_author(state)
    assert model.invoke.call_count == author._REPAIR_CALLS
    assert state.raw_latex_body == "$2+2=5$"
    assert not state.steps[-1].error
    assert "ble avvist" in model.invoke.call_args_list[1].args[1]


def test_a_math_repair_retries_after_a_rejected_edit_list(monkeypatch):
    from app.models.state import VerificationResult
    from app.pipeline.agents import author
    model = Mock()
    model.invoke.side_effect = ["ikke json", '{"edits":[{"before":"$2+2=5$","after":"$2+2=4$"}]}']
    monkeypatch.setattr(author, "LLMInterface", lambda **kwargs: model)
    state = PipelineState(request=GenerationRequest(grade="VG1 1T", topic="Algebra"),
                          raw_latex_body="$2+2=5$", author_retry_reason="math",
                          math_verification=VerificationResult(claims_checked=1, claims_incorrect=1))
    author.run_author(state)
    assert state.raw_latex_body == "$2+2=4$"
