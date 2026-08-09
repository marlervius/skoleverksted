# Pilot go/no-go

## Dom: `REJECTED`

> **Oppdatert 7. august 2026.** Produksjonen kjører nå kandidaten
> `ff725bb69978`. Gjeldende vurdering står i «Oppdatert vurdering etter
> kandidatdeploy» nederst; avsnittene rett under gjelder baselinereleasen
> `69b00d81e5a7`.

Skoleverksted skal ikke åpnes for én ekstern historielærer ennå. Den offentlige
produksjonen kjører fortsatt `69b00d81e5a7`; smoke bestod, men siste identiske
ekte modellkjøring fikk bare 32/44 verifiserte påstander (73 %), to kapitler i
`needs_revision`, og reparasjonsjobben fikk HTTP 504 etter 120 sekunder.

Siste lokale kandidat er `ff725bb6997879e74d60d1d539c57e18578f95ad` med
image-digest `sha256:d9fb7b5f4b4659aefdc729c34358b4e4d704716197f3ab96d3df7c32707c8792`.
Den er ikke deployet; readiness viser fortsatt `69b00d81e5a7`. Dommen er
derfor fortsatt `REJECTED`.

## Hvorfor

* Render readiness beviser fortsatt release `69b00d81e5a7`, prompt
  `skoleverksted-v3`, Gemini-modell og config-fingerprint; siste `rndr-id` er
  `e42efd6a-0b2f-4353`, men dashboardets formelle deploy-ID er utilgjengelig.
* Identisk scenario `084614b8247d413b8d1ba38cb6166fce` er kjørt mot ekte modell.
* Lærer-URL-ene ble propagert med `origin=teacher`, `fetch_status=provided`.
* PDF/Word ble korrekt blokkert med HTTP 409; ingen sluttfiler finnes.
* Rå modellrespons og varig source-/response-ledger mangler.

## Åpne feil

### P0

* 80 %-regelen feiler i identisk produksjonsscenario (32/44 = 73 %).
* Ingen vellykket produksjonsreparasjon eller manuell sluttproduktvurdering.
* Render-dashboardets formelle deploy-ID og varig response-ledger mangler.
* Kandidaten `ff725bb` er ikke publisert til Render-sporede `main`; Vercel
  production-branch er ikke verifisert fra repoet.

### P1

* Rå/normalisert truth- og modelltekst er ikke tilgjengelig i varig ledger.
* Vellykket reparasjon, frontend-fremdrift og refresh/omstart er ikke
  produksjonsverifisert.
* Ny PDF og Word er ikke visuelt kontrollert fordi compile-porten blokkerte.
* Identisk scenario er ikke kjørt på kandidaten `ff725bb`.

### P2

* Observability mangler varig rå-/normalisert response-ledger og per-URL
  hentelogger.
* Reparasjon etter server-timeout kan fortsatt bruke ressurser i daemon-tråd
  før fremtidig worker/cancellation-arkitektur.

## Hva en pilotlærer kan gjøre nå

Ingen ekstern pilot bør starte. Internt kan utviklere bruke lokal fixture,
plattformtestene og den eksisterende produksjonsfanen kun som observasjon av
gammel oppførsel.

## Hva pilotlæreren ikke skal gjøre

Ikke dele eller skrive ut generert tekst som faktaverifisert materiale, ikke
godkjenne et grønt pass uten å åpne kildene, og ikke bruke produksjonsstatusen
fra den gamle kjøringen som bevis på audit-endringene.

## Før ny vurdering

1. Reparer og kjør identisk scenario på nytt til minst 80 % evidens foreligger.
2. Kjør en vellykket produksjonsreparasjon og kontroller frontendens før/etter-
   visning, retry og kapittellås.
3. Lagre request-/operation-ID, rå/normalisert tekst, claims, kildestatus,
  reparasjonsendringer og logger.
4. Kjør de fem historiefixturene og kontroller PDF/Word visuelt etter grønt pass.
5. Få en ekstern historielærer til å vurdere innholdet før `CONDITIONAL PILOT`.

## Manuell produktgate

Status er `pending teacher review`. En navngitt Historie VG2-lærer må vurdere
den eksakte sluttversjonen på faglig korrekthet, kildekvalitet/proveniens,
språk/sammenheng, VG2-nivå, læringsmål, pedagogisk anvendbarhet,
nødvendige lærerredigeringer og layout/utskrift. Først etter denne vurderingen
kan det avgjøres om dokumentet faktisk kan deles ut.

## Stoppkriterier under neste pilot

Stopp umiddelbart dersom en kilde blir `model_reported` uten tydelig markering,
et teknisk verifikasjonsproblem vises som `unsupported`, en jobb mangler
terminal status, språkporten slipper fragmenter gjennom, eller PDF/Word kan
lastes ned uten eksplisitt lærergodkjenning.

---

## Oppdatert vurdering etter kandidatdeploy — 7. august 2026

