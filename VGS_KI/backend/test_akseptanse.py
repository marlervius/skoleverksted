"""Akseptansetest for SPEC_laeringsark_redesign (DEL 4).

Kjøres direkte:  python test_akseptanse.py
Krever typst på PATH. Bruker pdftotext når tilgjengelig (ellers pypdf).

Testene dekker:
  A1  bindestrek-bug: U+2011 m.fl. normaliseres og overlever pdftotext
  A2  ingen markdown-rester i PDF-tekst
  A3  ingen emoji i PDF-tekst
  A4  engelsk-lekkasjesjekk med verk-whitelist
  A5  alle nye komponenter kompilerer (margbegreper, kjede, K, oppgavebokser)
  A6  faktarapport som egen PDF med tekstetiketter + konklusjonslinje
  A7  glyf-test: alle spesialtegn malen bruker overlever runden gjennom PDF
"""
from __future__ import annotations

import sys

# Windows-konsoller kan stå i cp1252; testnavnene inneholder emoji/spesialtegn.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from laeringsark_renderer import (
    build_faktarapport_doc,
    build_laeringsark_doc,
    coerce_structured_lesson,
    coerce_structured_rapport,
    parse_oppgaver,
)
from pdf_service import compile_typst
from text_pipeline import (
    extract_pdf_pages,
    find_english_leaks,
    lint_pdf,
    normalize_text,
    strip_emoji,
    strip_markdown,
    typst_escape,
)

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    status = "OK  " if cond else "FAIL"
    print(f"[{status}] {name}" + (f"  -- {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(name)


# ── Enhetstester for text_pipeline ────────────────────────────────────────────

def test_unit() -> None:
    check("normalize: U+2011 -> '-'",
          normalize_text("Østerrike\u2011Ungarn") == "Østerrike-Ungarn")
    check("normalize: soft hyphen fjernes",
          normalize_text("hyper\u00adinflasjon") == "hyperinflasjon")
    check("strip_markdown fjerner ** og ##",
          strip_markdown("## Tittel\n**fet** og `kode`") == "Tittel\nfet og kode")
    check("strip_emoji fjerner emoji, beholder stjerner/hake/pil",
          strip_emoji("Hei 🎉★☆✓→📗!") == "Hei ★☆✓→!")
    check("typst_escape escaper # $ [ ]",
          typst_escape("#x $y [z]") == "\\#x \\$y \\[z\\]")

    leaks = find_english_leaks("Dette is en tekst med the problemer, men for og to er norske.")
    check("english-leak: finner 'is'/'the', ikke 'for'/'to'",
          sorted(w.lower() for w in leaks) == ["is", "the"], str(leaks))
    leaks_wl = find_english_leaks(
        "Boken «The Sleepwalkers» av Clark.", whitelist=("The Sleepwalkers",))
    check("english-leak: verk-whitelist respekteres", leaks_wl == [], str(leaks_wl))


# ── Testdata som dekker hele komponentbiblioteket ─────────────────────────────

SAMPLE_LESSON = {
    "tittel": "Mellomkrigstiden 1918\u20131939",
    "ingress": "Tyskland gikk fra demokrati til diktatur på under femten år. 🎉",
    "seksjoner": [
        {
            "tittel": "Versaillesfreden",
            "avsnitt": [
                "Østerrike\u2011Ungarn ble oppløst etter første verdenskrig. [K] "
                "Tyskland måtte betale **enorme** krigsskadeerstatninger. [K]",
                "Historikeren Clark omtaler dette i «The Sleepwalkers» som en *katastrofe*.",
            ],
            "begreper": [
                {"term": "Reparasjoner", "def": "Krigsskadeerstatninger som taperen må betale"},
                {"term": "Dolkestøtslegenden", "def": "Myten om at hæren ble sveket hjemmefra"},
                {"term": "Hyperinflasjon", "def": "Ekstrem prisstigning der pengene mister verdi"},
            ],
            "kjeder": [
                {"steg": ["Versaillesfreden", "Reparasjoner", "Hyperinflasjon", "Politisk ustabilitet"]}
            ],
        },
        {
            "tittel": "Veien mot diktatur",
            "avsnitt": [
                "På 1920\u2011tallet vokste ekstreme bevegelser fram i hele Europa. [K]",
            ],
            # 5 begreper -> skal trigge begrepsboks-fallback i full bredde
            "begreper": [
                {"term": "Fascisme", "def": "Autoritær nasjonalistisk ideologi"},
                {"term": "Nazisme", "def": "Tysk fascisme med raselære"},
                {"term": "Kommunisme", "def": "Revolusjonær sosialistisk ideologi"},
                {"term": "Weimarrepublikken", "def": "Det tyske demokratiet 1919 til 1933"},
                {"term": "Riksdagen", "def": "Den tyske nasjonalforsamlingen"},
            ],
            "kjeder": [],
        },
    ],
    "verk": ["The Sleepwalkers"],
}

SAMPLE_WORKSHEET_COMPREHENSION = """1. ★ Hva var Versaillesfreden?
2. ★★ Forklar hvorfor hyperinflasjonen rammet Tyskland.
3. ★★ Hva menes med dolkestøtslegenden?
a) En militær strategi
b) En myte om svik
c) En fredsavtale
"""

SAMPLE_WORKSHEET_DISCUSSION = """1. ★★★ Drøft om Versaillesfreden gjorde en ny storkrig uunngåelig.
"""

SAMPLE_RAPPORT = {
    "konklusjon": "Teksten er faglig forsvarlig, men forenkler årsaksbildet noe.",
    "punkter": [
        {"status": "dekket", "pastand": "Tyskland måtte betale reparasjoner",
         "kommentar": "Dekket av kilden, avsnitt 2."},
        {"status": "strid", "pastand": "Versaillesfreden alene førte til Hitler",
         "kommentar": "Omstridt kausalpåstand i forskningen."},
        {"status": "utenfor", "pastand": "Hyperinflasjonen toppet seg i 1923"},
        {"status": "usikker", "pastand": "Flertallet støttet dolkestøtslegenden"},
    ],
    "kausalitet": ["Reparasjoner → Hitler framstilles som en rett linje."],
    "perspektiver": ["Sovjetunionens rolle er ikke omtalt."],
    "ikke_dekket": ["Kvinners stemmerett i Weimarrepublikken."],
    "kilder": ["Store norske leksikon: Versaillesfreden"],
    "verk": ["The Sleepwalkers"],
}


def test_laeringsark_pdf() -> bytes:
    data = coerce_structured_lesson(SAMPLE_LESSON)
    check("coerce_structured_lesson godtar testdata", data is not None)
    assert data is not None

    oppgaver = parse_oppgaver(SAMPLE_WORKSHEET_COMPREHENSION, SAMPLE_WORKSHEET_DISCUSSION)
    check("parse_oppgaver finner 4 oppgaver", len(oppgaver) == 4, str(len(oppgaver)))
    check("parse_oppgaver: MCQ får 0 linjer",
          any(o["alternativer"] and o["linjer"] == 0 for o in oppgaver))

    doc = build_laeringsark_doc(
        data, fag="Historie", tema="Mellomkrigstiden", niva="VG3", modus="Standard",
        kilde="NDLA: Mellomkrigstiden", har_k_markorer=True,
        laeringsmaal="- Forklare årsakene til andre verdenskrig",
        oppgaver=oppgaver,
    )
    for component in ("#tittelblokk", "#fagseksjon", "#begrepsboks", "#kjede(",
                      "#k-legende", "#oppgaveboks", "#K"):
        check(f"A5 Typst-kilde bruker {component}", component in doc)

    pdf = compile_typst(doc)
    check("A5 læringsark kompilerer", len(pdf) > 1000)

    pages = extract_pdf_pages(pdf)
    check("PDF-tekst kan ekstraheres", pages is not None)
    text = "\f".join(pages or [])

    # A1: bindestrek-bug
    check("A1 'Østerrike-Ungarn' korrekt i PDF", "Østerrike-Ungarn" in text,
          repr([l for l in text.splitlines() if "sterrike" in l][:3]))
    check("A1 '1920-tallet' korrekt i PDF", "1920-tallet" in text)
    check("A1 ingen 'Østerrike1Ungarn'", "Østerrike1Ungarn" not in text)

    # A2/A3: ingen markdown/emoji
    check("A2 ingen '**' i PDF", "**" not in text)
    check("A2 ingen backtick i PDF", "`" not in text)
    check("A3 ingen 🎉 i PDF", "🎉" not in text)

    # A4 + 1.5: lint med verk-whitelist skal være ren
    issues = lint_pdf(pdf, ("The Sleepwalkers",))
    check("A4 lint_pdf uten funn (med whitelist)", issues == [], str(issues))
    issues_no_wl = lint_pdf(pdf, ())
    check("A4 lint flagger 'the' uten whitelist",
          any(i.startswith("engelske ord") for i in issues_no_wl), str(issues_no_wl))

    with open("test_laeringsark.pdf", "wb") as f:
        f.write(pdf)
    return pdf


def test_faktarapport_pdf() -> None:
    rapport = coerce_structured_rapport(SAMPLE_RAPPORT)
    check("coerce_structured_rapport godtar testdata", rapport is not None)
    assert rapport is not None

    doc = build_faktarapport_doc(rapport, fag="Historie", tema="Mellomkrigstiden",
                                 kilde="NDLA: Mellomkrigstiden")
    for component in ("#faktarapport-topp", "#konklusjonslinje",
                      "#st-dekket", "#st-strid", "#st-utenfor", "#st-usikker"):
        check(f"A6 rapport-kilde bruker {component}", component in doc)

    pdf = compile_typst(doc)
    check("A6 faktarapport kompilerer som egen PDF", len(pdf) > 1000)

    text = "\f".join(extract_pdf_pages(pdf) or [])
    for label in ("DEKKET AV KILDEN", "I STRID MED KILDEN", "UTENFOR KILDEN", "BØR PRESISERES"):
        check(f"A6 tekstetikett '{label}' i PDF", label in text)
    check("A6 konklusjon i PDF", "faglig forsvarlig" in text)
    check("A6 ingen emoji-statuser i PDF",
          all(e not in text for e in ("📗", "📕", "📘", "⚠")))

    with open("test_faktarapport.pdf", "wb") as f:
        f.write(pdf)


def test_glyf() -> None:
    """A7: alle spesialtegn malen bruker må overleve PDF-runden."""
    glyphs = "– — « » „ \u201c \u201d ★ ☆ ✓ → ‣ æ ø å Æ Ø Å é É"
    doc = (
        '#import "laeringsark.typ": *\n'
        '#show: doc => laeringsark-oppsett(doc, fag: "Glyftest", tema: "Glyftest")\n'
        f"Glyfer: {glyphs}\n\n"
        + ("Fylltekst for å unngå foreldreløs side-varsel i lint. " * 5)
    )
    pdf = compile_typst(doc)
    text = "\f".join(extract_pdf_pages(pdf) or [])
    missing = [g for g in glyphs.split() if g not in text]
    check("A7 alle glyfer overlever PDF-runden", not missing, f"mangler: {missing}")


if __name__ == "__main__":
    print("== Enhetstester (DEL 1/3) ==")
    test_unit()
    print("\n== Læringsark (DEL 2 + 1.5) ==")
    test_laeringsark_pdf()
    print("\n== Faktarapport (DEL 2.8) ==")
    test_faktarapport_pdf()
    print("\n== Glyftest (DEL 4) ==")
    test_glyf()

    print()
    if FAILURES:
        print(f"{len(FAILURES)} TESTER FEILET:")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    print("Alle akseptansetester bestått.")
