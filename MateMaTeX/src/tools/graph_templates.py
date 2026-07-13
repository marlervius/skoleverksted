"""
Graph Templates for MateMaTeX.
Pre-built TikZ/PGFPlots templates for common mathematical visualizations.
Organized by grade level and topic.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class GraphTemplate:
    """A reusable graph template."""
    id: str
    name: str
    category: str
    grade_range: str  # e.g., "1-4", "5-7", "8-10", "VG"
    description: str
    tikz_code: str
    parameters: list[str]  # Customizable parameters


# =============================================================================
# NUMBER LINES (Tallinje) - Grades 1-7
# =============================================================================

NUMBERLINE_BASIC = GraphTemplate(
    id="numberline_basic",
    name="Enkel tallinje",
    category="Tallinje",
    grade_range="1-4",
    description="Grunnleggende tallinje fra 0 til 10",
    tikz_code=r"""
\begin{figure}[H]
\centering
\begin{tikzpicture}
    % Draw the line
    \draw[thick, -stealth] (-0.5,0) -- (10.5,0);
    % Draw ticks and numbers
    \foreach \x in {0,1,...,10} {
        \draw[thick] (\x,0.15) -- (\x,-0.15) node[below] {\x};
    }
    % Optional: Mark a specific number
    % \fill[red] (MARK_VALUE,0) circle (4pt);
\end{tikzpicture}
\caption{Tallinje fra 0 til 10.}
\end{figure}
""",
    parameters=["MARK_VALUE"]
)

NUMBERLINE_NEGATIVE = GraphTemplate(
    id="numberline_negative",
    name="Tallinje med negative tall",
    category="Tallinje",
    grade_range="5-7",
    description="Tallinje fra -10 til 10 med null i midten",
    tikz_code=r"""
\begin{figure}[H]
\centering
\begin{tikzpicture}[scale=0.5]
    % Draw the line
    \draw[thick, stealth-stealth] (-11,0) -- (11,0);
    % Draw ticks and numbers
    \foreach \x in {-10,-9,...,10} {
        \draw[thick] (\x,0.25) -- (\x,-0.25);
        \ifnum\x=0
            \node[below, font=\bfseries] at (\x,-0.3) {\x};
        \else
            \node[below, font=\small] at (\x,-0.3) {\x};
        \fi
    }
    % Highlight negative side
    \draw[mainBlue, very thick] (-10,0) -- (0,0);
    % Highlight positive side
    \draw[mainGreen, very thick] (0,0) -- (10,0);
\end{tikzpicture}
\caption{Tallinje med negative og positive tall.}
\end{figure}
""",
    parameters=[]
)

NUMBERLINE_FRACTIONS = GraphTemplate(
    id="numberline_fractions",
    name="Tallinje med brøker",
    category="Tallinje",
    grade_range="5-7",
    description="Tallinje fra 0 til 2 med halvparter og fjerdedeler",
    tikz_code=r"""
\begin{figure}[H]
\centering
\begin{tikzpicture}[scale=3]
    % Draw the line
    \draw[thick, -stealth] (-0.2,0) -- (2.3,0);
    % Major ticks (whole numbers)
    \foreach \x in {0,1,2} {
        \draw[thick] (\x,0.12) -- (\x,-0.12) node[below=4pt] {\x};
    }
    % Minor ticks (quarters)
    \foreach \x in {0.25, 0.75, 1.25, 1.75} {
        \draw[mainGray] (\x,0.06) -- (\x,-0.06);
    }
    % Half ticks (labeled)
    \foreach \x in {0.5, 1.5} {
        \draw[mainBlue, thick] (\x,0.1) -- (\x,-0.1);
    }
    \node[below, mainBlue, font=\small] at (0.5,-0.15) {$\frac{1}{2}$};
    \node[below, mainBlue, font=\small] at (1.5,-0.15) {$1\frac{1}{2}$};
