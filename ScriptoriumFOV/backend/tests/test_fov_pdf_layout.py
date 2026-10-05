"""FOV layout rules in the Norsklæring PDF: left-aligned text, "Mitt språk"
lines, pre-reading vocabulary at A1-A2 and alt text on images.
"""

import io
import shutil

import pytest
from pypdf import PdfReader

from ScriptoriumFOV.backend import pdf_service
from ScriptoriumFOV.backend.pdf_service import create_lesson_pdf, create_typst_template
from ScriptoriumFOV.backend.text_cleaner import (
    NATIVE_LANGUAGE_LINE,
    format_vocabulary_as_list,
)

TEXT = "Isbjørnen er hvit. Den bor på Svalbard."
VOCABULARY = "Fossil: En gammel rest av et dyr.\nTemperert: Ikke for varmt og ikke for kaldt."
WORKSHEET = f"a) VIKTIGE BEGREPER\n{VOCABULARY}\n\nb) LESEFORSTÅELSE\n1. Hva er hvitt?\na) Isbjørnen *\nb) Solen\nc) Havet"


def _template(level: str, **kwargs) -> str:
    return create_typst_template(
        topic="Klima",
        level=level,
        main_text=TEXT,
        vocabulary=VOCABULARY,
        **kwargs,
    )


def test_text_is_never_justified():
    for level in ("A1.1", "A2.2", "B1.1", "B2.1"):
        doc = _template(level)
        assert "justify: true" not in doc
        assert "justify: false" in doc


def test_simple_fallback_template_is_not_justified_either():
    assert "justify: true" not in open(pdf_service.__file__, encoding="utf-8").read()


@pytest.mark.parametrize("level, expected", [("A1.1", True), ("A2.2", True), ("B1.1", True), ("B2.1", False)])
def test_my_language_line_follows_the_level(level, expected):
    assert (NATIVE_LANGUAGE_LINE in _template(level)) is expected


def test_my_language_can_be_switched_off_or_forced_on():
    assert NATIVE_LANGUAGE_LINE not in _template("A2", options={"native_language_field": False})
    assert NATIVE_LANGUAGE_LINE in _template("B2", options={"native_language_field": True})


def test_every_term_gets_its_own_my_language_line_and_default_output_is_unchanged():
    plain = format_vocabulary_as_list("Fossil: gammelt\nTemperert: mildt")
    assert NATIVE_LANGUAGE_LINE not in plain
    with_lines = format_vocabulary_as_list("Fossil: gammelt\nTemperert: mildt", native_language=True)
    assert with_lines.count(NATIVE_LANGUAGE_LINE) == 2
    assert with_lines.splitlines()[0].startswith("- #strong[Fossil:]")


@pytest.mark.parametrize("level, before", [("A1.2", True), ("A2.1", True), ("B1.1", False), ("B2.2", False)])
def test_vocabulary_comes_before_the_text_only_at_a1_and_a2(level, before):
    doc = _template(level)
    vocabulary_at = doc.index("Fossil:")
    text_at = doc.index("Isbjørnen er hvit")
    assert (vocabulary_at < text_at) is before


def test_pre_reading_instruction_is_shown_only_when_the_words_come_first():
    assert "Les ordene før du leser teksten." in _template("A2")
    assert "Les ordene før du leser teksten." not in _template("B1")
    assert "Skriv ordet på ditt språk." in _template("B1")


def test_vocabulary_order_can_be_overridden():
    assert _template("B1", options={"vocabulary_before_text": True}).index("Fossil:") < _template(
        "B1", options={"vocabulary_before_text": True}
    ).index("Isbjørnen er hvit")


def test_featured_image_has_escaped_alt_text():
    doc = _template("A2", image_path="bilde.jpg", image_caption='En "sol" over havet')
    assert 'alt: "En \\"sol\\" over havet"' in doc


def test_alt_text_falls_back_to_the_topic():
    assert 'alt: "Klima"' in _template("A2", image_path="bilde.jpg")


needs_typst = pytest.mark.skipif(shutil.which("typst") is None, reason="typst is not installed")


def _pdf_text(level: str) -> str:
    pdf = create_lesson_pdf(
        content_text=TEXT,
        worksheet_text=WORKSHEET,
        topic="Klima",
        level=level,
        subject="Norsk",
    )
    return "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)


@needs_typst
def test_a2_pdf_compiles_and_shows_pre_reading_words_with_my_language_lines():
    text = _pdf_text("A2.1")
    assert text.count("Mitt språk") == 2
    assert "Les ordene før du leser teksten." in text
    assert text.index("Fossil") < text.index("Isbjørnen er hvit")


@needs_typst
def test_b2_pdf_compiles_without_my_language_lines_and_keeps_the_text_first():
    text = _pdf_text("B2.1")
    assert "Mitt språk" not in text
    assert text.index("Isbjørnen er hvit") < text.index("Fossil")
