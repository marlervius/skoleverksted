# Skoleverksted production verification report

**Dom:** `REJECTED`

Denne rapporten er en uavhengig release-gate, ikke en ny produktanalyse.
Statusordene brukes slik: `IMPLEMENTERT`, `LOKALT TESTET`, `TESTET I RIKTIG
RUNTIME`, `TESTET MOT EKTE MODELL`, `TESTET I PRODUKSJON` og `IKKE VERIFISERT`.

## Miljø og commit

| Kontroll | Resultat |
|---|---|
| Aktiv gren | `laerebokdesign-hefte` |
| HEAD | `cb486fc Forbedre kildekontroll og jobbstabilitet` |
| Sporingsgren | `origin/laerebokdesign-hefte` peker lokalt på samme SHA |
| Audit-endringer | Ukommitterte i arbeidskopien; ikke i HEAD/deploy |
| Produksjonsfrontend | `https://skoleverksted.vercel.app` |
| Produksjonskompendium | `838938c88e994320a64281aafc871ec8` |
| Backend-runtime brukt i lokale tester | Docker-image `vgs_samlet-backend:latest`, Python 3.12, arbeidskopien montert |
| Friskt image fra nåværende Dockerfile | Ikke bygget ferdig; build ble avbrutt etter manglende fremdrift |
| Ekte modell | Ikke brukt i lokal test; ingen produksjonskall utført etter retting |

Urelaterte, allerede eksisterende lokale endringer er fortsatt urørte:
`MateMaTeX/backend/app/latex/preamble.py` og
`MateMaTeX/backend/tests/test_hefte_design.py`.

## Deploybevis

Produksjonsfanen ble kontrollert i nettleseren. Den viste fortsatt gammel
flyt: kapitlene hadde `Må revideres`, faktapasset viste `0 av 13`, og ingen av
de nye statusene eller den nye kildeproveniensvisningen var synlig. Dette er
direkte bevis på at audit-endringene ikke er verifisert i produksjon.

Render `/health/ready` kunne ikke åpnes fra nettleserkonteksten (`ERR_BLOCKED_BY_CLIENT`).
Ingen Render-commit-SHA, modellnavn, promptversjon, konfigurasjonsfingeravtrykk,
database-/diskstatus eller CORS-respons kunne derfor bekreftes. Ingen
hemmeligheter ble lest eller sendt.

**Status:** deploy `IKKE VERIFISERT`; produksjonskode er ikke audit-koden.

## Testkommandoer og resultater

Kommandoene ble kjørt i Docker-runtime med arbeidskopien montert, bortsett fra
frontendtestene som ble kjørt med lokal Node-runtime.

| Kommando | Resultat | Tid/status |
|---|---:|---|
| `docker run ... python -m pytest Skoleverksted/backend/tests -q` | 87 passed | 15.50 s, `TESTET I RIKTIG RUNTIME` |
| `docker run ... python -m pytest VGS_KI/backend/tests VGS_KI/backend/test_akseptanse.py -q` med `GOOGLE_API_KEY=test-key` og korrekt `PYTHONPATH` | 75 passed | 18.59 s, import-/render-tester; ikke ekte modell |
| `docker run ... python -m pytest ScriptoriumFOV/backend/tests -q` | 53 passed | 9.89 s |
| `docker run ... python -m pytest MateMaTeX/backend/tests -q` | 181 passed, 2 skipped | 28.13 s |
| `python -m compileall -q Skoleverksted/backend/platform Skoleverksted/backend/tests` | passed | lokal bundled Python |
| `npm test -- --run` | 13 passed | frontend |
| `npm run build` | passed | Next.js type-/produksjonsbuild |
| `docker ... python -m pytest -q` fra repo-roten med `GOOGLE_API_KEY=test-key`, `PYTHONPATH=/app` | 396 passed, 2 skipped | 53.26 s, 47 warnings; bakgrunnstest logger forventet ugyldig testnøkkel |