\end{tikzpicture}
\caption{Tallinje med brøker.}
\end{figure}
""",
    parameters=[]
)


# =============================================================================
# FRACTION VISUALIZATIONS (Brøkmodeller) - Grades 3-7
# =============================================================================

FRACTION_CIRCLE = GraphTemplate(
    id="fraction_circle",
    name="Brøksirkel",
    category="Brøk",
    grade_range="3-7",
    description="Sirkel delt inn i deler for å vise brøker",
    tikz_code=r"""
\begin{figure}[H]
\centering
\begin{tikzpicture}
    % Draw circle outline
    \draw[thick] (0,0) circle (2cm);
    % Divide into DENOMINATOR parts and shade NUMERATOR of them
    % Example: 3/4
    \foreach \i in {1,...,4} {
        \draw[thick] (0,0) -- ({90-(\i-1)*90}:2cm);
    }
    % Shade 3 parts (mainBlue)
    \fill[mainBlue!40] (0,0) -- (90:2cm) arc (90:0:2cm) -- cycle;
    \fill[mainBlue!40] (0,0) -- (0:2cm) arc (0:-90:2cm) -- cycle;
    \fill[mainBlue!40] (0,0) -- (-90:2cm) arc (-90:-180:2cm) -- cycle;
    % Label
    \node at (0,-2.8) {\Large $\frac{3}{4}$};
\end{tikzpicture}
\caption{Brøken $\frac{3}{4}$ vist som kakediagram.}
\end{figure}
""",
    parameters=["NUMERATOR", "DENOMINATOR"]
)

FRACTION_RECTANGLE = GraphTemplate(
    id="fraction_rectangle",
    name="Brøkrektangel",
    category="Brøk",
    grade_range="3-7",
    description="Rektangel delt inn i deler for å vise brøker",
    tikz_code=r"""
\begin{figure}[H]
\centering
\begin{tikzpicture}
    % Draw rectangle divided into 5 parts, shade 2
    \foreach \i in {0,...,4} {
        \draw[thick] (\i,0) rectangle (\i+1,1);
    }
    % Shade first 2 parts
    \fill[mainGreen!40] (0,0) rectangle (1,1);
    \fill[mainGreen!40] (1,0) rectangle (2,1);
    % Outline shaded parts
    \draw[mainGreen, very thick] (0,0) rectangle (2,1);
    % Label
    \node at (2.5,-0.5) {\Large $\frac{2}{5}$};
\end{tikzpicture}
\caption{Brøken $\frac{2}{5}$ vist som rektangel.}
\end{figure}
""",
    parameters=["NUMERATOR", "DENOMINATOR"]
)


# =============================================================================
# GEOMETRY (Geometri) - All grades
# =============================================================================

TRIANGLE_LABELED = GraphTemplate(
    id="triangle_labeled",
    name="Trekant med sider og vinkler",
    category="Geometri",
    grade_range="5-10",
    description="Trekant med merkede sider og vinkler",
    tikz_code=r"""
\begin{figure}[H]
\centering
\begin{tikzpicture}[scale=1.2]
    % Define vertices
    \coordinate (A) at (0,0);
    \coordinate (B) at (5,0);
    \coordinate (C) at (2,3);
    % Draw triangle
    \draw[thick, mainBlue] (A) -- (B) -- (C) -- cycle;
    % Label vertices
    \node[below left] at (A) {$A$};
    \node[below right] at (B) {$B$};
    \node[above] at (C) {$C$};
    % Label sides
    \node[below] at (2.5,0) {$c$};
    \node[above left] at (1,1.5) {$b$};
    \node[above right] at (3.5,1.5) {$a$};
    % Mark angle at A
    \draw[mainOrange, thick] (0.6,0) arc (0:56:0.6);
    \node[mainOrange] at (0.9,0.3) {$\alpha$};
