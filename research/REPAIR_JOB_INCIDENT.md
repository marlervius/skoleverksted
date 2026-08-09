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

## Produksjonsverifikasjon etter retting

Mot release `5b72a0541a20` ble repair testet på kompendium
`084614b8247d413b8d1ba38cb6166fce`, kapittel
`16eb2f0eeac544f08502ad93d2e6211e`. Kallet med operation-ID
`audit-identical-20260803b-repair-ch2` returnerte HTTP 504 etter den eksplisitte
120-sekundersgrensen. En umiddelbar retry returnerte HTTP 409 med teksten om at
samme kapittel allerede repareres og viste den aktive jobb-ID-en. Dette beviser
terminal timeout og idempotent kapittellås i backend. En vellykket ekte
modellreparasjon, frontendens fremdriftsvisning og etterfølgende
`revision_summary` ble ikke observert.

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

---

## Lukking — durable repair execution (8. august 2026)

Denne hendelsen er nå lukket på kodenivå. Rotårsaken var ikke bare manglende
timeout: **HTTP-requesten eide modellarbeidet**. `_run_repair_with_timeout()`
startet en daemon-tråd, men request-tråden blokkerte på `done.wait(120)`, så
ingen respons kunne sendes før arbeidet var ferdig. Låsen lå i prosessminne,
`operation_id` fantes bare i loggen, og det fantes ingen jobb-ID, ingen varig
status og ingen ledger. Derfor endte to forsøk i HTTP 504, ett forsøk svarte
HTTP 200 mens reparasjonen internt feilet, og en retry fikk HTTP 409 med en
operation-ID som ikke kunne slås opp noe sted.

Reparasjonen er flyttet til en varig jobb i
`Skoleverksted/backend/platform/repair.py`, med ledger og CAS i `store.py` og en
202-kontrakt i `router.py`. Den fullstendige tilstandsmaskinen, lås-livssyklusen
og restart-semantikken står i `research/REPAIR_DURABILITY_EXECPLAN.md`.

Det som er endret siden avsnittene over:

1. `COMPENDIUM_REPAIR_TIMEOUT_SECONDS` er borte. En klient-timeout bestemmer
   ikke lenger noe; `COMPENDIUM_REPAIR_LEASE_SECONDS` (standard 900) styrer hvor
   lenge et kapittel kan være reservert.
2. Kapittellåsen er ikke lenger en `dict` i prosessminne, men raden i
   `repair_jobs`. Den overlever restart og slippes av `recover_incomplete_repair_jobs()`
   og `expire_stale_repair_leases()`.
3. En jobb kan ikke lenger rapporteres som `succeeded` uten fullført write-back.
   Kapittel 1-tilfellet — HTTP 200 med intern feil — gir nå `failed_retryable`
   med kapittelstatusen som eget innholdsresultat.
4. Den gjenstående risikoen i avsnittet over («daemon-tråden kan fortsatt bruke
   ressurser etter server-timeout») gjelder fortsatt for selve modellkallet,
   men den kan ikke lenger skade kapitlet: cancel og CAS blokkerer write-back
   fra en sen worker.

Testdekning: `Skoleverksted/backend/tests/test_repair_durability.py`, 27 tester,
inkludert en HTTP-test mot den reelle ASGI-ruteren som beviser 202 uten å vente
på modellen, 409 ved parallell reparasjon, idempotent replay, gjenfinning etter
reload og `succeeded` først etter write-back. Full backend-suite: 120 bestått.

Ikke verifisert: en ekte Render-/Gemini-kjøring mot den nye kontrakten.
