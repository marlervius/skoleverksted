"""
Difficulty Analyzer for MateMaTeX.
Analyzes generated content and visualizes difficulty distribution.
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ExerciseAnalysis:
    """Analysis result for a single exercise."""
    number: int
    title: str
    difficulty: str  # "lett", "middels", "vanskelig"
    difficulty_score: float  # 0.0 - 1.0
    factors: list[str]  # Reasons for the difficulty rating
    word_count: int
    has_subparts: bool
    num_subparts: int
    concepts: list[str]


@dataclass
class ContentAnalysis:
    """Analysis result for entire content."""
    total_exercises: int
    easy_count: int
    medium_count: int
    hard_count: int
    average_difficulty: float
    exercises: list[ExerciseAnalysis]
    concepts_covered: list[str]
    estimated_time_minutes: int
    recommendations: list[str]


# Difficulty indicators
EASY_INDICATORS = [
    r'\b\d{1,2}\b',  # Small numbers (1-99)
    r'enkel',
    r'grunnleggende',
    r'direkte',
    r'beregn\b',
    r'finn\b',
    r'hva er',
]

MEDIUM_INDICATORS = [
    r'\b\d{3,4}\b',  # Larger numbers (100-9999)
    r'uttrykk',
    r'likning',
    r'formel',
    r'sammenheng',
    r'begrunn',
    r'forklar',
    r'\\frac\{',  # Fractions
    r'prosent',
]

HARD_INDICATORS = [
    r'\b\d{5,}\b',  # Very large numbers
    r'bevis',
    r'utled',
    r'generali',
    r'optimer',
    r'derivert',
    r'integral',
    r'\\sum',
    r'\\int',
    r'\\lim',
    r'kompleks',
    r'abstrakt',
    r'vis at',
    r'begrunn hvorfor',
]

# Concept patterns
CONCEPT_PATTERNS = {
    "addisjon": [r'pluss', r'\+', r'sum', r'legge sammen'],
    "subtraksjon": [r'minus', r'\-', r'differanse', r'trekke fra'],
    "multiplikasjon": [r'gange', r'\\cdot', r'\\times', r'produkt'],
    "divisjon": [r'dele', r'\\div', r'kvotient', r'\\frac'],
    "brøk": [r'brøk', r'\\frac', r'nevner', r'teller'],
    "prosent": [r'prosent', r'\\%', r'vekstfaktor'],
    "likning": [r'likning', r'løs', r'x\s*='],
    "funksjon": [r'funksjon', r'f\(x\)', r'graf'],
    "geometri": [r'areal', r'omkrets', r'volum', r'vinkel'],
    "trigonometri": [r'sin', r'cos', r'tan', r'vinkel'],
    "derivasjon": [r'derivert', r"f'", r'stigningstall'],
    "integrasjon": [r'integral', r'\\int', r'areal under'],
    "sannsynlighet": [r'sannsynlighet', r'P\(', r'utfall'],
    "statistikk": [r'gjennomsnitt', r'median', r'standardavvik'],
}


def analyze_exercise(content: str, number: int = 1, title: str = "") -> ExerciseAnalysis:
    """
    Analyze a single exercise.
    
    Args:
        content: LaTeX content of the exercise.
        number: Exercise number.
        title: Exercise title.
    
    Returns:
        ExerciseAnalysis object.
    """
    content_lower = content.lower()
    
    # Calculate difficulty score
    easy_score = 0
    medium_score = 0
    hard_score = 0
    factors = []
    
    # Check easy indicators
    for pattern in EASY_INDICATORS:
        if re.search(pattern, content_lower):
            easy_score += 1
    
    # Check medium indicators
    for pattern in MEDIUM_INDICATORS:
        if re.search(pattern, content_lower):
            medium_score += 1
    
    # Check hard indicators
    for pattern in HARD_INDICATORS:
        if re.search(pattern, content_lower):
            hard_score += 1
    
    # Check for subparts
    subparts = re.findall(r'\\item', content)
    num_subparts = len(subparts)
    has_subparts = num_subparts > 0
    
    if num_subparts > 3:
        hard_score += 1
        factors.append(f"{num_subparts} deloppgaver")
    elif num_subparts > 1:
        medium_score += 1
    
    # Check for nested fractions or complex expressions
    nested_fracs = len(re.findall(r'\\frac\{[^}]*\\frac', content))
    if nested_fracs > 0:
        hard_score += 1
        factors.append("Nestede brøker")
    
    # Check for multiple unknowns
    unknowns = set(re.findall(r'\b([a-z])\s*=', content_lower))
    if len(unknowns) > 1:
        hard_score += 1
        factors.append(f"{len(unknowns)} ukjente")
    
    # Word count
    clean_text = re.sub(r'\\[a-zA-Z]+\{[^}]*\}', '', content)
    words = clean_text.split()
    word_count = len(words)
    
    if word_count > 100:
        medium_score += 1
        factors.append("Lang oppgavetekst")
    
    # Identify concepts
    concepts = []
    for concept, patterns in CONCEPT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, content_lower):
                concepts.append(concept)
                break
    
    if len(concepts) > 2:
        hard_score += 1
        factors.append("Kombinerer flere konsepter")
    
    # Calculate final difficulty
    total = easy_score + medium_score + hard_score
    if total == 0:
        difficulty_score = 0.5
    else:
        difficulty_score = (medium_score * 0.5 + hard_score * 1.0) / max(total, 1)
    
    # Determine difficulty level
    if difficulty_score < 0.3:
        difficulty = "lett"
        if not factors:
            factors.append("Direkte oppgave")
    elif difficulty_score < 0.6:
        difficulty = "middels"
        if not factors:
            factors.append("Krever flere steg")
    else:
        difficulty = "vanskelig"
        if not factors:
            factors.append("Kompleks oppgave")
    
    return ExerciseAnalysis(
        number=number,
        title=title or f"Oppgave {number}",
        difficulty=difficulty,
        difficulty_score=difficulty_score,
        factors=factors[:3],  # Top 3 factors
        word_count=word_count,
        has_subparts=has_subparts,
        num_subparts=num_subparts,
        concepts=list(set(concepts)),
    )


def analyze_content(latex_content: str) -> ContentAnalysis:
    """
    Analyze entire LaTeX content.
    
    Args:
        latex_content: The LaTeX source code.
    
    Returns:
        ContentAnalysis object.
    """
    # Find all exercises
    exercise_pattern = r'\\begin\{taskbox\}\{([^}]+)\}(.*?)\\end\{taskbox\}'
    matches = list(re.finditer(exercise_pattern, latex_content, re.DOTALL))
    
    exercises = []
    all_concepts = set()
    
    for i, match in enumerate(matches):
        title = match.group(1)
        content = match.group(2)
        
        analysis = analyze_exercise(content, i + 1, title)
        exercises.append(analysis)
        all_concepts.update(analysis.concepts)
    
    # Calculate statistics
    easy_count = sum(1 for e in exercises if e.difficulty == "lett")
    medium_count = sum(1 for e in exercises if e.difficulty == "middels")
    hard_count = sum(1 for e in exercises if e.difficulty == "vanskelig")
    
    if exercises:
        avg_difficulty = sum(e.difficulty_score for e in exercises) / len(exercises)
    else:
        avg_difficulty = 0.5
    
    # Estimate time
    base_time = len(exercises) * 5  # 5 min per exercise average
    if avg_difficulty > 0.6:
        base_time = int(base_time * 1.3)
    elif avg_difficulty < 0.3:
        base_time = int(base_time * 0.8)
    
    # Generate recommendations
    recommendations = []
    
    if hard_count == 0 and len(exercises) > 5:
        recommendations.append("Legg til noen utfordrende oppgaver for differensiering")
    
    if easy_count == 0 and len(exercises) > 5:
        recommendations.append("Legg til enklere oppgaver for å bygge mestring")
    
    if len(all_concepts) < 2 and len(exercises) > 5:
        recommendations.append("Vurder å inkludere flere matematiske konsepter")
    
    balance = abs(easy_count - hard_count)
    if balance > 3 and len(exercises) > 5:
        if easy_count > hard_count:
            recommendations.append("Balansen heller mot enkle oppgaver")
        else:
            recommendations.append("Balansen heller mot vanskelige oppgaver")
    
    return ContentAnalysis(
        total_exercises=len(exercises),
        easy_count=easy_count,
        medium_count=medium_count,
        hard_count=hard_count,
        average_difficulty=avg_difficulty,
        exercises=exercises,
        concepts_covered=sorted(list(all_concepts)),
        estimated_time_minutes=base_time,
        recommendations=recommendations,
    )


def get_difficulty_distribution_chart_data(analysis: ContentAnalysis) -> dict:
    """
    Get data for a difficulty distribution chart.
    
    Args:
        analysis: ContentAnalysis object.
    
    Returns:
        Chart data dictionary.
    """
    return {
        "labels": ["Lett", "Middels", "Vanskelig"],
        "values": [analysis.easy_count, analysis.medium_count, analysis.hard_count],
        "colors": ["#10b981", "#f59e0b", "#f43f5e"],  # Green, Amber, Rose
        "percentages": [
            round(analysis.easy_count / max(analysis.total_exercises, 1) * 100, 1),
            round(analysis.medium_count / max(analysis.total_exercises, 1) * 100, 1),
            round(analysis.hard_count / max(analysis.total_exercises, 1) * 100, 1),
        ],
    }


def get_difficulty_emoji(difficulty: str) -> str:
    """Get emoji for difficulty level."""
    return {"lett": "🟢", "middels": "🟡", "vanskelig": "🔴"}.get(difficulty, "⚪")


def format_analysis_summary(analysis: ContentAnalysis) -> str:
    """
    Format analysis as a readable summary.
    
    Args:
        analysis: ContentAnalysis object.
    
    Returns:
        Formatted string summary.
    """
    lines = [
        f"📊 **Analyse av {analysis.total_exercises} oppgaver**",
        "",
        f"🟢 Lett: {analysis.easy_count} ({round(analysis.easy_count/max(analysis.total_exercises,1)*100)}%)",
        f"🟡 Middels: {analysis.medium_count} ({round(analysis.medium_count/max(analysis.total_exercises,1)*100)}%)",
        f"🔴 Vanskelig: {analysis.hard_count} ({round(analysis.hard_count/max(analysis.total_exercises,1)*100)}%)",
        "",
        f"⏱️ Estimert tid: ~{analysis.estimated_time_minutes} minutter",
        f"📚 Konsepter: {', '.join(analysis.concepts_covered) if analysis.concepts_covered else 'Ikke identifisert'}",
    ]
    
    if analysis.recommendations:
        lines.append("")
        lines.append("💡 **Anbefalinger:**")
        for rec in analysis.recommendations:
            lines.append(f"  • {rec}")
    
    return "\n".join(lines)
