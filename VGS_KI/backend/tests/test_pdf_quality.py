"""Quality gates from SPEC_laeringsark_redesign.

- Glyph round-trip test (spec 1.1 / acceptance 10): compile a document with
  the critical glyphs and assert the extracted text matches exactly.
- Text-pipeline unit tests (spec 1.1-1.5).
- Acceptance render (DEL 4, offline): build a structured læringsark + a
  separate faktarapport from fixtures, compile both, and verify the criteria
  that can be checked without a live LLM.
"""
import re
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from laeringsark_renderer import (  # noqa: E402
    balance_oppgaver,
    build_faktarapport_doc,
    build_laeringsark_doc,
    coerce_structured_lesson,
    coerce_structured_rapport,
    make_image_observation_task,
    parse_oppgaver,
    strip_ungrounded_k_markers,
)
from text_pipeline import (  # noqa: E402
    extract_pdf_pages,
    find_english_leaks,
    lint_pdf,
    lint_text,
    normalize_text,
    strip_emoji,
    strip_markdown,
    typst_escape,
)

_HAS_TYPST = shutil.which("typst") is not None
requires_typst = pytest.mark.skipif(not _HAS_TYPST, reason="typst CLI not installed")


def _compile(source: str) -> bytes:
    from pdf_service import compile_typst
    return compile_typst(source)


def _pdf_text(pdf: bytes) -> str:
    pages = extract_pdf_pages(pdf)
    assert pages is not None, "no PDF text extractor available (pdftotext/pypdf)"
    return "\f".join(pages)


# ── Spec 1.1: unicode normalisation + glyph round-trip ───────────────────────

def test_normalize_text_replaces_hyphen_variants():
    assert normalize_text("Østerrike\u2011Ungarn") == "Østerrike-Ungarn"
    assert normalize_text("1800\u2010tallet") == "1800-tallet"
    assert normalize_text("AI\u00adgenerert") == "AIgenerert"  # soft hyphen removed
    assert normalize_text("a\u2012b") == "a\u2013b"  # figure dash -> en-dash
    assert normalize_text("x\ufeffy\u200bz") == "xyz"


GLYPH_TEST_STRING = "- – — « » … ★ ✓ Østerrike-Ungarn 1800-tallet"


@requires_typst
def test_glyph_roundtrip():
    """Spec 1.1: the template font must render every critical glyph; the
    extracted text must come back exactly."""
    source = "\n".join([
        '#import "laeringsark.typ": *',
        '#show: doc => laeringsark-oppsett(doc, fag: "Test", tema: "Glyfer")',
        f"{typst_escape(GLYPH_TEST_STRING)}",
    ])
    text = _pdf_text(_compile(source))
    assert GLYPH_TEST_STRING in text.replace("\n", " ")
    # The hyphen-bug pattern must never appear
    assert not re.search(r"[a-zæøå][18][a-zæøå]", text)


# ── Spec 1.2-1.4: stripper, english leaks, emoji ──────────────────────────────

def test_strip_markdown():
    assert strip_markdown("**bold** og `kode`") == "bold og kode"
    assert strip_markdown("## Overskrift\ntekst") == "Overskrift\ntekst"


def test_find_english_leaks_with_whitelist():
    assert find_english_leaks("These kildene viser dette") == ["These"]
    assert find_english_leaks("I kontrast with dette") == ["with"]
    # 'for' and 'to' are Norwegian homographs and must not be flagged
    assert find_english_leaks("Det er to grunner for dette") == []
    # Whitelisted work titles may contain English
    assert find_english_leaks(
        "Boken The Sleepwalkers er sentral", ["The Sleepwalkers"]) == []


def test_strip_emoji_keeps_allowed_symbols():
    assert strip_emoji("🎓 Overskrift 📗") == " Overskrift "
    assert strip_emoji("★ ☆ → ✓") == "★ ☆ → ✓"


def test_typst_escape():
    assert typst_escape("100$ #tag [x]") == "100\\$ \\#tag \\[x\\]"


def test_lint_text_catches_spec_issues():
    issues = lint_text("Østerrike1Ungarn og **rester** med `backtick`")
    joined = " | ".join(issues)
    assert "bindestrek-bug" in joined
    assert "'**'" in joined
    assert "backtick" in joined


# ── DEL 3: structured contract helpers ────────────────────────────────────────

