# MateMaTeX 2.0 — Fase 2: Funksjonalitet

Du skal nå bygge ut funksjonaliteten i MateMaTeX 2.0. Fase 1 (AI-motor med LangGraph, SymPy-verifisering, modellagnostisk LLM-interface) og grunnstrukturen (FastAPI backend, Next.js frontend, PostgreSQL-skjema) er allerede på plass.

**Les gjennom hele den eksisterende kodebasen før du begynner.** Du skal bygge PÅ det som finnes — ikke reimplementere eller duplisere.

---

## KONTEKST: EKSISTERENDE ARKITEKTUR

```
backend/app/
├── main.py                    # FastAPI + SSE streaming
├── config.py                  # Pydantic-settings
├── cache.py                   # Semantisk caching
├── models/state.py            # PipelineState
├── models/llm.py              # Modellagnostisk LLM
├── pipeline/graph.py          # LangGraph pipeline
├── pipeline/agents/           # Pedagog, Forfatter, Verifikator, Redaktør, etc.
├── verification/              # SymPy + LaTeX-kompilering
├── curriculum/lk20.py         # LK20-data
└── latex/                     # Preamble + compiler

frontend/src/
├── app/page.tsx               # Genereringswizard + pipeline-progress
├── components/                # generation-wizard, pipeline-progress, result-view
└── lib/                       # Zustand store, API-klient med SSE

schema.sql                     # PostgreSQL med pgvector, RLS
```

**Viktige konvensjoner som allerede er etablert:**
- Backend: FastAPI, async, Pydantic v2, structlog
- Frontend: Next.js 14 App Router, Tailwind + shadcn/ui, Zustand, Framer Motion
- API-mønster: `POST /generate` → `GET /stream` → `GET /result`
- Database: PostgreSQL med pgvector-extension for embeddings

---

## 2.1 — INTERAKTIV LATEX-EDITOR

### Backend

Legg til i `backend/app/`:

**`editor/compiler.py`** — Inkrementell LaTeX-kompilering:
- Endepunkt `POST /compile` som tar LaTeX-body og returnerer PDF som base64
- Bruk en pool av pdflatex-prosesser (maks 4 samtidige) for å unngå flaskehals
- Cache kompilerte PDF-er med hash av LaTeX-innholdet som nøkkel
- Returner strukturerte feilmeldinger med linjenummer ved kompileringsfeil

**`editor/ai_actions.py`** — AI-assisterte redigeringer:
- `POST /editor/simplify` — Forenkle markert tekst (behold matten, enklere språk)
- `POST /editor/add-illustration` — Generer TikZ/PGFPlots for markert kontekst
- `POST /editor/variant` — Lag en alternativ versjon av en oppgave (nye tall, annen kontekst)
- `POST /editor/add-hint` — Generer progressive hint til en oppgave
- Alle endepunkter tar `{latex_selection: string, full_context: string}` og returnerer erstatnings-LaTeX
- Bruk samme LLM-interface som pipeline-agentene, men med egne spesialiserte prompts

### Frontend

**`components/latex-editor.tsx`** — Split-view editor:
- Venstre panel: Monaco Editor (`@monaco-editor/react`) med LaTeX-språkstøtte
  - Syntax highlighting (bruk `latex`-språkdefinisjonen)
  - Autocompletion for: `\begin{}`-miljøer (tcolorbox, tikzpicture, align, etc.), standard LaTeX-kommandoer, og prosjektets egne miljøer (oppgave, eksempel, definisjon, etc.)
  - Inline error markers fra kompileringsfeil (rød understrek på riktig linje)
  - Vim-modus som valgfri setting
- Høyre panel: PDF-preview (render base64 PDF i `<iframe>` eller bruk `react-pdf`)
- Debounced kompilering: 800ms etter siste tastetrykk, send til `/compile`
- Kontekstmeny (høyreklikk på markert tekst): "Forenkle", "Legg til illustrasjon", "Lag variant", "Legg til hint"
- Toolbar over editoren: Hurtigknapper for vanlige LaTeX-strukturer (brøk, integral, align-miljø, tcolorbox)
- Diff-visning: Vis AI-foreslåtte endringer som en diff før brukeren aksepterer

**Viktig:** Editoren skal åpnes FRA resultatvisningen. Etter en generering klikker brukeren "Rediger" og får split-view med det genererte innholdet.

---

## 2.2 — OPPGAVEBANK MED INTELLIGENT SØK

### Datamodell

Oppgavebanken bygger på `exercises`-tabellen i `schema.sql`. Utvid den om nødvendig med:
- `source_generation_id` — kobling til opprinnelig generering
- `times_used` — telling av gjenbruk
- `user_rating` — brukerens kvalitetsvurdering (1–5)
- `embedding` — vector(1536) for semantisk søk (generer med OpenAI `text-embedding-3-small` eller tilsvarende)

### Backend

**`exercises/parser.py`** — Parsing av LaTeX til atomiske oppgaver:
- Parse generert LaTeX og splitt i individuelle oppgaver
- Ekstraher metadata automatisk: oppgavetype (fra tcolorbox-miljø), vanskelighetsgrad (basert på innhold-analyse), emne (fra kontekst)
- Koble hvert utdrag til kompetansemål fra LK20-data
- Generer embedding for hver oppgave

