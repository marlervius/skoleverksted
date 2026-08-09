# Durable compendium repair — execution plan

Milepæl: **P0 — DURABLE COMPENDIUM REPAIR EXECUTION**.
Avgrenset til kapittelreparasjon. Ingen andre flows migreres.

## Fase 0 — forensisk baseline (før kodeendring)

### Dagens flyt, ende til ende

| Ledd | Fil | Adferd |
| --- | --- | --- |
| Knapp «Sjekk og rett automatisk» | `MateMaTeX/frontend/src/app/compendia/[id]/page.tsx:220` | `run("repair", …)` setter `localBusy="repair"` og venter på `Promise` |
| Batchvariant | samme fil:475 | Seriell løkke over kapitler, samme blokkerende kall |
| API-klient | `MateMaTeX/frontend/src/lib/platform-api.ts:519` | `POST …/repair`, forventer hele `Compendium` som svar |
| HTTP-timeout | samme fil:369 | `AbortController`, 150 s, kaster `PlatformApiError(408)` |
| Endepunkt | `Skoleverksted/backend/platform/router.py:218` | Synkront `def`, `response_model=Compendium` |
| Tidsgrense | samme fil:57 og 103 | `COMPENDIUM_REPAIR_TIMEOUT_SECONDS`, standard 120 s, `Event.wait()` |
| Kapittellås | samme fil:55-56, 82-99 | `dict` i prosessminne, `(compendium_id, chapter_id) -> operation_id` |
| Operation-ID | samme fil:228 | `x-request-id` eller tilfeldig hex, kun i minne og i logg |
| Job-ID | — | **finnes ikke** for repair |
| Arbeid | `platform/compendium.py:980` | To groundede Gemini-kall + `_audit_chapter_material` + `inspect_markdown` |
| Write-back | `router.py:263` | `store.replace_compendium_chapter()` uten versjonssjekk |
| Feilhåndtering | `router.py:235-262` | 404 / 409 / 504 / 502, ingen varig spor |
| Frontend retry | — | Manuell; ingen jobbstatus å gå tilbake til |

### Hvorfor HTTP-requesten fortsatt eier modellarbeidet

`_run_repair_with_timeout()` starter en daemon-tråd, men **request-tråden blokkerer
på `done.wait(_REPAIR_TIMEOUT_SECONDS)`**. Responsen kan ikke sendes før arbeidet
er ferdig eller tidsgrensen er nådd. Konsekvensene som ble observert i produksjon:

1. Render/ingress bryter forbindelsen → klienten ser **504** selv om arbeidet
   fortsetter i daemon-tråden.
2. Daemon-tråden fjerner låsen først i `finally` → en retry innen samme
   modellkall får **409** med en operation-ID som ikke kan slås opp noe sted.
3. Ett HTTP 200-forsøk skrev `source_grounding_failed` fordi `repair_compendium_chapter()`
   returnerer et *degradert kapittel* i stedet for å kaste. Endepunktet kan derfor
   ikke skille «modellen feilet» fra «reparasjonen lyktes».
4. Ingen ledger → hendelsesforløpet kunne ikke rekonstrueres i etterkant.
5. Prosess-restart mister både låsen og all kunnskap om at jobben fantes.

Rotårsak i én setning: **repair var en synkron forespørsel med minnebasert lås,
uten jobbidentitet, uten varig tilstand og uten evidens.**

### DurableJobGate i dag

`platform/queue.py` har kapasitetsport (`BoundedSemaphore`), Redis-lease,
`enqueue()`/`claim()`/`finish()`/`fail()`/`cancel()` og `store.recover_incomplete_jobs()`.
Den brukes av `POST /jobs/{id}/cancel` (`router.py:588`). Ingen plattformflyt
kaller `enqueue()`/`claim()` — porten er reell kode uten reell trafikk.
`tests/test_queue.py` dekker kun at Redis-lease er trygg uten Redis.

### Eksisterende repair-tester (før denne milepælen)

`tests/test_compendium.py`: `test_repair_timeout_is_explicit_and_does_not_return_a_fake_success`,
`test_repair_lock_rejects_parallel_requests`,
`test_automatic_repair_revises_checks_and_keeps_previous_version`,
`test_automatic_repair_can_upgrade_weak_sources_without_existing_notes`,
`test_automatic_repair_keeps_unresolved_claims_for_teacher_control`,
`test_automatic_repair_failure_never_overwrites_the_chapter`.
Alle tester funksjonen eller den minnebaserte låsen — ingen tester varighet.

