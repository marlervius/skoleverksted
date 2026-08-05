"""
Tests for the textbook design (Produksjonsoppskrift for matematikkhefter).

Two things are load-bearing here. First, worksheets must keep the look they have
always had — the textbook chrome is additive, not a global restyle. Second, the
parts the production spec makes mandatory in a hefte have to be enforced, since a
hefte that quietly drops its fasit is not the product that was ordered.
"""

import re
import shutil
import subprocess

import pytest

from app.latex.preamble import (
    TEXTBOOK_MATERIAL_TYPES,
    THEMES,
    build_preamble,
    wrap_with_style,
)
from app.models.state import GenerationRequest, PdfStyle
from app.verification.content_quality import evaluate_content_quality


def _without_comments(latex: str) -> str:
    """Drop LaTeX comments — they never reach the page."""
    return re.sub(r"(?m)(?<!\\)%.*$", "", latex)


# ── Palette and chrome ───────────────────────────────────────────────────────

class TestTextbookPreamble:
    def test_laerebok_palette_exists_and_is_complete(self):
        """Every theme must define the same colour names, or boxes break."""
        assert "laerebok" in THEMES
        assert set(THEMES["laerebok"]) == set(THEMES["default"])

    def test_worksheet_chrome_is_unchanged(self):
        """The classic look is the default and must not drift."""
        classic = build_preamble()
        assert "drop fuzzy shadow" in classic
        assert "attach boxed title to top left" in classic
        assert "arc=3mm" in classic
        # None of the textbook-only machinery leaks in.
        assert "MMAheftetittel" not in classic
        assert "MMAsteg" not in classic
        assert "bodyText" not in classic

    def test_textbook_chrome_drops_the_worksheet_decoration(self):
        textbook = build_preamble("laerebok", textbook=True)
        assert "drop fuzzy shadow" not in textbook
        assert "attach boxed title to top left" not in textbook
        assert "sharp corners" in textbook
        assert "leftrule=2.5pt" in textbook

    def test_textbook_mode_adds_the_booklet_macros(self):
        textbook = build_preamble("laerebok", textbook=True)
        for macro in (
            r"\newcommand{\MMAheftetittel}",
            r"\newcommand{\MMAsteg}",
            r"\newcommand{\MMAtabellhode}",
        ):
            assert macro in textbook

    def test_the_note_column_is_part_of_the_body(self):
        """
        Without includemp, geometry keeps the margins, silently drops textwidth
        and throws the note column clean off the paper.
        """
        textbook = build_preamble("laerebok", textbook=True)
        assert "includemp" in textbook
        assert "marginparwidth=3.0cm" in textbook
        assert r"\geometry" not in build_preamble()

    def test_flushbottom_wins_over_the_worksheet_raggedbottom(self):
        """
        \\raggedbottom is set globally for worksheets. The textbook block has to
        land after it, or the override never takes effect.
        """
        textbook = build_preamble("laerebok", textbook=True)
        assert textbook.index(r"\flushbottom") > textbook.index(r"\raggedbottom")

    def test_margin_note_macros_exist_only_in_textbook_mode(self):
        textbook = build_preamble("laerebok", textbook=True)
        classic = build_preamble()
        for macro in ("MMAmargbegrep", "MMAmargtips", "MMAmargtriks", "MMAmargnote"):
            assert f"\\newcommand{{\\{macro}}}" in textbook
            assert macro not in classic

    def test_exercise_list_and_caption_styling_are_present(self):
        textbook = build_preamble("laerebok", textbook=True)
        assert r"\newlist{oppgaver}" in textbook
        # caption is guarded — a TeX install without it must still compile.
        assert r"\IfFileExists{caption.sty}" in textbook

    def test_the_palette_is_three_hues_plus_neutrals(self):
        """
        Rule and mistake share the ochre; example and exploration share the
        teal. Seven distinct hues on one page reads busy.
        """
        p = THEMES["laerebok"]
        assert p["mainRed"] == p["mainOrange"]
        assert p["mainGreen"] == p["mainTeal"]
        hues = {p[k] for k in ("mainBlue", "mainTeal", "mainOrange")}
        assert len(hues) == 3

    def test_forklaring_cannot_butt_against_the_maths(self):
        """
        Written without the ``&&`` tab the annotation lands in the same cell as
        the expression. Without a space of its own it renders as
        "= \\sqrt{169}Adderer leddene", which is what shipped in the R1 vektorer
        chapter. The macro carries its own leading space so the collision cannot
        happen either way.
        """
        for preamble in (build_preamble(), build_preamble("laerebok", textbook=True)):
            assert r"\newcommand{\forklaring}[1]{\quad\text{" in preamble

    def test_soft_box_titles_sit_on_the_light_background(self):
        """
        husk/utforsk/laeringsmaal colour their title text in the frame colour.
        On a title bar of that same colour it is unreadable, so the title has to
        move into the box body.
        """
        assert "attach title to upper" in build_preamble("laerebok", textbook=True)
        assert "attach title to upper" not in build_preamble()

    def test_running_head_carries_the_subject_not_the_tool(self):
        """Rule 01 of the spec: textbook preg, not document preg."""
        textbook = build_preamble("laerebok", textbook=True, running_head="Funksjoner")
        header = _without_comments(textbook).split(r"\usepackage{fancyhdr}")[1]
        assert "Funksjoner" in header
        assert "Generert av MateMaTeX" not in header
        assert r"\today" not in header
        # The worksheet header still credits the tool and stamps the date.
        classic_header = build_preamble().split(r"\usepackage{fancyhdr}")[1]
        assert "Generert av MateMaTeX" in classic_header
        assert r"\today" in classic_header

    def test_the_worksheet_cover_is_rerouted_in_textbook_mode(self):
        """
        \\MMAforside signs the page "Generert av MateMaTeX" and stamps the date.
        Forbidding it in the prompt is not enough — it has to be neutralised.
        """
        textbook = build_preamble("laerebok", textbook=True)
        assert r"\renewcommand{\MMAforside}[4]{\MMAheftetittel{#1}{#3}{#2}}" in textbook
        assert r"\renewcommand{\MMAforside}" not in build_preamble()

    def test_running_head_is_escaped(self):
        """A topic like '50 % vekst & tolkning' must not break the preamble."""
        textbook = build_preamble(
            "laerebok", textbook=True, running_head="50 % vekst & tolkning_2"
        )
        assert r"50 \% vekst \& tolkning\_2" in textbook

    def test_empty_running_head_emits_no_header_field(self):
        textbook = build_preamble("laerebok", textbook=True, running_head="   ")
        assert r"\fancyhead[R]" not in textbook

    def test_high_contrast_still_wins_over_the_textbook_palette(self):
        """Accessibility must not be overridden by a design preference."""
        out = build_preamble("laerebok", textbook=True, high_contrast=True)
        assert r"\definecolor{lightBlue}{RGB}{255,255,255}" in out


