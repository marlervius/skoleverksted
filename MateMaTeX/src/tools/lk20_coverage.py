"""
LK20 Competency Coverage Report for MateMaTeX.
Analyzes content and shows which curriculum goals are covered.
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class CompetencyGoal:
    """Represents a competency goal from LK20."""
    id: str
    text: str
    grade_range: str  # e.g., "8-10", "VG1"
    category: str  # e.g., "Tall og algebra", "Geometri"
    keywords: list[str]


@dataclass
class CoverageResult:
    """Result of coverage analysis."""
    goal: CompetencyGoal
    covered: bool
    confidence: float  # 0.0 - 1.0
    evidence: list[str]  # Snippets showing coverage


@dataclass
class CoverageReport:
    """Complete coverage report."""
    grade_level: str
    topic: str
    covered_goals: list[CoverageResult]
    uncovered_goals: list[CompetencyGoal]
    coverage_percentage: float
    recommendations: list[str]


# LK20 Competency Goals Database
LK20_GOALS = {
    "1-4": [
        CompetencyGoal("M1-4-1", "Utforske og beskrive strukturer og mønster i lek og spill", "1-4", "Tall og algebra", 
                      ["mønster", "struktur", "lek", "spill", "rekke", "følge"]),
        CompetencyGoal("M1-4-2", "Bruke tallinja til beregninger og for å vise tallstørrelser", "1-4", "Tall og algebra",
                      ["tallinje", "beregning", "tallstørrelse", "plassere"]),
        CompetencyGoal("M1-4-3", "Utvikle, bruke og samtale om varierte regnestrategier", "1-4", "Tall og algebra",
                      ["regnestrategi", "addisjon", "subtraksjon", "multiplikasjon", "divisjon"]),
        CompetencyGoal("M1-4-4", "Eksperimentere med telling, dele opp og sette sammen mengder", "1-4", "Tall og algebra",
                      ["telling", "mengde", "dele", "sette sammen", "antall"]),
        CompetencyGoal("M1-4-5", "Kjenne igjen og beskrive kjennetegn ved enkle to- og tredimensjonale figurer", "1-4", "Geometri",
                      ["figur", "trekant", "firkant", "sirkel", "kube", "kule"]),
        CompetencyGoal("M1-4-6", "Lage og følge regler og trinnvise instruksjoner i lek og spill", "1-4", "Algoritmer",
                      ["instruksjon", "regel", "trinnvis", "algoritme", "programmering"]),
    ],
    "5-7": [
        CompetencyGoal("M5-7-1", "Representere og bruke brøk, desimaltall og prosent på ulike måter", "5-7", "Tall og algebra",
                      ["brøk", "desimaltall", "prosent", "representere", "omgjøre"]),
        CompetencyGoal("M5-7-2", "Utvikle og bruke ulike strategier for regning med brøk og desimaltall", "5-7", "Tall og algebra",
                      ["brøk", "desimaltall", "strategi", "regne", "beregne"]),
        CompetencyGoal("M5-7-3", "Utforske og beskrive primtall, faktorer og faktorisering", "5-7", "Tall og algebra",
                      ["primtall", "faktor", "faktorisering", "delelig", "delbarhet"]),
        CompetencyGoal("M5-7-4", "Bruke variabler og formler til å uttrykke sammenhenger", "5-7", "Tall og algebra",
                      ["variabel", "formel", "uttrykk", "sammenheng", "algebra"]),
        CompetencyGoal("M5-7-5", "Utforske og argumentere for hvordan areal og omkrets endres", "5-7", "Geometri",
                      ["areal", "omkrets", "endre", "sammenligne", "figur"]),
        CompetencyGoal("M5-7-6", "Utforske og bruke koordinatsystemet til å beskrive posisjoner", "5-7", "Geometri",
                      ["koordinat", "koordinatsystem", "posisjon", "x-akse", "y-akse"]),
    ],
    "8-10": [
        CompetencyGoal("M8-10-1", "Utforske og generalisere mønster", "8-10", "Tall og algebra",
                      ["mønster", "generalisere", "formel", "rekke", "følge"]),
        CompetencyGoal("M8-10-2", "Utforske, forstå og bruke formler for volum av ulike prismer og sylindere", "8-10", "Geometri",
                      ["volum", "prisme", "sylinder", "formel", "beregne"]),
        CompetencyGoal("M8-10-3", "Bruke Pytagoras' setning og trigonometri", "8-10", "Geometri",
                      ["pytagoras", "trigonometri", "sinus", "cosinus", "tangens", "hypotenus"]),
        CompetencyGoal("M8-10-4", "Løse likninger og ulikheter av første grad", "8-10", "Tall og algebra",
                      ["likning", "ulikhet", "løse", "første grad", "variabel"]),
        CompetencyGoal("M8-10-5", "Utforske og beskrive funksjoner", "8-10", "Funksjoner",
                      ["funksjon", "graf", "stigningstall", "lineær", "f(x)"]),
        CompetencyGoal("M8-10-6", "Bruke tall og regning til å undersøke problemstillinger", "8-10", "Tall og algebra",
                      ["problemløsning", "undersøke", "beregne", "anvendelse"]),
        CompetencyGoal("M8-10-7", "Utforske og bruke formler for areal og omkrets", "8-10", "Geometri",
                      ["areal", "omkrets", "sirkel", "trekant", "firkant"]),
        CompetencyGoal("M8-10-8", "Planlegge og gjennomføre undersøkelser og presentere resultatene", "8-10", "Statistikk",
                      ["undersøkelse", "statistikk", "diagram", "presentere", "data"]),
        CompetencyGoal("M8-10-9", "Beregne og vurdere sannsynlighet i statistikk og spill", "8-10", "Sannsynlighet",
                      ["sannsynlighet", "utfall", "hendelse", "beregne", "vurdere"]),
        CompetencyGoal("M8-10-10", "Bruke og forstå prosent, vekstfaktor og rentesrenteformel", "8-10", "Økonomi",
                      ["prosent", "vekstfaktor", "rente", "økonomi", "sparing", "lån"]),
    ],
    "VG1": [
        CompetencyGoal("VG1-1", "Utforske og beskrive egenskaper ved polynomfunksjoner", "VG1", "Funksjoner",
                      ["polynom", "funksjon", "nullpunkt", "ekstremalpunkt", "graf"]),
        CompetencyGoal("VG1-2", "Modellere situasjoner med eksponentielle og logaritmiske funksjoner", "VG1", "Funksjoner",
                      ["eksponentiell", "logaritme", "modell", "vekst", "halveringstid"]),
        CompetencyGoal("VG1-3", "Bruke sinussetningen og cosinussetningen", "VG1", "Geometri",
                      ["sinussetningen", "cosinussetningen", "trekant", "vinkel", "side"]),
        CompetencyGoal("VG1-4", "Utforske rekursive sammenhenger og bruke formler for aritmetiske og geometriske rekker", "VG1", "Tall og algebra",
                      ["rekursiv", "aritmetisk", "geometrisk", "rekke", "sum", "følge"]),
        CompetencyGoal("VG1-5", "Forenkle og regne med potenser og logaritmer", "VG1", "Tall og algebra",
                      ["potens", "logaritme", "forenkle", "regel", "beregne"]),
    ],
    "VG2": [
        CompetencyGoal("VG2-1", "Utlede og bruke regler for derivasjon", "VG2", "Derivasjon",
                      ["derivasjon", "derivere", "regel", "grenseverdi", "momentan"]),
        CompetencyGoal("VG2-2", "Analysere og tolke funksjoner ved hjelp av derivasjon", "VG2", "Derivasjon",
                      ["derivert", "monotoni", "ekstremalpunkt", "vendepunkt", "analyse"]),
        CompetencyGoal("VG2-3", "Løse praktiske optimaliseringsproblemer", "VG2", "Derivasjon",
                      ["optimalisering", "maksimere", "minimere", "praktisk", "problem"]),
        CompetencyGoal("VG2-4", "Beregne sannsynligheter ved hjelp av fordelinger", "VG2", "Sannsynlighet",
                      ["fordeling", "binomisk", "normalfordeling", "sannsynlighet"]),
    ],
}


def get_goals_for_grade(grade_level: str) -> list[CompetencyGoal]:
    """
    Get competency goals for a specific grade level.
    
    Args:
        grade_level: Grade level string (e.g., "8. trinn", "VG1").
    
    Returns:
        List of CompetencyGoal objects.
    """
    grade_lower = grade_level.lower()
    
    if any(x in grade_lower for x in ["1.", "2.", "3.", "4."]) and "10" not in grade_lower:
        return LK20_GOALS.get("1-4", [])
    elif any(x in grade_lower for x in ["5.", "6.", "7."]):
        return LK20_GOALS.get("5-7", [])
    elif any(x in grade_lower for x in ["8.", "9.", "10."]):
        return LK20_GOALS.get("8-10", [])
    elif "vg1" in grade_lower or "1t" in grade_lower or "1p" in grade_lower:
        return LK20_GOALS.get("VG1", [])
    elif "vg2" in grade_lower or "2p" in grade_lower or "r1" in grade_lower:
        return LK20_GOALS.get("VG2", [])
    else:
        return LK20_GOALS.get("8-10", [])  # Default


def analyze_coverage(latex_content: str, grade_level: str, topic: str = "") -> CoverageReport:
    """
    Analyze LaTeX content for LK20 competency goal coverage.
    
    Args:
        latex_content: The LaTeX source code.
        grade_level: Grade level string.
        topic: Optional topic name for additional context.
    
    Returns:
        CoverageReport object.
    """
    content_lower = latex_content.lower()
    goals = get_goals_for_grade(grade_level)
    
    covered = []
    uncovered = []
    
    for goal in goals:
        # Check for keyword matches
        matches = []
        confidence = 0.0
        
        for keyword in goal.keywords:
            if keyword.lower() in content_lower:
                matches.append(keyword)
                confidence += 1.0 / len(goal.keywords)
        
        # Check topic match
        if topic and any(kw in topic.lower() for kw in goal.keywords):
            confidence += 0.3
        
        # Cap confidence at 1.0
        confidence = min(confidence, 1.0)
        
        # Find evidence snippets
        evidence = []
        for keyword in matches[:3]:  # Max 3 evidence snippets
            # Find context around keyword
            pattern = rf'.{{0,50}}{re.escape(keyword)}.{{0,50}}'
            match = re.search(pattern, content_lower, re.IGNORECASE)
            if match:
                evidence.append(f"...{match.group(0)}...")
        
        result = CoverageResult(
            goal=goal,
            covered=confidence > 0.3,
            confidence=confidence,
            evidence=evidence
        )
        
        if result.covered:
            covered.append(result)
        else:
            uncovered.append(goal)
    
    # Calculate coverage percentage
    total = len(goals)
    coverage_pct = len(covered) / total if total > 0 else 0.0
    
    # Generate recommendations
    recommendations = []
    
    if coverage_pct < 0.3:
        recommendations.append("Vurder å inkludere flere kompetansemål fra læreplanen")
    
    uncovered_categories = set(g.category for g in uncovered)
    if uncovered_categories:
        for cat in list(uncovered_categories)[:2]:
            recommendations.append(f"Legg til oppgaver innen '{cat}' for bedre dekning")
    
    if coverage_pct > 0.7:
        recommendations.append("God dekning av kompetansemål!")
    
    return CoverageReport(
        grade_level=grade_level,
        topic=topic,
        covered_goals=covered,
        uncovered_goals=uncovered,
        coverage_percentage=coverage_pct,
        recommendations=recommendations
    )


def format_coverage_report(report: CoverageReport) -> str:
    """
    Format a coverage report as readable text.
    
    Args:
        report: CoverageReport object.
    
    Returns:
        Formatted string.
    """
    lines = [
        f"📊 **LK20 Kompetansemål-dekning**",
        f"",
        f"**Klassetrinn:** {report.grade_level}",
        f"**Tema:** {report.topic or 'Ikke spesifisert'}",
        f"**Dekningsgrad:** {int(report.coverage_percentage * 100)}%",
        "",
    ]
    
    # Progress bar
    filled = int(report.coverage_percentage * 20)
    bar = "█" * filled + "░" * (20 - filled)
    lines.append(f"[{bar}] {int(report.coverage_percentage * 100)}%")
    lines.append("")
    
    # Covered goals
    if report.covered_goals:
        lines.append(f"✅ **Dekket ({len(report.covered_goals)}):**")
        for result in report.covered_goals:
            conf_pct = int(result.confidence * 100)
            lines.append(f"  - {result.goal.id}: {result.goal.text[:60]}... ({conf_pct}%)")
        lines.append("")
    
    # Uncovered goals
    if report.uncovered_goals:
        lines.append(f"❌ **Ikke dekket ({len(report.uncovered_goals)}):**")
        for goal in report.uncovered_goals[:5]:  # Show max 5
            lines.append(f"  - {goal.id}: {goal.text[:60]}...")
        if len(report.uncovered_goals) > 5:
            lines.append(f"  ... og {len(report.uncovered_goals) - 5} til")
        lines.append("")
    
    # Recommendations
    if report.recommendations:
        lines.append("💡 **Anbefalinger:**")
        for rec in report.recommendations:
            lines.append(f"  - {rec}")
    
    return "\n".join(lines)


def get_coverage_badge(coverage_percentage: float) -> tuple[str, str]:
    """
    Get a badge color and label for coverage percentage.
    
    Args:
        coverage_percentage: Coverage as 0.0 - 1.0.
    
    Returns:
        Tuple of (color, label).
    """
    if coverage_percentage >= 0.8:
        return ("#10b981", "Utmerket")
    elif coverage_percentage >= 0.6:
        return ("#f59e0b", "God")
    elif coverage_percentage >= 0.4:
        return ("#f97316", "Moderat")
    else:
        return ("#ef4444", "Lav")
