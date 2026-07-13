# MateMaTeX

LK20-tilpassede **matematikkoppgaver, arbeidsark og prøver** for norske VGS-lærere — med **SymPy-verifisert fasit**, levert som LaTeX/PDF. **Ingen elevdata.**

Produktprinsippene står i [`MateMaTeX-grunnlov.md`](MateMaTeX-grunnlov.md). Kodeendringer skal kunne forsvares mot den.

## Arkitektur

| Komponent | Teknologi |
|-----------|-----------|
| Backend | Python 3.12, **FastAPI**, **LangGraph**, SymPy (matte-sjekk) |
| Frontend | **Next.js 14** (App Router), TypeScript, Tailwind, Zustand |
| Eldre demo | **Streamlit** (`app.py`, `src/`) — valgfritt |

## Kjør lokalt

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
copy .env.example .env    # fyll inn minst GOOGLE_API_KEY (eller annen LLM-leverandør)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
cp .env.example .env.local
# NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev
```

Åpne [http://localhost:3000](http://localhost:3000).

## Miljøvariabler (viktigste)

### Backend (`backend/.env`)

| Variabel | Beskrivelse |
|----------|-------------|
| `GOOGLE_API_KEY` | Gemini (standardleverandør) |
| `PRIMARY_MODEL` / `FALLBACK_MODEL` | f.eks. `gemini-3-flash-preview` |
| `MATE_API_KEY` | Valgfritt: krever `X-API-Key` eller `Authorization: Bearer` på API |
| `DATABASE_URL` | Valgfritt: PostgreSQL for oppgavebank / samarbeid |
| `FRONTEND_URL` | CORS-opprinnelse i produksjon |
| `OUTPUT_DIR` | Mappe for PDF-er og `job_snapshots/` (persistente jobber) |
| `VERIFICATION_FAIL_OPEN` | `false` (standard): blokker levering ved SymPy-feil i fasit (grunnlov §1) |
| `LAUNCH_GRADES` | Standard `VG1 1T,VG2 R1` — trinn vist først i UI (grunnlov §5) |

### Frontend (Vercel / `.env.local`)

| Variabel | Beskrivelse |
|----------|-------------|
| `NEXT_PUBLIC_API_URL` | Backend-URL (f.eks. Render) |
| `NEXT_PUBLIC_LAUNCH_GRADES` | Samme som backend — hvilke trinn som vises ved oppstart |
| `MATE_API_KEY` | **Kun på server** (Vercel): samme verdi som backend `MATE_API_KEY` — brukes av **SSE-proxy** (`/api/generate/.../stream`) slik at nøkkelen ikke eksponeres i nettleseren |
| `BACKEND_INTERNAL_URL` | Valgfritt: annen URL for server-til-server (f.eks. intern) |
| `NEXT_PUBLIC_MATE_API_KEY` | Kun hvis du **ikke** bruker proxy: sendes i nettleseren til POST/DELETE/GET og eventuelt `?api_key=` på SSE (mindre sikkert) |
| `NEXT_PUBLIC_STREAM_PROXY` | Sett til `false` for å strømme direkte til backend (krever da nøkkel i klient eller `api_key` i URL) |

**Anbefalt produksjon:** sett `MATE_API_KEY` på **både** Render og Vercel (server-only på Vercel), ikke `NEXT_PUBLIC_MATE_API_KEY`.

## API (kort)

- `POST /generate` — start jobb (rate limit: 30/min per IP)
- `GET /generate/{id}/stream` — SSE-fremdrift (krever API-nøkkel på samme måte som øvrige kall når `MATE_API_KEY` er satt)
- `GET /generate/{id}/result` — resultat (f.eks. `full_document`, `pdf_path`)
- `DELETE /generate/{id}` — avbryt
- Øvrige ruter: `/exercises`, `/editor`, `/export`, `/sharing`, … — se OpenAPI på `/docs` i utvikling

**Jobber:** ferdige/feilede jobber lagres under `OUTPUT_DIR/job_snapshots/` slik at `GET /result` kan fungere etter prosess-restart (én instans).

## Tester

```bash
cd backend && pytest
```

### M1 — verifikasjonsdekning (grunnlov milepæl M1)

Se [`M1-testprotokoll.md`](M1-testprotokoll.md). Etter at du har fylt `m1_skjema.csv` med ekte Udir-oppgaver:

```bash
python m1_scorer.py m1_skjema.csv
```

Eksempelrapport (dummy-data):

```bash
python m1_scorer.py m1_skjema_eksempel.csv
```

Filene `m1_scorer.py`, `m1_skjema.csv` og `backend/m1/` er referanseimplementasjonen — **uavhengig** av pipelinen, slik M1-tallet måles ærlig. Pipelen bruker samme numeriske ekvivalenssjekk (`m1.scorer`) for å redusere falske negativer.

```bash
cd frontend && npm test
```

## Deploy

- **Backend:** Docker (f.eks. Render) — se `backend/render.yaml`
- **Frontend:** Vercel — bygg `frontend/`, sett miljøvariabler som over

## Lisens / bidrag

Se repo for lisens. Ved feil: sjekk backend-logg, CORS (`FRONTEND_URL`), og at SSE-proxy har `MATE_API_KEY` når backend krever nøkkel.
