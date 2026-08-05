# Failed compendium forensic audit

Dato for lokal audit: 2. august 2026. Dette dokumentet analyserer den siste
kjøringen som faktisk er synlig i denne arbeidsflaten, og skiller observasjon
fra det som ikke kan rekonstrueres uten Render-database/loggtilgang.

## 1. Identifisert produksjonskjøring

Den eneste kjøringen som kan kobles entydig til scenarioet er kompendiet
`838938c88e994320a64281aafc871ec8` på Vercel-adressen
`https://skoleverksted.vercel.app/compendia/838938c88e994320a64281aafc871ec8`.
UI-testen viste Historie VG2, den franske revolusjonen 1789–1799, tre kapitler,
omtrent seks sider og lærerens kilde-URL-er. Disposisjonen tok omtrent 39
sekunder; kapitlene ble observert som ferdige etter omtrent fem minutter.

Følgende er ikke tilgjengelig lokalt: prosjekt-ID, bruker-ID, jobb-ID,
request-ID, promptversjon, modellnavn, server-tidsstempler, Render-requestlogg,
database-rader, rå modellrespons, lagrede kildetekster og reparasjonsledger.
Platform-kompendiumrutene var dessuten synkrone og opprettet ikke en varig
`Job`-rad. Manglende felt må derfor hentes fra Render disk/SQLite og
applikasjonslogger før en pålitelig tidslinje kan bli komplett.

## 2. Faktiske observasjoner

* Alle tre kapitlene fikk `Må revideres`; ingen ble godkjent.
* Disposisjonen hadde støtte- og fordypningsspørsmål.
* PDF-knappen var blokkert før eksplisitt godkjenning.
* Kapittel 1 viste blant annet `Særlig ble en finansiell katastrofe.`, `Blant
  disse var ...` og manglende subjekter.
* Kapittel 2 viste `en dyp sidebyrdig splittelse` og blanke tekstpartier.
* Kapittel 3 manglet subjekter/referanser, blant annet `var ikke bare ...`.
* Faktapasset viste 0/10, 0/17 og 0/14 påstander, og teksten sa at ingen
  konkrete validerte kildesider var registrert.
* Reparasjonsknappen stod i `Sjekker og retter …` i minst omtrent 100 sekunder.

## 3. Rekonstruert feilkjede

| Ledd | Forventet | Faktisk/konstatert | Feil? |
|---|---|---|---|
| Lærerinput | Tema, mål, URL-er og differensiering mottas og bevares | `source_brief` ble lagt inn i plan- og kapittelprompt | Delvis; ikke lagret som verifiseringskilder |
| Avgrensningskontrakt | Tidsrom/geografi/inkludering lagres | Scope-kontrakt ble lagret i kompendiet | Ikke hovedfeil |
| Disposisjon | Tre kapitler med spørsmål | Dette fungerte | Nei |
| Kildeinnhenting | Grounding og lærer-URL-er skal ha hentestatus | Modell-/grounding-kilder ble samlet; lærer-URL-er ble ikke koblet til sannhetslaget | Ja |
| Kildeekstraksjon | Hentet innhold eller eksplisitt utilgjengelig-status | Det finnes ingen lokal rå kilde-/hentelogger; modellen fikk søkeverktøy, men ingen durable fetch-status | Ja/udokumentert |
| Kapittelprompt | Fagtekst med komplette setninger | Kapittelprompten inkluderte kun ubehandlet `source_brief` og modellerte kilder | Medvirkende |
| Modellrespons | Gyldig, komplett JSON/Markdown | Rå respons mangler; lagret tekst var språklig skadet | Må fastslås for denne run |
| Parsing/laging | Teksten skal bevares | JSON-parseren sletter ikke tekst; men sannhetslaget gjorde tekstsubstitusjon | Ja |
| Påstandsuttrekk | Atomiske påstander med ordrette tekstutdrag | 41 påstander ble rapportert i UI, men rå register mangler | Ikke mulig å kontrollere rått |
| Evidenskobling | Kun observerte konkrete URL-er teller | `audit_truth` fikk ikke lærerens URL-er (`provided_sources` manglet) | Hovedfeil for 0 % |
| Faktapass | Teknisk feil skilles fra unsupported | Manglende kilde ble presentert som 0 %/ingen kilder | Ja |
| Automatisk revisjon | Bakgrunnsjobb med timeout/status | Reparasjon var synkront modellkall uten timeout/lock/job-ID | Hovedfeil |
| Frontendstatus | Fullført/feilet innen grense | Polling ventet på fetch-responsen og kunne stå i busy-state | Ja |
| Godkjenning | Kun grønt faktapass kan godkjennes | Eksisterende PDF-blokkering fungerte | Nei |
| PDF | Blokkeres til alle kapitler er godkjent | Blokkert | Nei |

