# Identical scenario E2E

> **Siste kjøring: kandidat `ff725bb69978`, 7. august 2026.** Se seksjonen
> «Identisk scenario på kandidaten» nederst. Dom fortsatt `REJECTED`, men av en
> annen grunn enn baseline: sannhetsdekningen består (42/48 = 88 %), mens
> reparasjonen ikke fullfører. Avsnittene under beskriver baselinekjøringen på
> `69b00d81e5a7` og er historikk.

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

---

# Identisk scenario på kandidaten `ff725bb69978` — 7. august 2026

Status: `KJØRT PÅ KANDIDAT — REJECTED AV REPARASJONSPORTEN`.

Scenarioet er kjørt med **samme inputkontrakt, samme akseptansekriterier og
samme terskel på 80 %** som baselinekjøringen. Ingenting er forenklet. Feltene
i planforespørselen ble rekonstruert fra den lagrede baselineresponsen
`C:\tmp\prod_outline_b.json`, slik at tema, fag, nivå, `kind`, `purpose`,
`audience`, `target_pages`, `chapter_count`, kompetansemål, `source_brief`,
`include_*`-flagg og `image_mode: none` er identiske.

## Produksjonsidentitet

| ID/felt | Baseline `69b00d81e5a7` | Kandidat `ff725bb69978` |
|---|---|---|
| Kompendium-ID | `084614b8247d413b8d1ba38cb6166fce` | `0689cd00b57946779fbdc3e44f2c1cb7` |
| Kapittel-ID-er | `71b44f94…`, `16eb2f0e…`, `3403e667…` | `154843d6…`, `e673cfd8…`, `00312e34…` |
| Request-ID-prefiks | `audit-identical-20260803b-*` | `audit-candidate-20260806-*` |
| Promptversjon | `skoleverksted-v3` | `skoleverksted-v3` |
| Modell | `gemini-3.5-flash` / `gemini-3.1-flash-image` | identisk |
| Config-fingerprint | `dc08f612a352` | `dc08f612a352` |
| Kø / lagring | `sqlite-local`, `/var/data/platform/skoleverksted.sqlite3` | identisk |

Fingerprinten er uendret, så forskjellen mellom kjøringene er isolert til
`truth.py`-endringen i `912007b` pluss modellens ikke-determinisme.

## Tidslinje

| Tid (UTC) | Hendelse | HTTP | Varighet | Jobb-/request-ID | rndr-id |
|---|---|---|---|---|---|
| 11:20:26 | Readiness | 200 | – | – | `0c15b19d-1744-43de` |
| 11:20:40 | Disposisjon | 201 | 13,26 s | `audit-candidate-20260806-outline` | `a1e67e41-0223-48b7` |
| 11:22:52 | Kapittel 1 generert | 200 | 132,08 s | `…-ch1` | `49f6291e-a94d-4427` |
| 11:26:19 | Kapittel 2 generert | 200 | 206,48 s | `…-ch2` | `044d07bc-020c-4c63` |
| 11:28:17 | Kapittel 3 generert | 200 | 118,78 s | `…-ch3` | `f3a528cb-459e-45ea` |
| 11:28:25 | Låseprobe kap. 1 | **409** | 0,11 s | `…-repair-ch1-retry` | `e569771f-8a1d-4383` |
| 11:29:33 | Reparasjon kap. 1 | **200** | 75,94 s | `…-repair-ch1` | `2c6a713d-9946-4dd3` |
| 11:29:41 | Låseprobe kap. 2 | **409** | 0,22 s | `…-repair-ch2-retry` | `a9bd3ce2-7108-4210` |
| 11:31:33 | Reparasjon kap. 2 | **504** | 120,11 s | `…-repair-ch2` | `a071c2be-6bad-403e` |
| 11:31:42 | Låseprobe kap. 3 | **409** | 0,24 s | `…-repair-ch3-retry` | `3a310cf9-6716-46a8` |
| 11:33:34 | Reparasjon kap. 3 | **504** | 120,21 s | `…-repair-ch3` | `a38cbf8b-4336-4e64` |
| 11:33:34 | Compile-port | **409** | 0,19 s | `…-compile` | `18915cf6-5e8d-40af` |
| 11:33:34 | Nedlasting PDF | **404** | 0,17 s | `…-download-pdf` | `2db9d3b4-11f4-4575` |
| 11:33:34 | Nedlasting Word | **404** | 0,24 s | `…-download-docx` | `e097bb24-5bcc-47f0` |

Alle svar ekko-et vår `X-Request-ID` tilbake i responsheaderen, så
korrelasjons-ID-en holdt gjennom hele platform-ruten i denne kjøringen.

## Påstandsresultat — punkt for punkt

| Kapittel | Baseline | Kandidat | Endring |
|---|---|---|---|
| 1 | 14/14 = 100 %, truth `verified` | 13/15 = 87 %, truth `needs_review` | ned |
| 2 | 13/21 = 62 %, truth `needs_review` | 17/20 = 85 %, truth `needs_review` | opp |
| 3 | 5/9 = 56 %, truth `needs_review` | 12/13 = 92 %, truth `needs_review` | opp |
| **Totalt** | **32/44 = 73 %** | **42/48 = 88 %** | **+15 prosentpoeng** |

