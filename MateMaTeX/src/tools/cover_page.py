"""
Cover Page Generator for MateMaTeX.
Creates professional cover pages for math documents.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class CoverPageConfig:
    """Configuration for a cover page."""
    title: str
    subtitle: Optional[str] = None
    grade: Optional[str] = None
    school_name: Optional[str] = None
    teacher_name: Optional[str] = None
    class_name: Optional[str] = None
    date: Optional[str] = None
    logo_path: Optional[str] = None
    style: str = "modern"  # modern, classic, minimal, colorful


# Cover page styles
COVER_STYLES = {
    "modern": "Moderne – Rent design med fargeaksenter",
    "classic": "Klassisk – Tradisjonelt lærebokutseende",
    "minimal": "Minimalistisk – Enkelt og profesjonelt",
    "colorful": "Fargerikt – Engasjerende for yngre elever",
}


def generate_cover_page_latex(config: CoverPageConfig) -> str:
    """
    Generate LaTeX code for a cover page.
    
    Args:
        config: Cover page configuration.
    
    Returns:
        LaTeX code for the cover page.
    """
    date_str = config.date or datetime.now().strftime("%d. %B %Y")
    
    if config.style == "modern":
        return _generate_modern_cover(config, date_str)
    elif config.style == "classic":
        return _generate_classic_cover(config, date_str)
    elif config.style == "minimal":
        return _generate_minimal_cover(config, date_str)
    elif config.style == "colorful":
        return _generate_colorful_cover(config, date_str)
    else:
        return _generate_modern_cover(config, date_str)


def _generate_modern_cover(config: CoverPageConfig, date_str: str) -> str:
    """Modern cover page with geometric accents."""
    
    school_line = ""
    if config.school_name:
        school_line = f"\\textcolor{{mainGray}}{{\\large {config.school_name}}}\\\\"
    
    class_line = ""
    if config.class_name or config.grade:
        class_text = config.class_name or config.grade
        class_line = f"\\textcolor{{mainBlue}}{{\\Large \\textbf{{{class_text}}}}}\\\\"
    
    teacher_line = ""
    if config.teacher_name:
        teacher_line = f"\\vspace{{0.3cm}}\\textcolor{{mainGray}}{{Lærer: {config.teacher_name}}}\\\\"
    
    subtitle_line = ""
    if config.subtitle:
        subtitle_line = f"\\vspace{{0.5cm}}\\textcolor{{mainGray}}{{\\large {config.subtitle}}}\\\\"
    
    return f"""
% ============= COVER PAGE =============
\\thispagestyle{{empty}}
\\begin{{tikzpicture}}[remember picture, overlay]
    % Background gradient effect
    \\fill[mainBlue!5] (current page.south west) rectangle (current page.north east);
    
    % Decorative circles
    \\fill[mainBlue!15] (current page.north east) ++(-3cm,-3cm) circle (5cm);
    \\fill[mainGreen!10] (current page.south west) ++(4cm,4cm) circle (4cm);
    \\fill[mainOrange!10] (current page.north west) ++(2cm,-6cm) circle (2.5cm);
    
    % Accent line
    \\fill[mainBlue] (current page.west) ++(0,2cm) rectangle ++(\\paperwidth,3pt);
\\end{{tikzpicture}}

\\vspace*{{4cm}}

\\begin{{center}}
    {school_line}
    \\vspace{{1cm}}
    
    {{\\Huge \\bfseries \\textcolor{{mainBlue}}{{{config.title}}}}}
    
    {subtitle_line}
    
    \\vspace{{1.5cm}}
    
    {class_line}
    
    {teacher_line}
    
    \\vfill
    
    \\textcolor{{mainGray}}{{{date_str}}}
    
    \\vspace{{1cm}}
    
    % Math symbols decoration
    \\textcolor{{mainBlue!30}}{{\\Huge $\\pi \\cdot e \\cdot \\phi \\cdot \\infty$}}
\\end{{center}}

\\newpage
% ============= END COVER PAGE =============
"""


def _generate_classic_cover(config: CoverPageConfig, date_str: str) -> str:
    """Classic textbook-style cover page."""
    
    school_line = ""
    if config.school_name:
        school_line = f"{{\\large {config.school_name}}}\\\\[0.5cm]"
    
    class_line = ""
    if config.class_name or config.grade:
        class_text = config.class_name or config.grade
        class_line = f"\\vspace{{0.5cm}}{{\\Large {class_text}}}\\\\[0.3cm]"
    
    teacher_line = ""
    if config.teacher_name:
        teacher_line = f"{{\\normalsize Lærer: {config.teacher_name}}}\\\\[0.3cm]"
    
    subtitle_line = ""
    if config.subtitle:
        subtitle_line = f"\\vspace{{0.3cm}}{{\\large\\itshape {config.subtitle}}}\\\\[0.5cm]"
    
    return f"""
% ============= COVER PAGE =============
\\thispagestyle{{empty}}

