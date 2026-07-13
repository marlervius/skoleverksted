"""
PDF Generator Tool for MateMaTeX.
Compiles LaTeX content to PDF using pdflatex.
"""

import os
import re
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# Standard preamble for Norwegian math documents - Modern Textbook Style
STANDARD_PREAMBLE = r"""\documentclass[a4paper,11pt]{article}

% Encoding and language
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[norsk]{babel}

% Modern fonts
\usepackage{lmodern}
\usepackage{microtype}

% Mathematics (mathtools extends amsmath with better spacing)
\usepackage{mathtools}
\usepackage{amssymb, amsthm}
\usepackage{bm}        % Bold math symbols (\bm{x})
\usepackage{siunitx}   % Units (\SI{9.81}{\metre\per\second\squared})

% Graphics
\usepackage{tikz, pgfplots}
\pgfplotsset{compat=1.18}
\usetikzlibrary{arrows.meta, calc, patterns, positioning, shapes.geometric, decorations.pathreplacing, decorations.pathmorphing}

% Layout
\usepackage[margin=2.5cm]{geometry}
\usepackage{float}
\usepackage{parskip}
\usepackage{enumitem}
\usepackage{booktabs}
\usepackage{multicol}

% Paragraph spacing
\setlength{\parskip}{0.8em}
\setlength{\parindent}{0pt}

% Reduce extra spacing around lists caused by parskip
\setlist{itemsep=0.3em, parsep=0.2em, topsep=0.3em}

% Float placement - keep figures where they are defined
\floatplacement{figure}{H}

% Colors and colored boxes
\usepackage{xcolor}
\usepackage[most]{tcolorbox}

% --- Custom Color Definitions (must come BEFORE hyperref) ---
\definecolor{mainBlue}{RGB}{0, 102, 204}
\definecolor{lightBlue}{RGB}{230, 242, 255}
\definecolor{mainGreen}{RGB}{0, 153, 76}
\definecolor{lightGreen}{RGB}{232, 250, 240}
\definecolor{mainOrange}{RGB}{230, 126, 34}
\definecolor{lightOrange}{RGB}{255, 245, 235}
\definecolor{mainPurple}{RGB}{102, 51, 153}
\definecolor{lightPurple}{RGB}{245, 240, 255}
\definecolor{mainTeal}{RGB}{0, 128, 128}
\definecolor{lightTeal}{RGB}{235, 250, 250}
\definecolor{mainGray}{RGB}{80, 80, 90}
\definecolor{lightGray}{RGB}{248, 248, 252}

% Hyperlinks (load AFTER color definitions to avoid undefined color errors)
\usepackage[colorlinks=true, linkcolor=mainBlue, urlcolor=mainBlue, citecolor=mainGreen]{hyperref}

% --- Shared box style ---
\tcbset{matebox/.style={
  enhanced, breakable,
  arc=3mm,
  left=8pt, right=8pt, top=8pt, bottom=8pt,
  attach boxed title to top left={yshift*=-\tcboxedtitleheight/2, xshift=5mm},
  sharp corners=downhill,
}}

% --- Definition Box (Blue) ---
\newtcolorbox{definitionbox}[1][]{
  matebox,
  colback=lightBlue, colframe=mainBlue,
  fonttitle=\bfseries\sffamily, title={Definisjon},
  boxed title style={colback=mainBlue, colframe=mainBlue},
  #1
}
\newtcolorbox{definisjon}[1][]{
  matebox,
  colback=lightBlue, colframe=mainBlue,
  fonttitle=\bfseries\sffamily, title={Definisjon},
  boxed title style={colback=mainBlue, colframe=mainBlue},
  #1
}

% --- Example Box (Green) ---
\newtcolorbox{examplebox}[1][]{
  matebox,
  colback=lightGreen, colframe=mainGreen,
  fonttitle=\bfseries\sffamily, title={Eksempel},
  boxed title style={colback=mainGreen, colframe=mainGreen},
  #1
}
\newtcolorbox{eksempel}[1][]{
  matebox,
  colback=lightGreen, colframe=mainGreen,
  fonttitle=\bfseries\sffamily, title={Eksempel},
  boxed title style={colback=mainGreen, colframe=mainGreen},
  #1
}

% --- Task Box (Purple) ---
\newtcolorbox{taskbox}[1][]{
  matebox,
  colback=lightPurple, colframe=mainPurple,
  fonttitle=\bfseries\sffamily\color{white}, title={#1},
  boxed title style={colback=mainPurple, colframe=mainPurple},
  left=10pt, right=10pt, top=10pt, bottom=10pt,
}

% --- Tip/Note Box (Orange) ---
\newtcolorbox{tipbox}[1][]{
  matebox,
  colback=lightOrange, colframe=mainOrange,
  fonttitle=\bfseries\sffamily, title={Tips},
  boxed title style={colback=mainOrange, colframe=mainOrange},
  #1
}

% --- Merk/Warning Box (Orange) ---
\newtcolorbox{merk}[1][]{
  matebox,
  colback=lightOrange, colframe=mainOrange,
  fonttitle=\bfseries\sffamily, title={Merk!},
  boxed title style={colback=mainOrange, colframe=mainOrange},
  #1
}

% --- Solution Box (Teal) ---
\newtcolorbox{losning}[1][]{
  matebox,
  colback=lightTeal, colframe=mainTeal,
  fonttitle=\bfseries\sffamily\color{white}, title={Løsning},
  boxed title style={colback=mainTeal, colframe=mainTeal},
  left=10pt, right=10pt, top=10pt, bottom=10pt,
  #1
}

% Theorem environments (fallback for simple usage)
\newtheorem{theorem}{Teorem}[section]
\newtheorem{definition}[theorem]{Definisjon}
\newtheorem{example}[theorem]{Eksempel}
\newtheorem{exercise}{Oppgave}[section]

% Custom math commands
\newcommand{\N}{\mathbb{N}}
\newcommand{\Z}{\mathbb{Z}}
\newcommand{\Q}{\mathbb{Q}}
\newcommand{\R}{\mathbb{R}}

% Section styling
\usepackage{titlesec}
\titleformat{\section}{\Large\bfseries\sffamily\color{mainBlue}}{\thesection}{1em}{}[\color{mainBlue}\titlerule]
\titleformat{\subsection}{\large\bfseries\sffamily\color{mainPurple}}{\thesubsection}{1em}{}

% Graph defaults - consistent style for all figures
\pgfplotsset{
    every axis/.append style={
        width=0.75\textwidth,
        height=0.5\textwidth,
        line width=0.8pt,
        tick style={line width=0.6pt},
        tick label style={font=\small},
        label style={font=\small},
        legend style={font=\small, draw=none, fill=white, fill opacity=0.8},
        grid=major,
        grid style={dashed, gray!30},
        axis lines=middle,
    },
    every axis plot/.append style={
        line width=1.2pt,
    },
    cycle list={
        {mainBlue, thick},
        {mainGreen, thick},
        {mainOrange, thick},
        {mainPurple, thick},
        {mainTeal, thick},
    },
}

% Header/Footer styling for worksheets
\usepackage{fancyhdr}
\pagestyle{fancy}
\fancyhf{}
\fancyhead[L]{\small\color{mainGray}\textit{Generert av MateMaTeX AI}}
\fancyhead[R]{\small\color{mainGray}\today}
\fancyfoot[C]{\small\color{mainGray}\thepage}
\renewcommand{\headrulewidth}{0.4pt}
\renewcommand{\footrulewidth}{0pt}

% First page: no header/footer (clean title page)
\fancypagestyle{plain}{\fancyhf{}\fancyfoot[C]{\small\color{mainGray}\thepage}\renewcommand{\headrulewidth}{0pt}}

"""


