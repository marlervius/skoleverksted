"""
Tests for the exercise parser — LaTeX → atomic exercises.
"""

import pytest

from app.exercises.parser import (
    Difficulty,
    ParsedExercise,
    _detect_type,
    _estimate_difficulty,
    _extract_keywords,
    exercises_to_latex,
    parse_exercises,
)


# ---------------------------------------------------------------------------
# Sample LaTeX content
# ---------------------------------------------------------------------------
SAMPLE_LATEX = r"""
\title{Algebra — 8. trinn}
\author{MateMaTeX AI}
\maketitle

\begin{taskbox}{Oppgave 1}
Løs likningen $2x + 3 = 7$.
\end{taskbox}

\begin{taskbox}{Oppgave 2}
Forenkle uttrykket $3(x + 2) - 5x$.
\begin{enumerate}
\item Multipliser ut parentesen.
\item Samle like ledd.
\item Skriv svaret på enklest form.
\end{enumerate}
\end{taskbox}

\begin{taskbox}{Oppgave 3}
Tegn grafen til funksjonen $f(x) = 2x - 1$ i et koordinatsystem.
\begin{tikzpicture}
\begin{axis}[xmin=-3,xmax=3,ymin=-3,ymax=3]
\addplot[domain=-3:3]{2*x - 1};
\end{axis}
\end{tikzpicture}
\end{taskbox}

\begin{taskbox}{Oppgave 4}
\begin{enumerate}
\item[A)] $x = 2$
\item[B)] $x = 3$
\item[C)] $x = 4$
\item[D)] $x = 5$
\end{enumerate}
Velg riktig alternativ: Hva er løsningen av $x + 1 = 4$?
\end{taskbox}

\begin{taskbox}{Oppgave 5}
En butikk selger epler for 5 kr stykket. Kari handler epler for 35 kr.
Hvor mange epler kjøpte hun?
\end{taskbox}

\section*{Løsningsforslag}
\textbf{Oppgave 1}
$2x + 3 = 7 \Rightarrow 2x = 4 \Rightarrow x = 2$

\textbf{Oppgave 2}
$3(x+2) - 5x = 3x + 6 - 5x = -2x + 6$

\textbf{Oppgave 3}
Grafen er en rett linje gjennom $(0, -1)$ med stigningstall $2$.
"""

HARD_EXERCISE = r"""
\begin{taskbox}{Oppgave 1}
Vis at $\int_0^1 \frac{\ln(1+x)}{x} \, dx$ konvergerer.
Begrunn svaret ditt ved å bruke \begin{cases} f(x) = \ln(1+x)/x \end{cases}.
\end{taskbox}
"""

EASY_EXERCISE = r"""
\begin{taskbox}{Oppgave 1}
Tell antall firkanter. Fargelegg 3 av dem.
Skriv av tallet 7.
\end{taskbox}
"""


# ---------------------------------------------------------------------------
# Tests: parse_exercises
# ---------------------------------------------------------------------------
class TestParseExercises:
    """Test exercise parsing from LaTeX."""

    def test_parses_correct_count(self):
        exercises = parse_exercises(SAMPLE_LATEX)
        assert len(exercises) == 5

    def test_exercise_titles(self):
        exercises = parse_exercises(SAMPLE_LATEX)
        assert exercises[0].title == "Oppgave 1"
        assert exercises[1].title == "Oppgave 2"
        assert exercises[4].title == "Oppgave 5"

    def test_exercise_numbers(self):
        exercises = parse_exercises(SAMPLE_LATEX)
        assert exercises[0].number == 1
        assert exercises[1].number == 2
        assert exercises[4].number == 5

    def test_solutions_matched(self):
        exercises = parse_exercises(SAMPLE_LATEX)
        assert "x = 2" in exercises[0].solution
        assert "-2x + 6" in exercises[1].solution
        # Oppgave 4 and 5 have no solutions in the sample
        assert exercises[3].solution == ""
        assert exercises[4].solution == ""

    def test_sub_parts_detected(self):
        exercises = parse_exercises(SAMPLE_LATEX)
        # Oppgave 2 has 3 sub-parts
        assert len(exercises[1].sub_parts) == 3
        assert "Multipliser ut parentesen" in exercises[1].sub_parts[0]

    def test_figures_detected(self):
        exercises = parse_exercises(SAMPLE_LATEX)
        # Oppgave 3 has a tikzpicture
        assert exercises[2].has_figure is True
        assert exercises[0].has_figure is False

    def test_content_hash_generated(self):
        exercises = parse_exercises(SAMPLE_LATEX)
        for ex in exercises:
            assert ex.content_hash != ""
            assert len(ex.content_hash) == 16

    def test_empty_input_returns_empty(self):
        exercises = parse_exercises("")
        assert exercises == []

    def test_no_taskbox_returns_empty(self):
        exercises = parse_exercises(r"\section{Intro} Hello world")
        assert exercises == []