\\begin{{center}}
    \\vspace*{{2cm}}
    
    {school_line}
    
    \\rule{{\\textwidth}}{{1pt}}
    
    \\vspace{{1.5cm}}
    
    {{\\Huge \\bfseries {config.title}}}
    
    {subtitle_line}
    
    \\vspace{{1cm}}
    
    \\rule{{0.5\\textwidth}}{{0.5pt}}
    
    {class_line}
    
    {teacher_line}
    
    \\vfill
    
    \\rule{{\\textwidth}}{{1pt}}
    
    \\vspace{{0.5cm}}
    
    {date_str}
\\end{{center}}

\\newpage
% ============= END COVER PAGE =============
"""


def _generate_minimal_cover(config: CoverPageConfig, date_str: str) -> str:
    """Minimal, professional cover page."""
    
    meta_line = ""
    parts = []
    if config.school_name:
        parts.append(config.school_name)
    if config.class_name or config.grade:
        parts.append(config.class_name or config.grade)
    if parts:
        meta_line = f"\\textcolor{{mainGray}}{{{' · '.join(parts)}}}"
    
    return f"""
% ============= COVER PAGE =============
\\thispagestyle{{empty}}

\\vspace*{{\\fill}}

\\begin{{center}}
    {{\\fontsize{{42}}{{50}}\\selectfont\\bfseries {config.title}}}
    
    \\vspace{{1cm}}
    
    {meta_line}
    
    \\vspace{{0.5cm}}
    
    \\textcolor{{mainGray!70}}{{{date_str}}}
\\end{{center}}

\\vspace*{{\\fill}}

\\newpage
% ============= END COVER PAGE =============
"""


def _generate_colorful_cover(config: CoverPageConfig, date_str: str) -> str:
    """Colorful, engaging cover for younger students."""
    
    school_line = ""
    if config.school_name:
        school_line = f"{{\\Large\\bfseries {config.school_name}}}\\\\[0.5cm]"
    
    class_line = ""
    if config.class_name or config.grade:
        class_text = config.class_name or config.grade
        class_line = f"\\tikz\\node[fill=mainOrange!20, rounded corners=8pt, inner sep=10pt]{{\\Large\\bfseries {class_text}}};"
    
    return f"""
% ============= COVER PAGE =============
\\thispagestyle{{empty}}
\\begin{{tikzpicture}}[remember picture, overlay]
    % Colorful background
    \\fill[mainBlue!20] (current page.south west) rectangle (current page.north east);
    
    % Fun geometric shapes
    \\fill[mainGreen!40] (current page.north west) ++(2cm,-4cm) circle (3cm);
    \\fill[mainOrange!40] (current page.north east) ++(-3cm,-6cm) circle (2.5cm);
    \\fill[mainBlue!40] (current page.south east) ++(-4cm,5cm) circle (2cm);
    \\fill[yellow!40] (current page.south west) ++(5cm,3cm) circle (1.5cm);
    
    % Stars decoration
    \\foreach \\x/\\y in {{3/8, 12/6, 8/2, 15/4, 2/3}} {{
        \\node[star, star points=5, fill=yellow!60, minimum size=0.5cm] 
            at (current page.south west) ++(\\x cm,\\y cm) {{}};
    }}
    
    % Math symbols scattered
    \\node[mainBlue!50, font=\\Huge] at (current page.north west) ++(3cm,-2cm) {{$+$}};
    \\node[mainGreen!50, font=\\Huge] at (current page.north east) ++(-2cm,-3cm) {{$\\times$}};
    \\node[mainOrange!50, font=\\Huge] at (current page.south west) ++(2cm,2cm) {{$=$}};
\\end{{tikzpicture}}

\\vspace*{{3cm}}

\\begin{{center}}
    {school_line}
    
    \\tikz\\node[fill=white, rounded corners=15pt, inner sep=20pt, drop shadow]{{
        {{\\fontsize{{36}}{{44}}\\selectfont\\bfseries\\textcolor{{mainBlue}}{{{config.title}}}}}
    }};
    
    \\vspace{{1.5cm}}
    
    {class_line}
    
    \\vfill
    
    \\tikz\\node[fill=white!80, rounded corners=5pt, inner sep=8pt]{{
        {date_str}
    }};
    
    \\vspace{{1cm}}
\\end{{center}}

\\newpage
% ============= END COVER PAGE =============
"""


def insert_cover_page(latex_content: str, config: CoverPageConfig) -> str:
    """
    Insert a cover page at the beginning of a LaTeX document.
    
    Args:
        latex_content: The original LaTeX content.
        config: Cover page configuration.
    
    Returns:
        LaTeX content with cover page inserted.
    """
    cover_latex = generate_cover_page_latex(config)
    
    # Find \begin{document} and insert cover page after it
    if "\\begin{document}" in latex_content:
        parts = latex_content.split("\\begin{document}", 1)
        return parts[0] + "\\begin{document}\n" + cover_latex + parts[1]
    else:
        # If no document environment, just prepend
        return cover_latex + latex_content


def get_cover_style_options() -> dict[str, str]:
    """Get available cover page styles."""
    return COVER_STYLES