\end{tikzpicture}
\caption{Trekant $ABC$ med sider $a$, $b$, $c$ og vinkel $\alpha$.}
\end{figure}
""",
    parameters=[]
)

TRIANGLE_RIGHT_ANGLE = GraphTemplate(
    id="triangle_right_angle",
    name="Rettvinklet trekant (Pytagoras)",
    category="Geometri",
    grade_range="8-10",
    description="Rettvinklet trekant med katetene og hypotenusen merket",
    tikz_code=r"""
\begin{figure}[H]
\centering
\begin{tikzpicture}[scale=0.8]
    % Draw triangle
    \draw[thick, mainBlue] (0,0) -- (4,0) -- (4,3) -- cycle;
    % Right angle mark
    \draw[thick] (3.7,0) -- (3.7,0.3) -- (4,0.3);
    % Labels
    \node[below] at (2,0) {$a = 4$};
    \node[right] at (4,1.5) {$b = 3$};
    \node[above left] at (2,1.5) {$c = 5$};
    % Squares on sides (Pythagorean visualization)
    \draw[mainGreen!50, fill=mainGreen!20] (0,0) -- (0,-4) -- (4,-4) -- (4,0);
    \draw[mainOrange!50, fill=mainOrange!20] (4,0) -- (7,0) -- (7,3) -- (4,3);
    \draw[mainBlue!50, fill=mainBlue!20] (0,0) -- (-3,4) -- (1,7) -- (4,3);
    % Area labels
    \node at (2,-2) {$a^2 = 16$};
    \node at (5.5,1.5) {$b^2 = 9$};
    \node at (0.5,3.5) {$c^2 = 25$};
