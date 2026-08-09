# Skoleverksted production verification report

**Dom:** `REJECTED`

> **Gjeldende release: `ff725bb69978`, deployet 6. august 2026 13:09:58Z.**
> Kandidatverifikasjonen fra 7. august 2026 står i siste seksjon og er den
> autoritative. Alt over den beskriver baselinereleasen `69b00d81e5a7` og er
> historikk. Merk korreksjonen av de lokale testtallene i seksjon 2 der:
> baseline er 396/2 og kandidat er 402/2, ikke 398/2.

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

---

## Kandidatverifikasjon i produksjon — 7. august 2026

**Dom:** `REJECTED`. **Kandidat:** `ff725bb6997879e74d60d1d539c57e18578f95ad`,
deployet som release `ff725bb69978`.

### 1. Pre-deploy-gate

| Kontroll | Resultat |
|---|---|
| Kandidat entydig | `ff725bb…` løser til én commit; `912007b` er direkte forfar |
| Diff mot `69b00d8` | 4 commits (`2e66ec7`, `22b80d9`, `912007b`, `ff725bb`), 11 filer, +809/−29 |
| Produksjonskode i diffen | kun `Skoleverksted/backend/platform/truth.py` |
| Urelaterte lokale endringer | 4 modifiserte + 1 utracket fil i arbeidskopien; ikke i kandidaten |
| Utelatte lokale commits | `266b1d2`, `53fd943`, `3bb1970`, `72e3e3c` (18 filer, +1359/−86, inkl. MateMaTeX-backendkode) holdt utenfor |
| Rollbackmål | `69b00d81e5a7…` bekreftet på GitHub og i live readiness før push |

### 2. Lokal teststatus — re-verifisert, ikke sitert

Alle gates ble kjørt på nytt mot rene `git worktree`-utsjekkinger for å unngå
forurensning fra den skitne arbeidskopien.

| Gate | Tidligere dokumentert | Målt 7. august 2026 |
|---|---|---|
| Docker-suite, kandidat-image | 398 passed, 2 skipped | **402 passed, 2 skipped, 47 warnings** |
| Docker-suite, baseline-image | 398 passed, 2 skipped | **396 passed, 2 skipped, 47 warnings** |
| `compileall` | bestått | exit 0 (kun eksisterende SyntaxWarnings) |
| Frontend vitest | 13 tester | 13 passed / 5 filer |
| TypeScript | bestått | `tsc --noEmit` exit 0 |
| Produksjonsbygg | bestått | `next build` exit 0 |
| Lint | not operational | bekreftet: ingen ESLint-konfigurasjon i treet |

**Korreksjon:** tallet `398 passed, 2 skipped` reproduserer verken for baseline
eller kandidat og er feil i tidligere dokumentasjon. Riktig baseline er
**396/2** og riktig kandidat er **402/2**. Differansen på +6 tilsvarer nøyaktig
de seks nye testfunksjonene i `test_truth.py` (6 → 12). Kandidattallet er
verifisert to uavhengige veier: image-intern `/app` og read-only mount av en ren
`ff725bb`-worktree ga begge 402/2.

### 3. Deploybevis

| Kontroll | Resultat |
|---|---|
| Push | `git push origin ff725bb…:refs/heads/main` — fast-forward `69b00d8..ff725bb`, ingen force |
| GitHub `main` | `ff725bb6997879e74d60d1d539c57e18578f95ad` |
| CI-run | `31104226437`, «Skoleverksted CI», conclusion `success`, alle fire jobber grønne |
| CI-testtall | platform-backend 91 passed / 3 skipped + gate 2 passed; frontend 5 filer / 13 tester; deterministic 67 passed; Fag 67/4 skipped, Norsk 53, Matematikk 179/3 skipped |
| Release-flipp | 2026-08-06 13:09:58Z, `69b00d81e5a7` → `ff725bb69978` |
| Readiness etter deploy | HTTP 200, `status=ready`, alle sjekker `true`, `rndr-id 965b3e3c-54f6-484f`, `X-Request-ID 6fb1632e23fd` |
| Runtime | `skoleverksted-v3`, `gemini-3.5-flash`, `gemini-3.1-flash-image`, fingerprint `dc08f612a352` — identisk med baseline |
| Produksjonssmoke | bestått på forsøk 1 |
| Vercel | `/`, `/fag`, `/norsk`, `/matematikk` svarte 200 (region `arn1`) |

**Uverifisert:** Render-dashboardets formelle deploy-ID, deploytidspunkt og
status, samt Vercels konfigurerte production-branch og aktive deployment-ID.
Miljøet hadde verken `RENDER_API_KEY` eller `VERCEL_TOKEN`, og `vercel.json`
inneholder ingen branch-konfigurasjon. Deployen er bevist via offentlig
readiness-SHA, ikke via dashboardene.

### 4. Identisk produksjonsscenario

Kompendium `0689cd00b57946779fbdc3e44f2c1cb7`. Full tidslinje og
punkt-for-punkt-sammenligning står i `IDENTICAL_SCENARIO_E2E.md`.

| Måling | Baseline `69b00d81e5a7` | Kandidat `ff725bb69978` |
|---|---|---|
| Påstander totalt | 44 | 48 |
| Verifisert | 32 | 42 |
| Dekning | 73 % | **88 %** |
| Kapittel 1 / 2 / 3 | 100 % / 62 % / 56 % | 87 % / 85 % / 92 % |
| Lærerkilder `teacher`/`provided` | 3/3 | 3/3 |
| Språkfragmenter | 0 | 0 |
| `removed_claims` | 0 / 5 / 3 | **0 / 0 / 0** |
| Reparasjon | 1 forsøk, 504 | 3 forsøk: 1× 200 (intern feil), 2× 504 |
| Retry-adferd | 409 med jobb-ID | 409 med jobb-ID, 0,11–0,24 s |
| Compile | 409 | 409 |
| PDF / Word | ingen | ingen (404, `artifact_version=0`) |
| Manuell lærervurdering | ikke mulig | ikke mulig |

