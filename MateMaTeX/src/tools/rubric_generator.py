"""
Assessment Rubric Generator for MateMaTeX.
Generates grading criteria and rubrics for math worksheets.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class RubricCriterion:
    """A single criterion in a rubric."""
    name: str
    description: str
    levels: dict[str, str]  # e.g., {"6": "Excellent", "5": "Good", ...}
    weight: float  # Percentage weight (0.0 - 1.0)


@dataclass
class Rubric:
    """Complete assessment rubric."""
    title: str
    grade_level: str
    topic: str
    criteria: list[RubricCriterion]
    max_points: int
    passing_threshold: float  # e.g., 0.4 for 40%


# Standard criteria templates
MATH_CRITERIA = {
    "understanding": RubricCriterion(
        name="Matematisk forståelse",
        description="Viser forståelse for matematiske begreper og sammenhenger",
        levels={
            "6": "Viser dyp forståelse og kan forklare sammenhenger selvstendig",
            "5": "Viser god forståelse og kan anvende begreper korrekt",
            "4": "Viser grunnleggende forståelse med noen unøyaktigheter",
            "3": "Viser delvis forståelse, men med flere misforståelser",
            "2": "Viser begrenset forståelse av grunnleggende begreper",
            "1": "Viser svært begrenset eller ingen forståelse",
        },
        weight=0.30
    ),
    "problem_solving": RubricCriterion(
        name="Problemløsning",
        description="Evne til å velge og anvende egnede strategier",
        levels={
            "6": "Velger optimale strategier og løser komplekse problemer elegant",
            "5": "Velger gode strategier og løser de fleste problemer effektivt",
            "4": "Velger passende strategier, men kan trenge veiledning",
            "3": "Trenger hjelp til å velge strategier, klarer enklere problemer",
            "2": "Sliter med å velge strategier, klarer kun enkle oppgaver med hjelp",
            "1": "Kan ikke velge eller anvende strategier selvstendig",
        },
        weight=0.25
    ),
    "calculation": RubricCriterion(
        name="Regning og nøyaktighet",
        description="Utfører beregninger korrekt og nøyaktig",
        levels={
            "6": "Alle beregninger er korrekte, viser god tallforståelse",
            "5": "Nesten alle beregninger korrekte, små regnefeil",
            "4": "De fleste beregninger korrekte, noen systematiske feil",
            "3": "Flere regnefeil, men viser forståelse for metoden",
            "2": "Mange regnefeil, begrenset tallforståelse",
            "1": "Svært mange feil, mangler grunnleggende regneferdigheter",
        },
        weight=0.25
    ),
    "communication": RubricCriterion(
        name="Matematisk kommunikasjon",
        description="Forklarer løsninger og bruker matematisk språk",
        levels={
            "6": "Forklarer tydelig med presist matematisk språk og notasjon",
            "5": "Forklarer godt med korrekt matematisk språk",
            "4": "Forklarer forståelig, men noe upresist språk",
            "3": "Forklaringer er uklare, begrenset bruk av fagtermer",
            "2": "Mangelfulle forklaringer, lite matematisk språk",
            "1": "Ingen eller uforståelige forklaringer",
        },
        weight=0.20
    ),
}

# Additional criteria for specific topics
GEOMETRY_CRITERIA = {
    "visualization": RubricCriterion(
        name="Romforståelse og visualisering",
        description="Evne til å forestille seg og tegne geometriske figurer",
        levels={
            "6": "Utmerket romforståelse, presise tegninger og konstruksjoner",
            "5": "God romforståelse, nøyaktige tegninger",
            "4": "Grunnleggende romforståelse, akseptable tegninger",
            "3": "Begrenset romforståelse, upresise tegninger",
            "2": "Svak romforståelse, mangelfulle tegninger",
            "1": "Mangler romforståelse",
        },
        weight=0.15
    ),
}

ALGEBRA_CRITERIA = {
    "symbolic": RubricCriterion(
        name="Symbolbehandling",
        description="Evne til å arbeide med variabler og uttrykk",
        levels={
            "6": "Behersker symbolmanipulasjon elegant og effektivt",
            "5": "God symbolbehandling med få feil",
            "4": "Grunnleggende symbolbehandling, noen feil",
            "3": "Begrenset symbolbehandling, trenger støtte",
            "2": "Sliter med variabler og uttrykk",
            "1": "Kan ikke arbeide med symboler",
        },
        weight=0.15
    ),
}


def generate_rubric(
    topic: str,
    grade_level: str,
    num_exercises: int = 10,
    include_geometry: bool = False,
    include_algebra: bool = False,
    custom_criteria: Optional[list[RubricCriterion]] = None
) -> Rubric:
    """
    Generate an assessment rubric for a math worksheet.
    
    Args:
        topic: The math topic.
        grade_level: Grade level (e.g., "8. trinn").
        num_exercises: Number of exercises in the worksheet.
        include_geometry: Include geometry-specific criteria.
        include_algebra: Include algebra-specific criteria.
        custom_criteria: Additional custom criteria.
    
    Returns:
        A complete Rubric object.
    """
    criteria = list(MATH_CRITERIA.values())
    
    # Ensure topic is a string (can be None from session state)
    topic = topic or ""
    
    # Add topic-specific criteria
    if include_geometry or "geometri" in topic.lower():
        criteria.append(GEOMETRY_CRITERIA["visualization"])
    
    if include_algebra or any(term in topic.lower() for term in ["algebra", "likning", "funksjon"]):
        criteria.append(ALGEBRA_CRITERIA["symbolic"])
    
    # Add custom criteria
    if custom_criteria:
        criteria.extend(custom_criteria)
    
    # Normalize weights
    total_weight = sum(c.weight for c in criteria)
    for c in criteria:
        c.weight = c.weight / total_weight
    
    # Calculate max points based on exercises
    max_points = num_exercises * 6  # 6 points per exercise max
    
    return Rubric(
        title=f"Vurderingskriterier: {topic}",
        grade_level=grade_level,
        topic=topic,
        criteria=criteria,
        max_points=max_points,
        passing_threshold=0.4
    )


def rubric_to_latex(rubric: Rubric) -> str:
    """
    Convert a rubric to LaTeX format.
    
    Args:
        rubric: The Rubric object.
    
    Returns:
        LaTeX code for the rubric.
    """
    latex = [
        r"\section*{" + rubric.title + "}",
        r"\textbf{Klassetrinn:} " + rubric.grade_level + r" \\",
        r"\textbf{Maksimal poengsum:} " + str(rubric.max_points) + r" poeng \\",
        r"\textbf{Bestått:} " + str(int(rubric.passing_threshold * 100)) + r"\% \\[1em]",
        "",
    ]
    
    for criterion in rubric.criteria:
        weight_pct = int(criterion.weight * 100)
        latex.append(r"\subsection*{" + criterion.name + f" ({weight_pct}\\%)" + "}")
        latex.append(r"\textit{" + criterion.description + r"} \\[0.5em]")
        latex.append(r"\begin{tabular}{|c|p{12cm}|}")
        latex.append(r"\hline")
        latex.append(r"\textbf{Karakter} & \textbf{Beskrivelse} \\ \hline")
        
        for grade in ["6", "5", "4", "3", "2", "1"]:
            if grade in criterion.levels:
                latex.append(f"{grade} & {criterion.levels[grade]} \\\\ \\hline")
        
        latex.append(r"\end{tabular}")
        latex.append(r"\\[1em]")
    
    return "\n".join(latex)


def rubric_to_markdown(rubric: Rubric) -> str:
    """
    Convert a rubric to Markdown format.
    
    Args:
        rubric: The Rubric object.
    
    Returns:
        Markdown text for the rubric.
    """
    md = [
        f"# {rubric.title}",
        "",
        f"**Klassetrinn:** {rubric.grade_level}",
        f"**Maksimal poengsum:** {rubric.max_points} poeng",
        f"**Bestått:** {int(rubric.passing_threshold * 100)}%",
        "",
    ]
    
    for criterion in rubric.criteria:
        weight_pct = int(criterion.weight * 100)
        md.append(f"## {criterion.name} ({weight_pct}%)")
        md.append(f"*{criterion.description}*")
        md.append("")
        md.append("| Karakter | Beskrivelse |")
        md.append("|----------|-------------|")
        
        for grade in ["6", "5", "4", "3", "2", "1"]:
            if grade in criterion.levels:
                md.append(f"| {grade} | {criterion.levels[grade]} |")
        
        md.append("")
    
    return "\n".join(md)


def get_grade_from_score(rubric: Rubric, score: int) -> str:
    """
    Calculate grade from score.
    
    Args:
        rubric: The Rubric object.
        score: Achieved score.
    
    Returns:
        Grade as string (1-6).
    """
    percentage = score / rubric.max_points
    
    if percentage >= 0.90:
        return "6"
    elif percentage >= 0.77:
        return "5"
    elif percentage >= 0.60:
        return "4"
    elif percentage >= 0.45:
        return "3"
    elif percentage >= 0.30:
        return "2"
    else:
        return "1"


def generate_quick_rubric(topic: str, grade_level: str) -> str:
    """
    Generate a quick rubric summary for display.
    
    Args:
        topic: The math topic.
        grade_level: Grade level.
    
    Returns:
        Formatted string summary.
    """
    rubric = generate_rubric(topic, grade_level)
    
    lines = [
        f"📋 **{rubric.title}**",
        "",
        f"📊 Maks poeng: {rubric.max_points} | Bestått: {int(rubric.passing_threshold * 100)}%",
        "",
        "**Vurderingskriterier:**",
    ]
    
    for c in rubric.criteria:
        weight_pct = int(c.weight * 100)
        lines.append(f"- {c.name} ({weight_pct}%)")
    
    lines.append("")
    lines.append("**Karaktergrenser:**")
    lines.append("6: 90%+ | 5: 77-89% | 4: 60-76% | 3: 45-59% | 2: 30-44% | 1: <30%")
    
    return "\n".join(lines)
