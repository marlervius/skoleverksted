"""Research-based rules for Norwegian sheets, without any model calls."""

import random

from ScriptoriumFOV.backend import agents, research_design
from ScriptoriumFOV.backend.pdf_service import (
    format_language_exercises,
    keep_line_breaks,
    render_scrambled_sentences,
)
from ScriptoriumFOV.backend.text_cleaner import format_mcq_content


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
