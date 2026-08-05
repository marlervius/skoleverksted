# Acceptance matrix

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
