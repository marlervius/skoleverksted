# Repair-job incident

## Incident

Kompendiet `838938c88e994320a64281aafc871ec8` viste
`Sjekker og retter …` i minst omtrent 100 sekunder etter at læreren trykket
automatisk reparasjon. Ingen ferdigtekst eller feilmelding ble synlig.

## Rekonstruert årsak

`POST /api/platform/compendia/{compendium_id}/chapters/{chapter_id}/repair`
kalte `repair_compendium_chapter()` direkte i samme request. Reparasjonen gjør
minst et genereringskall og et kontrollkall mot Google, med mulig intern JSON-
reparasjon og grounding. Det var ingen eksplisitt tidsgrense, ingen
kapittellås, ingen operation-ID og ingen varig jobbstatus. Frontendens `run()`
holdt `localBusy="repair"` til fetch returnerte. En hengende HTTP-/modell-
forespørsel kunne derfor se ut som en aktiv jobb uten ende.

Det finnes ingen Render-requestlogg eller databaseledger i arbeidsflaten. Vi
kan derfor ikke avgjøre om akkurat produksjonskallet hang i Google, retry,
nettverk eller worker. Det vi kan fastslå er at kodebanen ikke hadde en
stoppbetingelse.

## Implementert kontroll

`Skoleverksted/backend/platform/router.py:57-126` har nå:

1. konfigurerbar `COMPENDIUM_REPAIR_TIMEOUT_SECONDS`, standard 120 s, maks 300 s;
2. idempotent `(compendium_id, chapter_id)`-lås med operation-ID;
3. daemon-worker med `Event` og eksplisitt resultat/exception;
4. `409` når samme kapittel allerede repareres;
5. `504` med jobb-ID når tidsgrensen overskrides;
6. `502` med jobb-ID ved uventet feil.

Frontendens request-wrapper (`MateMaTeX/frontend/src/lib/platform-api.ts:369`)
avbryter etter 150 s og viser at kapittelet ikke er endret og kan prøves på
nytt. Statusen blir aldri liggende som en sann, permanent “aktiv” jobb etter
at HTTP-kallet har feilet.

## Testdekning

`test_repair_timeout_is_explicit_and_does_not_return_a_fake_success` bruker en
kontrollert hengende worker og verifiserer `RepairTimeoutError` og operation-ID.
Frontendens Vitest og produksjonsbuild bestod. Backendtesten krever prosjektets
FastAPI/Pytest-runtime og er derfor ikke kjørt i denne lokale Python-runtime.

Den samme reparasjonssuiten er nå kjørt i produksjonsnær Docker-runtime og
dekker suksess, modell-/nettverksfeil, timeout og parallell forespørsel. Dette
er fortsatt ikke en ekte Render-/Gemini-kjøring.

## Resterende risiko

Etter server-timeout kan den isolerte daemon-tråden fortsatt bruke modell- eller
nettverksressurser inntil kallet returnerer. For flere backend-instanser bør
reparasjon flyttes til den eksisterende durable job queue-en med database- eller
Redis-ledger og avbrytbar worker. Det er bevisst ikke gjort i denne auditten,
fordi produksjonsfeilen som er dokumentert her var manglende timeout/status,
ikke et skaleringskrav.
