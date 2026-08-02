# Pilot go/no-go

## Dom: `REJECTED`

Skoleverksted skal ikke åpnes for én ekstern historielærer ennå. Dette er ikke
fordi de lokale tiltakene mangler, men fordi de ikke er deployet og ikke er
verifisert mot ekte modell eller identisk produksjonskjøring.

## Hvorfor

* Produksjonsfanen kjører fortsatt gammel kode og viser 0/13 dokumenterte
  påstander samt `Må revideres`.
* Ingen Render commit-SHA, readiness, modell/prompt-fingerprint eller
  produksjonslogger kunne bekreftes.
* Identisk 3-kapitlers scenario er ikke kjørt etter retting.
* PDF/Word fra ny kjøring er ikke manuelt kontrollert.
* Rå modellrespons og kildefetch-ledger for originalhendelsen mangler.

## Åpne feil

### P0

* Ingen gyldig produksjonsbevis for audit-koden.
* Lærerens kilder kan ikke spores ende til ende i produksjon.
* Identisk produksjonsscenario og manuell vurdering mangler.
* Full monorepo-suite er nå grønn i Docker, men 47 warnings og en bakgrunnstest
  med ugyldig testnøkkel må ikke forveksles med produksjonsbevis.

### P1

* Ekte modellrespons, kildesøk og 80 %-faktapass er ikke testet.
* Ekte timeout, retry, refresh og backend-omstart for reparasjon er ikke testet.
* Ny PDF og Word er ikke visuelt kontrollert.
* Fresh Docker-image fra gjeldende releasecommit er bygget lokalt og består full
  monorepo-test, men er ikke publisert eller deployet.

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

1. Commit og deploy audit-koden til riktig Render/Vercel-tjeneste.
2. Kontroller readiness, commit-SHA, promptversjon, modell og CORS.
3. Kjør identisk scenario med samme tre kilder.
4. Lagre request-/operation-ID, rå/normalisert tekst, claims, kildestatus,
   reparasjonsendringer og logger.
5. Kjør de fem historiefixturene og kontroller PDF/Word visuelt.
6. Få en ekstern historielærer til å vurdere innholdet før `CONDITIONAL PILOT`.

## Stoppkriterier under neste pilot

Stopp umiddelbart dersom en kilde blir `model_reported` uten tydelig markering,
et teknisk verifikasjonsproblem vises som `unsupported`, en jobb mangler
terminal status, språkporten slipper fragmenter gjennom, eller PDF/Word kan
lastes ned uten eksplisitt lærergodkjenning.
