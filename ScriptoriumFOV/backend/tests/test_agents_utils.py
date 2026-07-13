"""
Tests for utility functions in agents.py that do not require AI API calls.

Run with:  pytest backend/tests/test_agents_utils.py -v
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

# Set a dummy API key so agents.py can be imported without failing at module level
os.environ.setdefault("GOOGLE_API_KEY", "test-dummy-key")

from agents import (
    _get_cache_key,
    _get_thumbnail_url,
    extract_language_exercises,
    get_level_constraints,
    format_level_constraints,
)


# ---------------------------------------------------------------------------
# _get_cache_key
# ---------------------------------------------------------------------------


def test_cache_key_deterministic():
    key1 = _get_cache_key("topic", "norsk", "A1.1", {}, None, None, None)
    key2 = _get_cache_key("topic", "norsk", "A1.1", {}, None, None, None)
    assert key1 == key2


def test_cache_key_differs_on_topic():
    key1 = _get_cache_key("topic1", "norsk", "A1.1", {}, None, None, None)
    key2 = _get_cache_key("topic2", "norsk", "A1.1", {}, None, None, None)
    assert key1 != key2


def test_cache_key_differs_on_options():
    opts_a = {"grammar_tasks": True}
    opts_b = {"grammar_tasks": False}
    key1 = _get_cache_key("topic", "norsk", "A1.1", opts_a, None, None, None)
    key2 = _get_cache_key("topic", "norsk", "A1.1", opts_b, None, None, None)
    assert key1 != key2


# ---------------------------------------------------------------------------
# get_level_constraints
# ---------------------------------------------------------------------------


def test_level_constraints_a1_norwegian():
    c = get_level_constraints("A1.1", is_english=False)
    assert c["max_sentence_words"] == 8
    assert "sublevel_note" in c


def test_level_constraints_b2_english():
    c = get_level_constraints("B2.2", is_english=True)
    assert c["max_sentence_words"] == 25


def test_level_constraints_sublevel_lower():
    c = get_level_constraints("A2.1", is_english=False)
    assert "sublevel_note" in c
    assert "LAVERE" in c["sublevel_note"]


def test_level_constraints_sublevel_upper():
    c = get_level_constraints("B1.2", is_english=False)
    assert "sublevel_note" in c
    assert "ØVRE" in c["sublevel_note"]


# ---------------------------------------------------------------------------
# format_level_constraints
# ---------------------------------------------------------------------------


def test_format_level_constraints_returns_string():
    result = format_level_constraints("A2.1", is_english=False)
    assert isinstance(result, str)
    assert "A2.1" in result


def test_format_level_constraints_english():
    result = format_level_constraints("B1.1", is_english=True)
    assert "LANGUAGE REQUIREMENTS" in result


def test_format_level_constraints_difficulty_modifier():
    result = format_level_constraints("A2.1", is_english=False, difficulty_modifier=2)
    assert "Vanskelighetsjustering" in result or "Difficulty" in result


# ---------------------------------------------------------------------------
# extract_language_exercises
# ---------------------------------------------------------------------------


def test_extract_language_exercises_valid_json():
    text = '{"grammar_tasks": [{"type": "verb"}], "vocabulary_tasks": [], "syntax_tasks": []}'
    result = extract_language_exercises(text)
    assert result["grammar_tasks"] == [{"type": "verb"}]
    assert result["vocabulary_tasks"] == []


def test_extract_language_exercises_markdown_json():
    text = '```json\n{"grammar_tasks": [], "vocabulary_tasks": [{"type": "cloze"}], "syntax_tasks": []}\n```'
    result = extract_language_exercises(text)
    assert result["vocabulary_tasks"] == [{"type": "cloze"}]


def test_extract_language_exercises_invalid_returns_default():
    result = extract_language_exercises("not json at all")
    assert result == {"grammar_tasks": [], "vocabulary_tasks": [], "syntax_tasks": []}


def test_extract_language_exercises_empty():
    result = extract_language_exercises("")
    assert result == {"grammar_tasks": [], "vocabulary_tasks": [], "syntax_tasks": []}


# ---------------------------------------------------------------------------
# _get_thumbnail_url
# ---------------------------------------------------------------------------


def test_thumbnail_url_already_thumb():
    url = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/File.jpg/800px-File.jpg"
    assert _get_thumbnail_url(url) == url


def test_thumbnail_url_builds_thumb():
    url = "https://upload.wikimedia.org/wikipedia/commons/a/ab/File.jpg"
    result = _get_thumbnail_url(url)
    assert "/thumb/" in result
    assert "800px-" in result


def test_thumbnail_url_passthrough_non_wikimedia():
    url = "https://example.com/image.jpg"
    assert _get_thumbnail_url(url) == url