class TestWrapWithStyle:
    def test_style_object_carries_textbook_mode_through(self):
        style = PdfStyle(theme="laerebok", textbook=True, running_head="Vektorer")
        doc = wrap_with_style(r"\section{Test}", style)
        assert "sharp corners" in doc
        assert "Vektorer" in doc

    def test_missing_attributes_fall_back_to_the_classic_look(self):
        """wrap_with_style is duck-typed; an old style object must still work."""

        class Legacy:
            theme = "default"

        doc = wrap_with_style(r"\section{Test}", Legacy())
        assert "drop fuzzy shadow" in doc


# ── Material type → design wiring ────────────────────────────────────────────

class TestMaterialTypeWiring:
    def _request(self, material_type: str, **kwargs) -> GenerationRequest:
        return GenerationRequest(
            grade="VG1 1T", topic="Funksjoner", material_type=material_type, **kwargs
        )

    def test_finished_products_get_the_textbook_design(self):
        for material_type in ("hefte", "kapittel"):
            req = self._request(material_type)
            assert req.pdf_style.textbook is True
            assert req.pdf_style.theme == "laerebok"
            assert req.pdf_style.running_head == "Funksjoner · VG1 1T"

    def test_worksheets_and_exams_are_untouched(self):
        for material_type in ("arbeidsark", "prøve", "differensiert"):
            req = self._request(material_type)
            assert req.pdf_style.textbook is False
            assert req.pdf_style.theme == "default"
            assert req.pdf_style.running_head == ""

    def test_explicit_opt_out_is_respected(self):
        req = self._request("hefte", pdf_style=PdfStyle(textbook=False))
        assert req.pdf_style.textbook is False
        assert req.pdf_style.theme == "default"

    def test_explicit_opt_in_is_respected(self):
        req = self._request("arbeidsark", pdf_style=PdfStyle(textbook=True))
        assert req.pdf_style.textbook is True
        assert req.pdf_style.theme == "laerebok"

    def test_a_deliberately_chosen_palette_is_never_overwritten(self):
        req = self._request("hefte", pdf_style=PdfStyle(theme="highcontrast"))
        assert req.pdf_style.theme == "highcontrast"
        assert req.pdf_style.textbook is True

    def test_caller_supplied_running_head_wins(self):
        req = self._request("hefte", pdf_style=PdfStyle(running_head="Egen tittel"))
        assert req.pdf_style.running_head == "Egen tittel"

    def test_hefte_counts_as_a_textbook_product(self):
        assert TEXTBOOK_MATERIAL_TYPES == {"hefte", "kapittel"}


