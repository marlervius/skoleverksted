"""
MateMaTeX document preamble.

Engine-agnostic: the same document compiles under LuaLaTeX/XeLaTeX (professional
OpenType fonts via fontspec + unicode-math) and under pdfLaTeX (Latin Modern
fallback). The active engine is chosen at compile time; this preamble branches on
``\\ifLuaTeX`` / ``\\ifXeTeX`` so a single body works everywhere.

Features:
- Theme system (color palettes): default, calm, playful, highcontrast
- Pedagogical macros: answer lines/grids, points, level markers, QR codes
- Accessibility: PDF language metadata, opt-in tagged PDF, dyslexia-friendly mode
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Themes — each maps the shared color names to an RGB triple "R,G,B".
# Boxes/sections reference these names, so swapping the palette reskins
# the whole document.
# ---------------------------------------------------------------------------
THEMES: dict[str, dict[str, str]] = {
    "default": {
        "mainBlue": "0,102,204", "lightBlue": "230,242,255",
        "mainGreen": "0,153,76", "lightGreen": "232,250,240",
        "mainOrange": "230,126,34", "lightOrange": "255,245,235",
        "mainPurple": "102,51,153", "lightPurple": "245,240,255",
        "mainTeal": "0,128,128", "lightTeal": "235,250,250",
        "mainGray": "80,80,90", "lightGray": "248,248,252",
        "mainRed": "200,55,55", "lightRed": "253,238,238",
    },
    # Softer, desaturated — calm reading experience
    "calm": {
        "mainBlue": "70,110,150", "lightBlue": "238,244,249",
        "mainGreen": "82,138,108", "lightGreen": "240,247,243",
        "mainOrange": "190,140,90", "lightOrange": "250,245,238",
        "mainPurple": "120,110,160", "lightPurple": "245,243,250",
        "mainTeal": "70,135,135", "lightTeal": "239,247,247",
        "mainGray": "95,100,110", "lightGray": "247,248,250",
        "mainRed": "170,90,90", "lightRed": "250,242,242",
    },
    # Brighter, friendlier — lower grades
    "playful": {
        "mainBlue": "0,140,220", "lightBlue": "224,243,255",
        "mainGreen": "30,180,90", "lightGreen": "226,250,236",
        "mainOrange": "245,140,30", "lightOrange": "255,243,228",
        "mainPurple": "150,70,200", "lightPurple": "245,235,255",
        "mainTeal": "0,170,170", "lightTeal": "224,250,250",
        "mainGray": "90,90,100", "lightGray": "247,247,250",
        "mainRed": "230,60,70", "lightRed": "255,235,236",
    },
    # Strong contrast for visual accessibility (WCAG-friendly)
    "highcontrast": {
        "mainBlue": "0,51,153", "lightBlue": "255,255,255",
        "mainGreen": "0,102,51", "lightGreen": "255,255,255",
        "mainOrange": "170,70,0", "lightOrange": "255,255,255",
        "mainPurple": "85,0,128", "lightPurple": "255,255,255",
        "mainTeal": "0,90,90", "lightTeal": "255,255,255",
        "mainGray": "20,20,20", "lightGray": "255,255,255",
        "mainRed": "153,0,0", "lightRed": "255,255,255",
    },
}

DEFAULT_THEME = "default"


def _color_block(theme: str) -> str:
    palette = THEMES.get(theme, THEMES[DEFAULT_THEME])
    lines = [f"\\definecolor{{{name}}}{{RGB}}{{{rgb}}}" for name, rgb in palette.items()]
    return "\n".join(lines)


def _text_font_block(*, dyslexia: bool) -> str:
    """
    Engine-conditional TEXT font setup (loaded early).

    Under LuaLaTeX/XeLaTeX we use professional OpenType fonts (Libertinus +
    Lato). Under pdfLaTeX we fall back to Latin Modern. Dyslexia mode makes the
    sans family the document default.

    The math font (unicode-math) is set later in :func:`_math_font_block`, after
    the other math packages, which is required for a clean load order.
    """
    # Whether the body should default to sans (dyslexia-friendly).
    lua_main = "Lato" if dyslexia else "Libertinus Serif"
    pdf_family_default = r"\renewcommand{\familydefault}{\sfdefault}" if dyslexia else ""
    return rf"""
