"""
Tests for text_cleaner.py

Run with:  pytest backend/tests/test_text_cleaner.py -v
"""

import sys
import os

# Allow importing backend modules directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from text_cleaner import (
    clean_ai_artifacts,
    clean_meta_instructions,
    clean_section_header,
    convert_markdown_lists_to_typst,
    format_mcq_content,
    format_vocabulary_as_list,
    remove_answer_markers,
    sanitize_comprehension_for_typst,
    sanitize_for_typst,
)


# ---------------------------------------------------------------------------
# clean_ai_artifacts
# ---------------------------------------------------------------------------


def test_clean_ai_artifacts_empty():
    assert clean_ai_artifacts("") == ""


def test_clean_ai_artifacts_removes_intro_phrases():
    text = "Her er den ferdige teksten:\nMye flott innhold her."
    result = clean_ai_artifacts(text)
    assert "Her er den ferdige teksten" not in result
    assert "Mye flott innhold her" in result


def test_clean_ai_artifacts_removes_thought_action():
    text = "Thought: I should do this\nAction: search\nAction Input: query\nMy actual content"
    result = clean_ai_artifacts(text)
    assert "Thought:" not in result
    assert "Action:" not in result
    assert "My actual content" in result


def test_clean_ai_artifacts_removes_markdown_headers():
    text = "## Overskrift\nBrødtekst"
    result = clean_ai_artifacts(text)
    assert "##" not in result
    assert "Brødtekst" in result


def test_clean_ai_artifacts_removes_guillemet_content():
    text = "«You ONLY have access to these tools» Normal tekst."
    result = clean_ai_artifacts(text)
    assert "«" not in result
    assert "Normal tekst." in result


# ---------------------------------------------------------------------------
# clean_section_header
# ---------------------------------------------------------------------------


def test_clean_section_header_removes_known_headers():
    text = "LESEFORSTÅELSE\nHer er spørsmål."
    result = clean_section_header(text)
    assert "LESEFORSTÅELSE" not in result
    assert "Her er spørsmål." in result


def test_clean_section_header_removes_bloom_labels():
    text = "Hvilke land finnes? (Huske)\nSvar her."
    result = clean_section_header(text)
    assert "(Huske)" not in result
    assert "Svar her." in result


def test_clean_section_header_preserves_content():
    text = "Dette er vanlig tekst om naturfag."
    result = clean_section_header(text)
    assert result.strip() == text.strip()


# ---------------------------------------------------------------------------
# remove_answer_markers
# ---------------------------------------------------------------------------


def test_remove_answer_markers_strips_trailing_stars():
    text = "a) Oslo *\nb) Bergen\nc) Tromsø ***"
    result = remove_answer_markers(text)
    assert "Oslo *" not in result
    assert "Oslo" in result
    assert "Bergen" in result


def test_remove_answer_markers_empty():
    assert remove_answer_markers("") == ""


# ---------------------------------------------------------------------------
# convert_markdown_lists_to_typst
# ---------------------------------------------------------------------------


def test_convert_markdown_lists():
    text = "* første punkt\n* andre punkt"
    result = convert_markdown_lists_to_typst(text)
    assert result == "- første punkt\n- andre punkt"


def test_convert_markdown_lists_preserves_bold():
    text = "**Bold text** should not be changed"
    result = convert_markdown_lists_to_typst(text)
    assert result == text


# ---------------------------------------------------------------------------
# sanitize_for_typst
# ---------------------------------------------------------------------------


def test_sanitize_for_typst_empty():
    assert sanitize_for_typst("") == ""


def test_sanitize_for_typst_escapes_hash():
    result = sanitize_for_typst("Test #color")
    assert "\\#color" in result


def test_sanitize_for_typst_escapes_dollar():
    result = sanitize_for_typst("$100")
    assert "\\$100" in result


def test_sanitize_for_typst_converts_bold():
    result = sanitize_for_typst("**ord** er viktig")
    assert "#strong[ord]" in result


def test_sanitize_for_typst_preserves_norwegian():
    text = "æ ø å Æ Ø Å"
    result = sanitize_for_typst(text)
    assert "æ" in result
    assert "ø" in result
    assert "å" in result


def test_sanitize_for_typst_section_content_removes_headers():
    text = "DISKUSJON\nSpørsmål 1: Hva er demokrati?"
    result = sanitize_for_typst(text, is_section_content=True)
    assert "DISKUSJON" not in result
    assert "Hva er demokrati" in result


# ---------------------------------------------------------------------------
# format_vocabulary_as_list
# ---------------------------------------------------------------------------


def test_format_vocabulary_as_list_colon_separated():
    text = "Demokrati\\: Styringsform der folket bestemmer"
    result = format_vocabulary_as_list(text)
    assert "#strong[Demokrati:]" in result
    assert "Styringsform" in result


def test_format_vocabulary_as_list_empty():
    assert format_vocabulary_as_list("") == ""


def test_format_vocabulary_as_list_adds_bullets():
    text = "ord: definisjon"
    result = format_vocabulary_as_list(text)
    assert result.startswith("- ")


# ---------------------------------------------------------------------------
# format_mcq_content
# ---------------------------------------------------------------------------


def test_format_mcq_content_formats_questions():
    text = "1. Hva er Norge?\na) Et land\nb) Et hav"
    result = format_mcq_content(text)
    assert "#strong[1.]" in result
    assert "a) Et land" in result


def test_format_mcq_content_empty():
    assert format_mcq_content("") == ""


# ---------------------------------------------------------------------------
# sanitize_comprehension_for_typst
# ---------------------------------------------------------------------------


def test_sanitize_comprehension_strips_stars():
    text = "a) Oslo *\nb) Bergen\nc) Tromsø"
    result = sanitize_comprehension_for_typst(text)
    assert "Oslo *" not in result
    assert "Oslo" in result


# ---------------------------------------------------------------------------
# clean_meta_instructions
# ---------------------------------------------------------------------------


def test_clean_meta_instructions_removes_patterns():
    text = "Her er 4 spørsmål basert på teksten:\n1. Hva er demokrati?"
    result = clean_meta_instructions(text)
    assert "Her er 4 spørsmål" not in result
    assert "Hva er demokrati" in result
