"""
Rule-based content quality gate for textbook products (hefte, kapittel) with
light checks for the other material types.

Scores pedagogical completeness: curriculum coverage, examples, graphs,
explore/analyze/draw (LK20), and off-topic guards.
"""

from __future__ import annotations

import re

from app.curriculum.topic_coverage import (
    get_topic_coverage_spec,
    keywords_for_subtopic,
)
from app.latex.preamble import TEXTBOOK_MATERIAL_TYPES
from app.models.state import ContentQualityIssue, ContentQualityReport, GenerationRequest


def _count_pattern(text: str, pattern: str) -> int:
    return len(re.findall(pattern, text, flags=re.IGNORECASE | re.MULTILINE))


def _has_any(text_lower: str, keywords: list[str]) -> bool:
    return any(kw.lower() in text_lower for kw in keywords)


def _subtopic_covered(text_lower: str, subtopic: str) -> bool:
    return _has_any(text_lower, keywords_for_subtopic(subtopic))


def _count_exercises(body: str) -> int:
    """
    Count exercises across both shapes we produce.

    Worksheets put one exercise per ``taskbox``. Textbook products use a
    numbered ``oppgaver`` list instead, so the items inside those lists have to
    count too — otherwise a hefte with twenty exercises reads as having none and
    fails its own coverage bar.
    """
    count = _count_pattern(body, r"\\begin\{taskbox\}")
    for block in re.findall(
        r"\\begin\{oppgaver\}.*?\\end\{oppgaver\}", body, flags=re.DOTALL
    ):
        count += len(re.findall(r"\\item\b", block))
    if count == 0:
        count = _count_pattern(body, r"\\textbf\{Oppgave\s+\d+")
    return count


# The production spec makes ten parts mandatory in a hefte, and forbids marking
# exercises by difficulty ("nivådeling skjer uten etiketter"). A hefte that
# silently drops the fasit or the mixed exercises is not the product that was
# ordered, so these are gate failures rather than warnings.
_HEFTE_REQUIRED = (
    ("missing_cover", r"\\MMAheftetittel", "Heftet mangler forside (\\MMAheftetittel)."),
    (
        "missing_learning_goals",
        r"\\begin\{laeringsmaal\}",
        "Heftet mangler «Hva skal du lære?» (laeringsmaal-boks).",
    ),
    (
        "missing_prior_knowledge",
        r"\\begin\{husk\}",
        "Heftet mangler forkunnskaper (husk-boks).",
    ),
    (
        "missing_summary",
        r"\\begin\{oppsummering\}",
        "Heftet mangler oppsummering.",
    ),
)

# "lett/middels/vanskelig" is only a problem as a *label* — in running prose it
# is ordinary Norwegian. Match it inside headings and task titles only.
_LEVEL_LABEL = re.compile(
    r"\\(?:section\*?|subsection\*?)\{[^}]*\b(lett|middels|vanskelig)\w*\b"
    r"|\\begin\{taskbox\}\{[^}]*\b(lett|middels|vanskelig)\w*\b",
    re.IGNORECASE,
)


def _hefte_issues(body: str, request: GenerationRequest) -> list[ContentQualityIssue]:
    """Check the parts the production spec makes mandatory in a hefte."""
    issues: list[ContentQualityIssue] = []

    for code, pattern, message in _HEFTE_REQUIRED:
        if not re.search(pattern, body):
            issues.append(ContentQualityIssue(code=code, message=message))

    if not re.search(r"\\section\*?\{[^}]*blandede", body, re.IGNORECASE):
        issues.append(
            ContentQualityIssue(
                code="missing_mixed_exercises",
                message="Heftet mangler «Blandede oppgaver» der eleven selv velger metode.",
            )
        )

    if request.include_solutions and not re.search(
        r"\\section\*?\{[^}]*fasit", body, re.IGNORECASE
    ):
        issues.append(
            ContentQualityIssue(
                code="missing_fasit",
                message="Heftet mangler fasit.",
            )
        )

    # The layout reserves a 3 cm note column on every page. If the author never
    # writes into it, the hefte is not just missing scaffolding — it looks
    # lopsided, with dead space down the whole outer edge.
    margin_notes = len(
        re.findall(r"\\MMAmarg(?:begrep|tips|triks|note)\b", body)
    )
    if margin_notes < 2:
        issues.append(
            ContentQualityIssue(
                code="unused_margin",
                message=(
                    f"Bare {margin_notes} margnotat(er). Margkolonnen skal brukes "
                    "til ordforklaringer, tips og triks — ellers står den tom."
                ),
            )
        )

    if r"\MMAniva" in body:
        issues.append(
            ContentQualityIssue(
                code="difficulty_label",
                message=(
                    "Heftet bruker \\MMAniva. Nivådeling skal skje uten "
                    "vanskelighetsmerking."
                ),
            )
        )
    elif _LEVEL_LABEL.search(body):
        issues.append(
            ContentQualityIssue(
                code="difficulty_label",
                message=(
                    "Oppgaver eller seksjoner er merket «lett/middels/vanskelig». "
                    "Progresjonen skal ligge i rekkefølgen, ikke i en merkelapp."
                ),
            )
        )

    return issues


