# Spesifikasjon: Redesign av læringsark-PDF (Scriptorium for VGS)

**Til:** Utvikler (Cursor)
**Gjelder:** `pdf_service.py` (Typst-maler) + sanitering i agent-pipelinen
**Referanse:** Mockup godkjent av Marius (se vedlagt bilde) + feilene i `leksjon__9_.pdf`

Målet er todelt: (1) fjerne fire vedvarende renderingsfeil, (2) implementere ny visuell mal.
P0-feilene MÅ fikses først — ny layout på toppen av ødelagte tegn er bortkastet.

---

## DEL 1 — P0: Feilrettinger i pipelinen (før Typst-arbeid)

### 1.1 Bindestrek-bug (kritisk)

**Symptom:** Bindestrek/tankestrek rendres som et siffer. I forrige generering «8»
(«Østerrike8Ungarn»), i siste generering «1» («Østerrike1Ungarn», «18001tallet»,
«fransk1tyske», «AI1generert»). Grep i siste PDF: `Østerrike1`, `18001`.

**Diagnose:** Tegnet som varierer mellom kjøringer tyder på at LLM-en av og til skriver
et ikke-standard strektegn (typisk U+2011 NON-BREAKING HYPHEN eller U+00AD SOFT HYPHEN),
og at fonten i Typst-malen mangler glyfen — fallback-glyfen blir et vilkårlig tegn.

**Fiks (begge deler):**

1. **Unicode-normalisering** av ALL agent-tekst før den når Typst:

```python
import unicodedata

CHAR_MAP = {
    "\u00ad": "",      # soft hyphen -> fjern
    "\u2010": "-",     # hyphen
    "\u2011": "-",     # non-breaking hyphen
    "\u2012": "\u2013",# figure dash -> en-dash
    "\u2043": "-",     # hyphen bullet
    "\ufeff": "",      # BOM
    "\u200b": "",      # zero-width space
}

def normalize_text(s: str) -> str:
    s = unicodedata.normalize("NFC", s)
    for bad, good in CHAR_MAP.items():
        s = s.replace(bad, good)
    return s
```

2. **Bytt/verifiser font.** Bruk en font med full latinsk dekning som følger med i
   Docker-imaget, f.eks. **Source Sans 3** (fri, OFL, dekker – — « » ✓ ★).
   Legg inn en glyf-test i CI: kompiler et testdokument med strengen
   `- – — « » … ★ ✓ Østerrike-Ungarn 1800-tallet` og assert at pdftotext
   gir nøyaktig samme streng tilbake.

### 1.2 Markdown-lekkasje

**Symptom i siste PDF:** `Oppgave 1**`, `★ **Hvilken hendelse`, og kausalkjeder som
vises som rå backticks: `` `Tysk samling → Fransk nederlag → ...` ``.

**Fiks:** Agentene skal levere **strukturert JSON, ikke markdown** (se datakontrakt i
del 3). Som sikkerhetsnett, kjør denne stripperen på alle tekstfelter:

```python
import re

def strip_markdown(s: str) -> str:
    s = re.sub(r"\*{1,3}", "", s)          # ** og *
    s = re.sub(r"^#{1,6}\s*", "", s, flags=re.M)
    s = s.replace("`", "")
    return s
```

Kausalkjeder skal aldri være fritekst med backticks: de leveres som
`{"type": "kjede", "steg": ["Tysk samling", "Fransk nederlag", ...]}` og rendres
med Typst-komponenten `kjede()` (del 2.7).

### 1.3 Engelske ord og skrivefeil slipper gjennom korrekturen

**Symptom i siste PDF:** «These kildene» (s. 4), «I kontrast **to** dette» (s. 3),
«imperialismen**ten**» (s. 1). LLM-korrektur alene fanger ikke dette pålitelig.

**Fiks:** Deterministisk sjekk ETTER korrektur-agenten:

```python
ENGLISH_TOKENS = {"the", "is", "and", "to", "of", "with", "these", "this",
                  "in", "that", "for", "are", "was", "has"}

def find_english_leaks(s: str) -> list[str]:
    words = re.findall(r"[a-zA-Z]+", s)
    return [w for w in words if w.lower() in ENGLISH_TOKENS]
