"""
Section Editor for MateMaTeX.
Allows parsing and regenerating specific sections of LaTeX content.
"""

import re
from typing import Optional
from dataclasses import dataclass


@dataclass
class Section:
    """Represents a section in the LaTeX document."""
    name: str
    section_type: str  # 'section', 'subsection', 'environment'
    start_pos: int
    end_pos: int
    content: str
    level: int = 1


def parse_sections(latex_content: str) -> list[Section]:
    """
    Parse LaTeX content and extract all sections.
    
    Args:
        latex_content: The LaTeX source code.
    
    Returns:
        List of Section objects.
    """
    sections = []
    
    # Find all sections
    section_pattern = r'\\(section|subsection)\*?\{([^}]+)\}'
    
    matches = list(re.finditer(section_pattern, latex_content))
    
    for i, match in enumerate(matches):
        section_type = match.group(1)
        section_name = match.group(2)
        start_pos = match.start()
        
        # Find end position (next section or end of content)
        if i + 1 < len(matches):
            end_pos = matches[i + 1].start()
        else:
            # Find end of document or end of string
            end_match = re.search(r'\\end\{document\}', latex_content[start_pos:])
            if end_match:
                end_pos = start_pos + end_match.start()
            else:
                end_pos = len(latex_content)
        
        content = latex_content[start_pos:end_pos]
        level = 1 if section_type == 'section' else 2
        
        sections.append(Section(
            name=section_name,
            section_type=section_type,
            start_pos=start_pos,
            end_pos=end_pos,
            content=content,
            level=level
        ))
    
    # Also find special environments
    env_patterns = [
        (r'\\begin\{definisjon\}(.*?)\\end\{definisjon\}', 'Definisjon'),
        (r'\\begin\{eksempel\}(?:\[title=([^\]]+)\])?(.*?)\\end\{eksempel\}', 'Eksempel'),
        (r'\\begin\{taskbox\}\{([^}]+)\}(.*?)\\end\{taskbox\}', 'Oppgave'),
    ]
    
    for pattern, env_type in env_patterns:
        for match in re.finditer(pattern, latex_content, re.DOTALL):
            # Get title from match groups
            if env_type == 'Eksempel':
                title = match.group(1) or 'Eksempel'
            elif env_type == 'Oppgave':
                title = match.group(1)
            else:
                title = env_type
            
            sections.append(Section(
                name=f"{env_type}: {title[:30]}",
                section_type='environment',
                start_pos=match.start(),
                end_pos=match.end(),
                content=match.group(0),
                level=3
            ))
    
    # Sort by position
    sections.sort(key=lambda s: s.start_pos)
    
    return sections


def get_section_summary(latex_content: str) -> list[dict]:
    """
    Get a summary of all sections for display.
    
    Args:
        latex_content: The LaTeX source code.
    
    Returns:
        List of section info dictionaries.
    """
    sections = parse_sections(latex_content)
    
    summary = []
    for section in sections:
        # Count exercises in section
        exercise_count = section.content.count('\\begin{taskbox}')
        
        # Get word count (approximate)
        clean_text = re.sub(r'\\[a-zA-Z]+\{[^}]*\}', '', section.content)
        word_count = len(clean_text.split())
        
        summary.append({
            'name': section.name,
            'type': section.section_type,
            'level': section.level,
            'exercises': exercise_count,
            'words': word_count,
            'start': section.start_pos,
            'end': section.end_pos,
        })
    
    return summary


def replace_section(latex_content: str, section_name: str, new_content: str) -> str:
    """
    Replace a section's content with new content.
    
    Args:
        latex_content: The original LaTeX source.
        section_name: Name of the section to replace.
        new_content: New content for the section.
    
    Returns:
        Updated LaTeX content.
    """
    sections = parse_sections(latex_content)
    
    for section in sections:
        if section.name == section_name:
            # Replace the section content
            before = latex_content[:section.start_pos]
            after = latex_content[section.end_pos:]
            return before + new_content + after
    
    return latex_content


def extract_section(latex_content: str, section_name: str) -> Optional[str]:
    """
    Extract a specific section's content.
    
    Args:
        latex_content: The LaTeX source code.
        section_name: Name of the section to extract.
    
    Returns:
        Section content or None.
    """
    sections = parse_sections(latex_content)
    
    for section in sections:
        if section.name == section_name:
            return section.content
    
    return None


def generate_section_prompt(
    section_type: str,
    section_name: str,
    grade: str,
    topic: str,
    context: str = ""
) -> str:
    """
    Generate a prompt for regenerating a specific section.
    
    Args:
        section_type: Type of section (section, subsection, environment).
        section_name: Name of the section.
        grade: Grade level.
        topic: Math topic.
        context: Surrounding context for consistency.
    
    Returns:
        Prompt string for the AI.
    """
    prompts = {
        'section': f"""
Generer en ny versjon av seksjonen "{section_name}" for {grade} om {topic}.
Følg samme LaTeX-formatering som resten av dokumentet.
Bruk \\section{{{section_name}}} som overskrift.

Kontekst fra dokumentet:
{context[:500] if context else 'Ingen kontekst tilgjengelig.'}
""",
        'subsection': f"""
Generer en ny versjon av underseksjonen "{section_name}" for {grade} om {topic}.
Følg samme LaTeX-formatering som resten av dokumentet.
Bruk \\subsection{{{section_name}}} som overskrift.

Kontekst fra dokumentet:
{context[:500] if context else 'Ingen kontekst tilgjengelig.'}
""",
        'environment': f"""
Generer en ny versjon av {section_name} for {grade} om {topic}.
Behold samme miljø-type og formatering.

Kontekst fra dokumentet:
{context[:500] if context else 'Ingen kontekst tilgjengelig.'}
""",
    }
    
    return prompts.get(section_type, prompts['section'])
