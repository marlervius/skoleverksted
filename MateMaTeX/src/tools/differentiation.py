"""
Differentiation Assistant for MateMaTeX.
Automatically generates content at multiple difficulty levels.
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class DifferentiatedContent:
    """Content at a specific difficulty level."""
    level: str  # "lett", "middels", "vanskelig"
    level_name: str  # Display name
    emoji: str
    color: str
    description: str
    latex_content: str
    num_exercises: int
    estimated_time: int  # minutes


@dataclass
class DifferentiatedSet:
    """A complete set of differentiated content."""
    topic: str
    grade_level: str
    easy: DifferentiatedContent
    medium: DifferentiatedContent
    hard: DifferentiatedContent


# Level configurations
LEVEL_CONFIG = {
    "lett": {
        "name": "Grunnleggende",
        "emoji": "🟢",
        "color": "#10b981",
        "description": "Enklere oppgaver med direkte anvendelse av grunnleggende ferdigheter",
        "characteristics": [
            "Enkle tall og verdier",
            "Direkte beregninger",
            "Ett steg løsninger",
            "Mye veiledning",
            "Visuell støtte",
        ],
        "num_exercises": 12,
        "time_per_exercise": 3,
    },
    "middels": {
        "name": "Standard",
        "emoji": "🟡",
        "color": "#f59e0b",
        "description": "Oppgaver på forventet nivå med noe problemløsning",
        "characteristics": [
            "Varierte tall",
            "Flere steg",
            "Noe problemløsning",
            "Begrenset veiledning",
            "Anvendelse av kunnskap",
        ],
        "num_exercises": 10,
        "time_per_exercise": 5,
    },
    "vanskelig": {
        "name": "Utfordring",
        "emoji": "🔴",
        "color": "#ef4444",
        "description": "Utfordrende oppgaver som krever dypere forståelse og kreativitet",
        "characteristics": [
            "Komplekse tall og uttrykk",
            "Flere konsepter kombinert",
            "Åpne oppgaver",
            "Minimal veiledning",
            "Bevis og begrunnelse",
        ],
        "num_exercises": 6,
        "time_per_exercise": 10,
    },
}


def get_level_prompt(level: str, topic: str, grade_level: str) -> str:
    """
    Generate a prompt for creating content at a specific level.
    
    Args:
        level: Difficulty level ("lett", "middels", "vanskelig").
        topic: The math topic.
        grade_level: Grade level.
    
    Returns:
        Prompt string for AI generation.
    """
    config = LEVEL_CONFIG.get(level, LEVEL_CONFIG["middels"])
    
    characteristics = "\n".join(f"- {c}" for c in config["characteristics"])
    
    # Build adjustment text based on level
    if level == "lett":
        adjustments = "- Bruk små, enkle tall\n- Gi tydelige eksempler før oppgavene\n- Inkluder hint ved hver oppgave"
    elif level == "middels":
        adjustments = "- Varier vanskelighetsgrad innen oppgavesettet\n- Inkluder noen tekstoppgaver\n- Krev at eleven viser fremgangsmåte"
    else:
        adjustments = "- Bruk komplekse uttrykk og tall\n- Inkluder bevisoppgaver\n- Kombiner flere emner\n- Krev fullstendig argumentasjon"
    
    return f"""Generer et matematikkark om '{topic}' for {grade_level}.

**Vanskelighetsgrad:** {config['name']} ({level})

**Kjennetegn for dette nivået:**
{characteristics}

**Antall oppgaver:** {config['num_exercises']}

**Tilpasninger:**
{adjustments}

Lag innholdet på norsk med LaTeX-formatering.
"""


def adjust_content_difficulty(
    latex_content: str,
    target_level: str
) -> str:
    """
    Adjust existing content to a different difficulty level.
    
    Args:
        latex_content: Original LaTeX content.
        target_level: Target difficulty level.
    
    Returns:
        Adjusted LaTeX content.
    """
    content = latex_content
    
    if target_level == "lett":
        # Simplify numbers
        content = re.sub(r'(\d{3,})', lambda m: str(int(m.group(1)) // 10), content)
        
        # Add hints section
        if "\\section*{Tips}" not in content:
            hint_section = r"""
\section*{Tips og hjelp}
\begin{itemize}
\item Les oppgaven nøye flere ganger
\item Skriv ned det du vet
\item Prøv med enklere tall først
\item Spør om hjelp hvis du står fast
\end{itemize}
"""
            content = content.replace(r"\end{document}", hint_section + r"\end{document}")
    
    elif target_level == "vanskelig":
        # Add challenge marker
        content = content.replace(
            r"\begin{taskbox}",
            r"\begin{taskbox}[Utfordring]"
        )
        
        # Add proof requirements
        content = re.sub(
            r"(Beregn|Finn|Løs)",
            r"\1 og begrunn",
            content,
            count=3
        )
    
    return content


def create_level_header(level: str) -> str:
    """
    Create a LaTeX header for a difficulty level.
    
    Args:
        level: Difficulty level.
    
    Returns:
        LaTeX code for the header.
    """
    config = LEVEL_CONFIG.get(level, LEVEL_CONFIG["middels"])
    
    return rf"""