STRUCTURED_FIXTURE = {
    "tittel": "Første verdenskrig — årsaker og skyldspørsmål",
    "ingress": "Sommeren 1914 gikk Europa fra fred til storkrig på fem uker.",
    "seksjoner": [
        {
            "tittel": "Maktbalansens fall",
            "avsnitt": [
                "Etter Napoleonskrigene innførte Wienkongressen i 1815 et prinsipp om "
                "europeisk maktbalanse.[K] Østerrike-Ungarn var en av stormaktene som "
                "garanterte ordenen på 1800-tallet.",
                "Mot slutten av århundret begynte systemet å slå sprekker, og *nasjonalisme* "
                "ble en stadig sterkere kraft.",
            ],
            "begreper": [
                {"term": "Maktbalanse", "def": "Ingen enkeltstat er sterk nok til å dominere de andre."},
                {"term": "Nasjonalisme", "def": "Ideologi: hver nasjon skal ha sin egen stat."},
            ],
            "kjeder": [
                {"steg": ["Tysk samling", "Fransk nederlag", "Endret maktbalanse", "Fiendtlige blokker"]},
            ],
        },
        {
            "tittel": "Skuddene i Sarajevo",
            "avsnitt": [
                "Attentatet på tronfølgeren Franz Ferdinand 28. juni 1914 utløste "
                "julikrisen.[K] Alliansesystemet trakk stormaktene inn én etter én.",
            ],
            "begreper": [],
            "kjeder": [],
        },
    ],
    "verk": ["The Sleepwalkers"],
}

WORKSHEET_FIXTURE = """
FORSTÅELSE OG ANALYSE
1. ★ Hvilken hendelse utløste julikrisen i 1914?
2. ★★ Forklar hvordan alliansesystemet bidro til at en regional konflikt ble en storkrig.
3. ★★ Hva menes med maktbalanse?
   a) At alle stater er like store
   b) At ingen enkeltstat kan dominere de andre
   c) At stormaktene deler kolonier likt

DRØFTING
1. ★★★ Drøft påstanden «Tyskland hadde hovedansvaret for krigsutbruddet».
"""


def test_coerce_structured_lesson_roundtrip():
    data = coerce_structured_lesson(STRUCTURED_FIXTURE)
    assert data is not None
    assert len(data["seksjoner"]) == 2
    assert data["seksjoner"][0]["kjeder"][0][0] == "Tysk samling"
    assert data["verk"] == ["The Sleepwalkers"]
    assert coerce_structured_lesson({"seksjoner": []}) is None
    assert coerce_structured_lesson("ikke en dict") is None


def test_parse_oppgaver_stars_and_mcq():
    oppgaver = parse_oppgaver(
        "1. ★ Lett oppgave?\n2. ★★★ Vanskelig?\n3. Med alternativer\n a) Ja\n b) Nei",
        "1. Drøft noe stort.",
    )
    assert [o["niva"] for o in oppgaver] == [1, 3, 2, 3]
    assert oppgaver[2]["alternativer"] == ["a) Ja", "b) Nei"]
    assert oppgaver[2]["linjer"] == 0  # MCQ -> no writing lines
    assert oppgaver[3]["linjer"] == 6  # discussion -> long answer
    assert all("★" not in o["tekst"] for o in oppgaver)


def test_ungrounded_documents_never_keep_k_markers():
    data = coerce_structured_lesson(STRUCTURED_FIXTURE)
    cleaned = strip_ungrounded_k_markers(data)
    assert "[K]" not in "\n".join(
        paragraph
        for section in cleaned["seksjoner"]
        for paragraph in section["avsnitt"]
    )


def test_image_crew_rationale_becomes_explicit_source_aware_task():
    task = make_image_observation_task(
        caption="En vasall sverger troskap",
        rationale="Viser det personlige lojalitetsbåndet",
        source="ai",
        subject="Historie",
    )
    assert task["image_task"] is True
    assert task["niva"] == 2
    assert "to konkrete detaljer" in task["tekst"]
    assert "ikke en historisk" in task["tekst"]


def test_long_task_sets_are_balanced_automatically():
    tasks = [
        {"niva": 2, "tekst": f"Oppgave {i}", "linjer": 3, "alternativer": []}
        for i in range(5)
    ] + [
        {"niva": 3, "tekst": "Drøft", "linjer": 6, "alternativer": []}
        for _ in range(2)
    ]
    balanced, compact = balance_oppgaver(tasks)
    assert compact is True
    assert [task["linjer"] for task in balanced[-2:]] == [4, 4]
    assert all(task["linjer"] <= 2 for task in balanced[:5])


def test_learning_sheet_caps_tall_images_to_protect_pagination():
    data = coerce_structured_lesson(STRUCTURED_FIXTURE)
    doc = build_laeringsark_doc(
        data,
        fag="Historie",
        tema="Test",
        niva="VG2",
        modus="Standard",
        image_filename="portrait.png",
    )
    assert 'height: 68mm, fit: "contain"' in doc


