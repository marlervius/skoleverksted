"""
Print Optimizer for MateMaTeX.
Creates print-friendly versions of LaTeX documents.
"""

import re
from typing import Optional


# Print-friendly preamble (grayscale, optimized for printing)
PRINT_PREAMBLE = r"""
\documentclass[11pt, a4paper]{article}

% Encoding and language
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[norsk]{babel}

% Page layout - optimized for printing
\usepackage[
    a4paper,
    margin=2cm,
    top=2.5cm,
    bottom=2.5cm
]{geometry}

% Basic packages
\usepackage{amsmath, amssymb, amsthm}
\usepackage{graphicx}
\usepackage{float}
\usepackage{booktabs}
\usepackage{enumitem}
\usepackage{multicol}
\usepackage{fancyhdr}
\usepackage{lastpage}

% TikZ for graphics (grayscale)
\usepackage{tikz}
\usepackage{pgfplots}
\pgfplotsset{compat=1.18}

% Print-friendly colors (grayscale)
\usepackage{xcolor}
\definecolor{printBlack}{gray}{0.0}
\definecolor{printDarkGray}{gray}{0.3}
\definecolor{printMediumGray}{gray}{0.5}
\definecolor{printLightGray}{gray}{0.85}
\definecolor{printWhite}{gray}{1.0}

% tcolorbox for styled boxes (print-friendly)
\usepackage[most]{tcolorbox}

% Definition box (light gray background, black border)
\newtcolorbox{definisjon}{
    colback=printLightGray,
    colframe=printBlack,
    fonttitle=\bfseries,
    title=Definisjon,
    boxrule=1pt,
    arc=0pt,
    left=8pt, right=8pt, top=6pt, bottom=6pt
}

% Example box (white background, gray border)
\newtcolorbox{eksempel}[1][]{
    colback=printWhite,
    colframe=printDarkGray,
    fonttitle=\bfseries,
    title=#1,
    boxrule=0.5pt,
    arc=0pt,
    left=8pt, right=8pt, top=6pt, bottom=6pt
}

% Task box (dashed border)
\newtcolorbox{taskbox}[1]{
    colback=printWhite,
    colframe=printMediumGray,
    fonttitle=\bfseries,
    title=#1,
    boxrule=0.5pt,
    arc=0pt,
    left=8pt, right=8pt, top=6pt, bottom=6pt,
    enhanced,
    borderline={0.5pt}{0pt}{printMediumGray, dashed}
}

% Note box (thin border)
\newtcolorbox{merk}{
    colback=printWhite,
    colframe=printDarkGray,
    fonttitle=\bfseries,
    title=Merk,
    boxrule=0.5pt,
    arc=0pt,
    left=8pt, right=8pt, top=6pt, bottom=6pt
}

% Solution box (dotted border)
\newtcolorbox{losning}{
    colback=printWhite,
    colframe=printMediumGray,
    fonttitle=\bfseries,
    title=Løsning,
    boxrule=0.5pt,
    arc=0pt,
    left=8pt, right=8pt, top=6pt, bottom=6pt,
    borderline={0.5pt}{0pt}{printMediumGray, dotted}
}

% Header and footer for printing
\pagestyle{fancy}
\fancyhf{}
\fancyhead[L]{\small\leftmark}
\fancyhead[R]{\small MateMaTeX}
\fancyfoot[C]{\small Side \thepage\ av \pageref{LastPage}}
\renewcommand{\headrulewidth}{0.4pt}
\renewcommand{\footrulewidth}{0.4pt}

% Hyperref (print-friendly - no colored links)
\usepackage[
    colorlinks=false,
    pdfborder={0 0 0}
]{hyperref}

\begin{document}
"""