# ── The spec's mandatory parts ───────────────────────────────────────────────

COMPLETE_HEFTE = r"""
\MMAheftetittel{Funksjoner}{Matematikk 1T · VG1}{Fra graf til formel}
\begin{laeringsmaal}[title={Hva skal du lære?}]
\item lese av grafen til en funksjon
\end{laeringsmaal}
\begin{husk}
Du bør kunne løse $2x+3=11$.
\end{husk}
\section{Funksjonsbegrepet}
En funksjon gir nøyaktig én verdi ut for hver verdi
inn.\MMAmargtips{Les $f(2)=7$ høyt: «$f$ av 2 er 7».}
\begin{definisjon}En funksjon gir én verdi ut per verdi inn.\end{definisjon}
Mengden av lovlige $x$-verdier har et eget
navn.\MMAmargbegrep{Definisjonsmengde}{Alle $x$-verdiene funksjonen er
definert for.}
\begin{eksempel}[title={Nullpunkt}]$x^2-4=0$ gir $x=\pm 2$.\end{eksempel}
Mangler førstegradsleddet, slipper du abc-formelen.\MMAmargtriks{Flytt
konstanten over og ta kvadratrot. Husk $\pm$.}
\section*{Oppgaver}
\begin{multicols}{2}
\begin{oppgaver}
  \item Finn nullpunktene til $g(x)=x^2-9$.
  \item Finn $f(3)$ når $f(x)=2x+1$.
  \item Løs $x^2=25$.
  \item Finn nullpunktet til $h(x)=3x-12$.
\end{oppgaver}
\end{multicols}
\begin{oppsummering}Nullpunkt er der grafen krysser $x$-aksen.\end{oppsummering}
\section*{Blandede oppgaver}
\begin{oppgaver}[start=5]
  \item Finn uttrykket til linjen gjennom $(0,3)$ og $(2,7)$.
  \item En ball har høyden $h(t)=-5t^2+20t$. Når treffer den bakken?
\end{oppgaver}
\section*{Fasit}
\begin{multicols}{3}
\small
\begin{oppgaver}
  \item $x=\pm 3$
  \item $f(3)=7$
  \item $x=\pm 5$
  \item $x=4$
  \item $f(x)=2x+3$
  \item $t=4$ s
\end{oppgaver}
\end{multicols}
"""


def _hefte_codes(body: str, **kwargs) -> set[str]:
    request = GenerationRequest(
        grade="VG1 1T", topic="Funksjoner", material_type="hefte", **kwargs
    )
    report = evaluate_content_quality(body, request)
    return {issue.code for issue in report.issues}


