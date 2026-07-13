# Skoleverksted

De tre tidligere appene er samlet i én lærerplattform:

- **Fag & læring** – læringsark, differensiering, prøver og sekvensplaner for VGS
- **Norsklæring** – CEFR-tilpassede læringsark for voksne som lærer norsk
- **Matematikk** – LK20-oppgaver og prøver med SymPy-verifisert fasit

Brukeren møter én oversikt og en fast verktøyvelger øverst. Hver fagmodul har
sin spesialiserte arbeidsflyt, mens frontend, prosjekter, jobbhistorikk,
kvalitetspass, drift og offentlig API-adresse er felles.

## Ny felles produktflyt

- **Temapakke** oppretter ett prosjekt med koordinerte arbeidsflater for fagtekst,
  CEFR-tilpasset norsk og matematikk.
- **Prosjekter** lagres varig i SQLite og kan senere flyttes til PostgreSQL uten
  å endre frontendkontrakten.
- **Felles historikk** indekserer jobber fra alle domenene. Domenenes egne
  jobbmotorer er fortsatt autoritative for filer og strømmer.
- **Kvalitetspass** viser deterministiske kontroller, kilder, kompetansemål,
  matematikkstatus, kompilering og begrensninger.
- Skjemaene autosaves lokalt slik at læreren kan bytte arbeidsflate uten å miste utkast.
- Skolepålogging og organisasjonstilknytning er bevisst utsatt til produktet er
  ferdig validert. Dagens modulspesifikke sikkerhet er beholdt.

## Arkitektur

```text
MateMaTeX/frontend/             Felles Next.js-frontend (Skoleverksted)
  src/features/fag              Fagmodulens aktive frontendkode
  src/features/norsk            Norskmodulens aktive frontendkode
Skoleverksted/backend/main.py   Felles FastAPI-inngang
Skoleverksted/backend/platform  Prosjekter, jobbindeks, kvalitet og Temapakke
  /api/fag                      VGS-modulen
  /api/norsk                    Scriptorium-modulen
  /api/matematikk               MateMaTeX-modulen
VGS_KI/                         Fagmodulens eksisterende domene-kode
ScriptoriumFOV/                 Norskmodulens eksisterende domene-kode
MateMaTeX/backend/              Matematikkmodulens eksisterende domene-kode
```

Backendene er montert som navngitte ASGI-moduler. Plattformmiddleware observerer
JSON- og SSE-resultater og bygger en varig, felles jobbindeks uten å endre bytes
eller strømmer fra domenene. Dette gjør migreringen trinnvis: senere kan selve
utførelsen flyttes til en felles Redis-kø uten å endre brukergrensesnittet.

Felles plattform-API ligger under `/api/platform`:

- `GET/POST /projects`
- `GET/PATCH /projects/{id}`
- `GET /jobs` og `GET /jobs/{id}`
- `POST /theme-packs`
- `POST /quality-passports`

## Lokal kjøring

### Backend

Opprett ett Python 3.12-miljø fra rotmappen og installer de samlede kravene:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r .\Skoleverksted\backend\requirements.txt
Copy-Item .\Skoleverksted\backend\.env.example .\.env
# Fyll inn GOOGLE_API_KEY i .env
uvicorn Skoleverksted.backend.main:app --reload --port 8000
```

Typst må være tilgjengelig i `PATH` for fag- og norsk-PDF-er. En TeX Live-
installasjon med `pdflatex` kreves for matematikk-PDF-er.

### Frontend

```powershell
Set-Location .\MateMaTeX\frontend
Copy-Item ..\..\Skoleverksted\frontend\.env.example .\.env.local
npm install
npm run dev
```

Åpne `http://localhost:3000`. Den eneste nødvendige frontendvariabelen er
`NEXT_PUBLIC_API_URL=http://localhost:8000`.

## Produksjon

- Bygg frontend fra `MateMaTeX/frontend`.
- Start backend med `uvicorn Skoleverksted.backend.main:app` fra repoets rot.
- Sett `GOOGLE_API_KEY`, `FRONTEND_URL` og eventuelt `REDIS_URL`, `DATABASE_URL`,
  `APP_PASSWORD` og `MATE_API_KEY`.
- Modulene kan fremdeles deployes separat ved å bruke de valgfrie
  `NEXT_PUBLIC_VGS_API_URL`, `NEXT_PUBLIC_NORSK_API_URL` og
  `NEXT_PUBLIC_MATE_API_URL`.

Alternativt kan begge tjenester startes med Docker:

```powershell
Copy-Item .\Skoleverksted\backend\.env.example .\.env
# Fyll inn GOOGLE_API_KEY
# Sett også MATE_API_KEY for den server-side matematikkproxyen i produksjon
docker compose up --build
```

SQLite-filen og genererte dokumenter ligger i volumet `skoleverksted_data`.
`/health/ready` kontrollerer plattformlager og viser om AI-, Redis- og PDF-
konfigurasjon er tilgjengelig.

## Kontroll

```powershell
Set-Location .\MateMaTeX\frontend
npm run build
npm test
```

Plattformtestene kan kjøres uten eksterne AI-kall:

```powershell
python -m unittest discover -s .\Skoleverksted\backend\tests -v
```

GitHub Actions kjører frontendtester, TypeScript, produksjonsbygg,
plattformtester, Python-kompilering og deterministiske matematikk-/pipeline-
tester. Hver modul beholder API-dokumentasjon på `/api/fag/docs`,
`/api/norsk/docs` og `/api/matematikk/docs`.

## AI- og kildepolicy

- Kreativitetstemperatur styres av `AI_TEMPERATURE` (standard `0.35`).
- `PROMPT_VERSION` følger resultater og kvalitetspass for sporbarhet.
- Lærerens kildetekst behandles som ubetrådde data, ikke som instruksjoner.
- Kildebaserte faktapåstander merkes med `[K]` i Fag og Norsk.
- Kjente matematikkfeil skal fortsatt blokkere levering i matematikkmodulen;
  uttrykk som ikke kan verifiseres merkes for manuell lærerkontroll.
