# Acceptance matrix

> **Autoritativ matrise er «Kandidatkjøring `ff725bb69978`» nederst
> (7. august 2026).** Tabellen rett under gjelder baselinereleasen
> `69b00d81e5a7` og er historikk. Merk særlig at C06 (80 %-porten) nå er
> bestått, mens C11 er forverret.

Resultatene under beskriver siste identiske produksjonskjøring på forrige
release. `IMPLEMENTERT` betyr kode finnes; det betyr ikke produksjonsgodkjenning.
Kandidatoppdateringen 2026-08-03 står i siste seksjon og er fortsatt
`REJECTED` fordi den ikke er deployet.

| ID | Kriterium | Bevis | Resultat | Alvorlighet | Oppfølging |
|---|---|---|---|---|---|
| C01 | Alle tre kapitler består strukturell språkkontroll | `text_quality.py`, produksjonsrespons | **BESTÅTT**; alle tre språkporter passerte | P1 | Fortsatt manuell språkreview |
| C02 | Ingen fragmenter/manglende subjekter | deployet språkport + E2E-tekst | **BESTÅTT** i identisk run; 0 flaggede fragmenter | P1 | Sammenlign rå modelltekst ved neste observability-løft |
| C03 | Kritiske faglige feil rettes/fjernes med evidens | truth-pass og reparasjonsresultat | **IKKE BESTÅTT**; kap. 2/3 trenger revisjon | P1 | Kjør vellykket reparasjon og lærergjennomgang |
| C04 | Alle kildelenker har tydelig hentestatus | `origin`/`fetch_status` i API-svar | **BESTÅTT** for lærer-URL-propagasjon (`provided`) | P1 | Legg til varig per-URL hentelogger |
| C05 | Teknisk verifikasjonsfeil skilles fra unsupported | Truth enum + produksjonsclaims | **BESTÅTT** i denne run; ingen teknisk feil ble feilmerket | P1 | Verifiser i UI med en fremprovosert fetch-feil |
| C06 | Minst 80 % konkrete påstander har evidens | `verified_count / total >= .8` | **IKKE BESTÅTT**: 32/44 = 73 % | P1 | Reparer og re-kjør samme scenario |
| C07 | Resterende påstander har riktig usikkerhetsstatus | produksjonsclaims | **BESTÅTT** for synlige statusser; ikke grønt pass | P1 | Manuell kontroll av alle `unsupported` |
| C08 | Reparasjon fullfører/feiler innen 120 s med jobb-ID | HTTP 504 + operation-ID, HTTP 409 lock | **DELVIS BESTÅTT**; timeout og lock bevist, suksess mangler | P1 | Verifiser vellykket reparasjon og frontendvisning |
| C09 | Lærer ser hva reparasjon endret | `revision_summary` beholdes | **IKKE VERIFISERT**; ingen suksessrespons | P2 | Kjør en reparasjon som fullfører |
| C10 | PDF kun etter eksplisitt godkjenning | compile endpoint | **BESTÅTT**; HTTP 409 blokkerte PDF/Word | P1 | Godkjenn kun etter grønt pass |
| C11 | Ingen skjulte feil i hele kjøringen | readiness + smoke + E2E-responser | **IKKE BESTÅTT** som full gate; rå ledger mangler og reparasjon timeoutet | P0 | Varig request-/response-ledger |
| C12 | Eksisterende tester består | Kandidat-image: 398 pass, 2 skip; frontend 13 pass, typecheck og build | **TESTET I RIKTIG RUNTIME** | P1 | Kjør ekte produksjonsscenario på kandidaten separat |
| A01 | Ingen fragmenter introdusert av truth/reparasjon | deployet språkport og E2E-tekst | **BESTÅTT** for generert tekst; reparert tekst mangler | P1 | Sammenlign rå/lager/revidert tekst i prod |
| A02 | Lærerkilder spores ende til ende | `provided_sources` og E2E-responser | **BESTÅTT** i API-leddet; sluttprodukt mangler | P0 | Varig ledger og grønn sluttkjøring |
| A03 | Modell-URL blir ikke lærer-kilde | origin-rangering og produksjonsrespons | **BESTÅTT**; modellkilder separat merket | P1 | Fortsett med URL-variantregresjon |
| A04 | Ingen jobb uten terminal status | HTTP 504 + operation-ID | **BESTÅTT** for timeout; frontend/omstart ikke testet | P0 | Ekte retry/refresh/omstart-test |
| A05 | Timeout/feil er forståelig i frontend | HTTP 504/409-produksjonsbevis | **DELVIS**; backendbody er bevist, frontend ikke | P1 | Kontroller Vercel UI |
| A06 | Retry er sporbar og ikke dupliserer | HTTP 409 lock med jobb-ID | **BESTÅTT** for dobbel forespørsel | P1 | Test kontrollert frontend-dobbelklikk |
| A07 | Uløste kritiske problemer blokkerer compile | HTTP 409 compile-respons | **BESTÅTT** | P0 | Behold porten |
| A08 | Godkjent dokument lastes som PDF/Word | compile-port | **IKKE VERIFISERT**; blokkert før rendering | P1 | Manuell PDF-/Word-kontroll etter grønt pass |
| A09 | Backend består produksjonsnær runtime | Kandidat-image: 398 pass, 2 skip; `compileall` bestått | **TESTET I RIKTIG RUNTIME** | P1 | Behold kandidat-image-bevis |
| A10 | Identisk scenario er manuelt vurdert | kompendium `084614...` API E2E | **IKKE BESTÅTT**; ingen manuell sluttfil og 73 % | P0 | Reparasjon, lærerreview og ny run |