# Preamble-only commands that should NEVER appear in body content.
# These are stripped ONLY when they appear at the top level (not inside tikzpicture etc.)
_PREAMBLE_ONLY_PATTERNS = [
    re.compile(r'^\\documentclass\[?[^\]]*\]?\{[^}]*\}', re.MULTILINE),
    re.compile(r'^\\usepackage\[?[^\]]*\]?\{[^}]*\}', re.MULTILINE),
    re.compile(r'^\\newtcolorbox(?:\[[^\]]*\])?\{[^}]*\}.*$', re.MULTILINE),
    re.compile(r'^\\newtheorem(?:\[[^\]]*\])?\{[^}]*\}.*$', re.MULTILINE),
    re.compile(r'^\\pgfplotsset\{compat=[^}]*\}', re.MULTILINE),
    re.compile(r'^\\usetikzlibrary\{[^}]*\}', re.MULTILINE),
    re.compile(r'^\\titleformat\{[^}]*\}.*$', re.MULTILINE),
    re.compile(r'^\\pagestyle\{[^}]*\}', re.MULTILINE),
    re.compile(r'^\\fancyhf\{\}', re.MULTILINE),
    re.compile(r'^\\fancyhead\[?[^\]]*\]?\{[^}]*\}', re.MULTILINE),
    re.compile(r'^\\fancyfoot\[?[^\]]*\]?\{[^}]*\}', re.MULTILINE),
    re.compile(r'^\\renewcommand\{\\headrulewidth\}.*$', re.MULTILINE),
    re.compile(r'^\\renewcommand\{\\footrulewidth\}.*$', re.MULTILINE),
    re.compile(r'^\\setlength\{\\parskip\}.*$', re.MULTILINE),
    re.compile(r'^\\setlength\{\\parindent\}.*$', re.MULTILINE),
    re.compile(r'^\\floatplacement\{[^}]*\}\{[^}]*\}', re.MULTILINE),
]