## Domeneinvarianter

Repair-jobbstatus er **egen** og adskilt fra `CompendiumChapterStatus`:

```
RepairJobStatus = queued | running | succeeded
                | failed_retryable | failed_terminal
                | cancelled | superseded
```

`succeeded` krever **alle** punktene:

1. modellen returnerte et svar,
2. svaret kunne parses til gyldig JSON,
3. kilde-/sannhetskontroll ble kjørt etter gjeldende policy,
4. CAS-token var fortsatt gyldig ved write-back,
5. `replace_compendium_chapter()` fullførte,
6. ledgeren ble oppdatert konsistent.

Kapittelstatus (`generated`, `source_grounding_failed`, …) er et **innholds-**
resultat og styrer ikke jobbstatus. En jobb som skriver
`source_grounding_failed` er `succeeded` som infrastruktur og rapporteres som
et truth-resultat i UI.

## Tilstandsmaskin

```
                    POST …/repair
                          │  (validering: 404 / 409 før registrering)
                          ▼
                     ┌────────┐
        cancel ──────│ queued │──────── restart / recover ──┐
           │         └────┬───┘                             │
           │              │ claim_repair_job (CAS på status)│
           ▼              ▼                                 ▼
    ┌───────────┐    ┌─────────┐                  ┌──────────────────┐
    │ cancelled │    │ running │─── restart ─────▶│ failed_retryable │
    └───────────┘    └────┬────┘   stale lease    └──────────────────┘
                          │                                 ▲
       ┌──────────────────┼───────────────────┬─────────────┘
       │                  │                   │
  token endret       cancel_requested     provider/parse/
       │                  │                write-feil
       ▼                  ▼                   │
┌────────────┐      ┌───────────┐             │
│ superseded │      │ cancelled │             │
└────────────┘      └───────────┘             │
       ▲                                      │
       │            ┌───────────┐             │
       └── ingen ───│ succeeded │             ▼
           write    └───────────┘   ┌──────────────────┐
                                    │ failed_terminal  │  (validering,
                                    └──────────────────┘   ikke-retrybar)
```

Terminale tilstander: `succeeded`, `failed_terminal`, `cancelled`, `superseded`.
`failed_retryable` er terminal for *jobben*, men låsen er sluppet og læreren kan
starte en ny jobb med ny `operation_id`.

### Overganger og hvem som utfører dem

| Fra | Til | Utløser | Aktør |
| --- | --- | --- | --- |
| — | `queued` | `POST …/repair` etter validering | request-tråd |
| `queued` | `running` | `claim_repair_job()` (atomisk `UPDATE … WHERE status='queued'`) | worker |
| `queued`/`running` | `cancelled` | `POST /jobs/{id}/cancel` | request-tråd |
| `running` | `succeeded` | CAS-write fullført | worker |
| `running` | `superseded` | CAS-token endret | worker |
| `running` | `failed_retryable` | provider-/parse-/write-feil, stale lease, restart | worker / recovery |
| `queued`/`running` | `failed_retryable` | `recover_incomplete_repair_jobs()` ved oppstart | oppstart |
| `queued` | `failed_terminal` | valideringsfeil oppdaget i worker | worker |

## Restart-semantikk

| Tidspunkt for restart | Resultat | Begrunnelse |
| --- | --- | --- |
| A. før modellkallet (`queued`) | `failed_retryable`, lås sluppet | ingen sideeffekt |
| B. under modellkallet (`running`) | `failed_retryable`, lås sluppet | ekstern kjøring kan ikke gjenopptas nøyaktig; vi later ikke som |
| C. etter modellrespons, før write | `failed_retryable` | resultatet er tapt, kapitlet uendret |
| D. etter write, før ledger-completion | `failed_retryable`, ledger viser `write_back`-hendelsen | kapitlet er allerede oppdatert; ny jobb blir CAS-`superseded` eller reparerer på nytt — aldri falsk grønn |

Ingen sti kan gi `succeeded` uten at write-back faktisk fullførte.