**Dom: fortsatt `REJECTED`.** Produksjonen kjører nå kandidaten
`ff725bb69978` (deployet 6. august 2026 13:09:58Z), ikke lenger
`69b00d81e5a7`. Dommen står, men begrunnelsen har endret seg.

### Det som ble bedre

* Sannhetsdekningen gikk fra 32/44 = 73 % til **42/48 = 88 %**, og hvert enkelt
  kapittel er over 80 % (87 %, 85 %, 92 %). Terskelen er ikke endret.
* Fail-closed sannhetsredigering er **produksjonsbevist**: `removed_claims` er
  0 i alle tre kapitlene, mot baselines 0/5/3. Den gamle koden fjernet åtte
  påstanders tekst automatisk i produksjon; kandidaten fjerner ingenting og
  flagger i stedet det uavklarte for læreren.
* Lærerkilder propageres fortsatt 3/3 som `origin=teacher`/`fetch_status=provided`,
  og modellens grounding-kilder holdes adskilt.
* Null språkfragmenter.
* Låsen mot dobbeltkjøring virker: 3/3 samtidige retry-forsøk ga HTTP 409 med
  navngitt aktiv jobb-ID på 0,11–0,24 s.

### Det som fortsatt blokkerer

* **0 av 3 reparasjoner fullførte.** Kapittel 2 og 3 fikk HTTP 504 etter 120 s.
  Kapittel 1 fikk HTTP 200 etter 76 s, men reparasjonen feilet internt og satte
  kapittelstatus til `source_grounding_failed` med teksten uendret.
* Ingen kapitler ble `approved`, compile ga HTTP 409, PDF og Word ga HTTP 404.
* **Manuell lærervurdering er fortsatt umulig** fordi ingen sluttfil finnes.

### Åpne feil — oppdatert

#### P0

* Reparasjonsutførelsen er ikke pålitelig: to tidsavbrudd og én intern feil på
  tre forsøk, uten durable jobb, uten gjenopptak og uten kansellering.
* En mislykket reparasjon rapporteres som HTTP 200. Det er en falsk grønn
  tilstand og bryter regelen om at `completed` skal bety fullført arbeid.
* Ingen vellykket produksjonsreparasjon og ingen manuell sluttproduktvurdering.
* Render-dashboardets deploy-ID og Vercels production-branch er fortsatt
  uverifisert; releaseidentiteten hviler på offentlig readiness alene.

#### P1

* Rå/normalisert truth- og modelltekst finnes ikke i noe varig ledger.
* `revision_summary` er tom i alle kapitler, så læreren kan ikke se hva en
  reparasjon eventuelt endret.
* Frontendens visning av 504/409/`source_grounding_failed` er ikke kontrollert.
* PDF og Word er fortsatt ikke visuelt kontrollert.

#### P2

* Kildekvalitetskontrollen flagget `scribd.com` og `en.wikipedia.org` som
  kilder som bør erstattes. Det fungerte som ment, men viser at
  grounding-kilder kan trekke inn svake kilder som må håndteres av læreren.
* Reparasjon etter server-timeout kan fortsatt bruke ressurser i daemon-tråd.

### Konsekvens for pilot

Ingen ekstern pilot skal starte. Kandidaten er et reelt fremskritt på
tillitssiden — læreren får ikke lenger tekst slettet i skjul — men lærerreisen
stopper fortsatt før første leverbare fil. En pilotlærer ville i dag brukt
omtrent ti minutter på å generere tre kapitler og deretter stått igjen uten
dokument.

---

## Oppdatering 8. august 2026 — durable repair, fortsatt `REJECTED`

Dommen er uendret `REJECTED`. Produksjonen kjører fortsatt `ff725bb69978`, og
den nye reparasjonsarkitekturen er ikke deployet.

Det som er løst siden forrige vurdering gjelder infrastrukturen rundt
reparasjon, ikke lærerens sluttresultat:

* Reparasjon er ikke lenger et blokkerende HTTP-kall. Læreren får en varig
  jobb-ID på under ett sekund og kan forlate siden.
* En mislykket reparasjon kan ikke lenger svare HTTP 200. Kapittel 1-tilfellet
  fra kandidatkjøringen ville i dag gitt `failed_retryable` med konkret retry.
* Et kapittel kan ikke lenger bli permanent låst av en timeout, en crash eller
  en restart.
* Lærerens egen redigering under en reparasjon blir aldri overskrevet.

Det som fortsatt blokkerer pilot er uendret:

* Ingen dokumentert vellykket reparasjon mot ekte modell i produksjon.
* Ingen godkjente kapitler, ingen PDF, ingen Word, ingen manuell faglig
  vurdering av en sluttfil.
* Ingen skolepålogging, ingen tenant-modell på plattformrutene.
* Render deploy-ID og Vercel production-branch er fortsatt `UKJENT`.

Konsekvens: ingen ekstern pilot. Neste port er en deploy av
durable-repair-kandidaten fulgt av det identiske Historie VG2-scenarioet, der
kravet er at reparasjonen er varig, observerbar, gjenopprettbar og ikke-
destruktiv — ikke at modellen alltid løfter kapitlet over kvalitetsporten.