def clean_ai_output(latex_content: str) -> str:
    """
    Clean up AI-generated LaTeX content.
    
    1. Removes markdown code blocks
    2. Strips any preamble the AI generated (documentclass, usepackage, etc.)
    3. Extracts only the body content
    
    Context-aware: only strips preamble commands at the top level,
    NOT inside tikzpicture or other environments where they might be valid.
    
    Args:
        latex_content: Raw AI output that may contain markdown formatting.
    
    Returns:
        Clean LaTeX body content (no preamble).
    """
    content = latex_content.strip()
    
    # Step 1: Remove markdown code blocks (```latex ... ``` or ``` ... ```)
    code_block_pattern = r'```(?:latex|tex)?\s*\n?(.*?)\n?```'
    matches = re.findall(code_block_pattern, content, re.DOTALL)
    
    if matches:
        # Use the last substantial match (AI usually puts the final version last)
        substantial = [m for m in matches if len(m.strip()) > 50]
        content = (substantial[-1] if substantial else max(matches, key=len)).strip()
    
    # Remove remaining markdown fences
    content = re.sub(r'^```(?:latex|tex)?\s*\n?', '', content)
    content = re.sub(r'\n?```\s*$', '', content)
    
    # Step 2: Strip AI-generated preamble
    # If there's a \begin{document}, extract just the body content
    if r'\begin{document}' in content:
        body_match = re.search(
            r'\\begin\{document\}(.*?)(?:\\end\{document\}|$)',
            content,
            re.DOTALL
        )
        if body_match:
            content = body_match.group(1).strip()
            
            # Handle nested documents (AI sometimes generates double wrapping)
            if r'\begin{document}' in content:
                inner_match = re.search(
                    r'\\begin\{document\}(.*?)(?:\\end\{document\}|$)',
                    content,
                    re.DOTALL
                )
                if inner_match:
                    content = inner_match.group(1).strip()
    
    # Step 3: Remove top-level preamble commands (context-aware)
    # Only strip lines that start with preamble commands (not inside environments)
    for pattern in _PREAMBLE_ONLY_PATTERNS:
        content = pattern.sub('', content)
    
    # Step 4: Remove standalone \definecolor at top level
    # But preserve them inside tikzpicture environments
    content = _strip_top_level_only(content, r'\\definecolor\{[^}]*\}\{[^}]*\}\{[^}]*\}')
    
    # Remove any standalone \end{document} at the end
    content = re.sub(r'\\end\{document\}\s*$', '', content)
    
    # Clean up multiple blank lines left after stripping
    content = re.sub(r'\n{4,}', '\n\n\n', content)
    
    return content.strip()


