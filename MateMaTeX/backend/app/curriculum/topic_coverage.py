"""
Topic coverage specs — map grade + tema to required subtopics and off-topic guards.

Used by pedagogue/author prompts and the content-quality gate so kapittel
material actually covers the curriculum (e.g. Funksjoner in VG1 1T).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.curriculum.lk20 import COMPETENCY_GOALS, get_topics_for_grade

# Keywords that indicate a subtopic is present in LaTeX (lowercase matching).
SUBTOPIC_KEYWORDS: dict[str, list[str]] = {
    "Lineære funksjoner": ["lineær", "stigningstall", "konstantledd", "f(x)=ax"],
    "Andregradsfunksjoner": ["andregrad", "parabel", "toppunkt", "bunnpunkt"],
    "Polynomfunksjoner": ["polynom", "graden til funksjonen", "polynomfunksjon"],
    "Rasjonale funksjoner": ["rasjonal", "asymptot"],
    "Eksponentialfunksjoner": ["eksponential", "vekstfaktor", "a \\cdot b^x", "a·b^x"],
    "Logaritmer": ["logaritm", "\\lg", "ln("],
    "Logaritmeregler": ["logaritmeregel", "lg(a", "lg a"],
    "Eksponentiallikninger": ["eksponentiallikning", "b^x", "10^x", "2^x"],
    "Lineære modeller": ["lineær modell", "modellere", "praktisk"],
    "Grafisk framstilling": ["koordinatsystem", "tegn graf", "grafen til"],
    "Tolkning av grafer": ["tolke graf", "avles", "skjæringspunkt"],
    "Praktiske funksjoner": ["tekstoppgave", "modell", "sammenheng"],
}

# Section titles / themes that must NOT appear when the focus category differs.
OFF_TOPIC_SECTION_PATTERNS: dict[str, list[str]] = {
    "Funksjoner": [
        r"\\section\*?\{[^}]*[Vv]ektor",
        r"\\section\*?\{[^}]*[Tt]rigonometri",
        r"\\section\*?\{[^}]*[Ss]inussetning",
        r"\\section\*?\{[^}]*[Cc]osinussetning",
        r"\\section\*?\{[^}]*[Kk]ombinatorikk",
        r"\\section\*?\{[^}]*[Ss]annsynlighet",
    ],
    "Algebra": [
        r"\\section\*?\{[^}]*[Vv]ektor",
        r"\\section\*?\{[^}]*[Ss]inussetning",
    ],
}

OFF_TOPIC_BODY_KEYWORDS: dict[str, list[str]] = {
    "Funksjoner": [
        "cosinussetningen",
        "sinussetningen",
        "skalarprodukt",
        "vektoraddisjon",
        "parallellogrammetoden",
    ],
}

COMPETENCY_EXTRA_REQUIREMENTS: dict[str, list[str]] = {
    "1T-03": [
        "Minst én \\begin{utforsk}-aktivitet (utforske)",
        "Minst 4 funksjonsgrafer (PGFPlots axis eller TikZ)",
        "Forklar sammenhengen mellom tabell, graf og formel",
        "Bruk ordene analyser/drøfte om funksjonsegenskaper",
    ],
    "MAT08-03": [
        "Minst én \\begin{utforsk}-aktivitet",
        "Minst 2 grafer av funksjoner",
        "Koble tabell, graf og formel",
    ],
    "MAT09-01": [
        "Modeller med lineære funksjoner i praktiske situasjoner",
        "Minst 2 grafer",
    ],
}


@dataclass
class TopicCoverageSpec:
    """Required coverage for a grade + topic combination."""

    grade: str
    topic: str
    category: str | None = None
    required_subtopics: list[str] = field(default_factory=list)
    forbidden_section_patterns: list[str] = field(default_factory=list)
    forbidden_body_keywords: list[str] = field(default_factory=list)
    competency_requirements: list[str] = field(default_factory=list)
    min_theory_sections: int = 5
    min_examples: int = 8
    min_graphs: int = 4
    min_exercises: int = 8
    min_body_chars: int = 10_000


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def _match_category(grade: str, topic: str) -> tuple[str | None, list[str]]:
    """Find the best TOPIC_LIBRARY category for *topic* at *grade*."""
    topics_by_cat = get_topics_for_grade(grade)
    if not topics_by_cat:
        return None, []

    topic_n = _normalize(topic)

    # Prefer an explicitly named subtopic over a broader category substring
    # (e.g. "Lineære funksjoner" must not become all of "Funksjoner").
    for category, subtopics in topics_by_cat.items():
        for sub in subtopics:
            if topic_n == _normalize(sub):
                return category, [sub]

    # Exact / substring category match (e.g. "Funksjoner" in "Funksjoner 1T").
    for category, subtopics in topics_by_cat.items():
        cat_n = _normalize(category)
        if cat_n in topic_n or topic_n in cat_n:
            return category, list(subtopics)

    # Match on subtopic name.
    for category, subtopics in topics_by_cat.items():
        for sub in subtopics:
            if _normalize(sub) in topic_n or topic_n in _normalize(sub):
                # A request for one named subtopic must not silently expand into
                # an entire category. Category-level requests still use all
                # subtopics via the branch above.
                return category, [sub]

    # Keyword overlap between topic and category words.
    topic_words = {w for w in re.split(r"[^\wæøåÆØÅ]+", topic_n) if len(w) > 3}
    best_cat: str | None = None
    best_score = 0
    best_subs: list[str] = []
    for category, subtopics in topics_by_cat.items():
        cat_words = {w for w in re.split(r"[^\wæøåÆØÅ]+", _normalize(category)) if len(w) > 3}
        score = len(topic_words & cat_words)
        if score > best_score:
            best_score = score
            best_cat = category
            best_subs = list(subtopics)

    if best_score > 0:
        return best_cat, best_subs

    return None, []


def get_topic_coverage_spec(
    grade: str,
    topic: str,
    *,
    material_type: str = "kapittel",
    num_exercises: int = 10,
    competency_goals: list[str] | None = None,
) -> TopicCoverageSpec:
    """Build a coverage spec for prompts and validation."""
    category, subtopics = _match_category(grade, topic)
    goals = competency_goals or []

    spec = TopicCoverageSpec(
        grade=grade,
        topic=topic,
        category=category,
        required_subtopics=subtopics,
        min_exercises=max(6, num_exercises),
    )

    if material_type != "kapittel":
        spec.min_theory_sections = 0
        spec.min_examples = 2
        spec.min_graphs = 1 if material_type != "prøve" else 0
        spec.min_body_chars = 2000
        return spec

    if subtopics:
        n = len(subtopics)
        spec.min_theory_sections = max(5, min(n, 7))
        spec.min_examples = max(6, min(n, 8))
        spec.min_graphs = max(3, min(n, 5))
        spec.min_body_chars = max(6000, min(n * 900, 12000))

    if category:
        spec.forbidden_section_patterns = list(OFF_TOPIC_SECTION_PATTERNS.get(category, []))
        spec.forbidden_body_keywords = list(OFF_TOPIC_BODY_KEYWORDS.get(category, []))

    for goal in goals:
        code = goal.split(":")[0].strip() if ":" in goal else goal.strip()
        for key, reqs in COMPETENCY_EXTRA_REQUIREMENTS.items():
            if key in code or code in key:
                spec.competency_requirements.extend(reqs)

    # De-duplicate while preserving order.
    seen: set[str] = set()
    unique_reqs: list[str] = []
    for r in spec.competency_requirements:
        if r not in seen:
            seen.add(r)
            unique_reqs.append(r)
    spec.competency_requirements = unique_reqs

    return spec


def keywords_for_subtopic(subtopic: str) -> list[str]:
    """Return detection keywords for a subtopic (fallback: words from name)."""
    if subtopic in SUBTOPIC_KEYWORDS:
        return SUBTOPIC_KEYWORDS[subtopic]
    words = [w.lower() for w in re.split(r"[^\wæøåÆØÅ]+", subtopic) if len(w) > 4]
    return words or [_normalize(subtopic)]


def format_coverage_for_prompt(
    grade: str,
    topic: str,
    *,
    material_type: str = "kapittel",
    num_exercises: int = 10,
    competency_goals: list[str] | None = None,
) -> str:
    """Human-readable checklist injected into pedagogue/author prompts."""
    spec = get_topic_coverage_spec(
        grade,
        topic,
        material_type=material_type,
        num_exercises=num_exercises,
        competency_goals=competency_goals,
    )

    if material_type != "kapittel":
        return ""

    lines = [
        f"=== PENSUMDEKNING FOR «{topic}» ({grade}) ===",
    ]
    if spec.category:
        lines.append(f"Fokuskategori: {spec.category}")
        lines.append(
            "VIKTIG: Hold deg STRICT til denne kategorien. Ikke bland inn andre "
            f"hovedtemaer fra {grade} (f.eks. vektorer/trigonometri i et funksjonskapittel)."
        )
    else:
        lines.append("Fokus: dekke hele temaet grundig uten å blande inn urelaterte kapitler.")

    if spec.required_subtopics:
        lines.append("")
        lines.append(
            "OBLIGATORISKE DELTEMAER (hver med egen \\section, teori, ≥2 eksempler, ≥1 graf):"
        )
        for i, sub in enumerate(spec.required_subtopics, 1):
            kws = ", ".join(keywords_for_subtopic(sub)[:3])
            lines.append(f"  {i}. {sub}  [nøkkelord: {kws}]")

    lines.extend(
        [
            "",
            "MINIMUMSKRAV FOR KAPITTEL:",
            f"- {spec.min_theory_sections}+ teoriseksjoner (\\section) før oppgavene",
            f"- {spec.min_examples}+ gjennomregnede \\begin{{eksempel}}",
            f"- {spec.min_graphs}+ funksjonsgrafer (\\begin{{axis}} eller TikZ)",
            "- Minst 1 \\begin{utforsk} (LK20: utforske)",
            "- Minst 2 \\begin{vanligfeil}",
            "- \\begin{{laeringsmaal}} øverst og \\begin{{oppsummering}} før oppgaver",
            "- Forklar tabell ↔ graf ↔ formel (alle tre representasjoner)",
            f"- {spec.min_exercises} oppgaver i \\section{{Oppgaver}}, kun innenfor temaet",
            f"- Minst {spec.min_body_chars} tegn teori — skriv UTFYLLENDE, ikke sammendrag",
        ]
    )

    if spec.forbidden_body_keywords:
        lines.append("")
        lines.append("FORBUDT INNHOLD (hører til andre kapitler — ikke inkluder):")
        for kw in spec.forbidden_body_keywords:
            lines.append(f"  ✗ {kw}")

    if spec.competency_requirements:
        lines.append("")
        lines.append("EKSTRA KRAV FRA VALGTE KOMPETANSEMÅL:")
        for req in spec.competency_requirements:
            lines.append(f"  • {req}")

    return "\n".join(lines)


def all_grade_categories(grade: str) -> list[str]:
    """Return category names for a grade (for tests)."""
    return list(get_topics_for_grade(grade).keys())


def competency_goals_for_grade(grade: str) -> list[str]:
    """Return competency goal strings for grade."""
    for key, goals in COMPETENCY_GOALS.items():
        if grade.lower() in key.lower() or key.lower() in grade.lower():
            return list(goals)
    return []