\end{tikzpicture}
\caption{Pytagoras' setning: $a^2 + b^2 = c^2$, her: $16 + 9 = 25$.}
\end{figure}
""",
    parameters=[]
)

CIRCLE_WITH_PARTS = GraphTemplate(
    id="circle_with_parts",
    name="Sirkel med radius, diameter og omkrets",
    category="Geometri",
    grade_range="5-10",
    description="Sirkel med alle viktige deler merket",
    tikz_code=r"""
\begin{figure}[H]
\centering
\begin{tikzpicture}
    % Draw circle
    \draw[thick, mainBlue] (0,0) circle (2.5cm);
    % Center point
    \fill (0,0) circle (2pt) node[below left] {$M$};
    % Radius
    \draw[thick, mainGreen, -stealth] (0,0) -- (2.5,0) node[midway, above] {$r$};
    % Diameter
    \draw[thick, mainOrange, dashed] (-2.5,0) -- (2.5,0);
    \node[mainOrange, below] at (0,-0.3) {$d = 2r$};
    % Point on circle
    \fill[mainBlue] (2.5,0) circle (3pt) node[right] {$P$};
    % Arc showing circumference
    \draw[thick, mainBlue!70, decorate, decoration={snake, amplitude=0.5mm}] 
        (0:2.7) arc (0:60:2.7);
    \node[mainBlue] at (1.8,2.2) {$O = 2\pi r$};
\end{tikzpicture}
\caption{Sirkel med sentrum $M$, radius $r$, diameter $d$ og omkrets $O$.}
\end{figure}
""",
    parameters=[]
)

COORDINATE_SYSTEM = GraphTemplate(
    id="coordinate_system",
    name="Koordinatsystem",
    category="Geometri",
    grade_range="5-10",
    description="Tomt koordinatsystem med rutenett",
    tikz_code=r"""
\begin{figure}[H]
\centering
\begin{tikzpicture}
    % Grid
    \draw[lightGray, thin] (-4,-4) grid (4,4);
    % Axes
    \draw[thick, -stealth] (-4.5,0) -- (4.5,0) node[right] {$x$};
    \draw[thick, -stealth] (0,-4.5) -- (0,4.5) node[above] {$y$};
    % Tick marks with numbers
    \foreach \x in {-4,-3,-2,-1,1,2,3,4} {
        \draw[thick] (\x,0.1) -- (\x,-0.1) node[below, font=\small] {\x};
    }
    \foreach \y in {-4,-3,-2,-1,1,2,3,4} {
        \draw[thick] (0.1,\y) -- (-0.1,\y) node[left, font=\small] {\y};
    }
    % Origin
    \node[below left] at (0,0) {$0$};
\end{tikzpicture}
\caption{Koordinatsystem.}
\end{figure}
""",
    parameters=[]
)


# =============================================================================
# FUNCTION GRAPHS (Funksjonsgrafer) - Grades 8-VG
# =============================================================================

LINEAR_FUNCTION = GraphTemplate(
    id="linear_function",
    name="Lineær funksjon",
    category="Funksjoner",
    grade_range="8-VG",
    description="Graf av lineær funksjon f(x) = ax + b",
    tikz_code=r"""
\begin{figure}[H]
\centering
\begin{tikzpicture}
\begin{axis}[
    width=0.75\textwidth,
    height=0.5\textwidth,
    xlabel={$x$},
    ylabel={$y$},
    grid=major,
    axis lines=middle,
    xmin=-5, xmax=5,
    ymin=-3, ymax=7,
    xtick={-4,-3,-2,-1,0,1,2,3,4},
    ytick={-2,-1,0,1,2,3,4,5,6},
    legend pos=north west,
    every axis plot/.append style={thick}
]
% Plot the linear function
\addplot[mainBlue, domain=-4:4, samples=50] {2*x + 1};
\legend{$f(x) = 2x + 1$}
% Mark y-intercept
\addplot[only marks, mark=*, mainGreen, mark size=3pt] coordinates {(0,1)};
\node[mainGreen, right] at (axis cs:0.2,1) {$(0, 1)$};
% Show slope triangle
\draw[mainOrange, thick, dashed] (axis cs:1,3) -- (axis cs:2,3) -- (axis cs:2,5);
\node[mainOrange, below] at (axis cs:1.5,3) {$1$};
\node[mainOrange, right] at (axis cs:2,4) {$2$};
\end{axis}
\end{tikzpicture}
\caption{Lineær funksjon $f(x) = 2x + 1$ med stigningstall $a = 2$ og konstantledd $b = 1$.}
\end{figure}
""",
    parameters=["A", "B"]
)

QUADRATIC_FUNCTION = GraphTemplate(
    id="quadratic_function",
    name="Andregradsfunksjon",
    category="Funksjoner",
    grade_range="10-VG",
    description="Parabel med toppunkt og nullpunkter",
    tikz_code=r"""
\begin{figure}[H]
\centering
\begin{tikzpicture}
\begin{axis}[
    width=0.75\textwidth,
    height=0.55\textwidth,
    xlabel={$x$},
    ylabel={$y$},
    grid=major,
    axis lines=middle,
    xmin=-4, xmax=6,
    ymin=-5, ymax=10,
    legend pos=north east,
    every axis plot/.append style={thick}
]
% Plot quadratic
\addplot[mainBlue, domain=-2:5, samples=100, smooth] {-(x-1.5)^2 + 6};
\legend{$f(x) = -(x-1.5)^2 + 6$}
% Mark vertex (toppunkt)
\addplot[only marks, mark=*, mainGreen, mark size=4pt] coordinates {(1.5,6)};
\node[mainGreen, above right] at (axis cs:1.5,6) {Toppunkt $(1.5, 6)$};
% Mark zeros (nullpunkter)
\addplot[only marks, mark=*, mainOrange, mark size=3pt] coordinates {(-0.95,0) (3.95,0)};
\node[mainOrange, below] at (axis cs:-0.95,0) {$x_1$};
\node[mainOrange, below] at (axis cs:3.95,0) {$x_2$};
\end{axis}
\end{tikzpicture}
\caption{Andregradsfunksjon med toppunkt og nullpunkter.}
\end{figure}
""",
    parameters=[]
)


# =============================================================================
# STATISTICS (Statistikk) - Grades 5-VG
# =============================================================================

HISTOGRAM = GraphTemplate(
    id="histogram",
    name="Histogram",
    category="Statistikk",
    grade_range="5-VG",
    description="Histogram med frekvenser",
    tikz_code=r"""
\begin{figure}[H]
\centering
\begin{tikzpicture}
\begin{axis}[
    width=0.7\textwidth,
    height=0.45\textwidth,
    ybar,
    bar width=0.8cm,
    xlabel={Verdi},
    ylabel={Frekvens},
    ymin=0,
    ymax=12,
    xtick={1,2,3,4,5},
    xticklabels={A, B, C, D, E},
    nodes near coords,
    every node near coord/.append style={font=\small},
    axis lines*=left,
    ymajorgrids=true,
    grid style={dashed, gray!30}
]
\addplot[fill=mainBlue!60, draw=mainBlue] coordinates {
    (1, 5)
    (2, 8)
    (3, 10)
    (4, 6)
    (5, 3)
};
\end{axis}
\end{tikzpicture}
\caption{Histogram som viser fordelingen av verdier.}
\end{figure}
""",
    parameters=[]
)

BOX_PLOT = GraphTemplate(
    id="box_plot",
    name="Boksplott",
    category="Statistikk",
    grade_range="8-VG",
    description="Boksplott med median, kvartiler og ekstremverdier",
    tikz_code=r"""
\begin{figure}[H]
\centering
\begin{tikzpicture}
    % Draw axis
    \draw[thick, -stealth] (0,0) -- (12,0) node[right] {Verdi};
    \foreach \x in {0,2,4,6,8,10} {
        \draw (\x,0.1) -- (\x,-0.1) node[below] {\x};
    }
    % Box plot at y=1
    % Whiskers
    \draw[thick] (1,1) -- (2,1);  % Left whisker
    \draw[thick] (8,1) -- (9,1);  % Right whisker
    \draw[thick] (1,0.7) -- (1,1.3);  % Left whisker end
    \draw[thick] (9,0.7) -- (9,1.3);  % Right whisker end
    % Box
    \draw[thick, fill=mainBlue!30] (2,0.5) rectangle (8,1.5);
    % Median line
    \draw[very thick, mainOrange] (5,0.5) -- (5,1.5);
    % Labels
    \node[below, font=\small] at (1,-0.3) {Min};
    \node[below, font=\small] at (2,-0.3) {$Q_1$};
    \node[below, font=\small, mainOrange] at (5,-0.3) {Median};
    \node[below, font=\small] at (8,-0.3) {$Q_3$};
    \node[below, font=\small] at (9,-0.3) {Maks};
\end{tikzpicture}
\caption{Boksplott med minimum, $Q_1$, median, $Q_3$ og maksimum.}
\end{figure}
""",
    parameters=[]
)

PIE_CHART = GraphTemplate(
    id="pie_chart",
    name="Sektordiagram",
    category="Statistikk",
    grade_range="5-VG",
    description="Kakediagram med prosenter",
    tikz_code=r"""
\begin{figure}[H]
\centering
\begin{tikzpicture}
    % Sector 1: 40%
    \fill[mainBlue!70] (0,0) -- (0:2.5) arc (0:144:2.5) -- cycle;
    \node[white, font=\bfseries] at (72:1.5) {40\%};
    % Sector 2: 30%
    \fill[mainGreen!70] (0,0) -- (144:2.5) arc (144:252:2.5) -- cycle;
    \node[white, font=\bfseries] at (198:1.5) {30\%};
    % Sector 3: 20%
    \fill[mainOrange!70] (0,0) -- (252:2.5) arc (252:324:2.5) -- cycle;
    \node[white, font=\bfseries] at (288:1.5) {20\%};
    % Sector 4: 10%
    \fill[mainGray!70] (0,0) -- (324:2.5) arc (324:360:2.5) -- cycle;
    \node[white, font=\bfseries] at (342:1.8) {10\%};
    % Draw outline
    \draw[thick] (0,0) circle (2.5);
    % Legend
    \node[right] at (3.5,1.5) {\tikz\fill[mainBlue!70] (0,0) rectangle (0.4,0.4); Kategori A};
    \node[right] at (3.5,0.8) {\tikz\fill[mainGreen!70] (0,0) rectangle (0.4,0.4); Kategori B};
    \node[right] at (3.5,0.1) {\tikz\fill[mainOrange!70] (0,0) rectangle (0.4,0.4); Kategori C};
    \node[right] at (3.5,-0.6) {\tikz\fill[mainGray!70] (0,0) rectangle (0.4,0.4); Kategori D};
\end{tikzpicture}
\caption{Sektordiagram som viser prosentfordeling.}
\end{figure}
""",
    parameters=[]
)


# =============================================================================
# COUNTING AND CONCRETE (Telling og konkret) - Grades 1-4
# =============================================================================

COUNTING_BLOCKS = GraphTemplate(
    id="counting_blocks",
    name="Tellebrikker",
    category="Telling",
    grade_range="1-4",
    description="Konkrete brikker for å vise tall",
    tikz_code=r"""
\begin{figure}[H]
\centering
\begin{tikzpicture}
    % Row of 7 counting blocks
    \foreach \x in {0,1,2,3,4} {
        \fill[mainBlue!70] (\x*0.8,0) circle (0.3);
    }
    \foreach \x in {0,1} {
        \fill[mainGreen!70] (\x*0.8,-0.9) circle (0.3);
    }
    % Labels
    \node[right] at (4.5,0) {$5$ blå};
    \node[right] at (4.5,-0.9) {$2$ grønne};
    \node[right, font=\bfseries] at (4.5,-1.8) {$5 + 2 = 7$ til sammen};
\end{tikzpicture}
\caption{$5 + 2 = 7$ vist med tellebrikker.}
\end{figure}
""",
    parameters=["NUM1", "NUM2"]
)

TEN_FRAME = GraphTemplate(
    id="ten_frame",
    name="Tierramme",
    category="Telling",
    grade_range="1-4",
    description="Tierramme for tallforståelse",
    tikz_code=r"""
\begin{figure}[H]
\centering
\begin{tikzpicture}[scale=0.8]
    % Draw 10-frame (2 rows x 5 columns)
    \foreach \x in {0,1,2,3,4} {
        \draw[thick] (\x,0) rectangle (\x+1,1);
        \draw[thick] (\x,1) rectangle (\x+1,2);
    }
    % Fill in 7 dots (representing the number 7)
    \foreach \x in {0,1,2,3,4} {
        \fill[mainBlue] (\x+0.5,1.5) circle (0.3);
    }
    \foreach \x in {0,1} {
        \fill[mainBlue] (\x+0.5,0.5) circle (0.3);
    }
    % Empty circles for remaining
    \foreach \x in {2,3,4} {
        \draw[mainGray, dashed] (\x+0.5,0.5) circle (0.3);
    }
    % Label
    \node at (2.5,-0.7) {\Large Tallet $7$};
\end{tikzpicture}
\caption{Tallet 7 vist i tierramme.}
\end{figure}
""",
    parameters=["NUMBER"]
)


# =============================================================================
# TEMPLATE COLLECTIONS BY GRADE
# =============================================================================

ALL_TEMPLATES = [
    # Number lines
    NUMBERLINE_BASIC,
    NUMBERLINE_NEGATIVE,
    NUMBERLINE_FRACTIONS,
    # Fractions
    FRACTION_CIRCLE,
    FRACTION_RECTANGLE,
    # Geometry
    TRIANGLE_LABELED,
    TRIANGLE_RIGHT_ANGLE,
    CIRCLE_WITH_PARTS,
    COORDINATE_SYSTEM,
    # Functions
    LINEAR_FUNCTION,
    QUADRATIC_FUNCTION,
    # Statistics
    HISTOGRAM,
    BOX_PLOT,
    PIE_CHART,
    # Counting
    COUNTING_BLOCKS,
    TEN_FRAME,
]

TEMPLATES_BY_CATEGORY = {
    "Tallinje": [NUMBERLINE_BASIC, NUMBERLINE_NEGATIVE, NUMBERLINE_FRACTIONS],
    "Brøk": [FRACTION_CIRCLE, FRACTION_RECTANGLE],
    "Geometri": [TRIANGLE_LABELED, TRIANGLE_RIGHT_ANGLE, CIRCLE_WITH_PARTS, COORDINATE_SYSTEM],
    "Funksjoner": [LINEAR_FUNCTION, QUADRATIC_FUNCTION],
    "Statistikk": [HISTOGRAM, BOX_PLOT, PIE_CHART],
    "Telling": [COUNTING_BLOCKS, TEN_FRAME],
}

TEMPLATES_BY_GRADE = {
    "1-4": [NUMBERLINE_BASIC, FRACTION_CIRCLE, FRACTION_RECTANGLE, COUNTING_BLOCKS, TEN_FRAME],
    "5-7": [NUMBERLINE_NEGATIVE, NUMBERLINE_FRACTIONS, FRACTION_CIRCLE, FRACTION_RECTANGLE, 
            TRIANGLE_LABELED, CIRCLE_WITH_PARTS, COORDINATE_SYSTEM, HISTOGRAM, PIE_CHART],
    "8-10": [NUMBERLINE_NEGATIVE, TRIANGLE_LABELED, TRIANGLE_RIGHT_ANGLE, CIRCLE_WITH_PARTS,
             COORDINATE_SYSTEM, LINEAR_FUNCTION, HISTOGRAM, BOX_PLOT, PIE_CHART],
    "VG": [COORDINATE_SYSTEM, LINEAR_FUNCTION, QUADRATIC_FUNCTION, HISTOGRAM, BOX_PLOT, PIE_CHART],
}


def get_templates_for_grade(grade: str) -> list[GraphTemplate]:
    """Get all templates suitable for a grade level."""
    if "1" in grade and ("trinn" in grade or "-" in grade):
        if "4" in grade or "3" in grade or "2" in grade:
            return TEMPLATES_BY_GRADE["1-4"]
    if "5" in grade or "6" in grade or "7" in grade:
        return TEMPLATES_BY_GRADE["5-7"]
    if "8" in grade or "9" in grade or "10" in grade:
        return TEMPLATES_BY_GRADE["8-10"]
    if "VG" in grade or "vg" in grade:
        return TEMPLATES_BY_GRADE["VG"]
    return ALL_TEMPLATES


def get_templates_for_category(category: str) -> list[GraphTemplate]:
    """Get all templates in a category."""
    return TEMPLATES_BY_CATEGORY.get(category, [])


def get_template_by_id(template_id: str) -> Optional[GraphTemplate]:
    """Get a specific template by ID."""
    for t in ALL_TEMPLATES:
        if t.id == template_id:
            return t
    return None


def get_all_categories() -> list[str]:
    """Get list of all template categories."""
    return list(TEMPLATES_BY_CATEGORY.keys())


def get_template_summary_for_prompt(grade: str) -> str:
    """
    Generate a summary of available templates for the AI prompt.
    This helps the Illustrator agent know what templates are available.
    """
    templates = get_templates_for_grade(grade)
    
    summary = "=== TILGJENGELIGE GRAFMALER ===\n\n"
    summary += "Du kan bruke disse ferdige TikZ-malene (kopier og tilpass):\n\n"
    
    for t in templates:
        summary += f"**{t.name}** ({t.category})\n"
        summary += f"   {t.description}\n"
        summary += f"   Bruk: [USE TEMPLATE: {t.id}]\n\n"
    
    return summary