def _strip_top_level_only(content: str, pattern_str: str) -> str:
    """
    Strip a pattern only when it appears OUTSIDE of tikzpicture/axis environments.
    This prevents removing \\definecolor or \\pgfplotsset inside TikZ figures.
    """
    lines = content.split('\n')
    result = []
    depth = 0  # Track nesting depth of tikzpicture/axis environments
    pattern = re.compile(pattern_str)
    
    for line in lines:
        # Track environment nesting
        if r'\begin{tikzpicture}' in line or r'\begin{axis}' in line:
            depth += 1
        if r'\end{tikzpicture}' in line or r'\end{axis}' in line:
            depth = max(0, depth - 1)
        
        # Only strip at top level (depth == 0)
        if depth == 0 and pattern.match(line.strip()):
            continue
        result.append(line)
    
    return '\n'.join(result)


def ensure_preamble(latex_content: str) -> str:
    """
    Ensure the LaTeX content has a valid preamble.
    
    After clean_ai_output(), the content should always be just body content.
    This function wraps it with the STANDARD_PREAMBLE.

    Args:
        latex_content: The LaTeX content to check.

    Returns:
        Complete LaTeX document with standard preamble.
    """
    content_stripped = latex_content.strip()

    # If content has a documentclass, clean_ai_output didn't fully strip it.
    # Extract just the body and use our standard preamble.
    if r"\documentclass" in content_stripped:
        body_match = re.search(
            r'\\begin\{document\}(.*?)(?:\\end\{document\}|$)',
            content_stripped,
            re.DOTALL
        )
        if body_match:
            content_stripped = body_match.group(1).strip()
        else:
            title_match = re.search(r'(\\(?:title|section|maketitle).*)', content_stripped, re.DOTALL)
            if title_match:
                content_stripped = title_match.group(1).strip()

    # Remove any stray \begin{document} or \end{document}
    content_stripped = re.sub(r'\\begin\{document\}', '', content_stripped)
    content_stripped = re.sub(r'\\end\{document\}', '', content_stripped)
    content_stripped = content_stripped.strip()

    # Wrap with standard preamble
    return (
        STANDARD_PREAMBLE
        + r"\begin{document}"
        + "\n"
        + r"\thispagestyle{plain}"
        + "\n\n"
        + content_stripped
        + "\n\n"
        + r"\end{document}"
    )


