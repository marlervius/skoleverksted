# TeachingPackage — exec-plan

**Status:** planlagt. **Ingen kode implementert.**

**Opprettet:** 2026-08-08

**Produksjonsdom:** `REJECTED`
([PRODUCTION_VERIFICATION_REPORT.md](research/PRODUCTION_VERIFICATION_REPORT.md),
[PILOT_GO_NO_GO.md](research/PILOT_GO_NO_GO.md))

> ## Implementeringsgate: LUKKET
>
> M1 skal ikke implementeres før gaten åpnes eksplisitt. Dette dokumentet er
> beslutningsgrunnlag og akseptansekontrakt, ikke en arbeidsordre.
>
> **Gjeldende prioritet er production verification.** Den ene aktive
> P0-oppgaven er å lukke den eksisterende production verification gate —
> reparasjonsutførelse og durable jobber
> ([PILOT_GO_NO_GO.md:124](research/PILOT_GO_NO_GO.md:124)). TP-M1 og
> [TRUTH_COVERAGE_RESEARCH_PLAN.md](research/TRUTH_COVERAGE_RESEARCH_PLAN.md)
> står begge `BLOCKED` bak den.

Arkitekturgrunnlaget er [TEACHING_PACKAGE_ARCHITECTURE.md](research/TEACHING_PACKAGE_ARCHITECTURE.md).
Evidensmerking følger `PRODUCT_EXCELLENCE_EXECPLAN.md` punkt 1.

**Navnekollisjon:** `PRODUCT_EXCELLENCE_EXECPLAN.md` bruker allerede M0–M5 for
plattformens milepæler, der M1 var sikker sannhetsmutasjon. Milepælene her
heter derfor **TP-M1**, **TP-M2**, … `TP-M1` er det brukeren omtaler som «M1».

---

## 1. Beslutningene

Gjengitt kort; full begrunnelse i arkitekturdokumentet punkt 0.

1. **Faktapass.** `approved` krever grønt faktapass. Ingen generell
   lærer-bypass i MVP. Åpne problemer lagres under `needs_review`,
   `needs_revision` eller `reviewed_with_issues`.
2. **Canonical source of truth.** TeachingPackage/TeachingArtifact eier
   innhold og tilstand. `period.materials` beholdes som avledet projeksjon.
3. **Jobbtid.** 3–8 minutter er akseptabelt i kontrollert pilot gitt asynkron,
   durable, gjenopptakbar generering med per-artefakt retry.
   `MAX_CONCURRENT_JOBS` økes ikke før pilotdata finnes.
4. **DurableJobGate fra dag én.** Ingen ny langvarig synkron HTTP-flyt.
5. **TP-M1 er frosset** som definert i punkt 2. Ingen PowerPoint, ingen andre
   artefakttyper. Utvidelse krever ny beslutning.
6. **80 %-kravet beholdes.** Terskelen senkes ikke for å gjøre
   undervisningspakker mulige. Manglende godkjenning rapporteres ærlig.
7. **`truth_requirement ∈ {required, not_applicable}`** legges til i
   domenedesignet (arkitekturdokumentet punkt 1.4), men implementeres ikke nå.
   For TP-M1: `learning_sheet → required`.
8. **`TRUTH-COVERAGE-01`** er registrert som strategisk risiko (punkt 8.1) og
   løses ikke inne i TeachingPackage.

---

## 2. TP-M1 — mål og avgrensning

### 2.1 Produktutfall

Læreren skal, fra én periode i en Historie VG2-årsplan, kunne bestille **én
undervisningsartefakt** (`learning_sheet`), navigere bort, komme tilbake, se
sann status, redigere, verifisere, godkjenne — og se den godkjente artefakten
som en avledet rad i periodens materialliste.

### 2.2 Hvorfor bare én artefakt

TP-M1 skal bevise **skjelettet**, ikke bredden: durable jobb, canonical SOT,
projeksjon og `approved`-invariant. Alle fire feilklassene vi allerede har
dokumentert — synkron langvarig flyt, falsk grønn status, dobbeltlagret
tilstand og godkjenning uten evidens — kan oppstå med én artefakt. Flere
artefakttyper legger til promptarbeid, ikke arkitekturbevis. Multi-artefakt er
TP-M2.

### 2.2b Frosset omfang (B5)

TP-M1 er frosset til nøyaktig dette settet. Listen er normativ:

| # | Element |
|---|---|
| 1 | Én Historie VG2-periode |
| 2 | Én `required` artefakt |
| 3 | `artifact_type = learning_sheet` |
| 4 | `DurableJobGate` |
| 5 | Canonical TeachingPackage-state |
| 6 | Truth/quality-gate |
| 7 | Lærerreview |
| 8 | Projeksjon til `period.materials` **først etter godkjenning** |

Ingenting utover dette hører til TP-M1 — spesielt ikke PowerPoint/`presentation`
eller andre artefakttyper. `truth_requirement` (arkitekturdokumentet punkt 1.4)
er design, ikke leveranse: TP-M1 implementerer det ikke, og oppfører seg
identisk med B1.

### 2.3 Eksplisitt utenfor TP-M1

| Utenfor | Milepæl |
|---|---|
| Flere artefakttyper i én pakke, fan-out og delvis feil på tvers | TP-M2 |
| PowerPoint / `presentation`-artefakt | TP-M2, tidligst |
| Implementasjon av `truth_requirement` og policytabell for flere typer | TP-M2, styrt av B7 |
| Endring av truth threshold, weighted claims, criticality scoring | **aldri i dette sporet** — se `TRUTH-COVERAGE-01` og [TRUTH_COVERAGE_RESEARCH_PLAN.md](research/TRUTH_COVERAGE_RESEARCH_PLAN.md) |
| Claim-level teacher override med begrunnelse og audit trail | TP-M4 (`not now`) |
| Migrering av kompendium til `DurableJobGate` | `PRODUCT_EXCELLENCE_EXECPLAN.md` M2 |
| Auth / tenant / eierskap på pakker | `PRODUCT_EXCELLENCE_EXECPLAN.md` M3 |
| Konsolidering av `theme-packs` mot TeachingPackage | ubesluttet |
| Radbasert lagring i stedet for JSON-payload | `not now` |
| Økning av `MAX_CONCURRENT_JOBS` | krever pilotdata (B3) |

---

## 3. TP-M1 — berørte filer

### 3.1 Backend, nye filer

| Fil | Ansvar |
|---|---|
| `Skoleverksted/backend/platform/teaching_package.py` | domenelogikk: bygg plan fra periode, generer artefakt, `can_approve_artifact()`, `can_approve_package()` |
| `Skoleverksted/backend/platform/teaching_package_jobs.py` | durable orkestrering mot `DurableJobGate`, CAS-skriving, gjenoppretting, instrumentering |
| `Skoleverksted/backend/platform/teaching_package_projection.py` | `project_package_materials()` — eneste skrivevei til pakkeeide materialrader |

### 3.2 Backend, endrede filer

| Fil | Endring |
|---|---|
| [models.py](Skoleverksted/backend/platform/models.py) | `TeachingArtifactStatus`, `TeachingPackageStatus`, `TeachingPackage`, `TeachingPackagePlan`, `ArtifactSpec`, `TeachingArtifact`, `TeachingArtifactUpdate`, `TeachingPackageCreate`; utvid `YearPlanMaterial` med `source_kind`, `teaching_package_id`, `artifact_id`, `artifact_type`, `artifact_version`, `artifact_status`, `projected_at`; utvid `MaterialKind` med `teacher_guide`; utvid `TruthPassport` med `content_revision` |
| [store.py](Skoleverksted/backend/platform/store.py) | tabell `teaching_packages` i `_init_schema` ([store.py:124](Skoleverksted/backend/platform/store.py:124)); `create/get/list/save_teaching_package`; `cas_update_artifact()`; `replace_projected_materials()`; utvid `recover_incomplete_jobs()`-oppfølging med domeneoversettelse |
| [router.py](Skoleverksted/backend/platform/router.py) | ni endepunkter, punkt 4; `PATCH .../materials/{id}` avviser projiserte rader (unntak `approved → used`) |
| [queue.py](Skoleverksted/backend/platform/queue.py) | ingen strukturendring; legg til hjelpefunksjon for å skrive allowlistede målinger i `Job.result_summary` |

### 3.3 Backend, tester

| Fil | Dekker |
|---|---|
| `Skoleverksted/backend/tests/test_teaching_package.py` | `approved`-invariant A1–A7, pakkeinvariant P1–P5, statusoverganger |
| `Skoleverksted/backend/tests/test_teaching_package_jobs.py` | varig registrering før arbeid, idempotent retry, per-artefakt isolasjon, restart uten falsk suksess, CAS/`superseded`, cancel, instrumenteringsfelt |
| `Skoleverksted/backend/tests/test_teaching_package_projection.py` | idempotens, ingen duplikatrader, ingen innholdsfelt, tilbaketrekking, skrivebeskyttelse |