class TestHefteCompleteness:
    def test_complete_hefte_reports_no_structural_gaps(self):
        codes = _hefte_codes(COMPLETE_HEFTE)
        structural = {
            "missing_cover",
            "missing_learning_goals",
            "missing_prior_knowledge",
            "missing_summary",
            "missing_mixed_exercises",
            "missing_fasit",
            "difficulty_label",
            "unused_margin",
        }
        assert codes & structural == set()

    def test_each_mandatory_part_is_detected_when_removed(self):
        cases = {
            r"\MMAheftetittel{Funksjoner}{Matematikk 1T · VG1}{Fra graf til formel}":
                "missing_cover",
            r"\begin{laeringsmaal}[title={Hva skal du lære?}]": "missing_learning_goals",
            r"\begin{husk}": "missing_prior_knowledge",
            r"\begin{oppsummering}": "missing_summary",
            r"\section*{Blandede oppgaver}": "missing_mixed_exercises",
            r"\section*{Fasit}": "missing_fasit",
        }
        for fragment, expected_code in cases.items():
            stripped = COMPLETE_HEFTE.replace(fragment, "")
            assert expected_code in _hefte_codes(stripped), (
                f"removing {fragment!r} should raise {expected_code}"
            )

    def test_fasit_is_not_required_when_solutions_are_excluded(self):
        stripped = COMPLETE_HEFTE.replace(r"\section*{Fasit}", "")
        assert "missing_fasit" not in _hefte_codes(stripped, include_solutions=False)

    def test_difficulty_stars_are_rejected(self):
        body = COMPLETE_HEFTE.replace(
            r"Finn nullpunktene til $g(x)=x^2-9$.",
            r"Finn nullpunktene til $g(x)=x^2-9$. \MMAniva{2}",
        )
        assert "difficulty_label" in _hefte_codes(body)

    def test_difficulty_labels_in_headings_are_rejected(self):
        body = COMPLETE_HEFTE.replace(
            r"\section*{Blandede oppgaver}",
            r"\section*{Blandede oppgaver}" + "\n" + r"\subsection{Vanskelige oppgaver}",
        )
        assert "difficulty_label" in _hefte_codes(body)

    def test_difficulty_words_in_prose_are_allowed(self):
        """'vanskelig' is ordinary Norwegian; only labels are forbidden."""
        body = COMPLETE_HEFTE.replace(
            "En funksjon gir én verdi ut per verdi inn.",
            "Det er vanskelig å se dette med det blotte øye, men lett når du "
            "tegner grafen. Middels store tall gjør regningen enklere.",
        )
        assert "difficulty_label" not in _hefte_codes(body)

    def test_an_empty_margin_column_is_caught(self):
        """The layout reserves 3 cm per page; unused, it just looks lopsided."""
        stripped = re.sub(r"\\MMAmarg\w+(\{[^{}]*\})+", "", COMPLETE_HEFTE)
        assert "unused_margin" in _hefte_codes(stripped)

    def test_exercises_in_lists_are_counted(self):
        """
        Textbook products number their exercises in a list rather than boxing
        each one. Counting only taskboxes would read a full hefte as empty.
        """
        report = evaluate_content_quality(
            COMPLETE_HEFTE,
            GenerationRequest(
                grade="VG1 1T", topic="Funksjoner", material_type="hefte"
            ),
        )
        assert report.exercise_count == 12

    def test_taskboxes_are_still_counted_for_worksheets(self):
        report = evaluate_content_quality(
            r"\begin{taskbox}{Oppgave 1}A\end{taskbox}"
            r"\begin{taskbox}{Oppgave 2}B\end{taskbox}",
            GenerationRequest(
                grade="VG1 1T", topic="Funksjoner", material_type="arbeidsark"
            ),
        )
        assert report.exercise_count == 2

    def test_the_body_uses_only_environments_the_preamble_defines(self):
        """
        The fixture doubles as the contract between prompt and preamble: every
        environment the hefte instructions tell the author to use must exist.
        """
        textbook = build_preamble("laerebok", textbook=True)
        # multicol and enumitem supply these two; the rest are our own boxes.
        provided = {"multicols": r"\usepackage{multicol}",
                    "oppgaver": r"\newlist{oppgaver}"}
        for env in set(re.findall(r"\\begin\{([a-z]+)\}", COMPLETE_HEFTE)):
            marker = provided.get(env, f"\\newtcolorbox{{{env}}}")
            assert marker in textbook, f"{env} is not available"

    def test_a_hefte_is_held_to_the_curriculum_coverage_bar(self):
        """
        A hefte goes through the same coverage and off-topic guards as a
        kapittel — a two-line hefte must not pass the gate.
        """
        report = evaluate_content_quality(
            r"\section{Funksjoner}Kort tekst.",
            GenerationRequest(
                grade="VG1 1T", topic="Funksjoner", material_type="hefte"
            ),
        )
        assert not report.passed


# ── Does it actually typeset? ────────────────────────────────────────────────

@pytest.mark.skipif(
    not shutil.which("lualatex"), reason="requires a LaTeX installation"
)
def test_textbook_preamble_compiles(tmp_path):
    """
    String assertions cannot tell whether tcolorbox accepts the options, so
    build the real thing. Guards against the whole design silently failing to
    typeset — the spec's last check is "PDF-en er kontrollert som ferdig utskrift".
    """
    from app.latex.preamble import wrap_with_preamble

    doc = wrap_with_preamble(
        COMPLETE_HEFTE + "\n" + r"\MMAsteg{01}{Les av grafen}{Finn krysningene.}"
        + "\n" + r"\MMAsteg{02}{Kontroller}{}"
        + "\n" + r"\begin{nokkelpoeng}Én verdi inn, én verdi ut.\end{nokkelpoeng}",
        theme="laerebok",
        textbook=True,
        running_head="Funksjoner · VG1 1T",
    )
    tex = tmp_path / "hefte.tex"
    tex.write_text(doc, encoding="utf-8")

    proc = subprocess.run(
        ["lualatex", "-interaction=nonstopmode", "-halt-on-error",
         f"-output-directory={tmp_path}", str(tex)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=300,
    )

    assert (tmp_path / "hefte.pdf").exists(), (
        "textbook preamble did not produce a PDF:\n"
        + "\n".join(l for l in proc.stdout.splitlines() if l.startswith("!"))
    )