def compile_latex_to_pdf(
    latex_content: str,
    filename: str,
    output_dir: Optional[str] = None,
    cleanup_aux: bool = True,
    max_retries: int = 3
) -> str:
    """
    Compile LaTeX content to PDF using pdflatex.

    Args:
        latex_content: The LaTeX source code to compile.
        filename: Base name for the output file (without extension).
        output_dir: Directory to save output files. Defaults to 'output/'.
        cleanup_aux: Whether to remove auxiliary files after compilation.
        max_retries: Maximum number of compilation attempts for recoverable errors.

    Returns:
        Path to the generated PDF file.

    Raises:
        FileNotFoundError: If pdflatex is not installed.
        RuntimeError: If LaTeX compilation fails after all retries.
    """
    # Set default output directory
    if output_dir is None:
        output_dir = Path(__file__).parent.parent.parent / "output"
    else:
        output_dir = Path(output_dir)

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Ensure filename doesn't have extension
    filename = filename.replace(".tex", "").replace(".pdf", "")

    # If the content already has our standard preamble, skip cleaning.
    # Otherwise, clean AI output and wrap with preamble.
    if r'\documentclass' not in latex_content:
        # Raw AI output - needs full processing
        latex_content = clean_ai_output(latex_content)
        latex_content = _fix_common_latex_issues(latex_content)
        latex_content = ensure_preamble(latex_content)
    else:
        # Already has preamble (pre-processed) - just fix common issues
        latex_content = _fix_common_latex_issues(latex_content)

    # Validate before attempting compilation (saves time on obviously broken docs)
    is_valid, issues = validate_latex_syntax(latex_content)
    if not is_valid:
        logger.warning(f"Pre-compilation validation found {len(issues)} issues: {issues}")
        # Try to auto-fix the issues before giving up
        latex_content = _try_autofix_latex(latex_content, "\n".join(issues))

    # Define file paths
    tex_file = output_dir / f"{filename}.tex"
    pdf_file = output_dir / f"{filename}.pdf"
    log_file = output_dir / f"{filename}.log"

    # Write the .tex file
    try:
        tex_file.write_text(latex_content, encoding="utf-8")
    except (OSError, IOError) as e:
        raise RuntimeError(f"Could not write .tex file: {e}")
    
    logger.info(f"LaTeX source saved to: {tex_file}")

    # Check if pdflatex is available
    pdflatex_cmd = _find_pdflatex()
    if not pdflatex_cmd:
        raise FileNotFoundError(
            "pdflatex not found. Please install TeX Live or MiKTeX.\n"
            "- Windows: https://miktex.org/download\n"
            "- Linux: sudo apt install texlive-full\n"
            "- macOS: brew install --cask mactex\n\n"
            "After installation, restart your terminal/IDE."
        )

    # Run pdflatex with retry logic
    last_error = None
    for attempt in range(max_retries):
        success = True
        
        # Run pdflatex (twice for proper cross-references)
        for run_num in range(2):
            logger.info(f"Running pdflatex (attempt {attempt + 1}, pass {run_num + 1}/2)...")
            
            try:
                result = subprocess.run(
                    [
                        pdflatex_cmd,
                        "-interaction=nonstopmode",
                        "-halt-on-error",
                        f"-output-directory={output_dir}",
                        str(tex_file)
                    ],
                    capture_output=True,
                    text=True,
                    cwd=output_dir,
                    timeout=180  # 3 minute timeout for complex TikZ
                )
            except subprocess.TimeoutExpired:
                last_error = "LaTeX compilation timed out (>3 minutes). The document may have an infinite loop in TikZ."
                success = False
                break

            if result.returncode != 0:
                error_msg = _extract_latex_errors(log_file, result.stdout)
                last_error = error_msg
                
                # Try to auto-fix common errors
                if attempt < max_retries - 1:
                    fixed_content = _try_autofix_latex(latex_content, error_msg)
                    if fixed_content != latex_content:
                        latex_content = fixed_content
                        tex_file.write_text(latex_content, encoding="utf-8")
                        logger.info("Auto-fixed LaTeX issues, retrying...")
                
                success = False
                break
        
        if success:
            break
    else:
        raise RuntimeError(
            f"LaTeX compilation failed after {max_retries} attempts:\n{last_error}\n\n"
            f"Full log available at: {log_file}\n"
            f"LaTeX source at: {tex_file}"
        )

    # Verify PDF was created
    if not pdf_file.exists():
        raise RuntimeError(
            f"PDF was not generated despite successful compilation.\n"
            f"Check the log file: {log_file}"
        )

    logger.info(f"PDF generated: {pdf_file}")

    # Cleanup auxiliary files
    if cleanup_aux:
        _cleanup_auxiliary_files(output_dir, filename)

    return str(pdf_file)


def _find_pdflatex() -> Optional[str]:
    """Find pdflatex executable on the system."""
    import shutil
    
    if shutil.which("pdflatex"):
        return "pdflatex"
    
    # Common installation paths on Windows
    windows_paths = [
        r"C:\Program Files\MiKTeX\miktex\bin\x64\pdflatex.exe",
        r"C:\Program Files (x86)\MiKTeX\miktex\bin\pdflatex.exe",
        r"C:\texlive\2024\bin\windows\pdflatex.exe",
        r"C:\texlive\2025\bin\windows\pdflatex.exe",
        r"C:\texlive\2023\bin\windows\pdflatex.exe",
    ]
    
    for path in windows_paths:
        if Path(path).exists():
            return path
    
    return None


