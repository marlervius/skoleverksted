"""
Watermark functionality for MateMaTeX.
Add school logos and watermarks to PDFs.
"""

import re
import base64
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class WatermarkConfig:
    """Configuration for watermarks."""
    text: Optional[str]
    image_path: Optional[str]
    position: str  # "header", "footer", "background", "corner"
    opacity: float  # 0.0 to 1.0
    size: str  # "small", "medium", "large"


def add_watermark_to_latex(
    latex_content: str,
    text: Optional[str] = None,
    image_path: Optional[str] = None,
    position: str = "header",
    school_name: Optional[str] = None
) -> str:
    """
    Add watermark to LaTeX content.
    
    Args:
        latex_content: Original LaTeX content.
        text: Text watermark (e.g., school name).
        image_path: Path to logo image.
        position: Where to place the watermark.
        school_name: School name for header/footer.
    
    Returns:
        Modified LaTeX content with watermark.
    """
    # Prepare watermark packages and commands
    watermark_preamble = ""
    header_footer = ""
    
    # Add fancyhdr for headers/footers
    if text or school_name:
        watermark_preamble += r"""
\usepackage{fancyhdr}
\pagestyle{fancy}
\fancyhf{}
"""
        
        if position == "header":
            if school_name:
                header_footer += f"\\fancyhead[L]{{{school_name}}}\n"
            if text:
                header_footer += f"\\fancyhead[R]{{{text}}}\n"
            header_footer += r"\fancyfoot[C]{\thepage}" + "\n"
        
        elif position == "footer":
            header_footer += r"\fancyhead[C]{}" + "\n"
            if school_name:
                header_footer += f"\\fancyfoot[L]{{{school_name}}}\n"
            header_footer += r"\fancyfoot[C]{\thepage}" + "\n"
            if text:
                header_footer += f"\\fancyfoot[R]{{{text}}}\n"
        
        watermark_preamble += header_footer
        watermark_preamble += r"\renewcommand{\headrulewidth}{0.4pt}" + "\n"
        watermark_preamble += r"\renewcommand{\footrulewidth}{0.4pt}" + "\n"
    
    # Add background watermark
    if text and position == "background":
        watermark_preamble += r"""
\usepackage{draftwatermark}
\SetWatermarkText{""" + text + r"""}
\SetWatermarkScale{0.5}
\SetWatermarkColor[gray]{0.9}
"""
    
    # Add logo in corner if image path provided
    if image_path and Path(image_path).exists():
        watermark_preamble += r"""
\usepackage{eso-pic}
\newcommand{\watermarklogo}{%
    \put(0,0){%
        \parbox[b][\paperheight]{\paperwidth}{%
            \vfill
            \centering
            \includegraphics[width=2cm,keepaspectratio]{""" + image_path + r"""}%
            \vfill
        }%
    }%
}
\AddToShipoutPicture{\watermarklogo}
"""
    
    # Insert preamble before \begin{document}
    if watermark_preamble:
        if r'\begin{document}' in latex_content:
            latex_content = latex_content.replace(
                r'\begin{document}',
                watermark_preamble + r'\begin{document}'
            )
        else:
            # Add at the beginning
            latex_content = watermark_preamble + latex_content
    
    return latex_content


def create_header_footer_latex(
    school_name: str,
    document_title: Optional[str] = None,
    include_date: bool = True,
    include_page_numbers: bool = True
) -> str:
    """
    Create LaTeX code for custom header and footer.
    
    Args:
        school_name: Name of the school.
        document_title: Optional document title for header.
        include_date: Include current date.
        include_page_numbers: Include page numbers.
    
    Returns:
        LaTeX preamble code.
    """
    latex = r"""
\usepackage{fancyhdr}
\usepackage{lastpage}
\pagestyle{fancy}
\fancyhf{}
"""
    
    # Header
    latex += f"\\fancyhead[L]{{\\textbf{{{school_name}}}}}\n"
    if document_title:
        latex += f"\\fancyhead[C]{{{document_title}}}\n"
    if include_date:
        latex += r"\fancyhead[R]{\today}" + "\n"
    
    # Footer
    if include_page_numbers:
        latex += r"\fancyfoot[C]{Side \thepage\ av \pageref{LastPage}}" + "\n"
    
    latex += r"""
\renewcommand{\headrulewidth}{0.4pt}
\renewcommand{\footrulewidth}{0.4pt}
"""
    
    return latex


def get_logo_latex(
    logo_path: str,
    position: str = "top-right",
    width: str = "2cm"
) -> str:
    """
    Generate LaTeX code for including a logo.
    
    Args:
        logo_path: Path to the logo file.
        position: Position of the logo.
        width: Width of the logo.
    
    Returns:
        LaTeX code.
    """
    if not Path(logo_path).exists():
        return ""
    
    position_code = {
        "top-right": r"\fancyhead[R]{\includegraphics[width=" + width + "]{" + logo_path + "}}",
        "top-left": r"\fancyhead[L]{\includegraphics[width=" + width + "]{" + logo_path + "}}",
        "bottom-right": r"\fancyfoot[R]{\includegraphics[width=" + width + "]{" + logo_path + "}}",
        "bottom-left": r"\fancyfoot[L]{\includegraphics[width=" + width + "]{" + logo_path + "}}",
    }
    
    return position_code.get(position, "")