## Lås-livssyklus

Låsen **er** raden i `repair_jobs`: unikt aktivt `(compendium_id, chapter_id)`.

- tas: atomisk `INSERT` i samme transaksjon som sjekker at ingen aktiv jobb finnes,
- eies av: `job_id` + `operation_id`,
- lease: `lease_expires_at`, fornyes med heartbeat mens jobben kjører,
- slippes: ved enhver terminal status,
- restart: `recover_incomplete_repair_jobs()` slipper alle,
- cancel: slipper umiddelbart,
- worker crash: lease utløper → `expire_stale_repair_leases()` slipper,
- klient-timeout: **ingen effekt** på låsen.

## Response ledger

Tabell `repair_events(id, job_id, operation_id, stage, created_at, payload)`.
Stadier: `registered`, `claimed`, `model_request`, `model_response`,
`model_failed`, `truth_audit`, `write_back`, `superseded`, `cancelled`,
`failed`, `succeeded`, `recovered`.

Lagres: modellnavn, prompt-versjon, promptlengde og prompt-hash,
start/slutt/varighet, om leverandøren returnerte, om svaret kunne parses,
truth-status/coverage/claims, antall foreslåtte endringer, innholds-hash før og
etter, kapittelstatus, feiltype og forkortet feilmelding.

Lagres **ikke**: promptens fritekst, rå modellrespons, API-nøkler, elev- eller
personopplysninger. En nøkkelfilter fjerner felter som ligner hemmeligheter.

## API-kontrakt

```
POST /api/platform/compendia/{cid}/chapters/{chid}/repair  -> 202 RepairJobAccepted
GET  /api/platform/compendia/{cid}/chapters/{chid}/repair  -> 200 RepairJob (nyeste)
GET  /api/platform/repair-jobs/{job_id}                    -> 200 RepairJob
GET  /api/platform/repair-jobs/{job_id}/events             -> 200 [RepairLedgerEntry]
POST /api/platform/jobs/{job_id}/cancel                    -> 200 Job   (gjenbrukt)
GET  /api/platform/jobs/{job_id}                           -> 200 Job   (gjenbrukt speil)
GET  /api/platform/queue                                   -> 200 [Job] (gjenbrukt)
```

`RepairJobAccepted`: `job_id`, `operation_id`, `compendium_id`, `chapter_id`,
`status`, `status_url`.

Hver repair-jobb speiles i den eksisterende `jobs`-ledgeren med samme `job_id`,
`module="platform"`, `kind="compendium_repair"`, slik at `/jobs`, `/queue` og
`/jobs/{id}/cancel` fungerer uendret. `JobStatus` utvides med `superseded`.

## Idempotens

- `operation_id` = `x-request-id` fra klienten, ellers generert. Én lærerinitiert
  reparasjon = én `operation_id`.
- Retry med **samme** `operation_id` mot samme kapittel returnerer `202` med den
  **eksisterende** jobben (idempotent), ikke en ny jobb.
- Retry med **ny** `operation_id` mot et kapittel med aktiv jobb gir `409` med
  aktiv `job_id`.
- Ny reparasjon etter terminal status gir ny `job_id` og ny `operation_id`.

## Stale-write-vern (CAS)

`chapter_content_token()` = SHA-256 av kapittelets `content_markdown` +
`revision_count`. Snapshot tas ved registrering. Før write-back sammenlignes
tokenet med lagret kapittel. Ved avvik: **ingen skriving**, status `superseded`,
ledger-hendelse med begge tokens.

## Frontend

`repairCompendiumChapter()` returnerer `RepairJobAccepted`. Kapittelkortet
holder `job_id`, poller `GET /repair-jobs/{id}` hvert 3. sekund, viser
`queued`/`running` med forklarende tekst, henter kapitlet på nytt ved
`succeeded`/`superseded`, viser konkret retry ved `failed_retryable`, og
gjenfinner aktiv jobb etter reload via `GET …/chapters/{chid}/repair`.
Ingen automatisk ny repair ved timeout.

## Non-goals

Durable generation/compile, årsplan, temapakker, TeachingPackage, PowerPoint,
Celery/Kafka/RabbitMQ, ny worker-infrastruktur, økt concurrency,
truth-policyendring.
