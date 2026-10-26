"""Research-based rules for Norwegian sheets, without any model calls."""

import random

import pytest

from ScriptoriumFOV.backend import agents, research_design
from ScriptoriumFOV.backend.pdf_service import (
    format_language_exercises,
    keep_line_breaks,
    render_scrambled_sentences,
)
from ScriptoriumFOV.backend.text_cleaner import format_mcq_content, sanitize_comprehension_for_typst


def _types(tasks):
    return [task["type"] for task in tasks]


def test_each_level_starts_with_its_processability_stage():
    rng = random.Random(1)
    assert _types(research_design.select_grammar_tasks("A1.1", 3, rng))[:2] == ["bestemt_form", "pronomen_subjekt"]
    assert _types(research_design.select_grammar_tasks("A2.1", 3, rng))[0] == "tidsbruk_preteritum_perfektum"
    assert _types(research_design.select_grammar_tasks("B1.2", 3, rng))[0] == "kombiner_leddsetning"


def test_tasks_never_leave_the_level_stage():
    for level in ("A1.1", "A2.2", "B1.1", "B2.1"):
        design = research_design.design_for(level)
        allowed = {task["type"] for task in design["core_tasks"] + design["pool"]}
        for seed in range(20):
            tasks = research_design.select_grammar_tasks(level, 3, random.Random(seed))
            assert len(tasks) == 3
            assert len(set(_types(tasks))) == 3
            assert set(_types(tasks)) <= allowed


def test_a1_never_trains_subordinate_clauses_or_inversion():
    design = research_design.design_for("A1.1")
    types = {task["type"] for task in design["core_tasks"] + design["pool"]}
    assert not types & {"kombiner_leddsetning", "relativsetninger", "ordstilling_leddsetning_forst", "passiv"}


def test_norwegian_grammar_selection_uses_the_stages_and_english_is_unchanged():
    norwegian = _types(agents.get_random_grammar_tasks("A1.1", False, 3))
    assert norwegian[:2] == ["bestemt_form", "pronomen_subjekt"]
    english = _types(agents.get_random_grammar_tasks("A1.1", True, 3))
    english_pool = {task["type"] for task in agents.GRAMMAR_TASKS_ENGLISH["A1_A2"]}
    assert set(english) <= english_pool


def test_unknown_level_falls_back_to_a2():
    assert research_design.base_level("C1") == "A2"
    assert research_design.base_level("b1.2") == "B1"


def test_open_questions_get_writing_lines():
    text = "1. Hvorfor sjekket Sara tallene? Svar med egne ord.\n2. Hva er riktig?\na) Ja\nb) Nei"
    result = format_mcq_content(text)
    first, second = result.split("#strong[2.]")
    assert "#line(" in first
    assert "#line(" not in second


def test_scrambled_sentences_do_not_turn_slashes_into_words():
    result = render_scrambled_sentences(["I går / fikk / Sara / lønnsslippen"])
    assert "[/]" not in result
    assert "[I går]" in result  # a time phrase stays one block: it is place 1
    assert "[Sara]" in result


def test_writing_tracks_keep_their_own_lines():
    text = "Basis: kort\nStandard: oppgaven\n\n- punkt\n- punkt"
    expected = "Basis: kort \\" + "\nStandard: oppgaven\n\n- punkt\n- punkt"
    assert keep_line_breaks(text) == expected


def test_sentence_building_tasks_get_one_line_per_prompt():
    exercises = {
        "vocabulary_tasks": [
            {
                "type": "setningsbygging",
                "instruction": "Skriv én setning med ordet om situasjonen.",
                "items": ["kontrakt – praksisplass på et verksted", "ansvar – kantina på skolen"],
            },
            {"type": "lyd_og_skrift", "instruction": "Les ordparene høyt.", "items": ["tak – takk"]},
        ]
    }
    result = format_language_exercises(exercises, {"vocabulary_tasks": True})
    assert result.count("#line(length: 100%") == 3
    assert "praksisplass på et verksted" in result


# ---------------------------------------------------------------------------
# Pre-A1 (NOR07-03 level 1, start phase)
# ---------------------------------------------------------------------------


def test_pre_a1_is_its_own_level_with_stage_one_tasks():
    assert research_design.base_level("Pre-A1") == "PRE-A1"
    tasks = _types(research_design.select_grammar_tasks("Pre-A1", 3, random.Random(3)))
    assert tasks[:2] == ["pronomen_subjekt", "tegnsetting_stor_bokstav"]
    design = research_design.design_for("Pre-A1")
    types = {task["type"] for task in design["core_tasks"] + design["pool"]}
    assert not types & {"bestemt_form", "tidsbruk_preteritum_perfektum", "kombiner_leddsetning", "feilretting"}


def test_pre_a1_text_is_short_practical_and_without_subordinate_linking():
    block = research_design.text_design_block("Pre-A1")
    assert "vaktliste" in block and "SMS" in block and "skjema" in block
    assert "fordi" not in block
    assert research_design.design_for("Pre-A1")["text_length"] == "40-80 ord"
    assert "fordi" in research_design.text_design_block("A2.1")


