# Skoleverksted production verification report

**Dom:** `REJECTED`

Denne rapporten er en uavhengig release-gate, ikke en ny produktanalyse.
Statusordene brukes slik: `IMPLEMENTERT`, `LOKALT TESTET`, `TESTET I RIKTIG
RUNTIME`, `TESTET MOT EKTE MODELL`, `TESTET I PRODUKSJON` og `IKKE VERIFISERT`.

## Miljø og commit

| Kontroll | Resultat |
|---|---|
| Aktiv gren | `laerebokdesign-hefte` |
| HEAD | `5b72a05 Fix nested heading quality gate` |
| Sporingsgren | `origin/laerebokdesign-hefte` og Render-tracked `main` peker på `5b72a05` |
| Audit-endringer | Kommittert og deployet; produksjon identitetsverifisert |
| Produksjonsfrontend | `https://skoleverksted.vercel.app` |
| Produksjonskompendium | `838938c88e994320a64281aafc871ec8` |
| Backend-runtime brukt i lokale tester | Docker-image `vgs_samlet-backend:latest`, Python 3.12, arbeidskopien montert |
| Friskt image fra nåværende Dockerfile | Bygget uten cache; seneste digest `sha256:034916e01d5787204e7b06d63832a0c299c98c5e857526fd31be511348eec646` |
| Ekte modell | Brukt i identisk produksjonsscenario mot `gemini-3.5-flash` |

Urelaterte, allerede eksisterende lokale endringer er fortsatt urørte:
`MateMaTeX/backend/app/latex/preamble.py` og
`MateMaTeX/backend/tests/test_hefte_design.py`.

## Deploybevis

Render `/health/ready` svarte HTTP 200 med:

* `release=5b72a0541a20`;
* `status=ready`, alle seks dependency checks `true`;
* `prompt_version=skoleverksted-v3`, `google_model=gemini-3.5-flash`;
* `config_fingerprint=dc08f612a352`;
* `storage.backend=sqlite`, `job_queue_backend=sqlite-local`.

Readiness-headeren hadde `rndr-id=7ce5fb96-3ba3-413f` og tidspunkt
`Sun, 02 Aug 2026 23:31:51 GMT`. Dette er en request-/Render-ID, ikke et
Render-dashboard deploy-ID; dashboardet var ikke autentisert, så deploy-ID og
Render image-digest kunne ikke hentes. Frontend-smoke bestod på forsøk 1 og
Vercel svarte HTTP 200 med `X-Vercel-Id=arn1::bl69g-1785713541664-6205d409a077`.

**Status:** deploy `VERIFISERT`; release-identiteten er bevist, men gate-
scenarioet er fortsatt `REJECTED`.

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
| `docker ... python -m pytest -q` fra repo-roten med `GOOGLE_API_KEY=test-key`, `PYTHONPATH=/app` | 397 passed, 2 skipped | 45.51 s, 47 warnings i seneste fresh image; bakgrunnstest logger forventet ugyldig testnøkkel |

Samlet autoritativ monorepo-suite i seneste ferske image: **397 passed, 2
skipped, 47 warnings** på 45.51 s. De tidligere to innsamlingsfeilene var testimport-/pakke-stifeil i
VGS_KI-testene og er rettet med kvalifiserte pakkeimporter; ingen tester ble
slettet eller deaktivert. En bakgrunnstest starter fortsatt en jobb med
`GOOGLE_API_KEY=test-key` og logger `API_KEY_INVALID`; det er en testharness-
begrensning, ikke en skjult grønn produksjonskontroll.

## Sporbarhetsmatrise

