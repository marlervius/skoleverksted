"""
Rule-based content quality gate for kapittel (and light checks for other types).

Scores pedagogical completeness: curriculum coverage, examples, graphs,
explore/analyze/draw (LK20), and off-topic guards.
"""

from __future__ import annotations

import re

from app.curriculum.topic_coverage import (
    get_topic_coverage_spec,
    keywords_for_subtopic,
)
from app.models.state import ContentQualityIssue, ContentQualityReport, GenerationRequest


def _count_pattern(text: str, pattern: str) -> int:
    return len(re.findall(pattern, text, flags=re.IGNORECASE | re.MULTILINE))


def _has_any(text_lower: str, keywords: list[str]) -> bool:
    return any(kw.lower() in text_lower for kw in keywords)


def _subtopic_covered(text_lower: str, subtopic: str) -> bool:
    return _has_any(text_lower, keywords_for_subtopic(subtopic))


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
    exercise_count = _count_pattern(body, r"\\begin\{taskbox\}")
    if exercise_count == 0:
        exercise_count = _count_pattern(body, r"\\textbf\{Oppgave\s+\d+")
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

    if request.material_type != "kapittel":
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