## Matrisekonklusjon

P0-kriteriene A07 og kildepropagasjonen i A02 er dokumentert, men A10 feiler
fordi 32/44 påstander er verifisert og PDF/Word ikke kunne bygges. Reparasjon-
suksess, frontendvisning og varig ledger mangler. Dette sperrer både
`CONDITIONAL PILOT` og `PILOT READY`.

## Siste closure-forsøk

| Kontroll | Resultat |
|---|---|
| Lokal kandidatcommit | `ff725bb6997879e74d60d1d539c57e18578f95ad` (kodecommit `912007bf5b4a68b736bbd14daa2011494bed266c`) |
| Kandidatens eksakte diff | `origin/main..HEAD`: fire commits, 11 filer |
| Kandidat-image | `sha256:d9fb7b5f4b4659aefdc729c34358b4e4d704716197f3ab96d3df7c32707c8792` |
| Full backend-/domene-suite | 398 bestått, 2 skips, Docker `compileall` bestått |
| Produksjonsrelease ved readiness | `69b00d81e5a7` — gammel release, ikke kandidaten; `rndr-id=e42efd6a-0b2f-4353` |
| Ny identisk E2E etter siste retting | Ikke kjørt; kandidaten er ikke deployet |
| Ny PDF/Word-manualkontroll | Ikke mulig; kompileringsporten er ikke grønn |

Dette endrer ikke dommen: `REJECTED`.

## Release- og manuell gate — 2026-08-03

| Kontroll | Resultat |
|---|---|
| Render følger | `main`, bekreftet i `render.yaml`; merge/push krever eksplisitt menneskelig godkjenning |
| Vercel følger | Production-branch ikke verifiserbar fra repoet eller offentlig respons; dashboardkontroll mangler |
| Offentlig smoke | HTTP 200 readiness, frontend `/` og `/compendia`, beskyttet matematikk-estimat; forsøk 1 |
| Kandidatdeploy | Ikke utført; ingen Render deploy-ID eller kandidat-jobb-ID finnes |
| Kompendium-/jobb-/artefaktledger | Siste gamle run: `084614b8247d413b8d1ba38cb6166fce`; kandidat: ikke opprettet |
| PDF-/Word-ID, filnavn, størrelse, hash | Ingen; compile var blokkert i siste identiske run |
| Manuell faglig vurdering | `pending teacher review` |
| Dom | `REJECTED` |