def evaluate_content_quality(
    latex_body: str,
    request: GenerationRequest,
) -> ContentQualityReport:
    """
    Evaluate LaTeX body. Strict for material_type=kapittel; lenient otherwise.
    """
    body = latex_body or ""
    semantic_body = re.sub(r"(?m)(?<!\\)%.*$", "", body)
    text_lower = semantic_body.lower()
    spec = get_topic_coverage_spec(
        request.grade,
        request.topic,
        material_type=request.material_type,
        num_exercises=request.num_exercises,
        competency_goals=request.competency_goals,
    )

    issues: list[ContentQualityIssue] = []
    missing_subtopics: list[str] = []

    section_count = _count_pattern(body, r"\\section\*?\{")
    example_count = _count_pattern(body, r"\\begin\{eksempel\}")
    graph_count = _count_pattern(body, r"\\begin\{axis\}") + _count_pattern(
        body, r"\\begin\{tikzpicture\}"
    )
    exercise_count = _count_exercises(body)
    body_chars = len(re.sub(r"\s+", " ", semantic_body).strip())

    report = ContentQualityReport(
        section_count=section_count,
        example_count=example_count,
        graph_count=graph_count,
        exercise_count=exercise_count,
        body_chars=body_chars,
    )

    if request.material_type == "arbeidsark":
        if request.include_exercises and exercise_count < min(3, request.num_exercises):
            issues.append(
                ContentQualityIssue(
                    code="few_exercises",
                    message=f"For få oppgaver i arbeidsarket: {exercise_count}",
                )
            )
        if request.include_theory and not _has_any(
            text_lower, ["\\begin{husk}", "\\begin{regel}", "\\begin{eksempel}"]
        ):
            issues.append(
                ContentQualityIssue(
                    code="missing_theory",
                    message="Arbeidsarket mangler kort teori, regel eller eksempel.",
                )
            )
    elif request.material_type == "prøve":
        if not re.search(r"\\section\*?\{[^}]*del\s*1", body, re.IGNORECASE):
            issues.append(
                ContentQualityIssue(
                    code="missing_exam_part_1",
                    message="Prøven mangler Del 1 uten hjelpemidler.",
                )
            )
        if not re.search(r"\\section\*?\{[^}]*del\s*2", body, re.IGNORECASE):
            issues.append(
                ContentQualityIssue(
                    code="missing_exam_part_2",
                    message="Prøven mangler Del 2 med hjelpemidler.",
                )
            )
        if "poeng" not in text_lower:
            issues.append(
                ContentQualityIssue(
                    code="missing_points",
                    message="Prøven mangler poengangivelse eller poengskjema.",
                )
            )
    elif request.material_type == "hefte":
        issues.extend(_hefte_issues(body, request))
    elif request.material_type == "differensiert":
        for level in ("grunnleggende", "standard", "avansert"):
            if not re.search(
                rf"\\section\*?\{{[^}}]*{level}", body, re.IGNORECASE
            ):
                issues.append(
                    ContentQualityIssue(
                        code=f"missing_level_{level}",
                        message=f"Mangler nivået {level.title()}.",
                    )
                )

    if request.material_type not in TEXTBOOK_MATERIAL_TYPES:
        report.issues = issues
        report.score = max(0, 100 - 25 * len(issues))
        report.passed = not issues
        return report

    # --- Off-topic guards ---
    for pattern in spec.forbidden_section_patterns:
        if re.search(pattern, body):
            issues.append(
                ContentQualityIssue(
                    code="off_topic_section",
                    message=f"Urelatert seksjon funnet (mønster: {pattern})",
                )
            )

    for kw in spec.forbidden_body_keywords:
        hits = text_lower.count(kw.lower())
        if hits >= 2:
            issues.append(
                ContentQualityIssue(
                    code="off_topic_content",
                    message=f"Urelatert innhold «{kw}» forekommer {hits} ganger",
                )
            )

    # --- Subtopic coverage ---
    for sub in spec.required_subtopics:
        if not _subtopic_covered(text_lower, sub):
            missing_subtopics.append(sub)
            issues.append(
                ContentQualityIssue(
                    code="missing_subtopic",
                    message=f"Mangler deltema: {sub}",
                )
            )
    report.missing_subtopics = missing_subtopics

    # --- Structure minimums ---
    if section_count < spec.min_theory_sections:
        issues.append(
            ContentQualityIssue(
                code="few_sections",
                message=(
                    f"For få seksjoner: {section_count} " f"(krav: {spec.min_theory_sections}+)"
                ),
            )
        )

    if request.include_examples and example_count < spec.min_examples:
        issues.append(
            ContentQualityIssue(
                code="few_examples",
                message=(f"For få eksempler: {example_count} " f"(krav: {spec.min_examples}+)"),
            )
        )

    if request.include_graphs and graph_count < spec.min_graphs:
        issues.append(
            ContentQualityIssue(
                code="few_graphs",
                message=(f"For få grafer: {graph_count} (krav: {spec.min_graphs}+)"),
            )
        )

    if body_chars < spec.min_body_chars:
        issues.append(
            ContentQualityIssue(
                code="thin_content",
                message=(f"For kort innhold: {body_chars} tegn " f"(krav: {spec.min_body_chars}+)"),
            )
        )

    if not re.search(r"\\begin\{laeringsmaal\}", body):
        issues.append(
            ContentQualityIssue(
                code="missing_laeringsmaal",
                message="Mangler \\begin{laeringsmaal}",
            )
        )

    if not re.search(r"\\begin\{oppsummering\}", body):
        issues.append(
            ContentQualityIssue(
                code="missing_oppsummering",
                message="Mangler \\begin{oppsummering}",
            )
        )

    if _count_pattern(body, r"\\begin\{utforsk\}") < 1:
        issues.append(
            ContentQualityIssue(
                code="missing_utforsk",
                message="Mangler \\begin{utforsk} (LK20: utforske)",
            )
        )

    if _count_pattern(body, r"\\begin\{vanligfeil\}") < 2:
        issues.append(
            ContentQualityIssue(
                code="few_vanligfeil",
                message="Minst 2 \\begin{vanligfeil} kreves",
            )
        )

    if _count_pattern(body, r"\\begin\{definisjon\}") < 3:
        issues.append(
            ContentQualityIssue(
                code="few_definisjoner",
                message="Minst 3 \\begin{definisjon} kreves",
            )
        )

    # Representations: table, graph, formula
    has_table = "tabell" in text_lower or "\\begin{tabular}" in body
    has_graph = graph_count > 0 or "graf" in text_lower
    has_formula = "formel" in text_lower or "f(x)" in text_lower
    if not (has_table and has_graph and has_formula):
        issues.append(
            ContentQualityIssue(
                code="missing_representations",
                message=(
                    "Mangler kobling mellom representasjoner "
                    f"(tabell={has_table}, graf={has_graph}, formel={has_formula})"
                ),
            )
        )

    # Analyze / discuss
    if not _has_any(text_lower, ["analys", "drøft", "egenskap", "tolke"]):
        issues.append(
            ContentQualityIssue(
                code="missing_analysis",
                message="Mangler analyse/drøfting av funksjonsegenskaper",
            )
        )

    if request.include_exercises and exercise_count < spec.min_exercises:
        issues.append(
            ContentQualityIssue(
                code="few_exercises",
                message=(f"For få oppgaver: {exercise_count} " f"(krav: {spec.min_exercises})"),
            )
        )

    if not re.search(r"\\section\*?\{[^}]*[Oo]ppgav", body):
        issues.append(
            ContentQualityIssue(
                code="missing_exercise_section",
                message="Mangler \\section{Oppgaver} til slutt",
            )
        )

    # --- Score ---
    critical_codes = {"missing_subtopic", "off_topic_section", "off_topic_content"}
    critical_issues = [i for i in issues if i.code in critical_codes]
    error_count = sum(1 for i in issues if i.severity == "error")
    max_checks = max(
        12,
        len(spec.required_subtopics) + 10,
    )
    penalty = min(100, error_count * (100 // max_checks))
    report.score = max(0, 100 - penalty)
    report.issues = issues
    # Pass when pensum is covered and score is good — minor style gaps are OK.
    report.passed = len(critical_issues) == 0 and report.score >= 75
    report.semantic_score = 100
    return report


def format_quality_report_for_author(report: ContentQualityReport) -> str:
    """Format issues as instructions for an author retry."""
    if report.passed:
        return "Ingen kvalitetsproblemer."

    lines = [
        "KVALITETSGATE — følgende MÅ rettes før dokumentet godkjennes:",
        f"Score: {report.score}/100",
        "",
    ]
    for issue in report.issues:
        lines.append(f"- [{issue.code}] {issue.message}")

    if report.missing_subtopics:
        lines.append("")
        lines.append(
            "MANGLENDE DELTEMAER (lag egen \\section med teori + 2 eksempler + graf for hver):"
        )
        for sub in report.missing_subtopics:
            lines.append(f"  • {sub}")

    lines.extend(
        [
            "",
            "UTVID dokumentet — ikke bare legg til én setning. Skriv full teori,",
            "flere \\begin{eksempel} med \\forklaring{}, og fjern alt urelatert innhold.",
        ]
    )
    return "\n".join(lines)
