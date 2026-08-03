# Pilot go/no-go

## Dom: `REJECTED`

Skoleverksted skal ikke åpnes for én ekstern historielærer ennå. Release
`5b72a0541a20` er deployet og smoke-testet, men den identiske ekte modell-
kjøringen fikk bare 32/44 verifiserte påstander (73 %), to kapitler i
`needs_revision`, og reparasjonsjobben fikk HTTP 504 etter 120 sekunder.

Siste lokale kandidat er `2e66ec7a5467f3fc23523930ec9ac51181e7c070` med
image-digest `sha256:db88579d5240abd7b1381ad0cfae035a7f8d73cbe01a11963ab92e685da47858`.
Den er ikke deployet; readiness viser fortsatt `69b00d81e5a7`. Dommen er
derfor fortsatt `REJECTED`.

## Hvorfor

* Render readiness beviser release `5b72a0541a20`, prompt `skoleverksted-v3`,
  Gemini-modell og config-fingerprint; dashboardets deploy-ID er fortsatt
  utilgjengelig.
* Identisk scenario `084614b8247d413b8d1ba38cb6166fce` er kjørt mot ekte modell.
* Lærer-URL-ene ble propagert med `origin=teacher`, `fetch_status=provided`.
* PDF/Word ble korrekt blokkert med HTTP 409; ingen sluttfiler finnes.
* Rå modellrespons og varig source-/response-ledger mangler.

## Åpne feil

### P0

* 80 %-regelen feiler i identisk produksjonsscenario (32/44 = 73 %).
* Ingen vellykket produksjonsreparasjon eller manuell sluttproduktvurdering.
* Render-dashboardets formelle deploy-ID og varig response-ledger mangler.
* Siste forensic-kandidat er ikke publisert til deploybranch.

### P1

* Rå/normalisert truth- og modelltekst er ikke tilgjengelig i varig ledger.
* Vellykket reparasjon, frontend-fremdrift og refresh/omstart er ikke
  produksjonsverifisert.
* Ny PDF og Word er ikke visuelt kontrollert fordi compile-porten blokkerte.
* Identisk scenario er ikke kjørt på kandidaten `2e66ec7`.

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

## Stoppkriterier under neste pilot

Stopp umiddelbart dersom en kilde blir `model_reported` uten tydelig markering,
et teknisk verifikasjonsproblem vises som `unsupported`, en jobb mangler
terminal status, språkporten slipper fragmenter gjennom, eller PDF/Word kan
lastes ned uten eksplisitt lærergodkjenning.