\usepackage{{iftex}}
\ifLuaTeX
  \usepackage{{fontspec}}
  \IfFontExistsTF{{{lua_main}}}{{\setmainfont{{{lua_main}}}}}{{}}
  \IfFontExistsTF{{Lato}}{{\setsansfont{{Lato}}}}{{}}
\else\ifXeTeX
  \usepackage{{fontspec}}
  \IfFontExistsTF{{{lua_main}}}{{\setmainfont{{{lua_main}}}}}{{}}
  \IfFontExistsTF{{Lato}}{{\setsansfont{{Lato}}}}{{}}
\else
  \usepackage[utf8]{{inputenc}}
  \usepackage[T1]{{fontenc}}
  \usepackage{{lmodern}}
  {pdf_family_default}
\fi\fi
\usepackage{{microtype}}
"""


# Loaded AFTER amsmath/mathtools/amsthm so unicode-math overrides cleanly.
# Under pdfLaTeX this is a no-op (Latin Modern math is used).
_MATH_FONT_BLOCK = r"""
\ifLuaTeX
  \usepackage{unicode-math}
  \IfFontExistsTF{Libertinus Math}{\setmathfont{Libertinus Math}}{}
\else\ifXeTeX
  \usepackage{unicode-math}
  \IfFontExistsTF{Libertinus Math}{\setmathfont{Libertinus Math}}{}
\fi\fi
"""


def build_preamble(
    theme: str = DEFAULT_THEME,
    *,
    student_mode: bool = False,
    accessible: bool = False,
    dyslexia: bool = False,
    high_contrast: bool = False,
) -> str:
    """
    Build a complete LaTeX preamble (everything before \\begin{document}).

    Args:
        theme: Color palette name (see THEMES).
        student_mode: Reserved — adds answer lines in task boxes for student copies.
        accessible: Emit PDF language metadata and opt into tagged-PDF mode.
        dyslexia: Sans-serif body + generous leading and spacing.
        high_contrast: Force the high-contrast palette regardless of `theme`.
    """
    if high_contrast:
        theme = "highcontrast"
    if theme not in THEMES:
        theme = DEFAULT_THEME

    # NOTE: full PDF/UA tagging via \DocumentMetadata needs pdfmanagement
    # (TeX Live 2023+ with pdfmanagement-testphase). That package is not
    # guaranteed to be present, and \DocumentMetadata must precede
    # \documentclass so it cannot be guarded with \IfFileExists. We therefore
    # deliver the accessibility win that actually matters for screen readers —
    # the document language — via hyperref's pdflang (set below) instead.
    doc_meta = ""

    leading = r"\linespread{1.5}" if dyslexia else r"\linespread{1.08}"
    parskip = "1.0em" if dyslexia else "0.8em"

    pdflang = r"pdflang=nb-NO, " if accessible else ""

    student_block = ""
    if student_mode:
        student_block = r"""
