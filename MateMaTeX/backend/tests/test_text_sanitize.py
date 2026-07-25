"""Tests for LaTeX text sanitization."""

from app.latex.text_sanitize import normalize_text, sanitize_latex_body, strip_markdown


class TestNormalizeText:
    def test_non_breaking_hyphen(self):
        assert normalize_text("1800\u2011tallet") == "1800-tallet"

    def test_soft_hyphen_removed(self):
        assert normalize_text("a\u00adb") == "ab"

    def test_nfc(self):
        assert normalize_text("café") == "café"


class TestStripMarkdown:
    def test_bold_stars(self):
        assert strip_markdown("Oppgave 1**") == "Oppgave 1"

    def test_preserves_inline_math(self):
        assert strip_markdown("Finn $x**2$") == "Finn $x**2$"

    def test_backticks(self):
        assert strip_markdown("`Tysk samling`") == "Tysk samling"

    def test_math_inside_command_is_restored(self):
        """A command wrapping inline math must come back intact, not as placeholders."""
        raw = r"\caption{Kule med radius $r$ og høyde $h$.}"
        assert strip_markdown(raw) == raw

    def test_no_placeholder_bytes_survive(self):
        raw = r"\section{Areal $A$}" + "\n" + r"\caption{Volum $V$ og masse $m$}"
        out = strip_markdown(raw)
        assert "\x00" not in out
        assert "MMTX" not in out


class TestSanitizeLatexBody:
    def test_combined(self):
        raw = "Østerrike\u2011Ungarn og **Oppgave 1**"
        out = sanitize_latex_body(raw)
        assert "Østerrike-Ungarn" in out
        assert "**" not in out

    def test_full_document_stays_compilable(self):
        """The preamble contains commands with inline math; none may be corrupted."""
        from app.latex.preamble import wrap_with_preamble

        out = sanitize_latex_body(wrap_with_preamble(r"\section*{Test} Hei $1+1=2$."))
        assert "\x00" not in out
