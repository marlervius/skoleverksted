# Acceptance matrix

Resultatene under er for release-gaten 2. august 2026. `IMPLEMENTERT` betyr
kode finnes; det betyr ikke produksjonsgodkjenning.

| ID | Kriterium | Bevis | Resultat | Alvorlighet | Oppfølging |
|---|---|---|---|---|---|
| C01 | Alle tre kapitler består strukturell språkkontroll | `text_quality.py`, plattformtester | **IKKE VERIFISERT** i identisk produksjon | P1 | Deploy og kjør tre kapitler på nytt |
| C02 | Ingen fragmenter/manglende subjekter | setningssikker remove + språkport | **LOKALT TESTET**; produksjon gammel | P1 | Kontroller rå/lagret/revidert tekst E2E |
| C03 | Kritiske faglige feil rettes/fjernes med evidens | truth-status og reparasjonstester | **IKKE VERIFISERT** mot ekte modell | P1 | Manuell lærerreview av alle kapitler |
| C04 | Alle kildelenker har tydelig hentestatus | `origin`/`fetch_status`, fixturetester | **LOKALT TESTET**; ikke deployet | P1 | Kontroller faktiske fetch-resultater i Render |
| C05 | Teknisk verifikasjonsfeil skilles fra unsupported | Truth enum + UI labels | **LOKALT TESTET** | P1 | Verifiser i produksjons-UI |
| C06 | Minst 80 % konkrete påstander har evidens | `verified_count / total >= .8` | **IMPLEMENTERT**, ikke ekte modelltestet | P1 | Kjør identisk scenario og lagre passport |
| C07 | Resterende påstander har riktig usikkerhetsstatus | nye statusenum + tester | **LOKALT TESTET** | P1 | Kontroller per claim i produksjon |
| C08 | Reparasjon fullfører/feiler innen 120 s med jobb-ID | timeout/lock-tester | **LOKALT TESTET** | P1 | Ekte modell-timeout og frontendtest |
| C09 | Lærer ser hva reparasjon endret | `revision_summary` beholdes | **LOKALT TESTET**; ingen deploy | P2 | Vis før/etter i identisk pilotkjøring |
| C10 | PDF kun etter eksplisitt godkjenning | compile/approve-regler | **LOKALT TESTET**; gammel UI-blokkering observert | P1 | Godkjent sluttfil må bygges i ny run |
| C11 | Ingen skjulte feil i hele kjøringen | ingen prod-logg tilgjengelig | **IKKE VERIFISERT** | P0 | Render logger + request ledger er obligatorisk |
| C12 | Eksisterende tester består | Full monorepo: 396 pass, 2 skip, 47 warnings; frontend 13 pass | **TESTET I RIKTIG RUNTIME** | P1 | Reduser testharness-warnings og kjør ekte modell separat |
| A01 | Ingen fragmenter introdusert av truth/reparasjon | 87 plattformtester + språkport | **LOKALT TESTET** | P1 | Sammenlign rå/lager/revidert tekst i prod |
| A02 | Lærerkilder spores ende til ende | `provided_sources` og fixturetest | **IKKE VERIFISERT** | P0 | Deploy, logg og passport må vise samme URL |
| A03 | Modell-URL blir ikke lærer-kilde | origin-rangering og truth filtering | **LOKALT TESTET** | P1 | Produksjonstest med modellrapportert URL |
| A04 | Ingen jobb uten terminal status | server timeout + frontend AbortError | **LOKALT TESTET**, gammel prod hadde hang | P0 | Ekte retry/refresh/omstart-test |
| A05 | Timeout/feil er forståelig i frontend | status 504/502 + request ID | **LOKALT TESTET** | P1 | Kontroller Vercel mot ny backend |
| A06 | Retry er sporbar og ikke dupliserer | kapittellås + operation ID | **LOKALT TESTET** | P1 | Test dobbel klikking og refresh i prod |
| A07 | Uløste kritiske problemer blokkerer compile | `chapter.status != approved` | **LOKALT TESTET** | P0 | Prod API-test |
| A08 | Godkjent dokument lastes som PDF/Word | eksisterende renderer-tester | **IKKE VERIFISERT** for ny run | P1 | Manuell PDF-/Word-kontroll |
| A09 | Backend består produksjonsnær runtime | Docker: full monorepo 396 pass, 2 skip | **TESTET I RIKTIG RUNTIME** | P1 | Fresh image fra releasecommit |
| A10 | Identisk scenario er manuelt vurdert | produksjonsfanen viser gammel versjon | **IKKE VERIFISERT** | P0 | Deploy current fixes og kjør scenario |

## Matrisekonklusjon

P0-kriteriene A02, A04, A07 og A10 er ikke dokumentert i ny produksjon. Det
alene sperrer `CONDITIONAL PILOT` og `PILOT READY`.
