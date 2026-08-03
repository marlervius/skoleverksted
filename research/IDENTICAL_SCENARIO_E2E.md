# Identical scenario E2E

Status: `RUN AFTER DEPLOY — REJECTED BY QUALITY GATE`.

Kjøringen ble gjennomført mot Render-readiness-SHA `5b72a0541a20` etter
produksjonssmoke. Den er identisk med fixturekontrakten, men bestod ikke fordi
to kapitler fortsatt hadde for lav verifiseringsdekning. Ingen PDF eller Word
ble produsert.

## Inputkontrakt

* Fag: Historie VG2
* Tema: Den franske revolusjonen 1789–1799
* Omfang: 3 kapitler, omtrent 6 sider
* Kompetansemål: samme anonymiserte kontrakt som i
  `evaluations/history_vg2/french_revolution_1789_1799/input.json`
* Læreroppgitte kilder: samme URL-sett som i `sources.json`
* Differensiering: støtte- og fordypningsspørsmål
* Dokumenttype: kompendium/hefte
* Bildevalg: samme valg som originalkjøringen
* Kvalitetskrav: `rubric.md` og `COMPENDIUM_ACCEPTANCE_CRITERIA.md`

## Produksjonsidentitet

| ID/felt | Verdi |
|---|---|
| Request-ID | `audit-identical-20260803b-outline`, `audit-identical-20260803b-writing`, `audit-identical-20260803b-ch1`, `audit-identical-20260803b-ch2`, `audit-identical-20260803b-ch3`, `audit-identical-20260803b-repair-ch2`, `audit-identical-20260803b-repair-ch2-retry`, `audit-identical-20260803b-compile` |
| Prosjekt-ID | Ikke brukt av platform/compendia-ruten |
| Kompendium-ID | Original: `838938c88e994320a64281aafc871ec8`; identisk etter deploy: `084614b8247d413b8d1ba38cb6166fce` |
| Kapittel-ID-er | `71b44f942dde49028e79d32d15f13ff7`, `16eb2f0eeac544f08502ad93d2e6211e`, `3403e66719f544c099ab4730dc7358da` |
| Plan-/kapitteljobb-ID-er | Platform-rutene oppretter ikke separat jobb-ID; request-ID er korrelasjons-ID |
| Reparasjonsjobb-ID-er | Timeout: `audit-identical-20260803b-repair-ch2`; retry fikk 409 og viste samme aktive ID |
| Kompileringsjobb-ID | Ingen; compile-ruten er synkron og svarte 409 |
| Promptversjon | `skoleverksted-v3` fra readiness |
| Modell | `gemini-3.5-flash`; bilde: `gemini-3.1-flash-image` |

## Tidslinje

| Tid | Hendelse | Jobbstatus | Request-ID | Resultat |
|---|---|---|---|---|
| 2026-08-02 23:31:51Z | Readiness | ready | `0bfba1f8e9a4` | HTTP 200, release `5b72a0541a20`, alle readiness-sjekker sanne |
| 2026-08-03 01:20:02+02 | Disposisjon opprettet | outline | `audit-identical-20260803b-outline` | HTTP 201, tre kapitler |
| 2026-08-03 01:20:02+02 | Skrivefase | writing | `audit-identical-20260803b-writing` | HTTP 200 |
| 2026-08-03 01:22:31+02 | Kapittel 1 ferdig | generated | `audit-identical-20260803b-ch1` | 14/14 verifisert, 100 % |
| 2026-08-03 01:25:28+02 | Kapittel 2 ferdig | needs_revision | `audit-identical-20260803b-ch2` | 13/21 verifisert, 62 %, truth `needs_review` |
| 2026-08-03 01:27:22+02 | Kapittel 3 ferdig | needs_revision | `audit-identical-20260803b-ch3` | 5/9 verifisert, 56 %, truth `needs_review` |
| 2026-08-03 01:29:xx+02 | Reparasjon tidsavbrutt | terminal error | `audit-identical-20260803b-repair-ch2` | HTTP 504 etter 120 s; kapittel uendret |
| 2026-08-03 01:30:09+02 | Dobbel/retry kontrollert | rejected | `audit-identical-20260803b-repair-ch2-retry` | HTTP 409, aktiv jobb-ID oppgitt |
| 2026-08-03 01:30:36+02 | Compile-port | blocked | `audit-identical-20260803b-compile` | HTTP 409; alle kapitler listet |

## Kildepropagering og truth