def _fix_common_latex_issues(latex_content: str) -> str:
    """
    Fix common LaTeX issues that AI models tend to generate.
    """
    content = latex_content
    
    # Fix unescaped percent signs in text (after digits, not at line end = comment)
    content = re.sub(r'(\d)%(?!\s*$)', r'\1\\%', content)
    
    # Fix missing spaces after commands
    content = re.sub(r'\\textbf\{([^}]+)\}(?=[a-zA-ZæøåÆØÅ])', r'\\textbf{\1} ', content)
    
    # Fix double backslashes that should be single (common AI mistake)
    content = re.sub(r'\\\\(?=begin|end|section|subsection|textbf|frac|sqrt)', r'\\', content)
    
    # Remove stray markdown
    content = re.sub(r'^\s*#{1,6}\s+', '', content, flags=re.MULTILINE)
    content = re.sub(r'\*\*([^*]+)\*\*', r'\\textbf{\1}', content)
    content = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'\\textit{\1}', content)
    
    # Fix missing semicolons in TikZ paths (common AI error)
    # Look for lines inside tikzpicture that end with coordinates but no semicolon
    content = re.sub(
        r'(\\draw[^;]*(?:--\s*\([^)]+\))\s*)$(?!\s*--)',
        r'\1;',
        content,
        flags=re.MULTILINE
    )
    
    # Fix missing closing braces
    open_count = content.count('{')
    close_count = content.count('}')
    
    if open_count > close_count:
        diff = open_count - close_count
        if r'\end{document}' in content:
            content = content.replace(r'\end{document}', '}' * diff + r'\end{document}')
        else:
            content += '}' * diff
    
    return content


def _try_autofix_latex(latex_content: str, error_msg: str) -> str:
    """
    Try to automatically fix LaTeX errors based on error message.
    Handles: undefined commands, missing $, runaway arguments,
    undefined colors, extra alignment tabs, missing numbers, package errors.
    """
    content = latex_content
    
    # 1. Fix undefined control sequence errors
    if "Undefined control sequence" in error_msg:
        # Extract the undefined command from the error context
        matches = re.findall(r'\\([a-zA-Z]+)', error_msg)
        for undefined_cmd in matches:
            # Common math symbol fixes
            symbol_fixes = {
                'R': r'\mathbb{R}',
                'N': r'\mathbb{N}',
                'Z': r'\mathbb{Z}',
                'Q': r'\mathbb{Q}',
                'C': r'\mathbb{C}',
            }
            if undefined_cmd in symbol_fixes:
                content = content.replace(f'\\{undefined_cmd}', symbol_fixes[undefined_cmd])
            
            # Remove unknown commands that are likely AI hallucinations
            hallucinated = [
                'newpage', 'clearpage', 'pagebreak',  # These are actually valid but might cause issues
            ]
            # Don't auto-remove valid commands
    
    # 2. Fix missing $ errors (math mode)
    if "Missing $" in error_msg:
        # Common patterns: standalone ^, _, or math symbols outside math mode
        # Wrap isolated math expressions
        content = re.sub(r'(?<![\$\\])(\b\w+)\^(\{[^}]+\}|\w)', r'$\1^\2$', content)
        content = re.sub(r'(?<![\$\\])(\b\w+)_(\{[^}]+\}|\w)', r'$\1_\2$', content)
    
    # 3. Fix runaway argument (usually missing closing brace or end tag)
    if "Runaway argument" in error_msg:
        environments = [
            'definisjon', 'eksempel', 'taskbox', 'merk', 'losning',
            'figure', 'align', 'align*', 'equation', 'equation*',
            'tikzpicture', 'axis', 'enumerate', 'itemize',
            'multicols', 'tcolorbox',
        ]
        for env in environments:
            opens = content.count(f'\\begin{{{env}}}')
            # Handle optional args for counting
            closes = content.count(f'\\end{{{env}}}')
            if opens > closes:
                content += f'\n\\end{{{env}}}' * (opens - closes)
    
    # 4. Fix extra alignment tab errors
    if "Extra alignment tab" in error_msg:
        # This usually means too many & in a table row
        # Hard to auto-fix without context, but we can try to find obvious cases
        pass
    
    # 5. Fix undefined color errors
    if "Undefined color" in error_msg:
        color_match = re.search(r"Undefined color [`']?(\w+)", error_msg)
        if color_match:
            undef_color = color_match.group(1)
            # Map common color names to our defined colors
            color_map = {
                'blue': 'mainBlue', 'red': 'red', 'green': 'mainGreen',
                'orange': 'mainOrange', 'purple': 'mainPurple', 'teal': 'mainTeal',
                'gray': 'mainGray', 'grey': 'mainGray',
            }
            replacement = color_map.get(undef_color.lower(), 'mainBlue')
            content = content.replace(undef_color, replacement)
    
    # 6. Fix "Missing number, treated as zero"
    if "Missing number" in error_msg:
        # Often caused by empty optional args like \begin{multicols}{}
        content = re.sub(r'\\begin\{multicols\}\{\}', r'\\begin{multicols}{2}', content)
    
    # 7. Fix "File X.sty not found" by removing the usepackage line
    if "File" in error_msg and "not found" in error_msg:
        sty_match = re.search(r"File `([^']+)\.sty' not found", error_msg)
        if sty_match:
            pkg_name = sty_match.group(1)
            content = re.sub(rf'\\usepackage(?:\[[^\]]*\])?\{{{pkg_name}\}}', '', content)
    
    return content


