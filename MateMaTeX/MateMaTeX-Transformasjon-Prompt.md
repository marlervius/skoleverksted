# MateMaTeX → MateMaTeX 2.0: Full Transformasjon

Du er en senior fullstack-utvikler og AI-arkitekt. Du skal transformere MateMaTeX fra en Streamlit-prototype til en produksjonsklar, banebrytende EdTech-plattform. Les hele dette dokumentet nøye før du begynner.

---

## KONTEKST

MateMaTeX er en AI-drevet applikasjon som genererer matematiske læremateriell (LaTeX → PDF) for norske lærere, tilpasset LK20-læreplanen. Nåværende stack: Streamlit + CrewAI + Google Gemini + pdflatex. Se vedlagt prosjektbeskrivelse for full arkitekturoversikt.

**Kjerneproblem med nåværende løsning:**
- Streamlit begrenser UX (ingen ekte state management, ingen offline, tregt)
- AI-pipelinen er lineær og dum — 3 agenter i sekvens uten feedback-loops
- Ingen verifikasjon av matematisk korrekthet
- LaTeX-output feiler ofte på kompilering
- Ingen brukerkontoer, ingen samarbeid, ingen persistering utover JSON-filer

---

## MÅL

Bygg verdens beste AI-verktøy for generering av matematisk undervisningsmateriell. Plattformen skal:

1. **Produsere matematisk korrekt output — alltid.** Dette er ikke-forhandlbart.
2. Generere profesjonelle PDF-er som ser ut som forlagsutgitte lærebøker.
3. Være lynrask og føles som et premium SaaS-produkt.
4. Være skalerbar for hele den norske lærerstanden (og internasjonalt på sikt).

---

## FASE 1: AI-MOTOR (HØYESTE PRIORITET)

### 1.1 — Multi-agent-arkitektur med verifikasjonsløkker

Erstatt den lineære CrewAI-pipelinen med et agentrammeverk som støtter sykliske grafer (LangGraph, AutoGen, eller egenbygget). Implementer denne flyten:

```
Brukerinput
    ↓
[Pedagog-agent] → Læreplankartlegging + pedagogisk plan
    ↓
[Forfatter-agent] → Genererer LaTeX-innhold
    ↓
[Matematikk-verifikator] → Verifiserer ALLE utregninger programmatisk
    ↓                         (SymPy / SageMath for CAS-verifikasjon)
    ↓ ← FEIL? → [Forfatter-agent] retter (maks 3 iterasjoner)
    ↓
[LaTeX-validator] → Kompilerer og sjekker syntaks
    ↓ ← FEIL? → [LaTeX-fikser-agent] retter automatisk
    ↓
[Redaktør-agent] → Kvalitetskontroll: pedagogikk, språk, konsistens
    ↓
[Layout-agent] → Optimaliserer visuell layout, sideskift, figurer
    ↓
Ferdig dokument
```

**Krav:**
- Hver agent skal ha klart definert ansvar og ALDRI overlappe med andre agenter
- Matematikk-verifikatoren skal bruke **SymPy** (ikke LLM) for å verifisere alle beregninger, ligninger og løsninger. Pakk ut alle matematiske påstander fra LaTeX og verifiser dem symbolsk.
- LaTeX-validatoren skal kjøre faktisk `pdflatex`-kompilering som sjekk — ikke bare pattern-matching
- Implementer retry-logikk med eksponentiell backoff og feilkontekst som sendes tilbake til feilende agent
- Hele pipelinen skal ha observability: logg hvert agent-steg med input/output, tid, tokentelling, og eventuelle feil

### 1.2 — Prompt engineering

Hvert agent-prompt skal:
- Inneholde 3–5 few-shot-eksempler av PERFEKT output for sin oppgavetype
- Ha eksplisitt negativliste ("ALDRI gjør dette: ...")
- Bruke XML-strukturert output der det er hensiktsmessig
- Inkludere trinnets kontekst fra LK20-læreplanen (tillatte/forbudte konsepter)
- Ha temperatur 0.1–0.2 for konsistens (ikke 0.3 som nå)

### 1.3 — Intelligent caching og kostnadsoptimalisering

- Implementer semantisk caching: Hvis en forespørsel er >90% lik en tidligere forespørsel, tilby cachet resultat med mulighet for regenerering
- Cache på agent-nivå, ikke bare pipeline-nivå — slik at f.eks. pedagog-planen kan gjenbrukes hvis kun vanskelighetsgrad endres
- Estimer og vis tokenkostnad FØR generering
- Støtt streaming av agent-output til frontend i sanntid

### 1.4 — Modellagnostisk arkitektur

- Abstrahér LLM-kallet bak et unified interface slik at modell kan byttes uten kodeendring
- Støtt minst: Google Gemini, Anthropic Claude, OpenAI GPT-4o, lokale modeller via Ollama
- Implementer automatic fallback: Hvis primærmodell feiler, prøv sekundærmodell
- La avanserte brukere velge modell per agent (f.eks. Claude for pedagogikk, Gemini for LaTeX)

