# VGS-Lærerassistent

En webapplikasjon som hjelper lærere i videregående skole (VGS) med å lage undervisningsmateriell som ferdige, utskriftsklare PDF-er — forankret i kompetansemål fra LK20-læreplanen.

## Fire moduser

| Modus | Hva den lager |
|---|---|
| **Læringsark** | Fagtekst med bilde, arbeidsark (forståelse, drøfting, fagbegreper m.m.) og valgfri fasit |
| **Differensiert** | Én PDF med tre nivåer av samme fagtekst — Støtte, Standard og Fordypning — pluss felles arbeidsark |
| **Prøve** | Komplett prøve med Del A (flervalg), Del B (kortsvar), Del C (langsvar), fasit og vurderingskriterier |
| **Sekvens** | Ukesplan/læringsløp med timeplaner, Blooms-progresjon og vurderingsopplegg |

## Tillit og tilpasning

- **NDLA-kildeforankring:** Uten egen kilde søker appen automatisk i NDLAs åpne læringsressurser og forankrer teksten i en relevant artikkel — med kildehenvisning i PDF-en. Kan slås av.
- **Kildeforankring:** Lim inn eget kildemateriale (lærebok, artikkel), så bygger modellen teksten på kilden, merker kontrollerbare påstander med `[K]`, og faktarapporten kryssjekkes mot kilden. Gjelder også prøver (spørsmål + fasit).
- **Kvalitetsrevisjon:** En redaktør-agent kritiserer og forbedrer tekstutkastet (engasjement, presisjon, struktur, nivå) før oppgavene lages — uten å kunne legge til nye fakta.
- **Faktarapport:** Kritisk kvalitetssikringsside til læreren — flagger usikre påstander, forenklinger og utelatte perspektiver.
- **Språktilpasning:** B1/B2-forenklet språk for minoritetsspråklige elever — faginnholdet forblir på VGS-nivå.
- **Tilpasning til eleven:** Interessebaserte eksempler (f.eks. fotball, gaming) og lesevennlig modus for lese-/skrivevansker.
- **Elevgrupper:** Lagre grupper med ulike behov (språknivå, lesevennlig, interesser) og generer en tilpasset versjon av samme tema til hver gruppe med ett klikk — samme pensum, ulik inngang.
- **LK20-kobling:** Kompetansemål hentes live fra Udirs Grep-API.
- **Redigering:** Rediger fagtekst/arbeidsark direkte i appen og rekompiler PDF-en uten ny AI-generering. Word-eksport (.docx) støttes.

## Prosjektstruktur

```
VGS_KI/
├── backend/              # Python FastAPI
│   ├── main.py           # API-ruter, SSE-jobber, caching, rate limiting
│   ├── agents.py         # CrewAI-agenter og prompts (Gemini)
│   ├── pdf_service.py    # Typst-maler og PDF-kompilering
│   ├── docx_service.py   # Word-eksport
│   ├── job_manager.py    # Asynkron jobbkø med SSE-fremdrift
│   ├── grep_api.py       # Udir Grep-API-klient (LK20-mål)
│   ├── ndla_service.py   # NDLA-kildesøk (åpne læringsressurser)
│   ├── tools.py          # Wikimedia Commons bildesøk
│   ├── config.py         # Miljøvariabler/innstillinger
│   └── tests/            # pytest
└── frontend/             # Next.js 14 (App Router, TypeScript, Tailwind)
    └── app/
        ├── page.tsx      # Hoved-UI
        └── components/   # API-klient, state (reducer), UI-komponenter
```

## Kom i gang

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows  (macOS/Linux: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env       # legg inn GOOGLE_API_KEY
uvicorn main:app --reload
```

API: `http://localhost:8000`. Krever [Typst CLI](https://typst.app) i PATH for PDF-kompilering.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App: `http://localhost:3000`. Sett `NEXT_PUBLIC_API_URL` hvis backend ikke kjører på localhost:8000.

### Tester

```bash
cd backend
pip install -r requirements-dev.txt
pytest tests/
```

## Deploy

- **Frontend:** Vercel (Root Directory = `frontend`, se `vercel.json`)
- **Backend:** Railway/Docker (`Dockerfile`, `Procfile`, `railway.json`). Sett `GOOGLE_API_KEY`, `ALLOWED_ORIGINS`/`FRONTEND_URL`, ev. `REDIS_URL` for delt cache.

## Teknologier

**Backend:** FastAPI · CrewAI · Google Gemini (`gemini-3.5-flash`, konfigurerbar via `GOOGLE_MODEL`) · Typst · diskcache/Redis · slowapi
**Frontend:** Next.js 14 · TypeScript · Tailwind CSS · Lucide React

## Støttede nivåer

VG1 · VG2 · VG3 · Yrkesfag
