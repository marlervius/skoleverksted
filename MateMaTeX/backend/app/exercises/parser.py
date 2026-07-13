"""
LaTeX → Atomic exercises parser.

Takes the LaTeX output from the pipeline and splits it into individual
exercises with automatically extracted metadata.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass, field
from enum import Enum

import structlog

logger = structlog.get_logger()


class Difficulty(str, Enum):
    LETT = "lett"
    MIDDELS = "middels"
    VANSKELIG = "vanskelig"


@dataclass
class ParsedExercise:
    """A single exercise extracted from LaTeX content."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    title: str = ""
    number: int = 0
    latex_content: str = ""
    solution: str = ""
    hints: list[str] = field(default_factory=list)
    difficulty: Difficulty = Difficulty.MIDDELS
    exercise_type: str = "standard"
    keywords: list[str] = field(default_factory=list)
    has_figure: bool = False
    sub_parts: list[str] = field(default_factory=list)
    content_hash: str = ""

    def __post_init__(self):
        if not self.content_hash and self.latex_content:
            self.content_hash = hashlib.sha256(
                self.latex_content.encode()
            ).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Main patterns
# ---------------------------------------------------------------------------

# Match \begin{taskbox}{Oppgave N} ... \end{taskbox}
_TASKBOX_PATTERN = re.compile(
    r'\\begin\{taskbox\}\{([^}]*)\}(.*?)\\end\{taskbox\}',
    re.DOTALL,
)

# Match solution blocks per exercise
_SOLUTION_SECTION = re.compile(
    r'\\section\*\{Løsningsforslag\}(.*)',
    re.DOTALL,
)

# Per-exercise solution: \textbf{Oppgave N}... up to next \textbf{Oppgave} or end
_SOLUTION_PER_EXERCISE = re.compile(
    r'\\textbf\{Oppgave\s*(\d+)\}(.*?)(?=\\textbf\{Oppgave|\Z)',
    re.DOTALL,
)

# Sub-parts: \item inside enumerate
_SUBPART_PATTERN = re.compile(r'\\item\s*(.*?)(?=\\item|\\end\{enumerate\})', re.DOTALL)

# Figures
_FIGURE_PATTERN = re.compile(r'\\begin\{(?:figure|tikzpicture)\}')

# Differentiation level headers
_LEVEL_PATTERN = re.compile(r'\\section\*?\{Nivå\s*(\d+)', re.IGNORECASE)

# Math-complexity indicators for difficulty estimation
_HARD_INDICATORS = [
    r'\\frac\{[^}]*\\frac',         # nested fractions
    r'\\sqrt\{[^}]*\\sqrt',          # nested roots
    r'\\int',                          # integrals
    r'\\lim',                          # limits
    r'\\sum',                          # summation
    r'\\prod',                         # product
    r'\\begin\{cases\}',              # piecewise
    r'\\ln|\\log',                     # logarithms
    r'\\sin|\\cos|\\tan',             # trigonometry
    r'bevis|vis at|forklar hvorfor',  # proof tasks (Norwegian)
]

_EASY_INDICATORS = [
    r'(?<!\d)\d{1,2}(?!\d)',          # only small numbers (1-99)
    r'fargelegg|tegn|tell',           # coloring/drawing/counting
    r'skriv av|fyll inn',             # copy/fill-in
]


def parse_exercises(latex_content: str) -> list[ParsedExercise]:
    """
    Parse LaTeX content into individual exercises.

    Extracts:
    - Exercise title and number
    - Content (full LaTeX of the exercise)
    - Solution (matched from the solution section)
    - Sub-parts (a, b, c...)
    - Difficulty (estimated from content complexity)
    - Whether it contains figures
    - Keywords

    Args:
        latex_content: The LaTeX body content (with or without preamble).

    Returns:
        List of ParsedExercise objects.
    """
    exercises: list[ParsedExercise] = []

    # Extract solution section
    solutions: dict[int, str] = {}
    sol_match = _SOLUTION_SECTION.search(latex_content)
    if sol_match:
        sol_text = sol_match.group(1)
        for m in _SOLUTION_PER_EXERCISE.finditer(sol_text):
            ex_num = int(m.group(1))
            solutions[ex_num] = m.group(2).strip()

    # Extract exercises from taskbox environments
    for match in _TASKBOX_PATTERN.finditer(latex_content):
        title = match.group(1).strip()
        body = match.group(2).strip()

        # Extract exercise number
        num_match = re.search(r'(\d+)', title)
        ex_num = int(num_match.group(1)) if num_match else 0

        # Extract sub-parts
        sub_parts = []
        for sp in _SUBPART_PATTERN.finditer(body):
            part_text = sp.group(1).strip()
            if part_text:
                sub_parts.append(part_text)

        # Check for figures
        has_figure = bool(_FIGURE_PATTERN.search(body))

        # Estimate difficulty
        difficulty = _estimate_difficulty(body)

        # Detect exercise type
        exercise_type = _detect_type(body)

        # Extract keywords
        keywords = _extract_keywords(body)

        # Get solution
        solution = solutions.get(ex_num, "")

        exercise = ParsedExercise(
            title=title,
            number=ex_num,
            latex_content=body,
            solution=solution,
            difficulty=difficulty,
            exercise_type=exercise_type,
            keywords=keywords,
            has_figure=has_figure,
            sub_parts=sub_parts,
        )
        exercises.append(exercise)

    logger.info(
        "exercises_parsed",
        count=len(exercises),
        with_solutions=sum(1 for e in exercises if e.solution),
        with_figures=sum(1 for e in exercises if e.has_figure),
    )

    return exercises