### 3.4 Frontend

| Fil | Endring |
|---|---|
| [platform-api.ts](MateMaTeX/frontend/src/lib/platform-api.ts) | typer + kall for de ni endepunktene; gjenbruk `requestJson` og eksisterende timeout-wrapper |
| `MateMaTeX/frontend/src/app/teaching-packages/[id]/page.tsx` | **ny** pakkeside: bestilling, progresjon, review, godkjenning |
| [app/year-plans/[id]/page.tsx](MateMaTeX/frontend/src/app/year-plans/[id]/page.tsx) | «Lag undervisningspakke» per periode; tre adskilte materialgrupper (manuelle, projiserte, ikke-godkjente pakker); projiserte rader skrivebeskyttet |
| `MateMaTeX/frontend/src/lib/platform-api.test.ts` | utvides med pakkekall og feilkontrakter |
| `MateMaTeX/frontend/src/app/teaching-packages/[id]/page.test.tsx` | **ny**: gjenopptakelse etter reload, ingen falsk «ferdig», deaktivert godkjenn med årsak |

Designkrav: den hvite stone/accent-standarden med lyst tema som default, som i
resten av modulene.

---

## 4. TP-M1 — endepunkter

Alle under `/api/platform`.

| # | Metode og sti | Svar | Kontrakt |
|---|---|---|---|
| 1 | `POST /teaching-packages` | `201` pakke | Lagrer `draft` fra `{year_plan_id, period_id, artifact_specs}`. Fryser `period_snapshot`. Ingen modellkall. `409` hvis plan/periode ikke finnes. |
| 2 | `GET /teaching-packages?year_plan_id=&period_id=&limit=` | `200` liste | |
| 3 | `GET /teaching-packages/{package_id}` | `200` pakke | Inkluderer per-artefakt status, `content_revision`, `artifact_job_id`. Grunnlaget for gjenopptakelse. |
| 4 | `POST /teaching-packages/{package_id}/generate` | **`202`** `{package_job_id, artifact_job_ids[]}` | Registrer alle jobber varig **før** arbeid; returner umiddelbart. `409` hvis en pakkejobb alt er aktiv. |
| 5 | `POST /teaching-packages/{package_id}/artifacts/{artifact_id}/regenerate` | **`202`** `{job_id}` | Deterministisk `job_id` → idempotent. `409` med aktiv `job_id` hvis den kjører. |
| 6 | `PATCH /teaching-packages/{package_id}/artifacts/{artifact_id}` | `200` pakke | Lærerredigering. Bumper `content_revision`, nuller `truth_passport`, setter `generation_token = None`. `409` ved forsøk på å sette `approved` direkte. |
| 7 | `POST /teaching-packages/{package_id}/artifacts/{artifact_id}/verify` | **`202`** `{job_id}` | Faktapass som durable jobb, aldri synkront. |
| 8 | `POST /teaching-packages/{package_id}/artifacts/{artifact_id}/approve` | `200` pakke / `409` | Håndhever A1–A7 med én presis årsak per brudd. |
| 9 | `POST /teaching-packages/{package_id}/approve` | `200` pakke / `409` | Håndhever P1–P5 og kaller `project_package_materials()` i samme steg. |

Støtteendepunkter som **finnes** og gjenbrukes uendret:
`GET /jobs/{job_id}` ([router.py:572](Skoleverksted/backend/platform/router.py:572)),
`GET /queue` ([router.py:580](Skoleverksted/backend/platform/router.py:580)),
`POST /jobs/{job_id}/cancel` ([router.py:588](Skoleverksted/backend/platform/router.py:588)).

Rendring i TP-M1: `POST /{package_id}/approve` produserer PDF for
`required`-artefakten via samme rendrerlag som kompendiet, og filen refereres
fra artefakten. Et eget `render`-endepunkt kommer i TP-M2 når flere
artefakttyper skal bygges uavhengig.

**Ingen** av de ni endepunktene gjør modell- eller rendringsarbeid i
request-tråden bortsett fra #9, som er lærerinitiert, kort og
transaksjonsavhengig. Hvis rendringen viser seg å nærme seg timeout-grensene,
flyttes den til `rnd:{package_id}`-jobben før TP-M1 lukkes.

---

## 5. TP-M1 — UI-steg