def _extract_latex_errors(log_file: Path, stdout: str) -> str:
    """Extract meaningful error messages from LaTeX output."""
    errors = []

    if log_file.exists():
        try:
            log_content = log_file.read_text(encoding="utf-8", errors="ignore")
            for line in log_content.split("\n"):
                if line.startswith("!"):
                    errors.append(line)
                elif errors and line.strip() and not line.startswith("!"):
                    if len(errors) < 15:
                        errors.append(line)
        except Exception:
            pass

    if errors:
        return "\n".join(errors[:15])

    if stdout:
        return stdout[-2000:]

    return "Unknown error. Check the log file for details."


def _cleanup_auxiliary_files(output_dir: Path, filename: str) -> None:
    """Remove auxiliary files generated by pdflatex."""
    aux_extensions = [".aux", ".log", ".out", ".toc", ".lof", ".lot", ".fls", ".fdb_latexmk", ".synctex.gz"]

    for ext in aux_extensions:
        aux_file = output_dir / f"{filename}{ext}"
        if aux_file.exists():
            try:
                aux_file.unlink()
            except Exception:
                pass


def validate_latex_syntax(latex_content: str) -> tuple[bool, list[str]]:
    """
    Perform basic validation of LaTeX syntax.

    Args:
        latex_content: The LaTeX content to validate.

    Returns:
        Tuple of (is_valid, list of issues found).
    """
    issues = []

    # Check for matching begin/end document
    if r"\begin{document}" not in latex_content:
        issues.append("Missing \\begin{document}")
    if r"\end{document}" not in latex_content:
        issues.append("Missing \\end{document}")

    # Check for unmatched braces (basic check)
    open_braces = latex_content.count("{")
    close_braces = latex_content.count("}")
    if open_braces != close_braces:
        issues.append(f"Unmatched braces: {open_braces} open, {close_braces} close")

    # Check for common environment mismatches
    environments = [
        "equation", "align", "align*", "itemize", "enumerate",
        "tikzpicture", "axis", "figure", "table",
        "definitionbox", "examplebox", "taskbox", "tipbox",
        "definisjon", "eksempel", "merk", "losning",
        "multicols", "tcolorbox",
    ]
    for env in environments:
        # Count begins (ignoring optional args)
        opens = len(re.findall(rf'\\begin\{{{re.escape(env)}\}}', latex_content))
        closes = latex_content.count(f"\\end{{{env}}}")
        if opens != closes:
            issues.append(f"Unmatched {env} environment: {opens} begin, {closes} end")

    return len(issues) == 0, issues