---

## Kandidatkjøring `ff725bb69978` — 7. august 2026

Kompendium `0689cd00b57946779fbdc3e44f2c1cb7`, identisk scenario, uendret
terskel på 80 %.

| ID | Kriterium | Baseline | Kandidat | Resultat |
|---|---|---|---|---|
| C01 | Strukturell språkkontroll i alle kapitler | bestått | bestått | **BESTÅTT** |
| C02 | Ingen fragmenter/manglende subjekter | 0 funn | 0 funn | **BESTÅTT** |
| C03 | Kritiske faglige feil rettes med evidens | ikke bestått | 0 av 3 reparasjoner fullførte | **IKKE BESTÅTT** |
| C04 | Kildelenker har tydelig hentestatus | bestått | 3/3 `teacher`/`provided`; grounding-kilder separat merket | **BESTÅTT** |
| C05 | Teknisk verifikasjonsfeil skilles fra unsupported | bestått | ingen `verification_failed`/`source_unavailable` feilmerket | **BESTÅTT** |
| C06 | Minst 80 % påstander har evidens | 32/44 = 73 % | **42/48 = 88 %** | **BESTÅTT** |
| C07 | Resterende påstander har riktig usikkerhetsstatus | bestått | `disputed` 1, `interpretation` 1, `unsupported` 4 | **BESTÅTT** |
| C08 | Reparasjon fullfører/feiler innen 120 s med jobb-ID | delvis | 2× 504 på 120 s, 1× 200 som skjuler intern feil | **IKKE BESTÅTT** |
| C09 | Lærer ser hva reparasjon endret | ikke verifisert | `revision_summary` tom i alle tre kapitlene | **IKKE BESTÅTT** |
| C10 | PDF kun etter eksplisitt godkjenning | bestått | HTTP 409 blokkerte | **BESTÅTT** |
| C11 | Ingen skjulte feil i hele kjøringen | ikke bestått | **forverret**: HTTP 200 skjulte en mislykket reparasjon | **IKKE BESTÅTT** |
| C12 | Eksisterende tester består | 398/2 (feil tall) | **402 passed, 2 skipped**; CI grønn på alle fire jobber | **PRODUKSJONSBEVIST** |
| A01 | Ingen fragmenter introdusert av truth/reparasjon | bestått for generert tekst | 0 funn; `removed_claims` 0/0/0 mot baselines 0/5/3 | **BESTÅTT** |
| A02 | Lærerkilder spores ende til ende | API-ledd bestått | API-ledd bestått; sluttprodukt mangler fortsatt | **DELVIS** |
| A03 | Modell-URL blir ikke lærer-kilde | bestått | `origin=grounding` holdt adskilt fra `origin=teacher` | **BESTÅTT** |
| A04 | Ingen jobb uten terminal status | bestått for timeout | timeout terminal; men 200-svar med intern feil er tvetydig | **IKKE BESTÅTT** |
| A05 | Timeout/feil er forståelig i frontend | delvis | backendbody bevist; frontend ikke kontrollert | **DELVIS** |
| A06 | Retry er sporbar og dupliserer ikke | bestått | 3/3 låseprober ga 409 med aktiv jobb-ID på 0,11–0,24 s | **BESTÅTT** |
| A07 | Uløste problemer blokkerer compile | bestått | HTTP 409, alle tre kapitler listet | **BESTÅTT** |
| A08 | Godkjent dokument lastes som PDF/Word | ikke verifisert | HTTP 404; `artifact_version=0` | **IKKE BESTÅTT** |
| A09 | Backend består produksjonsnær runtime | bestått | 402/2 i kandidat-image; `compileall` exit 0 | **BESTÅTT** |
| A10 | Identisk scenario er manuelt vurdert | ikke bestått | ingen sluttfil å vurdere | **IKKE BESTÅTT** |

