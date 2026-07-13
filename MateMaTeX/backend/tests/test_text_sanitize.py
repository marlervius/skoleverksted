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


class TestSanitizeLatexBody:
    def test_combined(self):
        raw = "Østerrike\u2011Ungarn og **Oppgave 1**"
        out = sanitize_latex_body(raw)
        assert "Østerrike-Ungarn" in out
        assert "**" not in out