# Predefined school templates
SCHOOL_TEMPLATES = {
    "generic": {
        "name": "Standard",
        "header_left": "{school_name}",
        "header_right": r"\today",
        "footer_center": r"Side \thepage",
        "line_color": "#000000",
    },
    "modern": {
        "name": "Moderne",
        "header_left": r"\textbf{{school_name}}",
        "header_right": "{document_title}",
        "footer_left": r"\today",
        "footer_right": r"\thepage/\pageref{LastPage}",
        "line_color": "#f0b429",
    },
    "minimal": {
        "name": "Minimalistisk",
        "header_center": "{school_name}",
        "footer_center": r"\thepage",
        "line_color": "#cccccc",
    },
    "academic": {
        "name": "Akademisk",
        "header_left": "{school_name}",
        "header_center": "{document_title}",
        "header_right": "{class_name}",
        "footer_left": "Matematikk",
        "footer_center": r"\thepage",
        "footer_right": r"\today",
        "line_color": "#1e3a5f",
    },
}


def get_template_list() -> list[dict]:
    """Get list of available watermark templates."""
    return [
        {"key": key, "name": template["name"]}
        for key, template in SCHOOL_TEMPLATES.items()
    ]


def apply_template(
    latex_content: str,
    template_key: str,
    school_name: str,
    document_title: str = "",
    class_name: str = ""
) -> str:
    """
    Apply a watermark template to LaTeX content.
    
    Args:
        latex_content: Original LaTeX content.
        template_key: Key of the template to apply.
        school_name: School name.
        document_title: Document title.
        class_name: Class/grade name.
    
    Returns:
        Modified LaTeX content.
    """
    if template_key not in SCHOOL_TEMPLATES:
        return latex_content
    
    template = SCHOOL_TEMPLATES[template_key]
    
    # Build preamble
    preamble = r"""
\usepackage{fancyhdr}
\usepackage{lastpage}
\pagestyle{fancy}
\fancyhf{}
"""
    
    # Replace placeholders
    replacements = {
        "{school_name}": school_name,
        "{document_title}": document_title,
        "{class_name}": class_name,
    }
    
    # Header
    for pos in ["left", "center", "right"]:
        key = f"header_{pos}"
        if key in template:
            value = template[key]
            for placeholder, replacement in replacements.items():
                value = value.replace(placeholder, replacement)
            pos_code = {"left": "L", "center": "C", "right": "R"}[pos]
            preamble += f"\\fancyhead[{pos_code}]{{{value}}}\n"
    
    # Footer
    for pos in ["left", "center", "right"]:
        key = f"footer_{pos}"
        if key in template:
            value = template[key]
            for placeholder, replacement in replacements.items():
                value = value.replace(placeholder, replacement)
            pos_code = {"left": "L", "center": "C", "right": "R"}[pos]
            preamble += f"\\fancyfoot[{pos_code}]{{{value}}}\n"
    
    # Lines
    preamble += r"\renewcommand{\headrulewidth}{0.4pt}" + "\n"
    preamble += r"\renewcommand{\footrulewidth}{0.4pt}" + "\n"
    
    # Insert before \begin{document}
    if r'\begin{document}' in latex_content:
        latex_content = latex_content.replace(
            r'\begin{document}',
            preamble + r'\begin{document}'
        )
    
    return latex_content


def render_watermark_preview_html(
    school_name: str,
    template_key: str = "generic"
) -> str:
    """Render a preview of the watermark."""
    template = SCHOOL_TEMPLATES.get(template_key, SCHOOL_TEMPLATES["generic"])
    
    header_left = template.get("header_left", "").replace("{school_name}", school_name)
    header_center = template.get("header_center", "").replace("{school_name}", school_name)
    header_right = template.get("header_right", "").replace(r"\today", "13.01.2026")
    
    footer_left = template.get("footer_left", "")
    footer_center = template.get("footer_center", "").replace(r"\thepage", "1").replace(r"\pageref{LastPage}", "5")
    footer_right = template.get("footer_right", "").replace(r"\today", "13.01.2026").replace(r"\thepage/\pageref{LastPage}", "1/5")
    
    return f"""
    <div style="
        background: white;
        border: 1px solid #374151;
        border-radius: 8px;
        padding: 0;
        width: 200px;
        height: 280px;
        position: relative;
        font-family: serif;
        color: #333;
    ">
        <!-- Header -->
        <div style="
            display: flex;
            justify-content: space-between;
            padding: 0.5rem;
            border-bottom: 1px solid #333;
            font-size: 0.5rem;
        ">
            <span>{header_left[:15]}</span>
            <span>{header_center[:15]}</span>
            <span>{header_right[:10]}</span>
        </div>
        
        <!-- Content placeholder -->
        <div style="
            padding: 1rem;
            font-size: 0.4rem;
            color: #999;
            line-height: 1.4;
        ">
            <div style="height: 8px; background: #eee; margin-bottom: 4px; border-radius: 2px;"></div>
            <div style="height: 8px; background: #eee; margin-bottom: 4px; border-radius: 2px; width: 80%;"></div>
            <div style="height: 8px; background: #eee; margin-bottom: 8px; border-radius: 2px; width: 60%;"></div>
            <div style="height: 8px; background: #eee; margin-bottom: 4px; border-radius: 2px;"></div>
            <div style="height: 8px; background: #eee; margin-bottom: 4px; border-radius: 2px; width: 90%;"></div>
        </div>
        
        <!-- Footer -->
        <div style="
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            display: flex;
            justify-content: space-between;
            padding: 0.5rem;
            border-top: 1px solid #333;
            font-size: 0.5rem;
        ">
            <span>{footer_left[:10]}</span>
            <span>{footer_center}</span>
            <span>{footer_right[:10]}</span>
        </div>
    </div>
    """
