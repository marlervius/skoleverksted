# Skoleverksted

De tre tidligere appene er samlet i én lærerplattform:

- **Fag & læring** – læringsark, differensiering, prøver og sekvensplaner for VGS
- **Norsklæring** – CEFR-tilpassede læringsark for voksne som lærer norsk
- **Matematikk** – LK20-oppgaver og prøver med SymPy-verifisert fasit

Brukeren møter én oversikt og en fast verktøyvelger øverst. Hver fagmodul har
fortsatt sin spesialiserte arbeidsflyt, mens frontend, drift og offentlig
API-adresse er felles.

## Arkitektur

```text
MateMaTeX/frontend/             Felles Next.js-frontend (Skoleverksted)
Skoleverksted/backend/main.py   Felles FastAPI-inngang
  /api/fag                      VGS-modulen
  /api/norsk                    Scriptorium-modulen
  /api/matematikk               MateMaTeX-modulen
VGS_KI/                         Fagmodulens eksisterende domene-kode
ScriptoriumFOV/                 Norskmodulens eksisterende domene-kode
MateMaTeX/backend/              Matematikkmodulens eksisterende domene-kode
```

Backendene er montert som navngitte ASGI-moduler. Dermed deler de server og
deploy, men beholder egne ruter, jobbtilstander og kvalitetssikringspipelines.
Dette er tryggere enn å blande tre sett med endepunkter som har flere like navn.

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

## Kontroll

```powershell
Set-Location .\MateMaTeX\frontend
npm run build
npm test
```

Backend-testene i hver domenemappe kan fortsatt kjøres separat. Den felles
inngangen har helsesjekk på `/health`, og hver modul beholder egne API-dokumenter
på `/api/fag/docs`, `/api/norsk/docs` og `/api/matematikk/docs`.
