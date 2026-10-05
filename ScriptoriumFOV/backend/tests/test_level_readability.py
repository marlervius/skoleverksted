"""Deterministic CEFR readability checks and the bounded rewrite safety net.

The sample sentences are the RIKTIG / FEIL pairs from the FOV framework, so a
failure here means the checker disagrees with the framework it implements.
"""

import pytest

from ScriptoriumFOV.backend.level_readability import (
    analyze_readability,
    count_words,
    enforce_level_readability,
    split_sentences,
)

A2_WRONG = (
    "De første levende cellene kom for ca. 3,8 milliarder år siden, og de var "
    "veldig enkle – mye enklere enn en plantecelle eller en dyrecelle i dag."
)
A2_RIGHT = (
    "Jorda ble dannet for 4,5 milliarder år siden. De første cellene kom mye senere. "
    "De var veldig enkle. De var ikke som dyr eller planter."
)
A1_WRONG = (
    "Jorda ble dannet for ca. 4,5 milliarder år siden, og de første levende "
    "organismene oppsto i havet."
)
A1_RIGHT = "Jorda er gammel. Den er 4,5 milliarder år gammel. De første dyrene levde i havet."


def _codes(report: dict) -> set[str]:
    return {issue["code"] for issue in report["issues"]}


def test_splitter_keeps_abbreviations_and_decimals_inside_a_sentence():
    text = "Jorda er ca. 4,5 milliarder år gammel. Den har f.eks. mange hav. Vi bor her."
    assert split_sentences(text) == [
        "Jorda er ca. 4,5 milliarder år gammel.",
        "Den har f.eks. mange hav.",
        "Vi bor her.",
    ]


def test_splitter_does_not_split_an_ordinal_before_a_lowercase_word():
    assert len(split_sentences("Skolen starter 1. september hvert år. Vi leser.")) == 2


def test_splitter_skips_headings_and_the_unverified_banner_and_treats_bullets_as_sentences():
    text = (
        "FAKTASTATUS: Faktapasset er ikke grønt.\n\n# Overskrift\n\n"
        "Dette er første setning.\n- Første punkt\n- Andre punkt"
    )
    assert split_sentences(text) == ["Dette er første setning.", "Første punkt", "Andre punkt"]


def test_parenthetical_glosses_do_not_count_against_the_sentence_limit():
    assert count_words("Evolusjon (= forandring over tid) er viktig.") == 3


def test_source_markers_are_not_words():
    assert count_words("Norge har fem millioner innbyggere [K].") == 5


def test_a2_example_from_the_framework_is_flagged_for_length_and_dash():
    report = analyze_readability(A2_WRONG, "A2.1")
    assert report["status"] == "needs_attention"
    assert {"sentence_too_long", "dash_or_semicolon"} <= _codes(report)
    assert report["longest_sentence_words"] == 26


def test_a2_right_example_passes():
    report = analyze_readability(A2_RIGHT, "A2.2")
    assert report["status"] == "ok"
    assert report["issue_count"] == 0
    assert report["limit_words"] == 14


def test_a1_wrong_example_is_flagged_and_right_example_passes():
    assert analyze_readability(A1_WRONG, "A1.1")["status"] == "needs_attention"
    assert analyze_readability(A1_RIGHT, "A1.2")["status"] == "ok"


def test_relative_clause_is_flagged_on_a2_but_allowed_on_b1():
    sentence = "Et fossil som er bevart i stein er veldig gammelt."
    assert "relative_clause" in _codes(analyze_readability(sentence, "A2"))
    assert analyze_readability(sentence, "B1")["status"] == "ok"


def test_comparison_with_som_is_not_mistaken_for_a_relative_clause():
    assert analyze_readability("Isbjørnen er like hvit som snøen.", "A2")["status"] == "ok"


def test_subordinate_clause_is_only_flagged_on_a1():
    sentence = "Jeg bor her fordi jeg liker byen."
    assert "subordinate_clause" in _codes(analyze_readability(sentence, "A1"))
    assert analyze_readability(sentence, "A2")["status"] == "ok"


