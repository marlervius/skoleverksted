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

* Hele monorepo-suiten i seneste ferske image: 397 tester bestått, 2 eksplisitte skips og 47 warnings;
* Skoleverksted-plattform: 87 tester;
* VGS_KI: 75 tester i separat suite;
* ScriptoriumFOV: 53 tester;
* MateMaTeX backend: 181 tester, 2 eksplisitte skips;
* frontend: 13 Vitest-tester og Next-produksjonsbuild;
* backend `compileall` og lokal språkport-smoke.

Reparasjonssuite dekker suksess, nettverksfeil, timeout og parallellforespørsel.
Dette er `LOKALT TESTET`/`TESTET I RIKTIG RUNTIME`; produksjonssmoke og release-
readiness er også verifisert.

## Ikke-verifiserte tiltak

* Render-dashboardets deploy-ID og image-digest (dashboardet var uautentisert);
* rå Gemini-respons, truth-intermediate og varig response-ledger;
* vellykket ekte modellreparasjon og synlig frontend-fremdrift;
* PDF-/Word-artefakter fra en grønn kjøring;
* manuell faglig vurdering av ekstern lærer.

Readiness viste release `5b72a0541a20`, prompt `skoleverksted-v3`, modell
`gemini-3.5-flash`, config-fingerprint `dc08f612a352`, og
`scripts/production_smoke.py` bestod med både Vercel og Render.

Identisk scenario `084614b8247d413b8d1ba38cb6166fce` ble kjørt: 44 påstander,
32 verifiserte (73 %). Lærer-URL-ene ble propagert som
`origin=teacher/fetch_status=provided`. Kapittel 2-reparasjonen fikk HTTP 504
etter 120 sekunder, og retry fikk HTTP 409 med aktiv jobb-ID. Compile-porten
svarte HTTP 409 og blokkerte PDF/Word korrekt.

## Regresjonsvern

Fem fixture-inputs dekker industrialisering i Norge, imperialisme/kolonialisme,
første verdenskrig, russisk revolusjon og historisk kontrovers. Testene validerer
inputkontrakt, lærer-kildeproveniens og språkport. De er ikke modell-snapshots og
kan ikke erstatte modell-/produksjonskjøring.

## Observability-gap

Det mangler varig response-ledger for rå/normalisert modelltekst, request-ID-
kobling mellom frontend og reparasjon og per-URL hentelogger. Release-
config-fingerprint er verifisert fra readiness, men er ikke knyttet til en
varig deployledger.

## Rollback-plan

Produksjonen står på verifisert release `5b72a0541a20`. Forrige kjente release
er `9d9ce243620b`; Render-dashboardets formelle deployreferanse mangler.
Ved kritisk
produksjonsfeil rulles Render/Vercel tilbake til forrige kjente fungerende SHA,
og PDF-blokkeringen beholdes.

## Kan hendelsen lukkes?

**Nei.** Deploy og identisk E2E er nå verifisert, men 80 %-regelen feiler,
to kapitler krever revisjon, reparasjonssuksess er ikke observert, og PDF/Word
ble korrekt blokkert. Incidenten er fortsatt åpen.

## Siste closure-forsøk — 3. august 2026

Commit `2e66ec7a5467f3fc23523930ec9ac51181e7c070` lukker et gjenværende
fragmenteringsgap i `qualify`-banen og har regresjonstest. Kandidatimagets
digest er `sha256:db88579d5240abd7b1381ad0cfae035a7f8d73cbe01a11963ab92e685da47858`.
Det består med 398 backendtester, 2 eksplisitte skips og 47 warnings.

Git-push til deploydestinasjonen ble ikke gjennomført, og readiness viser
fortsatt `69b00d81e5a7`. Det finnes derfor ikke et verifisert deploy-ID,
produksjons-SHA for kandidaten eller en identisk E2E-kjøring etter siste
retting. Hendelsen kan fortsatt ikke lukkes.
