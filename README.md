# Skoleverksted

De tre tidligere appene er samlet i én lærerplattform:

- **Fag & læring** – læringsark, differensiering, prøver og sekvensplaner for VGS
- **Norsklæring** – CEFR-tilpassede læringsark for voksne som lærer norsk
- **Matematikk** – LK20-oppgaver og prøver med SymPy-verifisert fasit

Brukeren møter én oversikt og en fast verktøyvelger øverst. Hver fagmodul har
sin spesialiserte arbeidsflyt, mens frontend, prosjekter, jobbhistorikk,
kvalitetspass, drift og offentlig API-adresse er felles.

## Ny felles produktflyt

- **Kompendier** lager først en avgrensningskontrakt og redigerbar disposisjon.
  Etter lærerens godkjenning produseres, kildekontrolleres og godkjennes ett
  kapittel om gangen før en versjonert PDF- og Word-utgave bygges. Dokumentet
  kan knyttes til én eller flere perioder i en årsplan.
- **Årsplaner** lager et redigerbart årshjul for fag, nivå, timetall og
  kompetansemål. Hver periode kan sende en ferdig utfylt bestilling til
  fagverkstedet. En periode kan opprette en varig undervisningspakke med
  redigerbar PowerPoint, læringsark, oppgaveark, fasit og lærerveiledning.
  Læreren godkjenner eksplisitt hvert artefakt og pakken før godkjente
  primærfiler projiseres til materiallisten.
- **Temapakke** oppretter ett prosjekt med koordinerte arbeidsflater for fagtekst,
  CEFR-tilpasset norsk og matematikk.
- **Prosjekter** lagres varig i SQLite og kan senere flyttes til PostgreSQL uten
  å endre frontendkontrakten.
- **Felles historikk** indekserer jobber fra alle domenene. Domenenes egne
  jobbmotorer er fortsatt autoritative for filer og strømmer.
- **Kvalitetspass** viser deterministiske kontroller, kilder, kompetansemål,
  matematikkstatus, kompilering og begrensninger.
- **Global kvalitetsport** kontrollerer alle KI-generatorer og alle eksportløp.
  Kildegodkjenning og lærergodkjenning bindes til samme tekstrevisjon; feil,
  gamle pass og endret innhold blokkeres på serveren.
- **TeachingPackage** har canonical pakke-/artefakttilstand, durable parent/child-
  jobber, innholdsrevisjoner, faktapass, kvalitetspass, lærerreview, atomisk
  årsplanprojeksjon og ZIP-eksport etter godkjenning. Ikke-godkjente artefakter
  blir aldri vist som ferdige læremidler i årsplanen.
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
  quality_gate.py               Felles revisjonsløkke, karantene og eksportport
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

- `GET /compendia` og `POST /compendia/outline`
- `GET/PATCH /compendia/{id}` og kapitteloperasjoner under `/chapters/{chapter_id}`
- `POST /compendia/{id}/compile` og `POST /compendia/{id}/approve`
- `GET /compendia/{id}/download/{pdf|docx}`
- `GET/POST /year-plans`
- `POST /year-plans/generate`
- `POST /year-plans/{id}/verify` og `POST /year-plans/{id}/approve`
- `GET/PATCH /year-plans/{id}` og perioder under `/periods/{period_id}`
- `POST /year-plans/{id}/periods/{period_id}/materials`
- `GET/POST /projects`
- `GET/PATCH /projects/{id}`
- `GET /jobs` og `GET /jobs/{id}`
- `POST /theme-packs`
- `POST /theme-packs/{id}/teacher-guide/approve`
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
- KI-bilder bruker som standard samme Google-nøkkel. `GOOGLE_IMAGE_API_KEY` kan
  settes hvis bildekall skal ha en separat nøkkel, og `GOOGLE_IMAGE_MODEL`
  overstyrer standardmodellen `gemini-3.1-flash-image`.
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

SQLite-filen, årsplanenes godkjente læremidler og genererte dokumenter ligger i
volumet `skoleverksted_data`.
`/health/ready` returnerer HTTP 503 hvis plattformlager, Gemini, Typst eller
pdfLaTeX mangler. Redis vises som en valgfri driftsstatus.

### Render

Rotmappen inneholder en komplett `render.yaml` for backend:

- Docker-basert web service i Frankfurt
- Starter-instans med 512 MB RAM og én jobb/kompilering om gangen
- 1 GB persistent disk montert på `/var/data`
- deploy fra `main` etter at GitHub-kontrollene har bestått
- streng health check på `/health/ready`

Opprett tjenesten med **New > Blueprint** i Render og koble til dette repoet.
Render ber om `GOOGLE_API_KEY`, `APP_PASSWORD`, `FRONTEND_URL` og
`ALLOWED_ORIGINS`. Se [RENDER_DEPLOYMENT.md](RENDER_DEPLOYMENT.md) for hele
oppskriften og frontendvariablene.

Bildemodus er alltid et aktivt lærervalg. «Frie bilder» bruker et eget
bildecrew, lisensfiltrering og Wikimedia Commons-attributt. «Lag AI-bilde»
lager maksimalt én illustrasjon per PDF og merker den som KI-generert.
I kompendier brukes KI-bildet bare som illustrasjon; historiske kart og
dokumentariske bilder skal komme fra kontrollerte, krediterte kilder.

### Vercel frontend

Frontenden deployes separat på Vercel fra `MateMaTeX/frontend`. Sett
`NEXT_PUBLIC_API_URL` og `BACKEND_INTERNAL_URL` til Render-backenden, og kopier
Render-tjenestens genererte `MATE_API_KEY` som en server-side variabel i Vercel.
Se [VERCEL_DEPLOYMENT.md](VERCEL_DEPLOYMENT.md) for komplett Hobby-oppsett,
CORS-tilkobling og smoke test.

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

Det isolerte testmiljøet er den anbefalte inngangen for nye kjøringer. Det
setter `APP_ENV=test`, unik lokal SQLite/temp-lagring, testnøkkel og fakes for
eksterne tjenester:

```powershell
pwsh -File .\scripts\test.ps1 -Suite quick -PythonPath .\.venv\Scripts\python.exe
pwsh -File .\scripts\test.ps1 -Suite full -PythonPath .\.venv\Scripts\python.exe
pwsh -File .\scripts\test.ps1 -Suite docs -PythonPath .\.venv\Scripts\python.exe
pwsh -File .\scripts\test.ps1 -Suite ai -PythonPath .\.venv\Scripts\python.exe
```

Se [docs/testing/README.md](docs/testing/README.md) for oppsett, testmatrise,
kvalitetsrubrikk og feil-playbook. Testene kan ikke koble til `DATABASE_URL`
i testprofilen; dokumentkjøringen krever `typst`/`pdflatex` for de modulene
som bruker dem.

TeachingPackage-fixturen kan renderes til `output/teaching-package-fixture` for
visuell QA:

```powershell
python scripts/render_teaching_package_fixture.py
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
- En rettelse blir ikke grønn før den reviderte teksten er kontrollert på nytt.
- Uløste, entydige hele setninger kan legges i sporbar karantene og fjernes fra
  alle eksportformater. Utrygge fragmenter blokkerer.
- Faktapass fra før kvalitetsmodell 2.0 må kjøres på nytt. Enhver redigering eller
  kildeendring opphever tidligere lærer- og kildegodkjenning.
- Nye generatorer og eksporter skal følge kontrakten i
  [research/GLOBAL_QUALITY_GATE.md](research/GLOBAL_QUALITY_GATE.md).