```

NB: tillat treff inni siterte engelske boktitler (*The Sleepwalkers*) — whitelist
tekst som står i `verk`-felter i JSON-en. Ved treff: send avsnittet tilbake til
korrektur-agenten med eksplisitt beskjed om ordet, maks 1 retry, ellers flagg i logg.

### 1.4 Emoji i PDF — forbudt

**Symptom:** 🎓 i seksjonsoverskrifter, og i faktarapporten kollapser fargekodingen
📗/📕/📘 til identiske 📜 — som ødelegger hele poenget med trefarget merking.

**Fiks:** Null emoji i Typst-input. Pipeline-regel: strip alle codepoints i
emoji-blokkene (`U+1F300–U+1FAFF`, `U+2600–U+27BF` unntatt ★ U+2605, ☆ U+2606,
→ U+2192, ✓ U+2713 som fonten skal dekke). Faktarapport-status erstattes av
fargede tekstetiketter (del 2.8).

### 1.5 PDF-lint (siste port før levering)

Kjør på ferdig kompilert PDF (pdftotext) + på Typst-input. Feil => regenerer/flagg:

- [ ] Ingen `**`, `` ` ``, `##` i tekst
- [ ] Ingen ord fra ENGLISH_TOKENS utenfor whitelist
- [ ] Ingen emoji-codepoints
- [ ] Balanserte «» og ()
- [ ] Mønsteret `[a-zæøå][18][a-zæøå]` (bokstav-siffer-bokstav med 1/8) finnes ikke
      — fanger bindestrek-buggen direkte
- [ ] Ingen side med < 120 tegn tekst (foreldreløse sider)

---

## DEL 2 — Typst-mal (ny layout)

Lag `templates/laeringsark.typ` med komponentene under. Alle farger og mål er
forpliktende — de matcher godkjent mockup.

### 2.1 Design-tokens

```typst
// === Farger (Scriptorium = blå; oppgaver = lilla; kilde-badge = grønn) ===
#let blue-50   = rgb("#E6F1FB")
#let blue-600  = rgb("#185FA5")
#let blue-800  = rgb("#0C447C")
#let purple-50  = rgb("#EEEDFE")
#let purple-200 = rgb("#AFA9EC")
#let purple-600 = rgb("#534AB7")
#let purple-800 = rgb("#3C3489")
#let green-50  = rgb("#EAF3DE")
#let green-800 = rgb("#27500A")
#let red-50    = rgb("#FCEBEB")
#let red-800   = rgb("#791F1F")
#let amber-50  = rgb("#FAEEDA")
#let amber-800 = rgb("#633806")
#let gray-100  = rgb("#F1EFE8")
#let gray-300  = rgb("#B4B2A9")
#let gray-400  = rgb("#888780")
#let gray-600  = rgb("#5F5E5A")
#let ink       = rgb("#2C2C2A")
```

### 2.2 Sideoppsett, topp- og bunntekst

```typst
#set text(font: "Source Sans 3", size: 10.5pt, lang: "nb", fill: ink)
#set par(leading: 0.62em, justify: false)

#set page(
  paper: "a4",
  margin: (top: 20mm, bottom: 18mm, left: 18mm, right: 16mm),
  header: context if counter(page).get().first() > 1 {
    set text(size: 8pt)
    grid(columns: (1fr, auto),
      text(fill: blue-600, weight: 500)[Scriptorium · #fag],
      text(fill: gray-400)[#tema])
    v(2pt); line(length: 100%, stroke: 0.4pt + gray-300)
  },
  footer: context {
    line(length: 100%, stroke: 0.4pt + gray-300); v(3pt)
    set text(size: 8pt, fill: gray-400)
    grid(columns: (1fr, auto),
      [Scriptorium for VGS · klasserom.ai],
      [Side #counter(page).display() av #counter(page).final().first()])
  },
)
```

`#fag` og `#tema` injiseres av `pdf_service` som variabler øverst i dokumentet.

### 2.3 Forside-topp: tittel, chips og kilde-badge

```typst
#let chip(txt, fill: blue-50, ink: blue-800) =
  box(fill: fill, radius: 8pt, inset: (x: 8pt, y: 3pt),
      text(size: 8.5pt, fill: ink, weight: 500)[#txt])

#let tittelblokk(tittel, niva, modus, kilde: none) = {
  grid(columns: (1fr, auto),
    text(size: 9pt, fill: blue-600, weight: 500, tracking: 0.3pt)[Scriptorium · #fag],
    chip[#niva · #modus])
  v(4pt)
  text(size: 19pt, weight: 500)[#tittel]
  v(6pt)
  if kilde != none {
    box(fill: green-50, radius: 4pt, inset: (x: 8pt, y: 4pt))[
      #text(size: 8.5pt, fill: green-800)[✓ Kildeforankret: #kilde]]
  } else {
    box(fill: amber-50, radius: 4pt, inset: (x: 8pt, y: 4pt))[
      #text(size: 8.5pt, fill: amber-800)[Ikke kildeforankret — fakta hviler på modellens kunnskap]]
  }
  v(10pt)
}
```

