# Skoleverksted production verification report

**Dom:** `REJECTED`

Denne rapporten er en uavhengig release-gate, ikke en ny produktanalyse.
Statusordene brukes slik: `IMPLEMENTERT`, `LOKALT TESTET`, `TESTET I RIKTIG
RUNTIME`, `TESTET MOT EKTE MODELL`, `TESTET I PRODUKSJON` og `IKKE VERIFISERT`.

## Miljø og commit

| Kontroll | Resultat |
|---|---|
| Aktiv gren | `laerebokdesign-hefte` |
| HEAD / releasekandidat | `ff725bb6997879e74d60d1d539c57e18578f95ad` (`Document product excellence baseline`) |
| Sporingsgren | `origin/main` og Render-tracked `main` peker på `69b00d81e5a7d823eb284bc7aee37a8cac6f29ed`; kandidatbranch er fire commits foran |
| Kandidatens kodecommit | `912007bf5b4a68b736bbd14daa2011494bed266c` (`Make truth edits sentence-safe`) |
| Audit-/M1-endringer | Lokalt verifisert; ikke pushet eller deployet |
| Produksjonsfrontend | `https://skoleverksted.vercel.app` |
| Produksjonskompendium | `838938c88e994320a64281aafc871ec8` |
| Backend-runtime brukt i lokale tester | Eksakt kandidat-image `skoleverksted-candidate:ff725bb`, Python 3.12 |
| Kandidat-image | `sha256:d9fb7b5f4b4659aefdc729c34358b4e4d704716197f3ab96d3df7c32707c8792` |
| Ekte modell | Brukt i identisk produksjonsscenario mot `gemini-3.5-flash` |

Urelaterte, allerede eksisterende lokale endringer er fortsatt urørte:
`MateMaTeX/backend/app/latex/preamble.py` og
`MateMaTeX/backend/tests/test_hefte_design.py`.

## Siste closure-forsøk — 3. august 2026

Den setningssikre rettingen ligger i `912007bf5b4a68b736bbd14daa2011494bed266c`;
releasekandidaten er `ff725bb6997879e74d60d1d539c57e18578f95ad`. Kandidatens
eksakte diff mot `origin/main` er fire commits (`2e66ec7`, `22b80d9`, `912007b`,
`ff725bb`) i 11 filer.

Kandidaten ble bygget fra ren Git-archive-context som
`skoleverksted-candidate:ff725bb`, image-digest
`sha256:d9fb7b5f4b4659aefdc729c34358b4e4d704716197f3ab96d3df7c32707c8792`.
Full backend-/domene-suite i image bestod med **398 passed og 2 skipped**;
`compileall` bestod. Kandidaten er ikke pushet eller deployet.

Offentlig readiness svarte HTTP 200, men viste fortsatt release
`69b00d81e5a7`, ikke kandidatcommitten. Ved siste kontroll var
`rndr-id=e42efd6a-0b2f-4353` og `Date=Mon, 03 Aug 2026 14:53:12 GMT`; dette er
en request-/Render-ID og ikke et dashboard-deploy-ID. Identisk
produksjonsscenario er derfor ikke kjørt på kandidaten.

## Deploybevis

Render `/health/ready` svarte HTTP 200 ved kontroll `2026-08-03 14:53:12 GMT`
med:

* `release=69b00d81e5a7`;
* `status=ready`, alle seks dependency checks `true`;
* `prompt_version=skoleverksted-v3`, `google_model=gemini-3.5-flash`;
* `config_fingerprint=dc08f612a352`;
* `storage.backend=sqlite`, `job_queue_backend=sqlite-local`.

Readiness-headeren hadde `rndr-id=e42efd6a-0b2f-4353` og tidspunkt
`Mon, 03 Aug 2026 14:53:12 GMT`. Dette er en request-/Render-ID, ikke et
Render-dashboard deploy-ID; dashboardet var ikke autentisert, så formelt
deploy-ID og Render image-digest kunne ikke hentes. Produksjonssmoke bestod på
forsøk 1; Vercel svarte HTTP 200 med
`X-Vercel-Id=arn1::8sldp-1785768793257-a08d9d8f809a`.

**Status:** deploy `VERIFISERT`; release-identiteten er bevist, men gate-
scenarioet er fortsatt `REJECTED`.

## Testkommandoer og resultater