### 5. Nytt funn: falsk grønn reparasjonsrespons

Reparasjonen av kapittel 1 svarte **HTTP 200** etter 75,94 s, men mislyktes
internt. Kapittelstatus gikk fra `needs_revision` til
**`source_grounding_failed`**, `revision_count` forble 0, `revision_summary`
forble tom, og verifikasjonsnoten sier «Automatisk retting kunne ikke
fullføres.» `compendium.py` fanger unntaket, setter feilstatus på kapitlet og
returnerer likevel 200. En klient kan ikke skille dette fra suksess på
HTTP-nivå.

Netto: **0 av 3 reparasjoner reparerte noe**, og én av dem gjorde
kapittelstatusen dårligere enn før den ble kalt.

### 6. Konklusjon

Kandidaten leverer det milepælen lovet — fail-closed sannhetsredigering er nå
produksjonsbevist, og sannhetsdekningen går fra 73 % til 88 % — men den løser
ikke reparasjonsporten. Uten fullført reparasjon finnes ingen godkjente
kapitler, ingen PDF, ingen Word og dermed ingen manuell faglig vurdering.
Dommen er `REJECTED`, og neste P0 er reparasjonsutførelse og durable jobber.

---

## 7. Durable repair execution — lokal verifikasjon 8. august 2026

**Status: `LOKALT TESTET` og `TESTET I RIKTIG RUNTIME`. Ikke `TESTET MOT EKTE
MODELL` og ikke `TESTET I PRODUKSJON`.** Dommen for produktet er uendret
`REJECTED`.

### Hva som ble endret

| Lag | Fil | Endring |
|---|---|---|
| Kontrakt | `platform/router.py` | `POST …/repair` gir **202** `RepairJobAccepted`; nye `GET …/repair`, `GET /repair-jobs/{id}`, `GET /repair-jobs/{id}/events`; `POST /jobs/{id}/cancel` rutes til repair-livssyklusen |
| Utførelse | `platform/repair.py` (ny) | `RepairService` med registrering, claim, heartbeat, CAS-write-back, cancel og ledger; bruker eksisterende `DurableJobGate` som kapasitetsport |
| Varighet | `platform/store.py` | Tabellene `repair_jobs` og `repair_events`; `register_repair_job`, `claim_repair_job`, `finish_repair_job`, `recover_incomplete_repair_jobs`, `expire_stale_repair_leases`, `replace_compendium_chapter_if_unchanged` |
| Domene | `platform/models.py` | `RepairJobStatus`, `RepairJob`, `RepairJobAccepted`, `RepairLedgerEntry`; `JobStatus` utvidet med `superseded` |
| Observability | `platform/compendium.py` | `repair_preconditions()` og en `observer`-krok som logger modellkall, parse, truth-resultat og innholds-hash |
| Frontend | `lib/platform-api.ts`, `app/compendia/[id]/page.tsx` | 202-kontrakt, polling, jobbstatus i UI, avbryt, gjenfinning etter reload, ingen automatisk ny repair |
| Drift | `render.yaml` | `COMPENDIUM_REPAIR_TIMEOUT_SECONDS` erstattet av `COMPENDIUM_REPAIR_LEASE_SECONDS` |

### Målt

| Kontroll | Resultat |
|---|---|
| Backend-suite `Skoleverksted/backend/tests` | **120 bestått**, 1 warning |
| Ny durability-suite | **27 bestått** |
| Responstid for `POST …/repair` med blokkert modellkall | **< 1 s, HTTP 202** |
| Parallell reparasjon av samme kapittel | **HTTP 409** med aktiv `job_id` |
| Replay av samme `operation_id` | **HTTP 202**, samme `job_id` |
| Jobb funnet igjen etter «reload» | **HTTP 200** på `GET …/chapters/{id}/repair` |
| Terminal status etter frigitt modellkall | **`succeeded`**, ledger slutter med `succeeded` |
| Speilet plattformjobb | `GET /jobs/{id}` → `completed` |
| Frontend Vitest / `tsc` / Next-bygg | **24 bestått** / bestått / bestått |

### Hva som fortsatt ikke er verifisert

* Ingen kjøring mot ekte Gemini. Alle modellkall i testene er stubbet.
* Ingen produksjonsdeploy; Render kjører fortsatt `ff725bb69978`.
* Ingen vellykket produksjonsreparasjon, og dermed fortsatt ingen godkjente
  kapitler, ingen PDF/Word og ingen manuell faglig vurdering.
* Postgres-banen for de nye tabellene er ikke kjørt; kun SQLite er testet.
* Nettleserverifikasjon av det nye statuspanelet er ikke gjort, fordi en ekte
  reparasjon krever `GOOGLE_API_KEY` og et seedet produksjonskompendium.

### Konklusjon

Milepælen løser den dokumenterte blockeren på kodenivå: repair execution er nå
varig, observerbar, gjenopprettbar og ikke-destruktiv, og kan ikke lenger
rapportere falsk suksess. Den beviser ikke at en reparasjon faktisk lykkes i
produksjon. Neste port er deploy etter eksplisitt godkjenning, fulgt av det
identiske Historie VG2-scenarioet.