---

## FASE 2: FUNKSJONALITET

### 2.1 — Interaktiv LaTeX-editor

- Implementer en split-view: LaTeX-kode til venstre, live PDF-preview til høyre
- Bruk Monaco Editor (VS Code-motoren) for LaTeX-editoren med:
  - Syntax highlighting for LaTeX
  - Autocompletion for LaTeX-kommandoer og matematikkmiljøer
  - Error markers som viser kompileringsfeil inline
- Live-kompilering med debounce (500ms etter siste tastetrykk)
- AI-assistert redigering: Marker tekst → høyreklikk → "Gjør enklere", "Legg til illustrasjon", "Lag alternativ oppgave"

### 2.2 — Oppgavebank med intelligent søk

- Hver generert oppgave lagres atomisk med metadata: emne, trinn, vanskelighetsgrad, kompetansemål, type, nøkkelord
- Vektorsøk (embeddings) for å finne lignende oppgaver semantisk
- "Finn lignende"-funksjon: Klikk på en oppgave → få 5 varianter med ulikt tall/kontekst
- Eksport av egendefinerte oppgavesett fra banken til PDF/Word
- Importér oppgaver fra eksisterende PDF-er (OCR + AI-parsing)

### 2.3 — Differensiering og tilpasning

- Generer automatisk 3 nivåer (grunnleggende, middels, avansert) med ÉN prompt
- Visuell diff mellom nivåene — vis hva som er endret
- Adaptiv vanskelighetsgrad basert på elevdata (hvis integrert med LMS)
- Generér hint-system: Oppgaver med progressive hint som kan avsløres steg-for-steg

### 2.4 — Samarbeid

- Delt oppgavebank mellom lærere på samme skole
- Delbare lenker til genererte materiell (med valgfri passord-beskyttelse)
- Kommentarfunksjon på delte dokumenter
- Versjonshistorikk: Se og gjenopprett tidligere versjoner av et dokument

### 2.5 — Eksport og integrasjoner

- PDF (som nå, men med forbedret layout)
- Word (.docx) med ren formattering — ikke bare LaTeX-konvertering
- PowerPoint med oppgaver som separate slides
- Google Classroom-integrasjon (distribuer direkte)
- SMART Notebook / Promethean-kompatibel eksport
- Print-optimalisert versjon (gråtoner, redusert blekk)
- QR-koder på oppgaveark som lenker til digitale løsninger/hint

---

## FASE 3: UX OG FRONTEND

### 3.1 — Teknisk stack

Bytt til **Next.js 14+ (App Router)** med:

| Lag | Teknologi |
|-----|-----------|
| Framework | Next.js 14+ (App Router, RSC) |
| Styling | Tailwind CSS + shadcn/ui |
| State | Zustand eller Jotai (lettvekts, ikke Redux) |
| Animasjoner | Framer Motion |
| Sanntid | WebSockets eller Server-Sent Events for agent-streaming |
| Auth | NextAuth.js eller Clerk |
| Database | PostgreSQL (Supabase eller Neon) + Prisma ORM |
| Fillagring | Supabase Storage eller S3 |
| Søk | Typesense eller Meilisearch for oppgavebanken |
| Vektor-DB | Pinecone, Qdrant, eller pgvector for semantisk søk |
| API | tRPC eller REST med Zod-validering |
| Deploy | Vercel (frontend) + Railway/Fly.io (AI-backend) |

### 3.2 — Design-prinsipper

- **Vertikal rytme**: Alt skal føles rolig og strukturert. Generous whitespace.
- **Mørkt tema som default** med lyst tema-alternativ
- **Skjelettlasting** (skeleton screens) mens AI genererer — ikke spinners
- **Progressiv avsløring**: Vis agent-stegene i sanntid som en visuell pipeline
- **Tastaturnavigasjon**: Power-brukere skal kunne gjøre alt uten mus
- **Responsivt**: Fungerer på iPad (mange lærere bruker det i klasserommet)
- **Norsk UI som default**, med engelsk som alternativ
- **Mikroanimasjoner**: Subtile transitions mellom states, ikke prangende

### 3.3 — Nøkkelskjermer

1. **Dashboard**: Oversikt over nylige genereringer, favoritter, oppgavebank-statistikk
2. **Genereringsflyt**: Step-by-step wizard: Trinn → Emne → Type → Tilpasninger → Generer
3. **Resultatvisning**: Split-view med LaTeX + PDF-preview, direkte redigering
4. **Oppgavebank**: Filtrér/søk med facets, bulk-eksport
5. **Innstillinger**: Skole-profil, standard LaTeX-preamble, modellvalg, API-nøkler

---

## FASE 4: BACKEND OG INFRASTRUKTUR