## 4. Hovedårsaker

### Språkfragmenter

Den dokumenterte kodefeilen er `_apply_decisions` i
`Skoleverksted/backend/platform/truth.py:181`. Når en påstand ble fjernet,
gjorde koden `result.replace(exact, "")`. Hvis `exact_text` bare var et navn,
subjekt eller en del av en setning, ble resten stående. Det forklarer både
blanke felter og fragmenter. Rå modelltekst mangler, så det kan ikke bevises om
`sidebyrdig` kom fra modellen eller fra en senere transformasjon. Det finnes
ingen annen generell regex som sletter navn i `_markdown_text` eller
`_extract_json`; begge bevarer i hovedsak tekst.

### 0 av 41 påstander

`_audit_chapter_material` i `Skoleverksted/backend/platform/compendium.py:198`
kalte sannhetslaget uten `provided_sources`. Selv om URL-er lå i lærerens
`source_brief`, ble de bare sendt som promptdata og ikke som tillatte,
observerte kildeobjekter. `truth.py` teller kun grounding-URL-er eller
`provided_sources`; modellskrevne URL-er blir filtrert bort. Resultatet ble
derfor teknisk kildefravær, ikke 41 faglig avviste påstander. Den gamle statusen
`needs_review` og 0 % maskerte dette som et ordinært faktapass.

### Fastlåst reparasjon

`repair_compendium_chapter` i `compendium.py:980` utfører flere synkrone
Google-kall. Rutinen i `router.py` ventet direkte på dette uten timeout,
in-flight-lås, operation-ID eller varig status. Frontendens `run()` holdt
knappen i busy-state til HTTP-kallet returnerte. Modellkall, retry eller
nettverksstopp kunne derfor holde UI-et på `Sjekker og retter …` uten synlig
feil.

## 5. Implementert i denne auditten

* Lærerens konkrete URL-er ekstraheres og merkes `origin=teacher`,
  `fetch_status=provided`; grounding og modellrapporterte kilder har egne
  proveniens-/hentestatus (`compendium.py:702`, `models.py:126`).
* Sannhetslaget får disse kildene eksplisitt, viser dem til verifikatoren og
  skiller `verification_failed`, `source_unavailable` og `not_evaluated` fra
  `unsupported` (`truth.py:251`).
* Grønt faktapass krever minst 80 % verifiserte påstander, konkrete kilder og
  ingen uoppløste tekstendringer.
* Påstands-fjerning skjer på setnings-/linjenivå, ikke ved rå fragment-sletting
  (`truth.py:181`).
* Deterministisk Markdown-port fanger tomme overskrifter, HTML, avkorting,
  manglende subjekt og strukturelle fragmenter (`text_quality.py:49`).
* Nye maskinstatusser brukes på kapittel: `parse_failure`,
  `generation_incomplete`, `language_quality_failed`,
  `source_grounding_failed` og `verification_failed`.
* Reparasjon har 120 sekunders konfigurerbar grense, idempotent kapittellås,
  operation-ID, 409 ved parallell jobb, 504 ved timeout og 502 ved skjult
  unntak (`router.py:57`, `router.py:75`, `router.py:219`).
* Frontend viser de nye statusene og avbryter HTTP-kall etter 150 sekunder med
  synlig retry-melding (`platform-api.ts:369`).
* Compile-ruten krever nå `status == approved` i tillegg til grønt faktapass;
  PDF-blokkeringen er beholdt (`router.py:270`).

## 6. Reproduksjon og begrensning

Scenarioet er anonymisert i
`evaluations/history_vg2/french_revolution_1789_1799/`. Lokal bundled Python
mangler prosjektets FastAPI/Pytest-avhengigheter og Google-nøkkel, men backend-
pakker er kjørt i eksisterende produksjonsnær Docker-runtime: 396 tester
bestått og 2 eksplisitte skips. En live identisk modellkjøring kan likevel ikke
utføres uten deploy-/Render-tilgang. Derfor er den deployede identiske testen
**ikke godkjent som bestått** før ny deploy og full ende-til-ende-kjøring er
utført.
