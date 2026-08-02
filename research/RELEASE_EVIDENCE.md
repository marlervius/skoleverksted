# Release evidence

Status: `DEPLOY PENDING` — dette dokumentet skal ikke leses som produksjonsbevis
før deploy-ID, verifisert SHA og readiness-respons er fylt inn fra Render og
Vercel.

## Release scope

| Fil | Begrunnelse | Inkluderes? | Risiko |
|---|---|---:|---|
| `Skoleverksted/backend/platform/compendium.py` | Lærer-kilder, truth-kall, språkport og reparasjonsflyt | Ja | Ekte modell-/kildedata må verifiseres |
| `Skoleverksted/backend/platform/models.py` | Proveniens- og maskinstatusser | Ja | Gamle lagrede rader kan mangle nye felt |
| `Skoleverksted/backend/platform/router.py` | Timeout, lås, operation-ID og compile-gate | Ja | Daemon-worker kan leve etter timeout |
| `Skoleverksted/backend/platform/truth.py` | Kildekobling, status og setningssikker revisjon | Ja | Semantisk faktastøtte må testes med ekte kilder |
| `Skoleverksted/backend/platform/text_quality.py` | Deterministisk språkport | Ja | Heuristikk er ikke full grammatikkontroll |
| `Skoleverksted/backend/tests/test_compendium.py` | Tester for compendium-/reparasjonsregler | Ja | Produksjonsmiljø må fortsatt testes |
| `Skoleverksted/backend/tests/test_truth.py` | Tester for truth-status og kildeproveniens | Ja | URL-tilgjengelighet må verifiseres live |
| `Skoleverksted/backend/tests/test_text_quality.py` | Tester for strukturelle fragmenter | Ja | Kan ikke dekke alle modellvarianter |
| `Skoleverksted/backend/tests/test_history_fixtures.py` | Fem historiske regresjonsfixturer | Ja | Fixturetestene bruker ikke ekte modell |
| `MateMaTeX/frontend/src/app/compendia/[id]/page.tsx` | Synlige kapittel-/reparasjonsfeil | Ja | Må kontrolleres mot ny backend |
| `MateMaTeX/frontend/src/app/compendia/page.tsx` | Progress-/feilstatus for kompendier | Ja | Må kontrolleres i Vercel |
| `MateMaTeX/frontend/src/components/truth-passport.tsx` | Viser truth-status og kildeproveniens | Ja | UI må verifiseres E2E |
| `MateMaTeX/frontend/src/lib/platform-api.ts` | Timeout og retry for reparasjon | Ja | Nettverks-/refresh-scenario mangler |
| `render.yaml` | Eksplisitt reparasjonstimeout i production | Ja | Render må bekrefte faktisk sync |
| `evaluations/` | Anonymiserte identiske/regresjons-fixtures | Ja | Ikke produksjonsdata |
| `research/` og `status.md` | Audit-, gate- og releasebevis | Ja | Må oppdateres etter deploy |
| `VGS_KI/backend/test_akseptanse.py` | Pakkeimport som gjør full innsamling deterministisk | Ja | Ingen produktlogikk endres |
| `VGS_KI/backend/tests/test_main.py` | Pakkeimport for riktig `main`-modul | Ja | Ingen produktlogikk endres |
| `VGS_KI/backend/tests/test_job_manager.py` | Pakkeimport for riktig jobbmodul | Ja | Ingen produktlogikk endres |
| `VGS_KI/backend/tests/test_pdf_quality.py` | Pakkeimport for riktig renderer/pdf-service | Ja | Ingen produktlogikk endres |
| `MateMaTeX/backend/app/latex/preamble.py` | Urelatert LaTeX-justering | Nei | Bevisst utelatt |
| `MateMaTeX/backend/tests/test_hefte_design.py` | Urelatert LaTeX-test | Nei | Bevisst utelatt |

## Repository identity

| Felt | Verdi |
|---|---|
| Branch | `laerebokdesign-hefte` |
| Upstream | `origin/laerebokdesign-hefte` |
| Implementasjonscommit | `1c36544` (`Close compendium forensic incident and harden verification`) |
| Release-/docscommit | fylles inn etter evidence-commit |
| Dockerfile | `./Dockerfile` |
| Render Blueprint branch | `main` (må samsvare med deploystrategien) |
| Frontend | Vercel-prosjektet `skoleverksted` |

## Runtime-test

Eksisterende produksjonsnært image ble kjørt med arbeidskopien montert:

```text
docker run --rm -e GOOGLE_API_KEY=test-key -e PYTHONPATH=/app \
  -v C:\APP\VGS_samlet:/app -w /app vgs_samlet-backend:latest \
  python -m pytest -q
```

Resultat etter pakkeimportretting: **396 passed, 2 skipped, 47 warnings** in
53.26 s. Samme test i ferskt no-cache image bestod med **396 passed, 2
skipped, 47 warnings** på 46.12 s. Testen brukte ingen gyldig Google-nøkkel; en bakgrunnstest logget
forventet `API_KEY_INVALID`, men testprosessen bestod. Dette er ikke ekte
modell- eller produksjonsbevis.

Ferskt image:

* Build-kommando: `docker buildx build --no-cache --pull --progress=plain --load -t skoleverksted-audit:20260803 .`
* Bygget: 2. august 2026 kl. 22:40 UTC (Docker metadata)
* Image-ID/digest: `sha256:fe99c5aafa50df4f58f543c8c04ba85ffb2243905d63787c39efd3f5ced70c40`
* Dockerfile-sjekker: Typst 0.14.2, pdfTeX/LuaHBTeX og `luaotfload-main.lua`

Runtime-versjoner:

* Python 3.12.11
* FastAPI 0.140.13
* Pydantic 2.12.5
* Pytest 8.4.2
* google-genai 1.65.0

## Deploybevis

| Felt | Verdi/status |
|---|---|
| Render deploy-ID | Ikke tilgjengelig ennå |
| Render verifisert SHA | Ikke tilgjengelig ennå |
| Image-ID/digest | `sha256:fe99c5aafa50df4f58f543c8c04ba85ffb2243905d63787c39efd3f5ced70c40` lokalt; ikke deployet |
| Deploytidspunkt | Ikke tilgjengelig ennå |
| Readiness | Ikke hentet fra deployet release |
| Promptversjon | `skoleverksted-v3` i Blueprint; faktisk runtime ikke bekreftet |
| Modell | `gemini-3.5-flash` i Blueprint; faktisk runtime ikke bekreftet |
| Config fingerprint | Ikke hentet fra deploy |
| Frontend-backend-kobling | Ikke verifisert mot ny release |
| Rollback | Forrige kjente deploy/commit må bekreftes av Render |

Ingen hemmeligheter, tokens eller persondata er skrevet i dette dokumentet.