def test_pre_a1_comprehension_has_three_questions():
    section = research_design.comprehension_section("b", "Pre-A1")
    assert "Lag 3 korte spørsmål" in section
    assert "Svar kort." in section
    assert "Svar med egne ord." not in section


def test_pre_a1_prompt_and_readability_limits():
    from ScriptoriumFOV.backend.level_readability import SENTENCE_LIMITS, analyze_readability

    block = agents.format_level_constraints("Pre-A1", False)
    assert "Maks 6 ord per setning" in block
    assert "Riktig Pre-A1" in block
    assert agents.LEVEL_CONSTRAINTS["PRE-A1"]["max_sentence_words"] <= SENTENCE_LIMITS["PRE-A1"]
    report = analyze_readability("Du begynner klokka fire fordi sjefen er syk.", "Pre-A1")
    assert report["status"] == "needs_attention"
    assert any(issue["code"] == "subordinate_clause" for issue in report["issues"])
    assert "Pre-A1" in report["summary"]


def test_english_pre_a1_uses_the_beginner_pool():
    english = _types(agents.get_random_grammar_tasks("Pre-A1", True, 3))
    assert set(english) <= {task["type"] for task in agents.GRAMMAR_TASKS_ENGLISH["A1_A2"]}


def test_the_api_accepts_pre_a1_for_single_and_dual_sheets():
    from ScriptoriumFOV.backend import main

    request = main.LessonRequest(topic="Første vakt", subject="Samfunnsfag", level="Pre-A1")
    assert request.level == "Pre-A1"
    assert main._ADJACENT_LEVELS["Pre-A1"] == ("Pre-A1", "A1.1")


@pytest.mark.parametrize("level", ["Pre-A1", "A1.1", "A1.2", "A2.1", "A2.2", "B1.1", "B1.2", "B2.1", "B2.2"])
def test_reading_tasks_require_evidence_and_unambiguous_choices_at_every_level(level):
    section = research_design.comprehension_section("c", level)
    assert section.startswith("c) LESEFORSTÅELSE")
    for rule in ("nøyaktig ett riktig svar", "klart feil ut fra teksten", "ingen overlappende svar",
                 "Ikke krev forkunnskaper", "regning", "personlige erfaringer", "Ikke finn på et svar"):
        assert rule in section
    assert "Ingen av dem skal kunne besvares ved å kopiere" not in section


@pytest.mark.parametrize("level", ["Pre-A1", "A1.1", "A1.2"])
def test_beginner_reading_does_not_require_paraphrasing_or_inference(level):
    section = research_design.comprehension_section("a", level)
    assert "Svar kort." in section
    assert "Svar med egne ord." not in section
    assert "Ikke krev" in section and "slutninger" in section
    if level == "Pre-A1":
        assert "ett ord eller et tall" in section
        assert "Spørsmål 4" not in section
    else:
        assert "to tomme felt" in section
        assert "hente svaret direkte fra teksten" in section


def test_a2_builds_on_explicit_links_before_b1_inference_and_b2_argument():
    a2 = research_design.comprehension_section("a", "A2.2")
    b1 = research_design.comprehension_section("a", "B1.1")
    b2 = research_design.comprehension_section("a", "B2.2")
    assert "to eksplisitte opplysninger" in a2
    assert "samme avsnitt" in a2
    assert "uttrykker tydelig" in a2
    assert "trekk en enkel slutning" not in a2
    assert "trekk en enkel slutning" in b1
    assert "ett konkret tekstbelegg" in b1
    assert "begrunnelse støtter hovedbudskapet" in b2
    assert "det eleven tolker" in b2
    assert research_design.comprehension_section("a", "unknown") == research_design.comprehension_section("a", "A2")


@pytest.mark.parametrize("deep_dive", [False, True])
def test_beginner_practical_text_is_not_forced_into_paragraphs(deep_dive):
    rule = research_design.text_structure_rule("Pre-A1", deep_dive)
    assert "korte linjer" in rule
    assert "2-3 avsnitt" not in rule
    assert "2-3 avsnitt" in research_design.text_structure_rule("A1.1")
    assert "2-3 avsnitt" not in research_design.text_structure_rule("A2.1", True)


@pytest.mark.parametrize("level", ["Pre-A1", "A1.1", "A2.1", "B1.1", "B2.1"])
def test_key_grades_reading_against_text_evidence_and_accepts_alternative_answers(level):
    key = research_design.teacher_key_rules(level)
    for rule in ("samme nummerering og antall", "flervalg", "åpne spørsmål", "tekstbelegg for hvert svar",
                 "hva svaret må inneholde", "ikke rettskriving", "ikke den eneste tillatte"):
        assert rule in key
    assert "spørsmål 3 og 4" not in key
    assert ("ikke krev omskriving" in key) == (level in ("Pre-A1", "A1.1"))


def test_short_beginner_answers_get_writing_space_without_exposing_choices():
    text = "1. Når starter vakten?\na) Klokka åtte *\nb) Klokka ni\nc) Klokka ti\n2. Hvor jobber Sara? Svar kort."
    rendered = format_mcq_content(sanitize_comprehension_for_typst(text))
    choice, short_answer = rendered.split("#strong[2.]")
    assert "*" not in choice
    assert "#line(" not in choice
    assert short_answer.count("#line(") == 2