| Påstand fra forensic audit | Kodebevis | Testbevis | Produksjonsbevis | Status |
|---|---|---|---|---|
| `str.replace()` laget fragmenter | `truth.py:_apply_decisions` er endret til setnings-/linjenivå | 87 plattformtester + språkport | Ny identisk run: 0 språkfragmenter flagget | `PRODUKSJONSTESTET` for generert tekst |
| Lærer-URL-er manglet i sannhetslaget | `compendium.py:_teacher_sources` og `provided_sources` | kildeproveniens- og fixturetester | Ny run viser alle tre som `teacher/provided` | `PRODUKSJONSTESTET` i API-leddet |
| Teknisk verifikasjonsfeil må skilles fra unsupported | Nye Pydantic-/Truth-statuser og UI-labels | truth-status-tester | Claims beholdt som `unsupported`/`interpretation`; compile ikke grønn | `PRODUKSJONSTESTET` |
| Reparasjon må ha timeout/lås/ID | `router.py:_run_repair_with_timeout` | timeout- og parallellåstest | Ny run: HTTP 504 etter 120 s + HTTP 409 lock med jobb-ID | `PRODUKSJONSTESTET`, suksess mangler |
| Femtema-regresjon | Fem anonymiserte fixture-inputs og kildeproveniens-test | fixture-kontraktstest | Modell-/produksjonskjøring mangler | `LOKALT TESTET` kun strukturelt |
| PDF/Word-blokkering | `compile_compendium` krever approved + verified | eksisterende plattformtester | Ny run: HTTP 409 listet alle tre kapitler | blokkering `PRODUKSJONSTESTET`; sluttfiler ikke produsert |

## Identisk produksjonsscenario

Scenarioet ble kjørt etter release `5b72a0541a20` med kompendium-ID
`084614b8247d413b8d1ba38cb6166fce` og tre kapittel-ID-er. Disposisjonen ble
opprettet med samme lærerinput, tre lærer-URL-er, differensiering, 3 kapitler,
6 sider og bildevalg `none`. Kapittelresultatene var:

| Kapittel | Status | Påstander | Verifisert | Dekning |
|---|---|---:|---:|---:|
| 1 `71b44f...` | `generated` / `verified` | 14 | 14 | 100 % |
| 2 `16eb2f...` | `needs_revision` / `needs_review` | 21 | 13 | 62 % |
| 3 `3403e6...` | `needs_revision` / `needs_review` | 9 | 5 | 56 % |
| **Totalt** | **ikke grønt** | **44** | **32** | **73 %** |

Alle tre lærer-URL-ene kom tilbake i kapittelsvarene som `origin=teacher`,
`fetch_status=provided`, og ble sendt til truth-laget. Modellrapporterte URL-er
var separat merket. Ingen språkfragmenter ble flagget av den deployede
strukturelle porten.

Reparasjonskallet for kapittel 2 fikk HTTP 504 etter 120 sekunder med
operation-ID `audit-identical-20260803b-repair-ch2`; retry fikk HTTP 409 og
viste aktiv jobb-ID. Det ble ikke observert en vellykket ekte modellreparasjon.
Compile-kallet fikk HTTP 409 med alle tre kapitlene listet, slik at PDF/Word
ikke ble produsert.

## Språk, kilder og reparasjon

Lokalt er språkporten og setningssikker fjerning testet. Fem regression-fixtures
verifiserer at lærer-URL-er får `origin=teacher` og `fetch_status=provided`.
Reparasjonsjobben har lokale tester for suksess, nettverks-/modellfeil, timeout
og dobbel forespørsel. I produksjon ble timeout og dobbel forespørsel observert;
vellykket modellreparasjon, frontendens synlige fremdriftsvisning og
retry-resultat er ikke verifisert som suksess.

## Kompilering og manuell dokumentvurdering

PDF-blokkeringen er fortsatt implementert og lokalt dekket av eksisterende
tester. En faktisk audit-generert PDF/Word fra identisk scenario er ikke
tilgjengelig. Manuell sluttproduktvurdering er derfor `IKKE VERIFISERT`.

## Konklusjon

Koden er deployet med bevist release-identitet, og hele monorepo-suiten samles
i fersk Docker-runtime. Identisk produksjonsscenario er kjørt, men 32/44
verifiserte påstander er under 80 %-regelen, to kapitler står i
`needs_revision`, og reparasjonsjobben nådde timeout. Dommen er derfor fortsatt
**REJECTED**.