Kommandoene ble kjørt i Docker-runtime med arbeidskopien montert, bortsett fra
frontendtestene som ble kjørt med lokal Node-runtime.

| Kommando | Resultat | Tid/status |
|---|---:|---|
| `docker run ... python -m pytest -q Skoleverksted/backend/tests` | 94 passed | kandidat-image, 10.84 s |
| `docker run ... python -m pytest -q VGS_KI/backend/tests` | 71 passed | kandidat-image, 11.51 s; test med ugyldig nøkkel logger forventet API-feil |
| `docker run ... python -m pytest -q ScriptoriumFOV/backend/tests` | 53 passed | kandidat-image, 5.69 s |
| `docker run ... python -m pytest -q MateMaTeX/backend/tests` | 180 passed, 2 skipped | kandidat-image, 19.48 s |
| `docker run ... python -m compileall -q ...` | passed | kandidat-image |
| `npm test -- --run` | 13 passed | frontend |
| `npm run build` | passed | Next.js type-/produksjonsbuild |
| `docker ... python -m pytest -q` fra repo-roten med `GOOGLE_API_KEY=test-key`, `PYTHONPATH=/app` | 397 passed, 2 skipped | 45.51 s, 47 warnings i seneste fresh image; bakgrunnstest logger forventet ugyldig testnøkkel |

Samlet autoritativ monorepo-suite i kandidat-imaget: **398 passed, 2 skipped**.
Ingen tester ble slettet eller deaktivert. VGS-suiten starter en bakgrunnstest
med `GOOGLE_API_KEY=test-key-not-used` og logger `API_KEY_INVALID`; det er en
testharness-begrensning, ikke produksjonsbevis eller en skjult grønn kontroll.

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

## Deploygate og rollback

| Kontroll | Status |
|---|---|
| Render branch | `main`, dokumentert i `render.yaml`; kandidat er ikke på `main` |
| Vercel production-branch | Ikke dokumentert i repoet eller offentlig respons; må bekreftes i Vercel-prosjektinnstillinger |
| Produksjonscommit nå | Render `69b00d81e5a7d823eb284bc7aee37a8cac6f29ed`; Vercel commit ikke eksponert i offentlig respons |
| Kandidatcommit | `ff725bb6997879e74d60d1d539c57e18578f95ad` |
| Kandidat deploy-ID | Ikke opprettet |
| Menneskelig godkjenning | Kreves før merge/push til `main` og før kontrollert deploy |

Påkrevd menneskelig handling er å godkjenne merge/push av kandidaten til den
faktiske deploybranchen etter CI. Forventet effekt er at readiness viser
kandidat-SHA. Risiko er ny modell-/kilde- eller reparasjonsregresjon. Rollback
er redeploy av `69b00d81e5a7d823eb284bc7aee37a8cac6f29ed`; ingen force-push,
nøkkelrotasjon eller produksjonsdataendring skal brukes.

## Manuell produktgate — `pending teacher review`

Denne pakken skal fylles ut av en faktisk Historie VG2-lærer for nøyaktig den
PDF-/Word-digesten som eventuelt produseres:

| Kontrollpunkt | Status før lærerreview |
|---|---|
| Faglig korrekthet og historisk presisjon | `pending teacher review` |
| Kildekvalitet, proveniens og kildebruk | `pending teacher review` |
| Språk, sammenheng og manglende fragmenter | `pending teacher review` |
| Nivåtilpasning til VG2 | `pending teacher review` |
| Læringsmål og kompetansemål | `pending teacher review` |
| Pedagogisk anvendbarhet og nødvendige lærerredigeringer | `pending teacher review` |
| Layout, PDF-/Word-lesbarhet og utskrift | `pending teacher review` |
| Kan dokumentet faktisk deles ut? | `pending teacher review` |

Ingen lærer har gjennomført vurderingen i denne milepælen. Den kan derfor ikke
markeres som bestått.

## Konklusjon

Forrige produksjonsrelease har bevist release-identitet, og den nye kandidaten
samles i eksakt Docker-runtime. Kandidaten er ikke deployet. Siste identiske
produksjonsscenario på forrige release hadde 32/44 verifiserte påstander under
80 %-regelen, to kapitler i `needs_revision`, repair-timeout og ingen sluttfil.
Kandidatens identiske scenario og lærerreview mangler. Dommen er derfor fortsatt
**REJECTED**.