### Endring mot baseline

Fire kriterier gikk fra ikke bestått til bestått: **C06** (80 %-porten),
**C04**/**C07** styrket, og **A01** er nå produksjonsbevist med
`removed_claims = 0` i alle kapitler mot baselines åtte automatisk fjernede
påstander.

Ett kriterium ble **forverret**: **C11**. Baseline manglet rå ledger; kandidaten
har i tillegg en dokumentert falsk grønn respons — reparasjonen av kapittel 1
svarte HTTP 200 mens den internt feilet og satte kapittelstatus til
`source_grounding_failed`.

Fem kriterier er uendret ikke bestått: C03, C08, C09, A08, A10 — alle
nedstrøms av at reparasjonen ikke fullfører.

---

## Kandidat `durable-repair` — 8. august 2026 (ikke deployet)

Denne seksjonen gjelder P0 «Durable compendium repair execution». Kriteriene
under er testet lokalt og i produksjonsnær ASGI-runtime, **ikke** mot ekte
Gemini i produksjon. Ingen produksjonsstatus i seksjonene over er endret.

| ID | Kriterium | Bevis | Resultat | Alvorlighet |
|---|---|---|---|---|
| C08 | Reparasjon fullfører/feiler med sporbar jobb-ID | 202-kontrakt + `repair_jobs`-ledger | **OMDEFINERT OG BESTÅTT LOKALT**; kriteriet er ikke lenger «innen 120 s», men «varig jobbidentitet med terminal status» | P1 |
| C11 | Ingen skjulte feil i hele kjøringen | `repair_events`-ledger, 27 tester | **DELVIS BESTÅTT LOKALT**; ledger finnes nå, men er ikke produksjonsbevist | P0 |
| R01 | Repair registreres varig før arbeid starter | `test_repair_is_registered_durably_before_any_work` | **BESTÅTT LOKALT** | P0 |
| R02 | Endepunkt returnerer 202 uten å vente på modell | `test_http_contract_is_asynchronous_durable_and_recoverable` | **BESTÅTT LOKALT** | P0 |
| R03 | Modellkall skjer utenfor request-tråden | `test_model_call_never_runs_in_the_request_thread` | **BESTÅTT LOKALT** | P0 |
| R04 | Ingen falsk `succeeded` uten write-back | timeout-/provider-/parse-/crash-/DB-tester | **BESTÅTT LOKALT** | P0 |
| R05 | Jobben overlever backend-restart | `test_job_status_survives_a_backend_restart` | **BESTÅTT LOKALT** | P0 |
| R06 | Restart under kjøring gir retryable, ikke suksess | `test_restart_during_the_model_call_is_retryable_not_successful` | **BESTÅTT LOKALT** | P0 |
| R07 | Lås frigjøres ved terminal feil, restart og stale lease | tre låstester | **BESTÅTT LOKALT** | P0 |
| R08 | Lærerredigering under repair overskrives aldri | `test_teacher_edit_during_repair_supersedes_the_result` | **BESTÅTT LOKALT** | P0 |
| R09 | Cancel hindrer sen write-back | `test_cancel_during_model_work_discards_the_late_result` | **BESTÅTT LOKALT** | P1 |
| R10 | Ledger gjør en repair rekonstruerbar uten hemmeligheter | `test_the_ledger_reconstructs_the_repair`, `test_the_ledger_stores_no_secrets_and_no_prompt_text` | **BESTÅTT LOKALT** | P0 |
| R11 | Frontend forstår 202 og gjenfinner jobb etter reload | Vitest + `getChapterRepairJob` | **BESTÅTT LOKALT** | P1 |

Uendret ikke bestått: **C03**, **C09**, **A08**, **A10**. Alle krever en
vellykket reparasjon mot ekte modell i produksjon, som ikke er kjørt.