# ---------------------------------------------------------------------------
# Difficulty estimation
# ---------------------------------------------------------------------------

def _estimate_difficulty(content: str) -> Difficulty:
    """
    Estimate difficulty based on mathematical complexity indicators.

    Uses pattern matching on the LaTeX to gauge complexity.
    """
    content_lower = content.lower()

    # Check for hard indicators
    hard_score = sum(
        1 for pattern in _HARD_INDICATORS
        if re.search(pattern, content_lower)
    )

    # Check for easy indicators
    easy_score = sum(
        1 for pattern in _EASY_INDICATORS
        if re.search(pattern, content_lower)
    )

    # Count mathematical operations
    frac_count = content.count(r'\frac')
    sqrt_count = content.count(r'\sqrt')
    operator_complexity = frac_count + sqrt_count

    # Multi-step (sub-parts count)
    part_count = content.count(r'\item')

    # Scoring
    if hard_score >= 2 or (operator_complexity >= 3 and part_count >= 3):
        return Difficulty.VANSKELIG
    elif easy_score >= 2 and hard_score == 0 and operator_complexity <= 1:
        return Difficulty.LETT
    else:
        return Difficulty.MIDDELS


# ---------------------------------------------------------------------------
# Type detection
# ---------------------------------------------------------------------------

_TYPE_PATTERNS: dict[str, list[str]] = {
    "flervalg": [r'\\item\s*\[?[A-D]\)?', r'alternativ', r'velg riktig'],
    "sant_usant": [r'sant eller usant', r'sant/usant', r'riktig eller galt'],
    "utfylling": [r'fyll inn', r'\\underline\{\\hspace', r'\\.\\.\\.'],
    "tekstoppgave": [r'kr\.?(?:\s|\\)', r'meter|km|liter|kilo', r'butikk|handle|reise'],
    "grafisk": [r'tegn|skisser|marker|avles', r'koordinatsystem', r'\\begin\{tikzpicture\}'],
    "bevis": [r'vis at|bevis|forklar hvorfor|begrunn'],
}


def _detect_type(content: str) -> str:
    """Detect exercise type from content patterns."""
    content_lower = content.lower()

    scores: dict[str, int] = {}
    for type_name, patterns in _TYPE_PATTERNS.items():
        score = sum(1 for p in patterns if re.search(p, content_lower))
        if score > 0:
            scores[type_name] = score

    if scores:
        return max(scores, key=scores.get)
    return "standard"


# ---------------------------------------------------------------------------
# Keyword extraction
# ---------------------------------------------------------------------------

_MATH_KEYWORDS = [
    "brøk", "desimal", "prosent", "likning", "ulikhet", "funksjon",
    "lineær", "kvadratisk", "eksponentiell", "logaritme", "derivert",
    "integral", "vektor", "geometri", "areal", "volum", "omkrets",
    "pytagoras", "trigonometri", "statistikk", "sannsynlighet",
    "algebra", "tall", "tallinje", "koordinat", "graf", "tabell",
    "potens", "rot", "faktorisering", "polynom", "rekke", "følge",
]


def _extract_keywords(content: str) -> list[str]:
    """Extract mathematical keywords from content."""
    content_lower = content.lower()
    found = [kw for kw in _MATH_KEYWORDS if kw in content_lower]
    return found[:10]  # Cap at 10


# ---------------------------------------------------------------------------
# Utility: re-assemble exercises into a worksheet
# ---------------------------------------------------------------------------

def exercises_to_latex(
    exercises: list[ParsedExercise],
    title: str = "Oppgaveark",
    include_solutions: bool = True,
) -> str:
    """
    Re-assemble selected exercises into a LaTeX document body.

    Useful for building custom worksheets from the exercise bank.
    """
    parts = [
        f"\\title{{{title}}}",
        "\\author{Generert av MateMaTeX AI}",
        "\\date{\\today}",
        "\\maketitle",
        "",
    ]

    for i, ex in enumerate(exercises, 1):
        parts.append(f"\\begin{{taskbox}}{{Oppgave {i}}}")
        parts.append(ex.latex_content)
        parts.append("\\end{taskbox}")
        parts.append("")

    if include_solutions and any(ex.solution for ex in exercises):
        parts.append("\\section*{Løsningsforslag}")
        parts.append("\\begin{multicols}{2}")
        for i, ex in enumerate(exercises, 1):
            if ex.solution:
                parts.append(f"\\textbf{{Oppgave {i}}}\\\\")
                parts.append(ex.solution)
                parts.append("")
        parts.append("\\end{multicols}")

    return "\n".join(parts)