Kandidaten passerer 80 %-terskelen på totalen og i hvert enkelt kapittel.
Terskelen er ikke endret for å oppnå dette.

Claim-statuser i kandidaten: kap. 1 `verified` 13, `disputed` 1,
`interpretation` 1; kap. 2 `verified` 17, `unsupported` 3; kap. 3 `verified` 12,
`unsupported` 1. Ingen `verification_failed`, `source_unavailable` eller
`not_evaluated` ble brukt.

## Fail-closed-effekten er produksjonsbevist

| Felt | Baseline | Kandidat |
|---|---|---|
| `removed_claims` kap. 1/2/3 | 0 / 5 / 3 | **0 / 0 / 0** |
| `limitations` per kapittel | «n usikre påstander kunne ikke endres automatisk» | samme form, men dekker nå alle uavklarte treff |

Dette er den direkte, observerte virkningen av `912007b`: den gamle koden
fjernet åtte påstanders tekst automatisk i produksjon. Kandidaten fjerner
ingenting og lar i stedet læreren se hva som er uavklart. Det er milepælens
formål, og det er nå `PRODUKSJONSBEVIST`.

## Språkport

`inspect_markdown` kjørt på alle tre kapitlene i begge kjøringene gir **null
funn** — ingen `empty_heading`, `sentence_fragment`, `missing_subject`,
`source_fragment`, `trailing_fragment`, `possible_truncation` eller
`content_too_short`. Ingen systemintroduserte språkfragmenter i kandidaten.

## Kildeproveniens

3/3 læreroppgitte URL-er er propagert med `origin=teacher` og
`fetch_status=provided` i alle tre kapitlene, i begge kjøringene. Lagrede
URL-er er vertsnormaliserte (`www.` fjernet); lærerens kanoniske adresser er
bevart.

Kandidatens kapittel 3 har i tillegg seks `origin=grounding`-kilder fra
modellen, tydelig merket som noe annet enn lærerkilder. To av dem
(`scribd.com`, `en.wikipedia.org`) ble flagget av kildekvalitetskontrollen med
krav om erstatning. Baseline hadde ingen grounding-kilder i sluttresponsen.

## Reparasjon — kjernefunnet

**Null av tre reparasjoner reparerte noe.**

* Kapittel 2 og 3: HTTP **504** etter 120,11 s og 120,21 s. Identisk feilmodus
  som baseline. Teksten er uendret, jobb-ID oppgitt i feilmeldingen.
* Kapittel 1: HTTP **200** etter 75,94 s — men reparasjonen feilet internt.
  Kapittelstatusen gikk fra `needs_revision` til **`source_grounding_failed`**,
  `revision_count` forble 0, `revision_summary` forble tom,
  `previous_content_markdown` ble aldri satt, og kapitlet fikk noten
  «Automatisk retting kunne ikke fullføres. Kapittelteksten er bevart uendret;
  prøv igjen om litt.»

Kapittel 1 er derfor et **falskt grønt svar**: klienten fikk HTTP 200 på en
operasjon som mislyktes og som gjorde kapittelets status dårligere enn før.
Koden i `compendium.py` fanger unntaket, setter `status=source_grounding_failed`
og returnerer kapitlet som en vanlig 200-respons. En lærer eller et
frontend-kall kan ikke skille dette fra en vellykket reparasjon på HTTP-nivå.

Låsen fungerte i alle tre tilfellene: samtidig andre-forespørsel ble avvist med
HTTP 409 og navngitt aktiv jobb-ID på 0,11–0,24 s.

## Kompilering og artefakter

Compile ga **HTTP 409** og listet alle tre kapitlene som uferdige. PDF- og
Word-nedlasting ga **HTTP 404**, «Dokumentfilen finnes ikke». I den endelige
tilstanden er `pdf_filename` og `docx_filename` tomme, `pdf_size_bytes` og
`docx_size_bytes` er 0, `artifact_version` er 0 og `approved_at` er `null`.

Dette er korrekt sikkerhetsutfall — porten skal blokkere — men det betyr at
ingen sluttfil finnes og at **manuell lærervurdering fortsatt er umulig**.

## Rå response-ledger

API-et eksponerer fortsatt ikke rå modellrespons, mellomliggende truth-prompt
eller en varig reparasjonsjobb-ledger. Alle rå API-svar fra denne kjøringen er
lagret lokalt i sesjonens scratchpad (`e2e_outline.json`, `e2e_ch1..3.json`,
`e2e_repairs.json`, `e2e_compile.json`, `e2e_final.json`, `e2e_log.json`), men
det er en klientside-logg, ikke et produksjonsledger.

## Avvik fra baselinescenarioet

Ny kompendium-ID og AI-generert disposisjon ga andre kapitteltitler.
Kapitteltall, sideantall, kilder, differensiering, dokumenttype og bildevalg
(`none`) er identiske. Platform-rutene er fortsatt synkrone, så separate
plan-/kapitteljobb-ID-er finnes ikke; request-ID er korrelasjons-ID.

## Dom

`REJECTED`. Sannhetsdekningen består for første gang, men reparasjon,
kompilering, PDF, Word og manuell lærervurdering gjør det ikke.
