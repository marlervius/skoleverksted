# Production incident closure

## Opprinnelig hendelse

Kompendium `838938c88e994320a64281aafc871ec8` (Historie VG2, fransk revolusjon,
tre kapitler) produserte fragmentert tekst, 0 dokumenterte påstander i alle
kapitler og en reparasjonsknapp som stod aktiv i minst omtrent 100 sekunder.
PDF-blokkeringen fungerte.

## Bekreftede rotårsaker

1. Truth-pipelinen mottok ikke lærerens URL-er som `provided_sources`.
2. `str.replace(exact_text, "")` kunne slette bare et subjekt eller en frase.
3. Kilde-/verifikasjonsstatus hadde ikke egne tekniske feilstater.
4. Reparasjon var synkron uten timeout, kapittellås eller operation-ID.
5. Frontend hadde ingen request-timeout for denne flyten.

Rå modellrespons og Render-logg for hendelsen mangler. Derfor er opprinnelsen
til ordfeilen `sidebyrdig` ikke endelig klassifisert.

## Medvirkende årsaker

* Render-database og response-ledger er ikke tilgjengelig i repoet.
* Kompendiumrutene opprettet ikke varige Job-rader.
* Monorepo-testinnsamlingen hadde to VGS_KI-modulsti-/pakkeimportfeil; de er nå
  rettet uten å deaktivere tester.
* Produksjonsdeployen har ikke blitt verifisert mot audit-arbeidskopien.

## Implementerte tiltak

* `origin`/`fetch_status` på kildeobjekter.
* lærer-URL-ekstraksjon og gjennomgående `provided_sources`.
* `verification_failed`, `source_unavailable`, `not_evaluated`.
* 80 %-grense for grønt faktapass.
* setnings-/linjenivå-fjerning og deterministisk språkport.
* maskinstatusser for parse-, genererings-, språk- og kildefeil.
* reparasjonstimeout, kapittellås, operation-ID, 409/504/502.
* frontend-timeout og retry-orientert feilmelding.
* fem historiske regression-fixtures og kontrakttester.

## Verifiserte tiltak

I produksjonsnær Docker-runtime består:

* Hele monorepo-suiten: 396 tester bestått, 2 eksplisitte skips og 47 warnings;
* Skoleverksted-plattform: 87 tester;
* VGS_KI: 75 tester i separat suite;
* ScriptoriumFOV: 53 tester;
* MateMaTeX backend: 181 tester, 2 eksplisitte skips;
* frontend: 13 Vitest-tester og Next-produksjonsbuild;
* backend `compileall` og lokal språkport-smoke.

Reparasjonssuite dekker suksess, nettverksfeil, timeout og parallellforespørsel.
Dette er `LOKALT TESTET`/`TESTET I RIKTIG RUNTIME`, ikke produksjonsbevis.

## Ikke-verifiserte tiltak

* deploy på Render med audit-koden;
* Vercel → riktig Render-backend og CORS;
* ekte Gemini-respons og kildesøk;
* faktiske source fetch-statusser;
* identisk 3-kapitlers produksjonskjøring;
* PDF-/Word-artefakter fra ny kjøring;
* manuell faglig vurdering av ekstern lærer;
* backend-omstart, frontend-refresh og ekte modell-timeout i prod.

## Regresjonsvern

Fem fixture-inputs dekker industrialisering i Norge, imperialisme/kolonialisme,
første verdenskrig, russisk revolusjon og historisk kontrovers. Testene validerer
inputkontrakt, lærer-kildeproveniens og språkport. De er ikke modell-snapshots og
kan ikke erstatte modell-/produksjonskjøring.

## Observability-gap

Det mangler varig response-ledger for rå/normalisert modelltekst, request-ID-
kobling mellom frontend og reparasjon, per-URL hentelogger og eksplisitt
production config-fingerprint i denne verifikasjonen. Disse feltene må samles
uten hemmeligheter før neste gate.

## Rollback-plan

Produksjonen står fortsatt på kjent HEAD `cb486fc`; audit-endringene er nå
kommittert som `1c36544` og lokalt verifisert i et ferskt image, men ikke
deployet. Før publisering må readiness kontrolleres og identisk scenario kjøres.
Ved kritisk
produksjonsfeil rulles Render/Vercel tilbake til forrige kjente fungerende SHA,
og PDF-blokkeringen beholdes.

## Kan hendelsen lukkes?

**Nei.** Tiltakene er lokalt implementert og testet, men incidenten kan ikke
lukkes før ny deploy, komplett produksjonslogg, identisk E2E-kjøring og manuell
PDF-/Word-vurdering foreligger.