**`exercises/router.py`** — API-endepunkter:
- `GET /exercises` — List med filtrering (emne, trinn, type, vanskelighetsgrad) og paginering
- `GET /exercises/search?q=...` — Fulltekstsøk (PostgreSQL `tsvector`) + semantisk søk (pgvector cosine similarity), kombinert med vektet scoring
- `GET /exercises/{id}/similar` — Finn 5 mest lignende oppgaver basert på embedding
- `POST /exercises/{id}/variant` — Generer ny variant med AI (endret tall/kontekst, same struktur)
- `POST /exercises/export` — Eksporter valgte oppgaver til PDF/Word. Tar `{exercise_ids: string[], format: "pdf" | "docx", include_solutions: boolean}`
- `POST /exercises/import` — Importer oppgaver fra opplastet PDF (OCR med Tesseract eller cloud API, deretter AI-parsing til strukturerte oppgaver)
- `PUT /exercises/{id}` — Oppdater metadata, rating
- `DELETE /exercises/{id}` — Soft delete

**Automatisk lagring:** Etter hver vellykket generering, parse og lagre oppgavene automatisk i banken (med brukerens samtykke — vis toggle i innstillinger).

### Frontend

**`app/exercises/page.tsx`** — Oppgavebank-visning:
- Søkefelt med sanntids-resultater (debounced 300ms)
- Filterbar: Emne (multi-select), trinn (chips), type (checkboxes), vanskelighetsgrad (slider 1–5)
- Visning: Grid (kort) eller liste — bytt med toggle
- Hvert oppgavekort viser: Preview av oppgavetekst (trunkert), emne-tag, trinn-badge, vanskelighetsgrad som dots/stjerner, "Lignende"-knapp, "Lag variant"-knapp
- Bulk-operasjoner: Velg flere → Eksporter som PDF, Legg til i mappe, Slett
- "Bygg eksamensett"-modus: Dra-og-slipp oppgaver inn i en liste, omorganiser, sett poengverdier, eksporter som ferdig eksamen med forside og poengskjema

---

## 2.3 — DIFFERENSIERING OG HINT-SYSTEM

### Backend

**`differentiation/generator.py`**:
- Utvid pipeline-grafen med en valgfri `differentiate`-node etter `editor`-agenten
- Denne noden tar ferdig LaTeX-output og genererer to ekstra versjoner:
  - **Grunnleggende**: Enklere tall, flere mellomregninger vist, ekstra hint, færre oppgaver
  - **Avansert**: Vanskeligere tall, færre mellomregninger, sammensatte oppgaver, bevisoppgaver
- Bruk ÉN LLM-kall med strukturert output (JSON med tre nivåer), deretter parse til tre separate LaTeX-dokumenter
- SymPy-verifisering kjøres på ALLE tre nivåer

**`differentiation/hint_engine.py`**:
- `POST /exercises/{id}/hints` — Generer progressive hint for en oppgave
- Returner 3 hint med stigende detalj:
  1. **Dytt**: Vag retningsindikasjon ("Tenk på hva som skjer når du flytter et ledd til andre siden")
  2. **Steg**: Første konkrete steg ("Start med å trekke fra 3 på begge sider")
  3. **Nesten-løsning**: Mesteparten av løsningen, mangler siste steg
- Lagre hint som JSON-array på oppgaven i databasen
- QR-kode-endepunkt: `GET /exercises/{id}/hints/qr` — Generer QR-kode som lenker til en enkel hint-visningsside

### Frontend

**Differensieringsvisning i resultatvisningen:**
- Tre faner: "Grunnleggende", "Standard", "Avansert"
- Visuell diff-markering mellom nivåene (highlight hva som er endret)
- Separat nedlasting per nivå eller alle tre i én PDF

**Hint-visning:**
- På oppgavekort i oppgavebanken: Ekspanderbar hint-seksjon
- Knapp "Generer hint" hvis hint ikke finnes ennå
- I eksportert PDF: Valgfri inkludering av hint (som fold-ut-boks eller QR til digital versjon)

---

## 2.4 — SAMARBEID OG DELING

### Backend

**`sharing/router.py`**:
- `POST /share` — Opprett delbar lenke. Tar `{resource_type: "generation" | "exercise_set" | "folder", resource_id: string, password?: string, expires_at?: datetime}`
- `GET /shared/{token}` — Hent delt ressurs (sjekk passord og utløpsdato)
- `POST /shared/{token}/clone` — Klon en delt ressurs til egen konto

**`collaboration/router.py`** (skolenivå):
- Brukere kan tilhøre en `school` (i users-tabellen)
- `GET /school/exercises` — Felles oppgavebank for skolen
- `POST /school/exercises/{id}/publish` — Del en oppgave med skolen
- Kommentarer: `POST /generations/{id}/comments`, `GET /generations/{id}/comments`

