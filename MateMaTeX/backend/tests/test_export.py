"""
Tests for the export module — PDF, Word, PowerPoint.
"""

import pytest

from app.export.word import _strip_latex_commands, latex_to_docx
from app.export.powerpoint import (
    _extract_exercises_for_slides,
    _simplify_latex_for_slide,
    latex_to_pptx,
)


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------
SAMPLE_LATEX = r"""
\documentclass[12pt]{article}
\begin{document}
\title{Test Ark}
\maketitle

\begin{taskbox}{Oppgave 1}
Løs likningen $2x + 3 = 7$.
\end{taskbox}

\begin{taskbox}{Oppgave 2}
Beregn $\frac{3}{4} + \frac{1}{2}$.
\end{taskbox}

\section*{Løsningsforslag}
\textbf{Oppgave 1}
$2x = 4 \Rightarrow x = 2$

\textbf{Oppgave 2}
$\frac{3}{4} + \frac{2}{4} = \frac{5}{4}$
\end{document}
"""


# ---------------------------------------------------------------------------
# Tests: LaTeX stripping
# ---------------------------------------------------------------------------
class TestLatexStripping:
    """Test LaTeX → plain text conversion."""

    def test_removes_documentclass(self):
        result = _strip_latex_commands(SAMPLE_LATEX)
        assert r"\documentclass" not in result

    def test_removes_begin_document(self):
        result = _strip_latex_commands(SAMPLE_LATEX)
        assert r"\begin{document}" not in result

    def test_preserves_content(self):
        result = _strip_latex_commands(SAMPLE_LATEX)
        assert "Løs likningen" in result or "likningen" in result

    def test_converts_fractions(self):
        result = _strip_latex_commands(r"$\frac{3}{4}$")
        assert "(3)/(4)" in result

    def test_converts_sqrt(self):
        result = _strip_latex_commands(r"$\sqrt{16}$")
        assert "√(16)" in result

    def test_converts_special_symbols(self):
        result = _strip_latex_commands(r"$a \cdot b$")
        assert "·" in result


# ---------------------------------------------------------------------------
# Tests: Exercise extraction for slides
# ---------------------------------------------------------------------------
class TestExerciseExtraction:
    """Test exercise extraction for PowerPoint slides."""

    def test_extracts_exercises(self):
        exercises = _extract_exercises_for_slides(SAMPLE_LATEX)
        assert len(exercises) == 2
        assert exercises[0]["title"] == "Oppgave 1"

    def test_exercise_body_content(self):
        exercises = _extract_exercises_for_slides(SAMPLE_LATEX)
        assert "likningen" in exercises[0]["body"]

    def test_empty_input(self):
        exercises = _extract_exercises_for_slides("")
        assert exercises == []


# ---------------------------------------------------------------------------
# Tests: Slide text simplification
# ---------------------------------------------------------------------------
class TestSlideSimplification:
    """Test LaTeX → slide text conversion."""

    def test_removes_environments(self):
        result = _simplify_latex_for_slide(r"\begin{align} x = 2 \end{align}")
        assert r"\begin" not in result
        assert "x = 2" in result

    def test_simplifies_math(self):
        result = _simplify_latex_for_slide(r"$\frac{1}{2}$")
        assert "(1)/(2)" in result


# ---------------------------------------------------------------------------
# Tests: Word export
# ---------------------------------------------------------------------------
class TestWordExport:
    """Test DOCX generation."""

    def test_generates_docx_bytes(self):
        try:
            result = latex_to_docx(SAMPLE_LATEX, title="Test")
            assert isinstance(result, bytes)
            assert len(result) > 100
            # DOCX files start with PK (ZIP format)
            assert result[:2] == b'PK'
        except ImportError:
            pytest.skip("python-docx not installed")

    def test_docx_with_empty_content(self):
        try:
            result = latex_to_docx("", title="Empty")
            assert isinstance(result, bytes)
        except ImportError:
            pytest.skip("python-docx not installed")


# ---------------------------------------------------------------------------
# Tests: PowerPoint export
# ---------------------------------------------------------------------------
class TestPowerPointExport:
    """Test PPTX generation."""

    def test_generates_pptx_bytes(self):
        try:
            result = latex_to_pptx(SAMPLE_LATEX, title="Test")
            assert isinstance(result, bytes)
            assert len(result) > 100
            # PPTX files start with PK (ZIP format)
            assert result[:2] == b'PK'
        except ImportError:
            pytest.skip("python-pptx not installed")

    def test_pptx_with_speaker_notes(self):
        try:
            result = latex_to_pptx(
                SAMPLE_LATEX,
                title="Test",
                solutions_as="speaker_notes",
            )
            assert isinstance(result, bytes)
        except ImportError:
            pytest.skip("python-pptx not installed")

    def test_pptx_with_hidden_slides(self):
        try:
            result = latex_to_pptx(
                SAMPLE_LATEX,
                title="Test",
                solutions_as="hidden_slides",
            )
            assert isinstance(result, bytes)
        except ImportError:
            pytest.skip("python-pptx not installed")