| Kilde | Mottatt | Lagret | `provided_sources` | Hentestatus | Koblet til påstand | Sluttprodukt |
|---|---|---|---|---|---|---|
| `https://snl.no/den_franske_revolusjonen` | Ja, i request | Ja, `origin=teacher` i alle tre kapittelresponsene | Ja, sendt til truth-laget | `provided` | Ja i kap. 1–3 der modellen brukte den; konkrete claims varierer | Ikke produsert |
| `https://www.britannica.com/event/French-Revolution` | Ja, i request | Ja, `origin=teacher` | Ja | `provided` | Ja i kap. 1–3 der modellen brukte den | Ikke produsert |
| `https://www.udir.no/lk20/his01-03/kompetansemaal-og-vurdering/kv103` | Ja, i request | Ja, `origin=teacher` | Ja | `provided` | Ja i truth-pass der brukt | Ikke produsert |

Modellrapporterte URL-er er separat merket `origin=model`/`model_reported` og
er ikke regnet som læreroppgitte kilder. Redirect-/variant-URL-er fra modellen
forekommer i enkelte responslister, men lærerens kanoniske URL-er beholdes.

## Påstandsresultat

| Kapittel | Status | Påstander | Verifisert | Dekning | Språkport |
|---|---|---:|---:|---:|---|
| 1 | `generated` / truth `verified` | 14 | 14 | 100 % | Bestått |
| 2 | `needs_revision` / truth `needs_review` | 21 | 13 | 62 % | Bestått; ingen `empty_heading` etter portretting |
| 3 | `needs_revision` / truth `needs_review` | 9 | 5 | 56 % | Bestått |
| **Totalt** | **Ikke grønt** | **44** | **32** | **73 %** | **Ingen systemintroduserte fragmenter** |

Resten er eksplisitt `unsupported`/`interpretation`/`needs_review` i truth-
passet; det er ikke behandlet som verifisert. Teknisk `verification_failed`,
`source_unavailable` eller `not_evaluated` ble ikke brukt i denne kjøringen.

Påstandsregisteret skal etter kjøring inneholde tekst, kilde, evidens,
konfidens, status og foreslått handling. Statusene må holdes adskilt:
`verified`, `undocumented`, `verification_failed`, `source_unavailable`,
`not_evaluated`, `interpretation`, `disputed` og `time_sensitive`.

## Tekst- og reparasjonssammenligning

API-responsene for disposisjon og hvert kapittel er lagret lokalt i
`C:\tmp\prod_outline_b.json`, `C:\tmp\prod_b_ch1.json`,
`C:\tmp\prod_b_ch2.json`, `C:\tmp\prod_b_ch3.json` og
`C:\tmp\prod_b_final.json`. API-et eksponerer ikke rå modellrespons,
intermediate truth-prompt eller separat reparasjonsjobbledger, så disse kan
ikke rekonstrueres fra produksjonen. Det finnes ingen reparert tekst fordi
jobben tidsavbrøt før et resultat ble lagret.

## Kompilering og manuell vurdering

PDF-status: korrekt blokkert med HTTP 409 fordi alle tre kapitlene ikke var
`approved`/`verified`. Word-status: ikke produsert av samme compile-port.
Manuell vurdering av sluttfiler: ikke utført. Dette er riktig sikkerhetsutfall.

## Avvik fra originalscenarioet

Avvik fra originalens synlige scenario: ny kompendium-ID og AI-generert
disposisjon ga andre kapitteltitler enn originalen; input, kapitteltall,
sideantall, kilder, differensiering, dokumenttype og bildevalg (`none`) var
identiske. Produksjonen bruker synkrone platform-ruter, så separate
plan-/kapitteljobb-ID-er finnes ikke. Incidenten er åpen og dommen er
`REJECTED`.

## Kandidatstatus etter siste lokale retting

Candidate commit `2e66ec7a5467f3fc23523930ec9ac51181e7c070` og image
`sha256:db88579d5240abd7b1381ad0cfae035a7f8d73cbe01a11963ab92e685da47858`
består lokal backend-suite med 398 passed, 2 skipped og 47 warnings.
Kandidaten er ikke deployet. Readiness viste release `69b00d81e5a7`, så ingen
ny request-ID, kompendium-ID, kapittel-/jobb-ID, kildepropagering,
truth-resultat, reparasjonsresultat eller kompilering kan tilskrives kandidaten.
Forrige produksjonskjøring står som historisk `32/44 = 73 %`, repair `504`,
retry `409` og compile `409`.