% ---- Elevkopi: plass til svar under oppgaver ----
\tcbset{
  taskbox/.append style={
    after upper={\par\vspace{1.6cm}\noindent\textcolor{gray!55}{\rule{0.42\textwidth}{0.35pt}}}
  }
}
"""

    return (
        doc_meta
        + r"\documentclass[a4paper,11pt]{article}" + "\n"
        + r"\usepackage[norsk]{babel}" + "\n"
        + _text_font_block(dyslexia=dyslexia)
        + _MATH_GRAPHICS_LAYOUT
        + _MATH_FONT_BLOCK
        + f"\n% ---- Theme: {theme} ----\n"
        + _color_block(theme)
        + "\n"
        + rf"\usepackage[colorlinks=true, {pdflang}linkcolor=mainBlue, urlcolor=mainBlue, citecolor=mainGreen]{{hyperref}}"
        + "\n"
        + _BOXES
        + _MATH_COMMANDS
        + _SECTION_STYLING
        + _PGFPLOTS_DEFAULTS
        + _FIGURE_MACROS
        + _PEDAGOGICAL_MACROS
        + _HEADER_FOOTER
        + student_block
        + f"\n% ---- Spacing ----\n{leading}\n"
        + rf"\setlength{{\parskip}}{{{parskip}}}" + "\n"
        + r"\setlength{\parindent}{0pt}" + "\n"
        + r"\setlist{itemsep=0.3em, parsep=0.2em, topsep=0.3em}" + "\n"
        + _LAYOUT_HARDENING
    )


# Track E: preventive line-breaking so most "Overfull \hbox" warnings never
# occur. \emergencystretch lets TeX stretch a paragraph rather than overflow;
# \hfuzz hides sub-point overfulls; widow/club penalties avoid orphan lines.
_LAYOUT_HARDENING = r"""
% ---- Layout robustness ----
\setlength{\emergencystretch}{3em}
\tolerance=1200
\hbadness=2000
\hfuzz=1pt
\widowpenalty=10000
\clubpenalty=10000
\raggedbottom
"""


# ---------------------------------------------------------------------------
# Static building blocks (engine-independent)
# ---------------------------------------------------------------------------
_MATH_GRAPHICS_LAYOUT = r"""
% Mathematics
\usepackage{mathtools}
\usepackage{amsthm}
% amssymb clashes with unicode-math (\eth etc.), so only load it on pdfLaTeX.
\ifLuaTeX\else\ifXeTeX\else\usepackage{amssymb}\fi\fi
\usepackage{bm}
\usepackage{siunitx}

% Graphics
\usepackage{tikz, pgfplots}
\pgfplotsset{compat=1.18}
\usetikzlibrary{%
  arrows.meta, calc, patterns, positioning, shapes.geometric,%
  decorations.pathreplacing, decorations.pathmorphing, decorations.markings,%
  angles, quotes, intersections, through,%
  3d, perspective,%
  shadings, fadings,%
  matrix, fit, backgrounds%
}

% Layout
\usepackage[margin=2.5cm]{geometry}
\usepackage{float}
\usepackage{parskip}
\usepackage{enumitem}
\usepackage{booktabs}
\usepackage{multicol}
% Optional packages — degrade gracefully if a TeX install lacks them.
\IfFileExists{qrcode.sty}{\usepackage{qrcode}}{\providecommand{\qrcode}[2][]{\fbox{QR}}}
\IfFileExists{pifont.sty}{\usepackage{pifont}}{\providecommand{\ding}[1]{$\star$}}
\floatplacement{figure}{H}

% Colored boxes
\usepackage{xcolor}
\usepackage[most]{tcolorbox}
"""

_BOXES = r"""
% Shared box style
\tcbset{matebox/.style={
  enhanced, breakable,
  arc=3mm,
  left=8pt, right=8pt, top=8pt, bottom=8pt,
  attach boxed title to top left={yshift*=-\tcboxedtitleheight/2, xshift=5mm},
  sharp corners=downhill,
  drop fuzzy shadow=black!12,
}}