\begin{{center}}
\colorbox{{{config['color']}!20}}{{
\parbox{{0.9\textwidth}}{{
\centering
\textbf{{\Large {config['emoji']} {config['name']}}}\\[0.5em]
\textit{{{config['description']}}}
}}
}}
\end{{center}}
\vspace{{1em}}
"""


def create_differentiated_set(
    topic: str,
    grade_level: str,
    base_content: Optional[str] = None
) -> DifferentiatedSet:
    """
    Create a complete differentiated content set.
    
    Args:
        topic: The math topic.
        grade_level: Grade level.
        base_content: Optional base content to adapt.
    
    Returns:
        DifferentiatedSet with three levels.
    """
    levels = {}
    
    for level_key, config in LEVEL_CONFIG.items():
        if base_content:
            content = adjust_content_difficulty(base_content, level_key)
            content = create_level_header(level_key) + content
        else:
            # Placeholder - in real use, this would call AI
            content = create_level_header(level_key) + f"""
\\section*{{{topic} - {config['name']}}}
\\textit{{Generert innhold for {config['name'].lower()} nivå.}}
"""
        
        levels[level_key] = DifferentiatedContent(
            level=level_key,
            level_name=config["name"],
            emoji=config["emoji"],
            color=config["color"],
            description=config["description"],
            latex_content=content,
            num_exercises=config["num_exercises"],
            estimated_time=config["num_exercises"] * config["time_per_exercise"]
        )
    
    return DifferentiatedSet(
        topic=topic,
        grade_level=grade_level,
        easy=levels["lett"],
        medium=levels["middels"],
        hard=levels["vanskelig"]
    )


def get_differentiation_summary(diff_set: DifferentiatedSet) -> str:
    """
    Get a summary of the differentiated content.
    
    Args:
        diff_set: DifferentiatedSet object.
    
    Returns:
        Formatted summary string.
    """
    lines = [
        f"🎯 **Differensiert opplegg: {diff_set.topic}**",
        f"**Klassetrinn:** {diff_set.grade_level}",
        "",
        "| Nivå | Oppgaver | Estimert tid |",
        "|------|----------|--------------|",
    ]
    
    for level in [diff_set.easy, diff_set.medium, diff_set.hard]:
        lines.append(
            f"| {level.emoji} {level.level_name} | {level.num_exercises} | ~{level.estimated_time} min |"
        )
    
    lines.extend([
        "",
        "**Kjennetegn:**",
        f"- 🟢 **Grunnleggende:** Direkte anvendelse, mye støtte",
        f"- 🟡 **Standard:** Problemløsning, moderat støtte",
        f"- 🔴 **Utfordring:** Kompleks, selvstendig arbeid",
    ])
    
    return "\n".join(lines)


def merge_differentiated_pdf(diff_set: DifferentiatedSet) -> str:
    """
    Merge all levels into a single LaTeX document.
    
    Args:
        diff_set: DifferentiatedSet object.
    
    Returns:
        Combined LaTeX content.
    """
    parts = [
        r"\documentclass[a4paper,11pt]{article}",
        r"\usepackage[utf8]{inputenc}",
        r"\usepackage[norsk]{babel}",
        r"\usepackage{amsmath,amssymb}",
        r"\usepackage{xcolor}",
        r"\usepackage{geometry}",
        r"\geometry{margin=2.5cm}",
        r"",
        r"\begin{document}",
        r"",
        rf"\title{{{diff_set.topic} - Differensiert opplegg}}",
        rf"\author{{{diff_set.grade_level}}}",
        r"\date{\today}",
        r"\maketitle",
        r"",
        r"\tableofcontents",
        r"\newpage",
        r"",
    ]
    
    for level in [diff_set.easy, diff_set.medium, diff_set.hard]:
        parts.append(rf"\section{{{level.emoji} {level.level_name}}}")
        parts.append(level.latex_content)
        parts.append(r"\newpage")
    
    parts.append(r"\end{document}")
    
    return "\n".join(parts)


def get_level_recommendations(current_score: float) -> str:
    """
    Recommend a difficulty level based on previous performance.
    
    Args:
        current_score: Score from 0.0 to 1.0.
    
    Returns:
        Recommended level and explanation.
    """
    if current_score >= 0.85:
        return "🔴 **Anbefalt nivå: Utfordring**\nBasert på tidligere resultater anbefales et høyere nivå."
    elif current_score >= 0.60:
        return "🟡 **Anbefalt nivå: Standard**\nGode resultater! Fortsett på dette nivået."
    else:
        return "🟢 **Anbefalt nivå: Grunnleggende**\nMer øving på grunnleggende ferdigheter anbefales."