Badgen skal stå i selve PDF-en på side 1 — alltid, i begge varianter.

### 2.4 Seksjonsoverskrift med fargestripe

```typst
#let seksjonsteller = counter("seksjon")
#let seksjonstittel(t) = {
  seksjonsteller.step()
  block(above: 1.5em, below: 0.7em, grid(
    columns: (3pt, auto), column-gutter: 8pt, align: horizon,
    rect(width: 3pt, height: 12pt, fill: blue-600, radius: 0pt),
    text(size: 12.5pt, weight: 500, fill: blue-800)[
      #context seksjonsteller.display() · #t]))
}
```

NB: `radius: 0` på stripen — ingen avrundede hjørner på ensidige aksenter.

### 2.5 Margbegreper (viktigste nye komponent)

Hver fagtekst-seksjon rendres som en grid med hovedtekst venstre og begrepskolonne
høyre. Begrepene kommer strukturert fra agenten (del 3) — IKKE lenger som parenteser
i løpende tekst.

```typst
#let begrepskolonne(begreper) = block(
  stroke: (left: 0.5pt + gray-300), inset: (left: 4mm))[
  #text(size: 7.5pt, fill: gray-400, tracking: 0.6pt, weight: 500)[BEGREPER]
  #v(2.5mm)
  #for b in begreper [
    #text(size: 8.5pt, weight: 500, fill: blue-600)[#b.term] \
    #text(size: 8.5pt, fill: gray-600)[#b.def]
    #v(2.5mm)
  ]
]

#let fagseksjon(tittel, begreper: (), body) = {
  seksjonstittel(tittel)
  if begreper.len() > 0 {
    grid(columns: (1fr, 44mm), column-gutter: 6mm,
         body, begrepskolonne(begreper))
  } else { body }
}
```

**Kjent begrensning (akseptert):** grid-raden kan brytes over sider; begrepskolonnen
topp-justeres da på første side av seksjonen. Hvis en seksjon har > 4 begreper eller
kolonnen blir høyere enn brødteksten, fall tilbake til en begrepsboks (gray-100,
full bredde) rett under seksjonstittelen i stedet. Implementer fallbacken som en
enkel heuristikk i Python: `if len(begreper) > 4: bruk boks`.

### 2.6 K-markør (kildehenvisning)

```typst
#let K = h(0.5pt) + super(text(size: 6.5pt, fill: gray-300)[K])
```

Pipeline: skribent-agenten markerer setninger med token `[K]`; Python erstatter
`[K]` med `#K` i Typst-kilden. Legenden («K = påstanden bygger på kildematerialet…»)
beholdes, 7.5pt grå, nederst i fagteksten.

### 2.7 Oppgaveboks, svarlinjer og kausalkjede

```typst
#let svarlinjer(n) = for _ in range(n) {
  v(13pt); line(length: 100%, stroke: 0.5pt + purple-200)
}

#let oppgaveboks(nr, niva, tekst, linjer: 0) = block(
  breakable: false, fill: purple-50, radius: 6pt,
  inset: 11pt, width: 100%, above: 1em, below: 1em)[
  #grid(columns: (1fr, auto),
    text(size: 10pt, weight: 500, fill: purple-800)[Oppgave #nr],
    text(size: 9pt, fill: purple-600)[
      #("★" * niva)#("☆" * (3 - niva)) #h(3pt)
      #if niva == 1 [Grunnleggende] else if niva == 2 [Middels] else [Avansert]])
  #v(4pt)
  #text(size: 9.5pt, fill: purple-600)[#tekst]
  #if linjer > 0 { svarlinjer(linjer) }
]

#let kjede(steg) = block(fill: gray-100, radius: 4pt, inset: 9pt,
  width: 100%, breakable: false)[
  #set text(size: 9pt, fill: gray-600)
  #steg.map(s => box(s)).join(text(fill: blue-600)[ → ])
]
```

`breakable: false` på oppgavebokser er obligatorisk — instruks og svarlinjer skal
aldri splittes over sidebryting. Stjerne-legenden i bunnen av arket fjernes
(nivået står nå i klartekst i hver boks).

### 2.8 Faktarapport — egen fil + tekstetiketter

To endringer:

1. **Egen PDF.** `pdf_service` kompilerer to dokumenter: `laeringsark_<tema>.pdf`
   (elev) og `faktarapport_<tema>.pdf` (lærer). API-responsen returnerer begge;
   frontend viser to nedlastingsknapper. Dette eliminerer risikoen for at læreren
   skriver ut rapporten til elevene ved «skriv ut alle sider».

2. **Statusetiketter i stedet for emoji:**

```typst
#let etikett(txt, fill, ink) = box(fill: fill, radius: 2pt,
  inset: (x: 4pt, y: 1.5pt),
  text(size: 7pt, weight: 500, fill: ink, tracking: 0.4pt)[#txt])

#let st-dekket  = etikett("DEKKET AV KILDEN", green-50, green-800)
#let st-strid   = etikett("I STRID MED KILDEN", red-50, red-800)
#let st-utenfor = etikett("UTENFOR KILDEN", blue-50, blue-800)
#let st-usikker = etikett("BØR PRESISERES", amber-50, amber-800)
```

Faktasjekk-agenten leverer status som enum-streng (`"dekket" | "strid" | "utenfor"
| "usikker"`), aldri som symbol. Rapportens forside får i tillegg en
**konklusjonslinje** øverst (én setning fra agenten, f.eks. «Trygt å bruke;
2 påstander bør presiseres muntlig»), satt i 11pt weight 500.

---

## DEL 3 — Datakontrakt (endring i agent-output)

Skribent-agentens output-skjema utvides. Begreper flyttes ut av brødteksten:

```json
{
  "tittel": "Første verdenskrig — årsaker og skyldspørsmål",
  "seksjoner": [
    {
      "tittel": "Maktbalansens fall",
      "avsnitt": [
        "Etter Napoleonskrigene innførte Wienkongressen i 1815 et prinsipp om europeisk maktbalanse[K]. ..."
      ],
      "begreper": [
        {"term": "Maktbalanse", "def": "Ingen enkeltstat er sterk nok til å dominere de andre."},
        {"term": "Nasjonalisme", "def": "Ideologi: hver nasjon skal ha sin egen stat."}
      ],
      "kjeder": [
        {"steg": ["Tysk samling", "Fransk nederlag", "Endret maktbalanse", "Fiendtlige blokker"]}
      ]
    }
  ]
}
```

Prompt-regler for skribenten (legg til i agents.py):
- Begrepsdefinisjoner skal IKKE stå i parentes i brødteksten — kun i `begreper`-listen.
  I brødteksten brukes begrepet naturlig, første forekomst kan stå i kursiv.
- `def` maks 12 ord (margkolonnen er smal).
- Maks 4 begreper per seksjon.
- Kausalkjeder kun i `kjeder`, aldri som tekst med piler/backticks.

**Typst-escaping (viktig):** All agent-tekst som interpoleres inn i Typst-kilden må
escapes for Typst-spesialtegn før interpolering: `# $ @ [ ] < > \ _ *`.
Enklest: skriv en `typst_escape()` i Python og bruk den på hvert tekstfelt — uten
dette vil en LLM-generert `#` eller `$` knekke kompileringen sporadisk.

---

## DEL 4 — Akseptansekriterier

Generer testarket «Første verdenskrig, Historie, VG3, Fordypning» og verifiser:

1. `pdftotext` av PDF-en inneholder `Østerrike-Ungarn` og `1800-tallet` korrekt,
   og null treff på regex `[a-zæøå][18][a-zæøå]`.
2. Null forekomster av `**`, `` ` ``, emoji-codepoints, og ord fra ENGLISH_TOKENS.
3. Side 1 viser tittelblokk med chip og kilde-badge (grønn eller gul variant).
4. Hver fagtekst-seksjon har blå stripe + nummer, og begreper i høyre margkolonne
   (eller boks-fallback ved > 4 begreper). Ingen definisjoner i parentes i brødtekst.
5. K-markører er hevet, 6.5pt, grå.
6. Alle oppgavebokser er hele (ingen splittet over sidebryting), med stjerner +
   nivånavn i topplinjen og svarlinjer der `linjer > 0`.
7. Kausalkjeder rendres som grå boks med blå piler — aldri backticks.
8. Faktarapporten er en SEPARAT PDF med konklusjonslinje øverst og fargede
   tekstetiketter (ingen emoji).
9. Ingen side med under 120 tegn innhold.
10. Glyf-testen i CI er grønn.

Estimert rekkefølge: 1.1–1.4 (½ dag), Typst-komponenter 2.1–2.7 (1–2 dager),
faktarapport-splitt 2.8 + datakontrakt del 3 (1 dag), lint + CI del 1.5/4 (½ dag).