# ---------------------------------------------------------------------------
# Tests: difficulty estimation
# ---------------------------------------------------------------------------
class TestDifficultyEstimation:
    """Test difficulty estimation heuristics."""

    def test_hard_exercise(self):
        exercises = parse_exercises(HARD_EXERCISE)
        assert len(exercises) == 1
        assert exercises[0].difficulty == Difficulty.VANSKELIG

    def test_easy_exercise(self):
        exercises = parse_exercises(EASY_EXERCISE)
        assert len(exercises) == 1
        assert exercises[0].difficulty == Difficulty.LETT

    def test_medium_default(self):
        exercises = parse_exercises(SAMPLE_LATEX)
        # Basic algebra should be medium
        assert exercises[0].difficulty == Difficulty.MIDDELS


# ---------------------------------------------------------------------------
# Tests: type detection
# ---------------------------------------------------------------------------
class TestTypeDetection:
    """Test exercise type classification."""

    def test_multiple_choice(self):
        exercises = parse_exercises(SAMPLE_LATEX)
        # Oppgave 4 is multiple choice
        assert exercises[3].exercise_type == "flervalg"

    def test_word_problem(self):
        exercises = parse_exercises(SAMPLE_LATEX)
        # Oppgave 5 is a text/word problem (butikk, kr)
        assert exercises[4].exercise_type == "tekstoppgave"

    def test_graphical_exercise(self):
        exercises = parse_exercises(SAMPLE_LATEX)
        # Oppgave 3 involves drawing/tikz
        assert exercises[2].exercise_type == "grafisk"


# ---------------------------------------------------------------------------
# Tests: keyword extraction
# ---------------------------------------------------------------------------
class TestKeywordExtraction:
    """Test mathematical keyword extraction."""

    def test_algebra_keywords(self):
        exercises = parse_exercises(SAMPLE_LATEX)
        # Oppgave 1 should have "likning" related keywords
        # Content: "Løs likningen $2x + 3 = 7$."
        kw = exercises[0].keywords
        assert isinstance(kw, list)

    def test_function_keywords(self):
        exercises = parse_exercises(SAMPLE_LATEX)
        # Oppgave 3 mentions "funksjon", "graf", "koordinat"
        kw = exercises[2].keywords
        assert "funksjon" in kw or "koordinat" in kw or "graf" in kw

    def test_max_keywords(self):
        exercises = parse_exercises(SAMPLE_LATEX)
        for ex in exercises:
            assert len(ex.keywords) <= 10


# ---------------------------------------------------------------------------
# Tests: exercises_to_latex (re-assembly)
# ---------------------------------------------------------------------------
class TestExercisesToLatex:
    """Test re-assembling exercises into LaTeX."""

    def test_reassembly_structure(self):
        exercises = parse_exercises(SAMPLE_LATEX)
        result = exercises_to_latex(exercises[:2], title="Test ark")
        assert r"\title{Test ark}" in result
        assert r"\begin{taskbox}{Oppgave 1}" in result
        assert r"\begin{taskbox}{Oppgave 2}" in result

    def test_reassembly_with_solutions(self):
        exercises = parse_exercises(SAMPLE_LATEX)
        result = exercises_to_latex(exercises[:2], include_solutions=True)
        assert r"\section*{Løsningsforslag}" in result

    def test_reassembly_without_solutions(self):
        exercises = parse_exercises(SAMPLE_LATEX)
        result = exercises_to_latex(exercises[:2], include_solutions=False)
        assert r"\section*{Løsningsforslag}" not in result

    def test_empty_exercises(self):
        result = exercises_to_latex([], title="Empty")
        assert r"\title{Empty}" in result


# ---------------------------------------------------------------------------
# Tests: ParsedExercise model
# ---------------------------------------------------------------------------
class TestParsedExercise:
    """Test the ParsedExercise dataclass."""

    def test_id_generation(self):
        ex = ParsedExercise(latex_content="test")
        assert len(ex.id) == 12

    def test_content_hash(self):
        ex1 = ParsedExercise(latex_content="same content")
        ex2 = ParsedExercise(latex_content="same content")
        assert ex1.content_hash == ex2.content_hash

    def test_different_content_different_hash(self):
        ex1 = ParsedExercise(latex_content="content A")
        ex2 = ParsedExercise(latex_content="content B")
        assert ex1.content_hash != ex2.content_hash

    def test_default_difficulty(self):
        ex = ParsedExercise()
        assert ex.difficulty == Difficulty.MIDDELS