**Versjonshistorikk:**
- Hver redigering av en generering oppretter en ny rad i `generation_versions`-tabellen
- `GET /generations/{id}/versions` — List alle versjoner
- `POST /generations/{id}/versions/{version_id}/restore` — Gjenopprett en versjon

### Frontend

**Delingsflyt:**
- "Del"-knapp på resultatsiden → Modal med: lenke (kopierbar), valgfritt passord, utløpsdato
- Offentlig visningsside for delte ressurser (egen route: `app/shared/[token]/page.tsx`)
- "Klon til min konto"-knapp for innloggede brukere

**Skole-oppgavebank:**
- Eget fane/seksjon i oppgavebanken: "Mine oppgaver" | "Skolens oppgaver"
- Publiserings-workflow: Marker oppgave → "Del med skolen" → Synlig for kollegaer

---

## 2.5 — EKSPORT OG INTEGRASJONER

### Backend

**`export/router.py`**:
- `POST /export/pdf` — Allerede delvis implementert via LaTeX-compiler. Legg til støtte for:
  - Forside med skolenavn, lærernavn, dato, fag, emne
  - Innholdsfortegnelse (for fulle kapitler)
  - Print-optimalisert variant (gråtoner, uten bakgrunnsfarger i tcolorbox)
- `POST /export/docx` — LaTeX → Word-konvertering:
  - Bruk pandoc som backend (`latex → docx` med custom reference doc for styling)
  - Alternativt: Parse LaTeX og bygg docx programmatisk med python-docx for mer kontroll
  - Matematikk som OMML (Office Math Markup) — ikke bilder
- `POST /export/pptx` — Hver oppgave som egen slide:
  - python-pptx med konsistent template
  - Tittelslide med metadata
  - Én oppgave per slide, løsninger som skjulte slides eller speaker notes

**`export/qr.py`**:
- Generer QR-koder som lenker til digitale løsninger/hint
- Kan embeddes i LaTeX-output med `\includegraphics` av generert QR-bilde
- QR-landingsside: Enkel, mobilvennlig side som viser løsning eller progressive hint

### Frontend

**Eksport-modal (`components/export-modal.tsx`):**
- Format-valg: PDF, Word, PowerPoint
- Opsjoner per format:
  - PDF: Med/uten løsninger, med/uten forside, print-optimalisert, inkluder QR-koder
  - Word: Med/uten løsninger
  - PowerPoint: Oppgaver som slides, løsninger som speaker notes
- Forhåndsvisning av forside (live preview mens brukeren fyller inn skolenavn etc.)
- Nedlasting + "Send til Google Classroom" (fremtidig integrasjon — vis som disabled knapp med "Kommer snart")

---

## TEKNISKE KRAV FOR DENNE FASEN

### Nye avhengigheter (backend)
```
# Legg til i requirements.txt
monaco-languageserver    # Ikke nødvendig backend — dette er frontend
pandoc                   # System-dependency for docx-eksport
python-docx>=1.1.0       # Word-generering
python-pptx>=0.6.23      # PowerPoint-generering
qrcode[pil]>=7.4.0       # QR-koder
Pillow>=10.0.0            # Bildeprosessering
httpx>=0.27.0             # Async HTTP for embedding-API
```

### Nye avhengigheter (frontend)
```json
{
  "@monaco-editor/react": "^4.6.0",
  "react-pdf": "^9.0.0",
  "@dnd-kit/core": "^6.1.0",
  "@dnd-kit/sortable": "^8.0.0",
  "qrcode.react": "^3.1.0"
}
```

### Testing
- `test_exercise_parser.py` — Verifiser at LaTeX-parsing korrekt splitter oppgaver
- `test_differentiation.py` — Sjekk at alle tre nivåer kompilerer og at SymPy godkjenner matte i alle
- `test_export.py` — Verifiser at PDF, Word og PowerPoint genereres uten feil
- `test_sharing.py` — Tilgangskontroll: Passord, utløpsdato, school-scoping
- Frontend: Cypress E2E-test for genereringswizard → redigering → eksport-flyten

### API-dokumentasjon
- Alle nye endepunkter skal ha OpenAPI-docs med eksempel-requests og responses
- Grupper endepunktene med tags: `editor`, `exercises`, `differentiation`, `sharing`, `export`

---

## ARBEIDSREKKEFØLGE

1. **Oppgavebank** (2.2) — Parser + database + API + frontend. Dette er fundamentet som alt annet bygger på.
2. **LaTeX-editor** (2.1) — Split-view med Monaco + live kompilering. Bygger på kompilerings-endepunktet.
3. **Differensiering + hint** (2.3) — Utvider pipeline + oppgavebank.
4. **Eksport** (2.5) — PDF-forbedringer, Word, PowerPoint, QR.
5. **Samarbeid** (2.4) — Deling, skole-bank, kommentarer, versjonering.

For hvert steg: Implementer backend med tester FØRST, deretter frontend.

---

*Begynn med 2.2: Implementer `exercises/parser.py` som tar LaTeX-output fra pipeline og splitter det i atomiske oppgaver med metadata. Vis meg parseren og tilhørende tester.*