\newtcolorbox{definitionbox}[1][]{matebox, colback=lightBlue, colframe=mainBlue,
  fonttitle=\bfseries\sffamily, title={Definisjon},
  boxed title style={colback=mainBlue, colframe=mainBlue}, #1}
\newtcolorbox{definisjon}[1][]{matebox, colback=lightBlue, colframe=mainBlue,
  fonttitle=\bfseries\sffamily, title={Definisjon},
  boxed title style={colback=mainBlue, colframe=mainBlue}, #1}

\newtcolorbox{examplebox}[1][]{matebox, colback=lightGreen, colframe=mainGreen,
  fonttitle=\bfseries\sffamily, title={Eksempel},
  boxed title style={colback=mainGreen, colframe=mainGreen}, #1}
\newtcolorbox{eksempel}[1][]{matebox, colback=lightGreen, colframe=mainGreen,
  fonttitle=\bfseries\sffamily, title={Eksempel},
  boxed title style={colback=mainGreen, colframe=mainGreen}, #1}

\newtcolorbox{taskbox}[1][]{matebox, colback=lightPurple, colframe=mainPurple,
  fonttitle=\bfseries\sffamily\color{white}, title={#1},
  boxed title style={colback=mainPurple, colframe=mainPurple},
  left=10pt, right=10pt, top=10pt, bottom=10pt}

\newtcolorbox{tipbox}[1][]{matebox, colback=lightOrange, colframe=mainOrange,
  fonttitle=\bfseries\sffamily, title={Tips},
  boxed title style={colback=mainOrange, colframe=mainOrange}, #1}
\newtcolorbox{merk}[1][]{matebox, colback=lightOrange, colframe=mainOrange,
  fonttitle=\bfseries\sffamily, title={Merk!},
  boxed title style={colback=mainOrange, colframe=mainOrange}, #1}

\newtcolorbox{losning}[1][]{matebox, colback=lightTeal, colframe=mainTeal,
  fonttitle=\bfseries\sffamily\color{white}, title={Løsning},
  boxed title style={colback=mainTeal, colframe=mainTeal},
  left=10pt, right=10pt, top=10pt, bottom=10pt, #1}

% Assessment / grading criteria box (gray)
\newtcolorbox{vurdering}[1][]{matebox, colback=lightGray, colframe=mainGray,
  fonttitle=\bfseries\sffamily, title={Vurdering},
  boxed title style={colback=mainGray, colframe=mainGray}, #1}

% ---- Textbook-style boxes (lærebok-bokser) ----

% Rule / theorem / formula — the box pupils memorise. Strong red frame like
% Norwegian textbooks use for "Regel"/"Setning".
\newtcolorbox{regel}[1][]{matebox, colback=lightRed, colframe=mainRed,
  fonttitle=\bfseries\sffamily, title={Regel},
  boxed title style={colback=mainRed, colframe=mainRed}, #1}
\newtcolorbox{setning}[1][]{matebox, colback=lightRed, colframe=mainRed,
  fonttitle=\bfseries\sffamily, title={Setning},
  boxed title style={colback=mainRed, colframe=mainRed}, #1}

% Recall of prior knowledge — chapter openers ("Husk fra før")
\newtcolorbox{husk}[1][]{enhanced, breakable, arc=2mm,
  colback=lightTeal, colframe=mainTeal!70,
  borderline west={2.5pt}{0pt}{mainTeal},
  fonttitle=\bfseries\sffamily\color{mainTeal}, title={Husk fra før},
  left=8pt, right=8pt, top=6pt, bottom=6pt, #1}

% Common mistake / misconception — shows the wrong way and the right way
\newtcolorbox{vanligfeil}[1][]{enhanced, breakable, arc=2mm,
  colback=lightRed, colframe=mainRed!70,
  borderline west={2.5pt}{0pt}{mainRed},
  fonttitle=\bfseries\sffamily\color{mainRed}, title={Vanlig feil},
  left=8pt, right=8pt, top=6pt, bottom=6pt, #1}

% Exploration / inquiry activity ("Utforsk") — open-ended thinking task
\newtcolorbox{utforsk}[1][]{enhanced, breakable, arc=2mm,
  colback=lightPurple, colframe=mainPurple!70,
  borderline west={2.5pt}{0pt}{mainPurple},
  fonttitle=\bfseries\sffamily\color{mainPurple}, title={Utforsk},
  left=8pt, right=8pt, top=6pt, bottom=6pt, #1}

% Learning goals — chapter opener ("I dette kapittelet lærer du å ...")
\newtcolorbox{laeringsmaal}[1][]{enhanced, breakable, arc=2mm,
  colback=lightBlue, colframe=mainBlue!60,
  borderline west={2.5pt}{0pt}{mainBlue},
  fonttitle=\bfseries\sffamily\color{mainBlue}, title={I dette kapittelet lærer du å},
  left=8pt, right=8pt, top=6pt, bottom=6pt, #1}

% Chapter summary — collects the key formulas/methods
\newtcolorbox{oppsummering}[1][]{matebox, colback=lightBlue, colframe=mainBlue,
  fonttitle=\bfseries\sffamily, title={Sammendrag},
  boxed title style={colback=mainBlue, colframe=mainBlue}, #1}

% Theorem environments (fallback)
\newtheorem{theorem}{Teorem}[section]
\newtheorem{definition}[theorem]{Definisjon}
\newtheorem{example}[theorem]{Eksempel}
\newtheorem{exercise}{Oppgave}[section]
"""

_MATH_COMMANDS = r"""
\newcommand{\N}{\mathbb{N}}
\newcommand{\Z}{\mathbb{Z}}
\newcommand{\Q}{\mathbb{Q}}
\newcommand{\R}{\mathbb{R}}

% Norwegian number and unit conventions (siunitx).
% Only keys supported by both siunitx v2 and v3 — exotic keys break on
% mixed TeX installs.
\sisetup{
  output-decimal-marker = {,},
  group-separator = {\,},
  group-minimum-digits = 5,
}

% Step justification in align-environments, textbook style:
%   2x &= 8 && \forklaring{del begge sider på 2}
\newcommand{\forklaring}[1]{\text{\small\color{mainGray}#1}}

% Consistent display-math spacing + allow page breaks in long align-blocks
\allowdisplaybreaks[1]
\AtBeginDocument{%
  \setlength{\abovedisplayskip}{0.6em plus 0.2em minus 0.2em}%
  \setlength{\belowdisplayskip}{0.6em plus 0.2em minus 0.2em}%
  \setlength{\abovedisplayshortskip}{0.3em}%
  \setlength{\belowdisplayshortskip}{0.4em}%
}
"""

_SECTION_STYLING = r"""
\usepackage{titlesec}
\titleformat{\section}{\Large\bfseries\sffamily\color{mainBlue}}{\thesection}{1em}{}[\color{mainBlue}\titlerule]
\titleformat{\subsection}{\large\bfseries\sffamily\color{mainPurple}}{\thesubsection}{1em}{}
"""

_PGFPLOTS_DEFAULTS = r"""
\pgfplotsset{
    every axis/.append style={
        width=0.75\textwidth, height=0.5\textwidth,
        line width=0.8pt,
        tick style={line width=0.6pt},
        tick label style={font=\small}, label style={font=\small},
        legend style={font=\small, draw=none, fill=white, fill opacity=0.8},
        grid=major, grid style={dashed, gray!30},
        axis lines=middle,
    },
    every axis plot/.append style={line width=1.2pt},
    cycle list={{mainBlue, thick},{mainGreen, thick},{mainOrange, thick},{mainPurple, thick},{mainTeal, thick}},
}
"""

# Existing \MMA figure macros (geometry/diagrams)
_FIGURE_MACROS = r"""
% ============================================================
% MateMaTeX Figure Macros — AI calls these, never raw TikZ
% ============================================================
\newcommand{\MMArettvinklet}[3]{%
  \begin{tikzpicture}[scale=0.9, font=\small]
    \coordinate (A) at (0,0); \coordinate (B) at (#1,0); \coordinate (C) at (#1,#2);
    \fill[lightBlue!60] (A) -- (B) -- (C) -- cycle;
    \draw[thick, mainBlue] (A) -- (B) -- (C) -- cycle;
    \draw[mainBlue] (#1,0.3) -- (#1-0.3,0.3) -- (#1-0.3,0);
    \node[below] at (#1/2,0) {$a = #1$}; \node[right] at (#1,#2/2) {$b = #2$};
    \node[above left] at (#1/2,#2/2) {$c = #3$};
    \node[below left] at (A) {$A$}; \node[below right] at (B) {$B$}; \node[above right] at (C) {$C$};
  \end{tikzpicture}%
}
\newcommand{\MMAtrigfig}{%
  \begin{tikzpicture}[scale=0.85, font=\small]
    \coordinate (O) at (0,0); \coordinate (A) at (5,0); \coordinate (B) at (5,3.75);
    \fill[lightBlue!50] (O) -- (A) -- (B) -- cycle;
    \draw[thick, mainBlue] (O) -- (A) -- (B) -- cycle;
    \draw[mainBlue] (5,0.35) -- (4.65,0.35) -- (4.65,0);
    \draw[mainOrange, thick] (0.8,0) arc(0:36.87:0.8);
    \node at (1.2,0.28) {$v$};
    \node[below, mainBlue] at (2.5,0) {Hosliggende};
    \node[right, mainBlue] at (5,1.875) {Motstående};
    \node[above left, mainBlue] at (2.5,2.0) {Hypotenus};
    \node[below left] at (O) {$O$}; \node[below right] at (A) {$A$}; \node[above right] at (B) {$B$};
  \end{tikzpicture}%
}
\newcommand{\MMArektangel}[2]{%
  \begin{tikzpicture}[scale=0.8, font=\small]
    \fill[lightBlue!40] (0,0) rectangle (#1,#2);
    \draw[thick, mainBlue] (0,0) rectangle (#1,#2);
    \node at (#1/2, #2/2) {$A = #1 \cdot #2$};
    \draw[<->, mainOrange, thick] (0,-0.5) -- (#1,-0.5) node[midway,below] {$#1$ cm};
    \draw[<->, mainOrange, thick] (#1+0.5,0) -- (#1+0.5,#2) node[midway,right] {$#2$ cm};
  \end{tikzpicture}%
}
\newcommand{\MMAsylinder}{%
  \begin{tikzpicture}[scale=0.7, font=\small]
    \fill[lightBlue!30] (-1.2,-2.5) arc(180:360:1.2 and 0.4) -- (1.2,0) arc(0:180:1.2 and 0.4) -- cycle;
    \fill[lightBlue!50] (0,0) ellipse (1.2 and 0.4);
    \draw[thick, mainBlue] (0,0) ellipse (1.2 and 0.4);
    \draw[thick, mainBlue] (-1.2,0) -- (-1.2,-2.5);
    \draw[thick, mainBlue] (1.2,0) -- (1.2,-2.5);
    \draw[thick, mainBlue] (0,-2.5) ellipse (1.2 and 0.4);
    \draw[<->, mainOrange, thick] (1.6,0) -- (1.6,-2.5) node[midway,right]{$h$};
    \draw[<->, mainOrange, thick] (0,0) -- (1.2,0) node[midway,above]{$r$};
    \node[below] at (0,-3.1) {Sylinder};
  \end{tikzpicture}%
}
\newcommand{\MMAkjegle}{%
  \begin{tikzpicture}[scale=0.7, font=\small]
    \fill[lightBlue!30] (-1.2,-2.5) -- (0,0) -- (1.2,-2.5) arc(0:-180:1.2 and 0.4) -- cycle;
    \draw[thick, mainBlue] (-1.2,-2.5) -- (0,0) -- (1.2,-2.5);
    \draw[thick, mainBlue] (0,-2.5) ellipse (1.2 and 0.4);
    \draw[<->, mainOrange, thick] (1.6,0) -- (1.6,-2.5) node[midway,right]{$h$};
    \draw[<->, mainOrange, thick] (0,-2.5) -- (1.2,-2.5) node[midway,below]{$r$};
    \node[below] at (0,-3.1) {Kjegle};
  \end{tikzpicture}%
}
\newcommand{\MMAkule}{%
  \begin{tikzpicture}[scale=0.7, font=\small]
    \fill[lightBlue!30] (0,0) circle (1.5);
    \draw[thick, mainBlue] (0,0) circle (1.5);
    \draw[thick, mainBlue, dashed] (0,0) ellipse (1.5 and 0.45);
    \draw[<->, mainOrange, thick] (0,0) -- (1.5,0) node[midway,above]{$r$};
    \node[below] at (0,-1.9) {Kule};
  \end{tikzpicture}%
}
\newcommand{\MMAromfigurer}{%
  \begin{figure}[H]\centering
  \MMAsylinder\qquad\MMAkjegle\qquad\MMAkule
  \caption{Sylinder, kjegle og kule med radius $r$ og høyde $h$.}
  \end{figure}%
}
\newcommand{\MMAprosent}[1]{%
  \begin{tikzpicture}[scale=0.35, font=\scriptsize]
    \foreach \r in {0,...,9} {
      \foreach \c in {0,...,9} {
        \pgfmathsetmacro{\idx}{int(\r*10 + \c + 1)}
        \ifnum\idx>#1 \fill[lightGray] (\c,\r) rectangle (\c+1,\r+1);
        \else \fill[mainBlue!70] (\c,\r) rectangle (\c+1,\r+1); \fi
        \draw[white, thin] (\c,\r) rectangle (\c+1,\r+1);
      }
    }
    \draw[thick, mainBlue] (0,0) rectangle (10,10);
  \end{tikzpicture}%
}
\newcommand{\MMAvektor}[2]{%
  \begin{tikzpicture}[scale=0.85, font=\small, >=Stealth]
    \draw[lightGray, thin] (-0.5,-0.5) grid (#1+0.5,#2+0.5);
    \draw[thick, ->] (-0.5,0) -- (#1+0.8,0) node[right] {$x$};
    \draw[thick, ->] (0,-0.5) -- (0,#2+0.8) node[above] {$y$};
    \foreach \x in {1,...,#1} { \node[below, font=\scriptsize] at (\x,-0.15) {\x}; }
    \foreach \y in {1,...,#2} { \node[left, font=\scriptsize] at (-0.15,\y) {\y}; }
    \node[below left, font=\scriptsize] at (0,0) {$0$};
  \end{tikzpicture}%
}
"""

# Pedagogical macros: answer space, points, difficulty, QR, page break, cover.
_PEDAGOGICAL_MACROS = r"""
% ============================================================
% Pedagogical macros — student-facing layout helpers
% ============================================================

% \MMAsvarlinjer[n] — n ruled answer lines (default 3)
\newcommand{\MMAsvarlinjer}[1][3]{%
  \par\vspace{0.4em}%
  \foreach \mmaln in {1,...,#1}{\noindent\textcolor{mainGray!55}{\rule{\linewidth}{0.4pt}}\par\vspace{1.15em}}%
}

% \MMAsvarfelt[height] — empty boxed answer area (default 3cm)
\newcommand{\MMAsvarfelt}[1][3cm]{%
  \par\vspace{0.3em}%
  \noindent\fcolorbox{mainGray!40}{white}{\begin{minipage}[t][#1]{\dimexpr\linewidth-2\fboxsep\relax}\strut\end{minipage}}%
  \par\vspace{0.3em}%
}

% \MMArutefelt{cols}{rows} — squared-paper answer grid (5mm cells)
\newcommand{\MMArutefelt}[2]{%
  \par\vspace{0.3em}\noindent
  \begin{tikzpicture}
    \draw[step=0.5cm, mainGray!25, very thin] (0,0) grid (#1*0.5,#2*0.5);
    \draw[mainGray!50, thin] (0,0) rectangle (#1*0.5,#2*0.5);
  \end{tikzpicture}\par\vspace{0.3em}%
}

% \MMApoeng{n} — right-aligned points badge for tests
\newcommand{\MMApoeng}[1]{\hfill{\small\bfseries\color{mainGray}(#1 p)}}

% \MMAniva{1..3} — difficulty stars (filled/empty)
\newcommand{\MMAniva}[1]{%
  \textcolor{mainOrange}{%
    \ifcase#1\relax
      \or \ding{72}\ding{73}\ding{73}%
      \or \ding{72}\ding{72}\ding{73}%
      \else \ding{72}\ding{72}\ding{72}%
    \fi}%
}

% \MMAqr{url} — QR code to a digital resource (solutions, GeoGebra ...)
\newcommand{\MMAqr}[1]{\qrcode[height=2cm]{#1}}
\newcommand{\MMAqrtekst}[2]{%
  \begin{center}\qrcode[height=2cm]{#1}\\[0.3em]{\small\color{mainGray}#2}\end{center}%
}

% \MMAnyside — force a page break (one task per page)
\newcommand{\MMAnyside}{\clearpage}

% \MMAforside{tittel}{undertittel}{skole}{laerer} — polished cover page
\newcommand{\MMAforside}[4]{%
  \thispagestyle{empty}%
  \begin{titlepage}
  \centering
  \vspace*{3cm}
  {\color{mainBlue}\rule{\linewidth}{2pt}}\\[0.6cm]
  {\Huge\bfseries\sffamily #1}\\[0.4cm]
  {\LARGE\sffamily\color{mainGray} #2}\\[0.3cm]
  {\color{mainBlue}\rule{\linewidth}{2pt}}\\[2cm]
  {\large #3}\\[0.4cm]
  {\large #4}\\[0.4cm]
  {\large \today}\\
  \vfill
  {\small\color{mainGray} Generert av MateMaTeX}
  \end{titlepage}%
}
"""

_HEADER_FOOTER = r"""
\usepackage{fancyhdr}
\pagestyle{fancy}
\fancyhf{}
\fancyhead[L]{\small\color{mainGray}\textit{Generert av MateMaTeX}}
\fancyhead[R]{\small\color{mainGray}\today}
\fancyfoot[C]{\small\color{mainGray}\thepage}
\renewcommand{\headrulewidth}{0.4pt}
\renewcommand{\footrulewidth}{0pt}
\fancypagestyle{plain}{\fancyhf{}\fancyfoot[C]{\small\color{mainGray}\thepage}\renewcommand{\headrulewidth}{0pt}}
"""


# Backwards-compatible default preamble (default theme, pdf-safe).
STANDARD_PREAMBLE = build_preamble()


def wrap_with_preamble(
    body_content: str,
    *,
    theme: str = DEFAULT_THEME,
    student_mode: bool = False,
    accessible: bool = False,
    dyslexia: bool = False,
    high_contrast: bool = False,
) -> str:
    """
    Wrap body content with a complete preamble.

    Keyword options select theme/accessibility. With no options the output is
    equivalent to the classic default document, so existing callers are
    unaffected.
    """
    body = body_content.strip()
    preamble = build_preamble(
        theme,
        student_mode=student_mode,
        accessible=accessible,
        dyslexia=dyslexia,
        high_contrast=high_contrast,
    )
    return (
        preamble
        + r"\begin{document}"
        + "\n"
        + r"\thispagestyle{plain}"
        + "\n\n"
        + body
        + "\n\n"
        + r"\end{document}"
    )


# ── Grunnlov §1: verification trust markers in the PDF ─────────────────────

VERIFIED_FASIT_BANNER = r"""
\begin{merk}[title={SymPy-verifisert fasit}]
Alle utregninger som kunne kontrolleres maskinelt, er sjekket med SymPy før utlevering.
\end{merk}
\vspace{0.4em}
"""

LAERERKONTROLL_BANNER = r"""
\begin{merk}[title={Lærer kontroll anbefales}]
Noen oppgaver (f.eks.\ «vis at», geometriske bevis, modellering eller tolkning) kunne ikke verifiseres automatisk.
Kontroller fasit manuelt før du bruker materialet i undervisningen.
\end{merk}
\vspace{0.4em}
"""


def inject_verification_banner(body: str, *, verified: bool, needs_teacher_review: bool) -> str:
    """Prepend a trust marker to the document body (grunnlov §1)."""
    parts: list[str] = []
    if verified:
        parts.append(VERIFIED_FASIT_BANNER.strip())
    if needs_teacher_review:
        parts.append(LAERERKONTROLL_BANNER.strip())
    if not parts:
        return body
    return "\n\n".join(parts) + "\n\n" + body.lstrip()


def wrap_with_style(body_content: str, style: object | None = None) -> str:
    """
    Convenience wrapper that reads options off a duck-typed style object
    (e.g. ``PipelineState.request.pdf_style``). ``None`` reproduces defaults.
    """
    if style is None:
        return wrap_with_preamble(body_content)
    return wrap_with_preamble(
        body_content,
        theme=getattr(style, "theme", DEFAULT_THEME),
        student_mode=getattr(style, "student_mode", False),
        accessible=getattr(style, "accessible", False),
        dyslexia=getattr(style, "dyslexia", False),
        high_contrast=getattr(style, "high_contrast", False),
    )