def create_print_version(latex_content: str) -> str:
    """
    Create a print-friendly version of LaTeX content.
    
    Args:
        latex_content: Original LaTeX content.
    
    Returns:
        Print-optimized LaTeX content.
    """
    content = latex_content
    
    # Remove existing preamble if present
    doc_start = re.search(r'\\begin\{document\}', content)
    if doc_start:
        # Extract content after \begin{document}
        content_start = doc_start.end()
        doc_end = re.search(r'\\end\{document\}', content)
        if doc_end:
            content = content[content_start:doc_end.start()]
        else:
            content = content[content_start:]
    
    # Replace colors with grayscale
    color_replacements = [
        (r'\\color\{mainBlue\}', r'\\color{printDarkGray}'),
        (r'\\color\{mainGreen\}', r'\\color{printDarkGray}'),
        (r'\\color\{mainOrange\}', r'\\color{printDarkGray}'),
        (r'\\color\{mainRed\}', r'\\color{printBlack}'),
        (r'\\color\{blue\}', r'\\color{printDarkGray}'),
        (r'\\color\{red\}', r'\\color{printBlack}'),
        (r'\\color\{green\}', r'\\color{printDarkGray}'),
        (r'\\color\{orange\}', r'\\color{printDarkGray}'),
        (r'\\textcolor\{[^}]+\}', r'\\textcolor{printBlack}'),
    ]
    
    for old, new in color_replacements:
        content = re.sub(old, new, content)
    
    # Update TikZ/PGFPlots colors
    tikz_color_replacements = [
        (r'\[blue,', r'[printDarkGray,'),
        (r'\[red,', r'[printBlack,'),
        (r'\[green,', r'[printDarkGray,'),
        (r'\[orange,', r'[printMediumGray,'),
        (r'\[mainBlue,', r'[printDarkGray,'),
        (r'\[mainGreen,', r'[printDarkGray,'),
        (r'\[mainOrange,', r'[printMediumGray,'),
        (r'color=blue', r'color=printDarkGray'),
        (r'color=red', r'color=printBlack'),
        (r'color=green', r'color=printDarkGray'),
        (r'color=orange', r'color=printMediumGray'),
    ]
    
    for old, new in tikz_color_replacements:
        content = content.replace(old, new)
    
    # Add "PRINT VERSION" to title
    content = re.sub(
        r'\\title\{([^}]+)\}',
        r'\\title{\1 (Utskriftsversjon)}',
        content
    )
    
    # Assemble final document
    result = PRINT_PREAMBLE + content + "\n\\end{document}"
    
    return result


def optimize_for_ink_saving(latex_content: str) -> str:
    """
    Optimize LaTeX for minimal ink usage.
    
    Args:
        latex_content: Original LaTeX content.
    
    Returns:
        Ink-optimized LaTeX content.
    """
    content = latex_content
    
    # Remove all background colors
    content = re.sub(r'colback=[^,\]]+', 'colback=white', content)
    
    # Make all frames thinner
    content = re.sub(r'boxrule=\d+(?:\.\d+)?pt', 'boxrule=0.3pt', content)
    
    # Remove shadow effects
    content = re.sub(r'shadow[^,\]]*', '', content)
    
    # Remove gradients
    content = re.sub(r'shading[^,\]]*', '', content)
    
    return content


def add_page_breaks(latex_content: str, break_before_sections: bool = True) -> str:
    """
    Add page breaks for better printing layout.
    
    Args:
        latex_content: Original LaTeX content.
        break_before_sections: Whether to add breaks before sections.
    
    Returns:
        LaTeX content with page breaks.
    """
    content = latex_content
    
    if break_before_sections:
        # Add page break before main sections (but not the first one)
        sections = list(re.finditer(r'\\section\{', content))
        if len(sections) > 1:
            for match in reversed(sections[1:]):  # Skip first section
                pos = match.start()
                content = content[:pos] + '\\clearpage\n' + content[pos:]
    
    # Add page break before solutions section
    content = re.sub(
        r'(\\section\*?\{Løsningsforslag\})',
        r'\\clearpage\n\1',
        content
    )
    
    return content


def create_answer_sheet(latex_content: str) -> Optional[str]:
    """
    Extract and create a separate answer sheet.
    
    Args:
        latex_content: Original LaTeX content.
    
    Returns:
        LaTeX content for answer sheet only, or None if no answers found.
    """
    # Find solutions section
    solutions_match = re.search(
        r'\\section\*?\{Løsningsforslag\}(.*?)(?=\\section|\\end\{document\}|$)',
        latex_content,
        re.DOTALL
    )
    
    if not solutions_match:
        return None
    
    solutions_content = solutions_match.group(1)
    
    # Extract title
    title_match = re.search(r'\\title\{([^}]+)\}', latex_content)
    title = title_match.group(1) if title_match else "Matematikk"
    
    answer_sheet = f"""
\\documentclass[11pt, a4paper]{{article}}
\\usepackage[utf8]{{inputenc}}
\\usepackage[T1]{{fontenc}}
\\usepackage[norsk]{{babel}}
\\usepackage[margin=2cm]{{geometry}}
\\usepackage{{amsmath, amssymb}}
\\usepackage{{multicol}}
\\usepackage{{enumitem}}

\\title{{{title} - Fasit}}
\\author{{MateMaTeX}}
\\date{{\\today}}

\\begin{{document}}
\\maketitle

\\section*{{Løsningsforslag}}
{solutions_content}

\\end{{document}}
"""
    
    return answer_sheet


def remove_solutions(latex_content: str) -> str:
    """
    Remove solutions section from document (for student version).
    
    Args:
        latex_content: Original LaTeX content.
    
    Returns:
        LaTeX content without solutions.
    """
    # Remove solutions section
    content = re.sub(
        r'\\section\*?\{Løsningsforslag\}.*?(?=\\section|\\end\{document\}|$)',
        '',
        latex_content,
        flags=re.DOTALL
    )
    
    # Remove individual solution boxes
    content = re.sub(
        r'\\begin\{losning\}.*?\\end\{losning\}',
        '',
        content,
        flags=re.DOTALL
    )
    
    return content