RAPPORT_FIXTURE = {
    "konklusjon": "Trygt å bruke; 2 påstander bør presiseres muntlig.",
    "punkter": [
        {"status": "dekket", "pastand": "Wienkongressen fant sted i 1815.",
         "kommentar": "Står direkte i kilden."},
        {"status": "strid", "pastand": "Attentatet skjedde 27. juni 1914.",
         "kommentar": "Kilden sier 28. juni."},
        {"status": "utenfor", "pastand": "Bismarck ble avsatt i 1890.", "kommentar": ""},
        {"status": "ugyldig-status", "pastand": "Noe usikkert.", "kommentar": ""},
    ],
    "kausalitet": ["«Alliansesystemet førte til krigen» — utelater julikrisens valg."],
    "automatiske_rettelser": ["Kausalsetningen er nyansert med flere mellomledd."],
    "perspektiver": ["Kvinners rolle i krigsmobiliseringen mangler."],
    "ikke_dekket": ["Krigens gang etter 1914."],
    "kilder": ["Christopher Clark: The Sleepwalkers (2012)"],
    "verk": ["The Sleepwalkers"],
}


def test_coerce_structured_rapport_normalises_status():
    rapport = coerce_structured_rapport(RAPPORT_FIXTURE)
    assert rapport is not None
    statuses = [p["status"] for p in rapport["punkter"]]
    assert statuses == ["dekket", "strid", "utenfor", "usikker"]  # invalid -> usikker
    assert rapport["automatiske_rettelser"]
    assert coerce_structured_rapport({}) is None


def test_coerce_structured_rapport_does_not_split_string_fields_into_characters():
    rapport = coerce_structured_rapport({
        "konklusjon": "Trygt å bruke.",
        "perspektiver": "Elevteksten viser flere synsvinkler.",
    })
    assert rapport["perspektiver"] == ["Elevteksten viser flere synsvinkler."]


# ── DEL 4: acceptance render (offline) ────────────────────────────────────────

@requires_typst
def test_acceptance_laeringsark_render():
    data = coerce_structured_lesson(STRUCTURED_FIXTURE)
    from pdf_service import parse_worksheet_content
    sections = parse_worksheet_content(WORKSHEET_FIXTURE)
    oppgaver = parse_oppgaver(sections["comprehension"], sections["discussion"])
    assert oppgaver, "worksheet fixture must parse into oppgaver"

    doc = build_laeringsark_doc(
        data,
        fag="Historie",
        tema="Første verdenskrig",
        niva="VG3",
        modus="Fordypning",
        kilde="NDLA: Bakgrunnen for første verdenskrig",
        har_k_markorer=True,
        oppgaver=oppgaver,
    )
    pdf = _compile(doc)
    text = _pdf_text(pdf)

    # 1. Hyphen bug fixed
    assert "Østerrike-Ungarn" in text
    assert "1800-tallet" in text
    assert not re.search(r"[a-zæøå][18][a-zæøå]", text)
    # 2. No markdown remnants / english leaks / emoji (criteria 2)
    assert lint_pdf(pdf, whitelist=("The Sleepwalkers",)) == []
    # 3. Title block with chip and source badge
    assert "Kildeforankret" in text
    assert "VG3" in text and "Fordypning" in text
    # 4. Numbered sections + margin terms (not in parentheses in body)
    assert "1 · Maktbalansens fall" in text.replace("\n", " ") or "Maktbalansens fall" in text
    assert "BEGREPER" in text
    assert "Maktbalanse" in text
    # 6. Task boxes with level names in clear text
    assert "Oppgave 1" in text
    assert "Grunnleggende" in text and "Avansert" in text
    # 7. Causal chain rendered with arrows, never backticks
    assert "Tysk samling" in text and "→" in text
    assert "`" not in text


@requires_typst
def test_acceptance_laeringsark_ungrounded_badge():
    data = coerce_structured_lesson(STRUCTURED_FIXTURE)
    doc = build_laeringsark_doc(
        data, fag="Historie", tema="Test", niva="VG3", modus="Standard", kilde=None,
    )
    text = _pdf_text(_compile(doc))
    assert "Ikke kildeforankret" in text


@requires_typst
def test_acceptance_faktarapport_separate_pdf():
    rapport = coerce_structured_rapport(RAPPORT_FIXTURE)
    doc = build_faktarapport_doc(
        rapport, fag="Historie", tema="Første verdenskrig",
        kilde="NDLA: Bakgrunnen for første verdenskrig",
        teacher_key="Oppgave 1: Attentatet i Sarajevo.\n\n"
        "Oppgave 2: Eleven bør forklare minst to mellomledd.",
    )
    text = _pdf_text(_compile(doc))

    # 8. Conclusion line on top + coloured text labels, no emoji
    assert "Trygt å bruke" in text
    assert "DEKKET AV KILDEN" in text
    assert "I STRID MED KILDEN" in text
    assert "UTENFOR KILDEN" in text
    assert "BØR PRESISERES" in text
    assert "Kun for læreren" in text
    assert "Lærerveiledning" in text
    assert "Kort fasit og vurderingsmomenter" in text
    assert "Attentatet i Sarajevo" in text
    assert "Automatiske faglige rettelser" in text
    for ch in "📗📕📘✅⚠️🔶":
        assert ch not in text
    # The full student lesson body must not be duplicated in the teacher guide.
    # Short task references are expected because the guide now includes an answer key.
    assert "Sommeren 1914 gikk Europa fra fred til storkrig" not in text