Samlet autoritativ monorepo-suite: **396 passed, 2 skipped, 47 warnings** på
53.26 s. De tidligere to innsamlingsfeilene var testimport-/pakke-stifeil i
VGS_KI-testene og er rettet med kvalifiserte pakkeimporter; ingen tester ble
slettet eller deaktivert. En bakgrunnstest starter fortsatt en jobb med
`GOOGLE_API_KEY=test-key` og logger `API_KEY_INVALID`; det er en testharness-
begrensning, ikke en skjult grønn produksjonskontroll.

## Sporbarhetsmatrise

| Påstand fra forensic audit | Kodebevis | Testbevis | Produksjonsbevis | Status |
|---|---|---|---|---|
| `str.replace()` laget fragmenter | `truth.py:_apply_decisions` er endret til setnings-/linjenivå | 87 plattformtester + språkport | Gammel produksjon viser fragmentert tekst | `LOKALT TESTET`, ikke produksjonsverifisert |
| Lærer-URL-er manglet i sannhetslaget | `compendium.py:_teacher_sources` og `provided_sources` | kildeproveniens- og fixturetester | Produksjon viser fortsatt 0/13 og gammel versjon | `LOKALT TESTET`, ikke deployet |
| Teknisk verifikasjonsfeil må skilles fra unsupported | Nye Pydantic-/Truth-statuser og UI-labels | truth-status-tester | Ikke synlig i produksjon | `LOKALT TESTET`, ikke deployet |
| Reparasjon må ha timeout/lås/ID | `router.py:_run_repair_with_timeout` | timeout- og parallellåstest | Gammel produksjon har gammel flyt | `LOKALT TESTET`, ikke deployet |
| Femtema-regresjon | Fem anonymiserte fixture-inputs og kildeproveniens-test | fixture-kontraktstest | Modell-/produksjonskjøring mangler | `LOKALT TESTET` kun strukturelt |
| PDF/Word-blokkering | `compile_compendium` krever approved + verified | eksisterende plattformtester | Gammel produksjon viste blokkering | blokkering `LOKALT TESTET`; sluttfiler `IKKE VERIFISERT` |

## Identisk produksjonsscenario

Ikke kjørt etter retting. Det ville ha testet gammel deploykode, ikke den lokale
audit-koden, og ville derfor ikke være gyldig releasebevis. Følgende mangler:

* request-/operation-ID og komplett tidslinje;
* rå og normalisert modellrespons;
* truth-input/-output og `provided_sources` i produksjon;
* kildenes faktiske hentestatus;
* før-/ettertekst fra reparasjon;
* nye frontend-statusmeldinger;
* godkjent PDF og Word med manuell gjennomgang;
* ekte modellkostnad og runtime-logger.

## Språk, kilder og reparasjon

Lokalt er språkporten og setningssikker fjerning testet. Fem regression-fixtures
verifiserer at lærer-URL-er får `origin=teacher` og `fetch_status=provided`.
Ingen modellrespons er brukt i disse fixturetestene. Reparasjonsjobben har
lokale tester for suksess, nettverks-/modellfeil, timeout og dobbel forespørsel.
Produksjonsrefresh, omstart, retry og ekte modell-timeout er ikke testet.

## Kompilering og manuell dokumentvurdering

PDF-blokkeringen er fortsatt implementert og lokalt dekket av eksisterende
tester. En faktisk audit-generert PDF/Word fra identisk scenario er ikke
tilgjengelig. Manuell sluttproduktvurdering er derfor `IKKE VERIFISERT`.

## Konklusjon

Koden har dokumenterte lokale tiltak, og hele monorepo-suiten samles nå i
produksjonsnær Docker-runtime. Gatekravene krever likevel deploybevis og en ny
identisk produksjonskjøring. Siden deployen fortsatt viser gammel oppførsel og
produksjonslogger/health/config ikke kan bekreftes, er dommen **REJECTED**.