### 4.1 — API-design

- Separert frontend (Next.js) og AI-backend (Python FastAPI)
- Backend eksponerer:
  - `POST /generate` — Start generering (returnerer job-id)
  - `GET /generate/{id}/stream` — SSE-stream av agent-progress
  - `GET /generate/{id}/result` — Ferdig resultat
  - `POST /compile` — Kompiler LaTeX til PDF
  - CRUD for oppgavebank, favoritter, maler, innstillinger
- Rate limiting og queue-system (Celery + Redis eller BullMQ) for AI-jobber
- Helsekontroller for alle eksterne tjenester (LLM-APIer, LaTeX-kompilator)

### 4.2 — Database-skjema (PostgreSQL)

Tenk gjennom et skikkelig relasjonelt skjema med minst:
- `users` (auth, profil, skole, preferanser)
- `generations` (all generert output med full metadata)
- `exercises` (atomiske oppgaver med embedding-vektor)
- `templates` (egendefinerte maler)
- `folders` / `tags` (organisering)
- `shared_links` (deling med tilgangskontroll)

### 4.3 — Sikkerhet

- Brukerautentisering (email + passord, eller SSO via Feide for norske skoler)
- Row Level Security i Supabase/PostgreSQL
- API-nøkler kryptert at rest
- Rate limiting per bruker
- Input-sanitering av all brukerinput før det sendes til LLM (prompt injection-beskyttelse)

---

## TEKNISKE KRAV

### Kodekvalitet
- TypeScript (strict mode) for all frontend-kode
- Python 3.12+ med type hints overalt
- Pydantic v2 for alle datamodeller i backend
- 80%+ testdekning for AI-pipelinen (unit tests for agenter, integrasjonstester for pipeline)
- ESLint + Prettier (frontend), Ruff + mypy (backend)
- Pre-commit hooks

### Ytelse
- Første sidlast < 1.5 sekunder (Lighthouse score > 90)
- AI-generering: Første token synlig i frontend innen 2 sekunder
- LaTeX-kompilering < 5 sekunder
- Oppgavebank-søk < 200ms

### Observability
- Strukturert logging (JSON) med korrelasjon-IDer
- OpenTelemetry traces for AI-pipeline
- Metrikkdashboard: Genereringer per dag, feilrate, gjennomsnittlig tid, tokenkostnad
- Alerting på feilede genereringer > 5%

---

## EKSISTERENDE KODE SOM SKAL BEVARES

Følgende logikk fra nåværende kodebase er verdifull og skal porteres (ikke kastes):

1. **`curriculum.py`** — LK20-data (emner, kompetansemål, trinngrenser). Konvertér til database-seed eller TypeScript-modul.
2. **LaTeX-preamble** — De fargekodede tcolorbox-miljøene (definisjon, eksempel, oppgave, etc.) fungerer bra. Behold og forbedre.
3. **Agent-prompts** — Bruk som utgangspunkt, men utvid kraftig med few-shot-eksempler.
4. **Språknivå-logikk** (B1/B2) — Viktig for inkludering. Behold og integrér i ny agent-pipeline.
5. **Verktøymoduler** som `formula_library`, `graph_templates`, `difficulty_analyzer` — Portér logikken.

---

## ARBEIDSMETODE

1. **Start med AI-motoren** (Fase 1). Få den til å produsere perfekt, verifisert output før du rører frontend.
2. **Bygg API-laget** (Fase 4.1) rundt den nye AI-motoren.
3. **Bygg frontend** (Fase 3) som kobler til API-et.
4. **Legg til funksjonalitet** (Fase 2) inkrementelt.

For hvert steg:
- Skriv tester FØRST for kritisk logikk (spesielt matematikkverifisering)
- Dokumentér alle API-endepunkter med OpenAPI/Swagger
- Commit med konvensjonelle commit-meldinger (`feat:`, `fix:`, `refactor:`)

---

## HVA SUKSESS SER UT SOM

Når denne transformasjonen er ferdig, skal en lærer kunne:

1. Logge inn, velge "8. trinn → Algebra → Likninger" og få et komplett, feilfritt oppgaveark på 30 sekunder
2. Se AI-en jobbe i sanntid: "Pedagogen planlegger... Forfatteren skriver... Verifiserer matte... Kompilerer PDF..."
3. Klikke på en feil oppgave og si "gjør denne enklere" — og få en oppdatert versjon umiddelbart
4. Dele resultatet med en kollega via lenke
5. Bygge et eksamensett fra oppgavebanken ved å dra-og-slippe oppgaver
6. Stole på at matematikken ALLTID er korrekt

---

*Begynn med Fase 1.1: Implementer den nye multi-agent-pipelinen med SymPy-verifikasjon. Vis meg arkitekturen og koden for de første to agentene (Pedagog + Forfatter) med verifiseringsløkke.*