| Steg | Skjerm | Handling og synlig tilstand |
|---|---|---|
| 1 | Årsplan → periodekort | Knapp «Lag undervisningspakke». Kaller #1, navigerer til `/teaching-packages/{id}`. |
| 2 | Pakkeside, bestilling | Skjema forhåndsfylt fra `period_snapshot`: tema, læringsmål, kompetansemål, timetall, kildefelt. Tekst: «Planen bygger på perioden slik den var <tidspunkt>.» Knapp «Start generering» → #4. |
| 3 | Pakkeside, progresjon | Etter `202`: per-artefakt rad med status, køposisjon, forsøk, medgått tid. Eksplisitt tekst: «Du kan lukke siden. Genereringen fortsetter.» Estimat oppgis som «3–8 minutter», og som **UKJENT** til `queue_wait_ms`/`generation_ms` finnes. |
| 4 | Reload midt i jobben | Siden leser `package_id` fra URL, kaller #3 + `GET /jobs/{job_id}` og gjenopptar polling. Ingen tilstand kun i minnet. |
| 5 | Pakkeside, review | Innhold, kilder med `origin`/`fetch_status`, faktapass med claim-liste. Rediger-felt (#6). Knapp «Sjekk og rett» (#7). Ved lærerendring vises «Faktapasset må kjøres på nytt». |
| 6 | Godkjenning per artefakt | «Godkjenn» er **deaktivert med synlig årsak** når A1–A7 ikke holder — f.eks. «Faktapasset er ikke grønt (32 av 44 påstander verifisert).» Alternativknapper: «Trenger revisjon» og «Gjennomgått med åpne problemer». |
| 7 | Godkjenning av pakke | «Godkjenn pakke og legg i årsplanen» deaktivert med årsak til P1–P5 holder. Ved suksess: bekreftelse med lenke til periodens materialliste. |
| 8 | Tilbake i årsplanen | Tre adskilte grupper: manuelle materialer, projiserte godkjente artefakter (badge + lenke til pakken), og «Pakker under arbeid» som **ikke** ser ut som læremidler. |
| 9 | Feil på artefakt | Feilstatus med enum-forklaring på norsk og knapp «Prøv denne på nytt» (#5), uten å berøre resten av pakken. |

Forbudte UI-tilstander, i tråd med `PRODUCT_EXCELLENCE_EXECPLAN.md` punkt 5:

- spinner uten varig jobb bak seg;
- «Ferdig» uten at artefaktstatus er terminal i backend;
- aktiv godkjenn-knapp uten grønt faktapass;
- ikke-godkjent pakke framstilt som læremiddel i årsplanen;
- estimert tid framstilt som målt tid.

---

## 6. TP-M1 — akseptansekriterier

Hvert kriterium er en test. Ingen av dem er oppfylt i dag.

### Durabilitet

| # | Kriterium |
|---|---|
| D1 | `POST /{id}/generate` returnerer `202` og alle jobbrader finnes i `jobs`-tabellen **før** noe modellarbeid starter. Verifiseres med en generator som blokkerer. |
| D2 | Request-tråden gjør null modellkall. Verifiseres ved at responstiden er uavhengig av en kunstig 60-sekunders generator. |
| D3 | Prosess-restart mens en artefakt er `generating` gir retryable feilstatus — **aldri** `generated` og **aldri** `approved`. |
| D4 | Retry på samme `job_id` øker `attempt` og lager **ikke** en parallell jobb. `enqueue` kalt to ganger gir én rad. |
| D5 | `POST .../regenerate` på en kjørende artefakt gir `409` med den aktive `job_id`-en. |
| D6 | Én feilende artefakt hindrer ikke at de andre fullfører og blir synlige. (Realiseres i TP-M1 med to artefakter i testen, selv om produktet leverer én.) |
| D7 | Lærerredigering under kjørende jobb: jobbens skriving forkastes, artefakten beholder lærerens tekst, jobben ender `superseded`. |
| D8 | Frontend gjenopptar status etter full reload uten tap av jobbidentitet. |
| D9 | `POST /jobs/{id}/cancel` gir terminal `cancelled` og ingen senere skriving fra den jobben. |

### Sannhet og godkjenning

| # | Kriterium |
|---|---|
| S1 | `approve` avvises med `409` når `truth_passport` mangler. |
| S2 | `approve` avvises når `truth_passport.status != "verified"`. |
| S3 | `approve` avvises når passet gjelder en tidligere `content_revision` (A5). |
| S4 | `approve` avvises når kildesjekken gir merknader (A4). |
| S5 | `approve` avvises under aktiv jobb (A6). |
| S6 | Godkjent artefakt har `approved_by` og `approved_at` satt (A7). |
| S7 | Det finnes **ingen** kodevei som setter `approved` uten å gå gjennom invariantfunksjonen. Verifiseres med en test som søker etter direkte statustilordning. |
| S8 | `reviewed_with_issues` kan lagres med åpne problemer, og artefakten er da ikke godkjent og ikke projisert. |
| S9 | Pakke-`approve` avvises med `409` ved brudd på P1–P5, med presis årsak. |

### Canonical source of truth og projeksjon

| # | Kriterium |
|---|---|
| C1 | `YearPlanMaterial` inneholder ikke `content_markdown`, `truth_passport`, `quality_passport`, `sources` eller kildesnapshot. Håndheves av en feltnavntest. |
| C2 | Projeksjon av samme artefakt to ganger gir én materialrad, ikke to. |
| C3 | Ny godkjent versjon oppdaterer samme rad og bumper `artifact_version`. |
| C4 | Ikke-godkjente artefakter projiseres aldri. |
| C5 | Tilbaketrekking setter raden til `needs_revision` og oppdaterer `artifact_status`; raden slettes ikke. |
| C6 | `PATCH .../materials/{id}` gir `409` for projiserte rader, unntatt `approved → used`. |
| C7 | `project_package_materials()` er den eneste funksjonen som skriver pakkeeide materialrader. Verifiseres med kallgraf-/søketest. |

### Instrumentering

| # | Kriterium |
|---|---|
| I1 | `queue_wait_ms`, `generation_ms`, `retry_count`, `failure_reason` finnes i `Job.result_summary` for hver artefaktjobb. |
| I2 | `package_total_ms` finnes på pakkejobben. |
| I3 | `failure_reason` er en enum-kode fra den definerte listen, aldri rå modell- eller feiltekst. |
| I4 | Ingen kilde-, elev- eller lærertekst havner i `result_summary`. Verifiseres med negativ test. |
| I5 | `MAX_CONCURRENT_JOBS` er fortsatt `1`. |
| I6 | P50/P95 rapporteres som **UKJENT** til antallet observasjoner er dokumentert. |

### Suite og bygg

| # | Kriterium |
|---|---|
| B1 | Full backend-suite grønn i det dokumenterte Docker-imaget. Baseline å slå: **398 bestått, 2 hoppet over** (`PRODUCT_EXCELLENCE_EXECPLAN.md` punkt 10). |
| B2 | Frontend: `npm test -- --run`, `npx tsc --noEmit` og produksjonsbygg grønne. Baseline 13 tester. |
| B3 | `npm run lint` er fortsatt **ikke operativ** (manglende ESLint-konfigurasjon) og rapporteres som gjeld, ikke som bestått. |
| B4 | Diffen inneholder bare filene i punkt 3, og TP-M1 har egen commit. |

**TP-M1 er ikke fullført før alle D-, S-, C-, I- og B-kriterier er grønne.**
Delvis oppfyllelse rapporteres som delvis, aldri som fullført.

---

## 7. Milepælrekkefølge

| Milepæl | Utfall | Port | Status |
|---|---|---|---|
| TP-M0 | Beslutninger og arkitektur nedfelt | dette dokumentet + arkitekturdokumentet | **Fullført** 2026-08-08 |
| **TP-M1** | Én durable, canonical, projisert, evidensgatet artefakt | D1–D9, S1–S9, C1–C7, I1–I6, B1–B4 | **Ikke startet — gate lukket** |
| TP-M2 | Full pakke: flere artefakttyper, fan-out, delvis feil, uavhengig retry og rendring | TP-M1-kriteriene per artefakt + fan-out-tester | Ikke startet |
| TP-M3 | Pilotmålinger: observerte P50/P95 for kø og generering | dokumentert observasjonsantall | Ikke startet |
| TP-M4 | Vurdering av claim-level teacher override | krever revisjonsvisning + audit trail + eksplisitt beslutning | `not now` |

Avhengigheter utenfor dette sporet: `PRODUCT_EXCELLENCE_EXECPLAN.md` M3
(pilotisolasjon) må være løst eller piloten teknisk isolert til én bruker uten
sensitive data før en pakke med reelt innhold brukes i produksjon. TP-M1 er
teknisk uavhengig, men *pilotbruk* av TP-M1 er det ikke.

---

## 8. Risiko og rollback for TP-M1

| Risiko | Håndtering |
|---|---|
| Nye tabeller og modellfelt kan bryte eksisterende rader | alle nye felt nullbare eller med default; `CREATE TABLE IF NOT EXISTS`; ingen migrering av eksisterende `year_plans`-payload |
| `TruthPassport.content_revision` er et nytt felt på en eksisterende modell | default `0`; eksisterende kompendiumpass forblir gyldige; A5 gjelder bare TeachingArtifact |
| Ny UI-flate øker produktbredden i et produkt som alt er for bredt | TP-M1 legger til én side og én knapp; ingen ny modul i hovednavigasjonen før pakken er bevist |
| Streng `approved`-invariant kan gi at ingen pakke blir godkjent i piloten | ønsket oppførsel; men det gjør faktapassets dekningsgrad til den reelle flaskehalsen — se `TRUTH-COVERAGE-01` i punkt 8.1 |
| Rollback | TP-M1 er additiv. Rollback er å redeploye forrige release; `teaching_packages`-tabellen blir liggende ubrukt. Ingen eksisterende produksjonsdata muteres. |

### 8.1 TRUTH-COVERAGE-01 — strategisk risiko

**ID:** `TRUTH-COVERAGE-01`
**Status:** registrert. Ikke en TP-M1-oppgave. Ikke aktivert.

Observed production evidence
([PRODUCTION_VERIFICATION_REPORT.md:118](research/PRODUCTION_VERIFICATION_REPORT.md:118)):

```
44 claims
32 verified
73 %
```

Current approval threshold:

```
80 %
```

Consequence: **A technically correct TeachingPackage implementation may remain
unusable for approval if the truth pipeline cannot reliably reach the quality
gate.**

Håndtering:

- Terskelen senkes **ikke** (B6). 73 % behandles som en dokumentert
  produktbegrensning, ikke som et argument for å svekke kvalitetsgaten.
- Risikoen løses **ikke** inne i TeachingPackage.
- Undersøkelsen ligger i
  [TRUTH_COVERAGE_RESEARCH_PLAN.md](research/TRUTH_COVERAGE_RESEARCH_PLAN.md),
  som er `BLOCKED` og ikke aktivert.
- Konsekvens for akseptanse: hvis TP-M1 er teknisk grønn på D-, S-, C-, I- og
  B-kriteriene, men ingen pakke blir `approved` fordi faktapasset ikke er
  grønt, er TP-M1 **fullført** og produktverdien **begrenset**. De to skal
  rapporteres hver for seg, aldri slås sammen til «virker ikke» eller
  «virker».

Full utdyping, inkludert de to presiseringene om aggregat versus per artefakt
og om at 80 % er nødvendig men ikke tilstrekkelig, står i arkitekturdokumentet
punkt 6.1.

---

## 9. Beslutningslogg

| Dato | Beslutning | Kilde |
|---|---|---|
| 2026-08-08 | B1 faktapass, B2 canonical SOT, B3 jobbtid, B4 DurableJobGate fra dag én | brukerbeslutning før TP-M1 |
| 2026-08-08 | Plattformrutenes manglende bruk av `DurableJobGate` + repair-hendelsen behandles som eksplisitt arkitekturevidens for B4 | brukerbeslutning; `KODEBEVIST` + `DOKUMENTERT` |
| 2026-08-08 | TP-M1 begrenses til én artefakttype for å bevise skjelettet, ikke bredden | denne planen punkt 2.2 |
| 2026-08-08 | Claim-level teacher override er `not now` | B1 |
| 2026-08-08 | B5: TP-M1 frosset til de åtte elementene i punkt 2.2b. Ingen PowerPoint eller andre artefakter. | brukerbeslutning |
| 2026-08-08 | B6: 80 %-terskelen beholdes. 73 % er en dokumentert produktbegrensning, ikke grunn til å senke gaten. | brukerbeslutning |
| 2026-08-08 | B7: `truth_requirement ∈ {required, not_applicable}` nedfelt i design, ikke implementert. Deterministisk fra `artifact_type`/policy. Ingen unknown-as-pass, ingen teacher bypass, ingen silent fallback, ingen modellklassifisering. | brukerbeslutning |
| 2026-08-08 | B8: `TRUTH-COVERAGE-01` registrert som strategisk risiko; løses utenfor TeachingPackage | brukerbeslutning |
| 2026-08-08 | `TRUTH_COVERAGE_RESEARCH_PLAN.md` opprettet som `BLOCKED` forskningsplan, ikke arbeidsordre | brukerbeslutning |
| 2026-08-08 | Gjeldende prioritet forblir production verification. TP-M1 og truth-coverage-research står `BLOCKED`. | brukerbeslutning |