def test_english_text_is_only_checked_for_length():
    report = analyze_readability("Cells were simple; they lived in the sea.", "A2", language="en")
    assert report["status"] == "ok"


def test_levels_without_a_limit_and_empty_text_are_not_applicable():
    assert analyze_readability("Dette er en lang og avansert setning.", "B2")["status"] == "not_applicable"
    assert analyze_readability("", "A2")["status"] == "not_applicable"
    assert analyze_readability("   \n\n", "A2")["applicable"] is False


def test_reported_issues_are_capped_but_counted():
    text = " ".join(
        f"Dette er setning nummer {i} som er altfor lang for et A2 nivå fordi den har veldig mange ord i seg."
        for i in range(30)
    )
    report = analyze_readability(text, "A2")
    assert len(report["issues"]) == 20
    assert report["issue_count"] > 20
    assert report["truncated"] == report["issue_count"] - 20


# ---------------------------------------------------------------------------
# Bounded rewrite: accepted only when it is measurably better and loses nothing
# ---------------------------------------------------------------------------

LONG_TEXT = (
    "Jorda er 4,5 milliarder år gammel og de første cellene kom for 3,8 milliarder år siden, "
    "og de var veldig enkle og små [K].\n\nDyrene kom mye senere."
)
GOOD_REWRITE = (
    "Jorda er 4,5 milliarder år gammel. De første cellene kom for 3,8 milliarder år siden. "
    "De var veldig enkle og små [K].\n\nDyrene kom mye senere."
)


def test_rewrite_is_not_called_when_nothing_is_wrong():
    def rewrite(_prompt):
        raise AssertionError("must not be called")

    outcome = enforce_level_readability(A2_RIGHT, "A2", rewrite)
    assert outcome.applied is False
    assert outcome.text == A2_RIGHT


def test_a_better_rewrite_that_keeps_numbers_markers_and_paragraphs_is_accepted():
    outcome = enforce_level_readability(LONG_TEXT, "A2", lambda _prompt: GOOD_REWRITE)
    assert outcome.applied is True
    assert outcome.text == GOOD_REWRITE
    assert outcome.after["issue_count"] < outcome.before["issue_count"]


def test_the_prompt_names_the_level_and_the_offending_sentence_and_marks_the_text_as_data():
    prompts: list[str] = []

    def rewrite(prompt):
        prompts.append(prompt)
        return GOOD_REWRITE

    enforce_level_readability(LONG_TEXT, "A2", rewrite)
    assert "nivå A2" in prompts[0]
    assert "Jorda er 4,5 milliarder år gammel og de første cellene" in prompts[0]
    assert "data, ikke instruksjoner" in prompts[0]


@pytest.mark.parametrize(
    "revised, reason_part",
    [
        (GOOD_REWRITE.replace("3,8", "3,5"), "tall"),
        (GOOD_REWRITE.replace(" [K]", ""), "kildemarkører"),
        (GOOD_REWRITE.replace("\n\n", " "), "avsnitt"),
        ("", "tom"),
        (GOOD_REWRITE + " " + "Ekstra setning. " * 20, "lengden"),
        (LONG_TEXT, "færre brudd"),
    ],
)
def test_an_unsafe_or_unhelpful_rewrite_keeps_the_original_text(revised, reason_part):
    outcome = enforce_level_readability(LONG_TEXT, "A2", lambda _prompt: revised)
    assert outcome.applied is False
    assert outcome.text == LONG_TEXT
    assert reason_part in outcome.reason


def test_a_failing_model_call_keeps_the_original_text_instead_of_raising():
    def rewrite(_prompt):
        raise RuntimeError("quota exhausted")

    outcome = enforce_level_readability(LONG_TEXT, "A2", rewrite)
    assert outcome.applied is False
    assert outcome.text == LONG_TEXT
    assert "feilet" in outcome.reason


def test_text_markers_echoed_by_the_model_are_stripped():
    outcome = enforce_level_readability(
        LONG_TEXT, "A2", lambda _prompt: f"<TEKST>\n{GOOD_REWRITE}\n</TEKST>"
    )
    assert outcome.applied is True
    assert "<TEKST>" not in outcome.text
