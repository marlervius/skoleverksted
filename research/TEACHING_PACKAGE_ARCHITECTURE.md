# TeachingPackage — arkitektur

**Status:** designdokument. Ingen kode er implementert.

**Opprettet:** 2026-08-08

**Produksjonsdom for plattformen:** `REJECTED` (`PILOT_GO_NO_GO.md`,
`PRODUCTION_VERIFICATION_REPORT.md`). Implementeringsgaten for M1 er **lukket**
og åpnes bare ved eksplisitt beslutning.

Evidensmerking følger hierarkiet i `PRODUCT_EXCELLENCE_EXECPLAN.md` punkt 1.
Alt i dette dokumentet som beskriver *eksisterende* kode er `KODEBEVIST`. Alt
som beskriver TeachingPackage er `DESIGN` — det finnes ikke ennå. Søk i repoet
2026-08-08 ga null treff på `TeachingPackage`, `teaching_package` og
`TeachingArtifact`.

---

## 0. Vedtatte beslutninger

Disse er besluttet og er ikke åpne for reforhandling i TP-M1-design.

| # | Beslutning | Konsekvens |
|---|---|---|
| B1 | `approved` krever grønt faktapass. Ingen generell lærer-bypass i MVP. | Læreren kan lagre og gjennomgå med åpne problemer, men da under en eksplisitt ikke-godkjent status. |
| B2 | TeachingPackage er canonical source of truth. `period.materials` beholdes for MVP/bakoverkompatibilitet, men kun som avledet projeksjon. | Undervisningsinnhold dobbeltlagres ikke. Én eksplisitt projeksjonsfunksjon. |
| B3 | 3–8 minutter er akseptabelt i kontrollert pilot, forutsatt asynkron og durable generering, gjenopptakbar status, synlig progresjon og per-artefakt retry. `MAX_CONCURRENT_JOBS` økes ikke før produksjons-/pilotdata finnes. | Obligatorisk instrumentering av kø- og genereringstid. |
| B4 | TeachingPackage-generering skal bruke `DurableJobGate` fra første implementerte versjon. | Ingen ny langvarig synkron HTTP-flyt. |
| B5 | **TP-M1 er frosset** som definert: én Historie VG2-periode, én `required` artefakt, `artifact_type = learning_sheet`, DurableJobGate, canonical TeachingPackage-state, truth/quality-gate, lærerreview, projeksjon til `period.materials` først etter godkjenning. | Ingen PowerPoint, ingen ekstra artefakttyper i TP-M1. Utvidelse krever ny beslutning, ikke skjønn under implementering. |
| B6 | **80 %-kravet beholdes.** Dagens truth threshold senkes ikke for å gjøre undervisningspakker mulige. | Hvis en pakke ikke kan godkjennes fordi sannhetsmotoren ikke når kravet, skal systemet rapportere det ærlig. Ikke-godkjenning er et gyldig utfall. |
| B7 | Truth-invarianten generaliseres i *designet* med `truth_requirement ∈ {required, not_applicable}`, deterministisk bestemt av `artifact_type`/policy. **Ikke implementert nå.** | Punkt 1.5. For TP-M1: `learning_sheet → required`, altså identisk oppførsel med B1. |
| B8 | Truth coverage registreres som strategisk risiko `TRUTH-COVERAGE-01`, og skal **ikke** løses inne i TeachingPackage. | Punkt 6.1 og [TRUTH_COVERAGE_RESEARCH_PLAN.md](research/TRUTH_COVERAGE_RESEARCH_PLAN.md), som er `BLOCKED`. |

### Arkitekturevidens bak B4

To uavhengige funn peker samme vei, og de behandles som eksplisitt
arkitekturevidens, ikke som anekdoter:

1. **Plattformrutene bruker i dag ikke `DurableJobGate` til arbeid.**
   `KODEBEVIST`. `DurableJobGate` finnes i
   [queue.py](Skoleverksted/backend/platform/queue.py) med `enqueue`, `claim`,
   `finish`, `fail`, `cancel`, SQLite-ledger, Redis-lease og
   `recover_incomplete_jobs()`. Men i
   [router.py](Skoleverksted/backend/platform/router.py) brukes
   `get_durable_job_queue()` bare i `cancel_job`
   ([router.py:590](Skoleverksted/backend/platform/router.py:590)). Alt reelt
   plattformarbeid — `create_compendium_outline`, `produce_compendium_chapter`,
   `compile_compendium`, `generate_year_plan`, `create_theme_pack` — kaller
   modell- og rendringsarbeid direkte i request-tråden. Kapasitetsgaten og den
   varige jobbledgeren er altså tilgjengelig, men omgått.

2. **Kompendium-repair-hendelsen.** `DOKUMENTERT`
   ([REPAIR_JOB_INCIDENT.md](research/REPAIR_JOB_INCIDENT.md)). Et synkront
   repair-kall sto i «Sjekker og retter …» i ~100 sekunder uten tidsgrense,
   uten operation-ID og uten varig status. Rettelsen ble en lokal
   `(compendium_id, chapter_id)`-lås, en daemon-tråd og en 120-sekunders
   timeout i router-laget — altså en ad hoc jobbarkitektur ved siden av den
   som finnes. Den gjenværende risikoen er dokumentert i samme rapport: tråden
   kan fortsette å bruke modellressurser etter server-timeout, og løsningen
   holder ikke for flere backend-instanser.

En komplett undervisningspakke er per B3 tre til åtte minutter arbeid — én til
to størrelsesordener over repair-kallet som allerede feilet. Å bygge den som en
ny synkron flyt ville reprodusere den samme feilklassen i større format.

---

## 1. Revidert domeneinvariant for `approved`

### 1.1 Statusrom

To nye statusenumer. Navnene er valgt slik at ingen ikke-godkjent tilstand kan
forveksles med en godkjent.

```
TeachingArtifactStatus =
    planned                  # bestilt, ikke generert
  | generating               # en durable jobb eier artefakten nå
  | generated                # innhold finnes, ikke verifisert
  | needs_review             # verifisert med åpne punkter; venter på lærer
  | needs_revision           # læreren har avvist; må endres
  | reviewed_with_issues     # læreren har lest og akseptert åpne problemer
  | approved                 # sterkt løfte, se 1.2
  | generation_incomplete    # terminal genereringsfeil
  | parse_failure
  | language_quality_failed
  | source_grounding_failed
  | verification_failed
  | superseded               # lærerendring gjorde et jobbresultat foreldet

TeachingPackageStatus =
    draft | planning | generating | needs_review | needs_revision
  | reviewed_with_issues | approved | archived
```

`reviewed_with_issues` er den eksplisitte tilstanden B1 krever. Den betyr:
læreren har sett artefakten, kjenner de åpne problemene og velger å beholde
den. Den er **ikke** godkjent, og den projiseres **ikke** til
`period.materials` (se 3.4).

`superseded` finnes fordi lærerens redigeringer ikke skal overskrives av en
gammel jobb (se 4.5). Uten en egen status ville et forkastet jobbresultat måtte
rapporteres som suksess eller som feil, og ingen av dem er sanne.

### 1.2 Invariant for artefakt-`approved`

En `TeachingArtifact` kan ha status `approved` **kun** når alle disse holder
samtidig, kontrollert i én funksjon i domenelaget, ikke i UI:

| # | Krav | Begrunnelse |
|---|---|---|
| A1 | `content_markdown.strip()` er ikke tom | ingen tom godkjenning |
| A2 | `truth_passport` finnes og `truth_passport.status == "verified"` | B1; samme prinsipp som kapittelgaten i [router.py:184](Skoleverksted/backend/platform/router.py:184) |
| A3 | `quality_passport.overall_status != "failed"` | deterministiske kontroller skal ikke kunne overkjøres |
| A4 | kildesjekken gir null merknader (`_source_quality_notes`-ekvivalent) | samme regel som compile-gaten i [router.py:289](Skoleverksted/backend/platform/router.py:289) |
| A5 | `truth_passport.content_revision == artifact.content_revision` | passet må gjelde *den teksten som godkjennes*, ikke en tidligere versjon |
| A6 | ingen aktiv jobb eier artefakten: `generation_token is None` og status ikke `generating` | godkjenning midt i en generering er ikke et løfte |
| A7 | eksplisitt lærerhandling er registrert: `approved_by`, `approved_at` | `approved` skal ikke kunne oppstå som bieffekt av en jobb |

A5 er den nye, viktige delen. I dagens kompendiumkode nulles `truth_passport`
ved innholdsendring ([router.py:169-174](Skoleverksted/backend/platform/router.py:169)).
Det er riktig, men implisitt. TeachingArtifact gjør det eksplisitt og
kontrollerbart: en monoton `content_revision` bumpes ved hver innholdsendring,
og passet bærer den revisjonen det ble utstedt for. Da kan A5 testes direkte i
stedet for å hvile på at all skrivekode husker å nulle feltet.

Brudd på A1–A7 gir `409` med en presis, handlingsrettet feiltekst per krav.
Ikke én generisk «kan ikke godkjennes».

### 1.3 Invariant for pakke-`approved`

| # | Krav |
|---|---|
| P1 | Alle artefakter merket `required` i pakkens plan har status `approved` |
| P2 | Valgfrie artefakter er i en terminal tilstand — `approved`, `reviewed_with_issues`, `needs_revision` eller en feilstatus — aldri `generating` eller `planning` |
| P3 | Minst én rendret fil (PDF eller DOCX) finnes for hver `required`-artefakt |
| P4 | Ingen jobb tilknyttet pakken er i `queued`, `planning`, `generating`, `verifying` eller `rendering` |
| P5 | Projeksjonen til `period.materials` fullførte uten feil, i samme transaksjonelle steg som statusendringen |

P5 gjør projeksjonen til en del av godkjenningen, ikke et etterarbeid som kan
feile stille. Feiler projeksjonen, forblir pakken ikke-godkjent.

### 1.4 Generalisert truth-invariant — `truth_requirement` (DESIGN, ikke implementert)

`DESIGN`. Dette er B7. Feltet skal **ikke** implementeres i TP-M1; det er
nedfelt nå slik at framtidige artefakttyper ikke tvinger fram en ad hoc
oppmykning av A2 senere.

Antakelsen bak A2 i punkt 1.2 er at enhver artefakt inneholder
faktapåstander. Den antakelsen holder for `learning_sheet`, men er ikke
generelt sann for alle framtidige `TeachingArtifact`-typer. Uten en eksplisitt
generalisering vil den første artefakttypen uten faktapåstander bli et press
for å svekke gaten. Derfor:

```
TruthRequirement = required | not_applicable
```

Regel, håndhevet i samme domenefunksjon som A1–A7:

```
IF truth_requirement == required:
    artifact kan bare bli approved dersom gjeldende truth-gate er bestått
    (A2 + A5 uendret).

IF truth_requirement == not_applicable:
    manglende truth passport er ikke i seg selv blocker.
    A1, A3, A4, A6, A7 gjelder fortsatt uendret.
```

Det skal **ikke** finnes:

- `unknown`-as-pass — en tredje, uavklart verdi som i praksis slipper igjennom;
- generell teacher bypass;
- silent fallback — manglende eller ukjent policy skal feile lukket, ikke anta
  `not_applicable`;
- automatisk klassifisering fra modellen som kan omgå gaten.

`truth_requirement` bestemmes **deterministisk** av `artifact_type` via en
policytabell i domenelaget. Den er ikke et felt læreren, klienten eller
generatoren kan sette.

For TP-M1 er tabellen ett rad:

| `artifact_type` | `truth_requirement` |
|---|---|
| `learning_sheet` | `required` |

Følgende er **eksempler til framtidig vurdering**, ikke vedtatt mapping. De
fastsettes ikke nå, og de fastsettes ikke uten et konkret behov:

| `artifact_type` | Mulig vurdering |
|---|---|
| `presentation` | trolig `required` |
| `student_sheet` | `required` dersom den inneholder fagtekst |
| `teacher_sheet` | `required` dersom den inneholder faglige påstander |
| `exercise_sheet` | policyavhengig av innholdstype |
| `exit_ticket` | mulig `not_applicable` dersom den bare inneholder spørsmål/instruksjoner |

Fordi TP-M1 kun har `learning_sheet → required`, er observerbar oppførsel i
TP-M1 identisk med B1. Generaliseringen endrer altså ingenting nå; den gjør at
den senere utvidelsen er en policyendring på ett sted i stedet for en
gjennomgripende endring av godkjenningsinvarianten.

### 1.5 Hva som eksplisitt *ikke* er med i MVP

Claim-level teacher override. Den senere modellen — eksplisitt begrunnelse,
lærerhandling, tidspunkt, originalstatus og audit trail — er skissert i
`TEACHING_PACKAGE_EXECPLAN.md` punkt 7 som «not now». Den bygges ikke i M1.
Begrunnelsen er at et override-spor uten revisjonsvisning og uten
elevkonsekvensanalyse er en bakdør i det eneste løftet produktet har.

---

## 2. Canonical-source-of-truth-modellen

### 2.1 Eierskapstabell

| Data | Eier (canonical) | Avledet kopi tillatt | Kommentar |
|---|---|---|---|
| Undervisningsinnhold (`content_markdown`, oppgaver, fasit) | `TeachingArtifact` | nei | aldri i `period.materials` |
| `truth_passport` | `TeachingArtifact` | nei | |
| `quality_passport` | `TeachingArtifact` | nei | |
| Kilder og `fetch_status` | `TeachingArtifact` | nei | |
| Kildesnapshot / grounding-tekst | `TeachingArtifact` | nei | |
| Pakkeplan / bestilling | `TeachingPackage.plan` | nei | |
| Jobb- og forsøkshistorikk | `jobs`-tabellen via `DurableJobGate` | nei | ledgeren er alt varig |
| Rendrede filer (bytes) | filstore, referert fra `TeachingArtifact` | filreferanse i `period.materials` | én fil, to referanser, ikke to filer |
| Periodens faglige ramme (mål, uker, tema) | `YearPlanPeriod` | ja, som lesekopi i `TeachingPackage.plan` frosset ved bestilling | pakken skal ikke endre seg fordi perioden redigeres midt i en jobb |
| Referanse til godkjente artefakter | `TeachingArtifact` | **ja** — dette er projeksjonen | se punkt 3 |

### 2.2 Datamodell (skisse)

```
TeachingPackage
  id, year_plan_id, period_id, subject, level, title
  status: TeachingPackageStatus
  plan: TeachingPackagePlan          # frosset bestilling
  artifacts: list[TeachingArtifact]
  package_job_id: str | None         # foreldrejobben
  planning_source: "ai" | "fallback" | "manual"
  created_at, updated_at, approved_at, approved_by

TeachingPackagePlan
  artifact_specs: list[ArtifactSpec]      # type, tittel, required, rekkefølge
  lesson_count, competency_goals, learning_goals, key_concepts
  source_brief, source_name
  period_snapshot: dict                   # lesekopi av perioden ved bestilling

TeachingArtifact
  id, package_id, order
  artifact_type: MaterialKind-kompatibel  # learning_sheet, worksheet, ...
  required: bool
  title
  content_markdown
  content_revision: int                   # monoton, bumpes ved hver endring
  sources: list[CompendiumSource-ekvivalent]
  truth_passport: TruthPassport | None     # bærer content_revision
  quality_passport: QualityPassport | None
  status: TeachingArtifactStatus
  generation_token: str | None             # job_id:attempt som eier artefakten
  artifact_job_id: str | None
  revision_count, previous_content_markdown
  pdf_filename, pdf_size_bytes, docx_filename, docx_size_bytes, artifact_version
  approved_at, approved_by
  updated_at
```

`artifact_type` gjenbruker `MaterialKind`
([models.py:19](Skoleverksted/backend/platform/models.py:19)) med tillegg av
`teacher_guide`, slik at projeksjonen til `YearPlanMaterial.kind` er en
identitetsavbildning og ikke en oversettelsestabell som kan drifte.

### 2.3 Lagring

Ny tabell `teaching_packages` etter samme mønster som `year_plans` og
`compendia` i [store.py:124-181](Skoleverksted/backend/platform/store.py:124):
`id`, `year_plan_id`, `period_id`, `subject`, `level`, `status`, `payload`,
`created_at`, `updated_at`, med indeks på `(year_plan_id, period_id)` og
`updated_at DESC`.

Én kjent svakhet arves og skal dokumenteres, ikke skjules: dagens
`_save_year_plan` / `_save_compendium` er read-modify-write av hele
JSON-objektet. `PRODUCT_EXCELLENCE_EXECPLAN.md` punkt 4 fører dette opp som
risiko for tapte samtidige endringer. TeachingPackage reduserer eksponeringen
med en CAS-skriving på artefaktnivå (punkt 4.5), men fjerner ikke
grunnproblemet. Full radbasert lagring er `not now`.

---

## 3. `period.materials`-projeksjonen

### 3.1 Retning og eneste skrivevei

```
TeachingArtifact (approved)
        │
        │  project_package_materials()      ← eneste skrivevei
        ▼
YearPlanPeriod.materials[]  (avledet referanse)
```

Projeksjonen er ensrettet. Ingen kode leser undervisningsinnhold fra
`period.materials`, og ingen kode skriver til `period.materials` for en
pakkeeid artefakt utenom denne funksjonen.

### 3.2 Utvidelse av `YearPlanMaterial`

`YearPlanMaterial` ([models.py:216](Skoleverksted/backend/platform/models.py:216))
utvides med et smalt referansesett. Alle felt er nullbare eller har default,
slik at eksisterende manuelt opplastede materialer forblir gyldige.

| Felt | Type | Betydning |
|---|---|---|
| `source_kind` | `"manual" \| "teaching_package"` | default `"manual"`; skiller projiserte rader fra lærerens egne opplastinger |
| `teaching_package_id` | `str \| None` | |
| `artifact_id` | `str \| None` | projeksjonsnøkkel |
| `artifact_type` | `MaterialKind` | speiler `kind` |
| `artifact_version` | `int` | pakkens `artifact_version`, ikke materialradens egen `version` |
| `artifact_status` | `str` | alltid `"approved"` i MVP; feltet finnes for at UI ikke skal utlede status |
| `projected_at` | `str` | tidspunkt for siste projeksjon |

Eksisterende felt som beholdes og fylles: `title`, `kind`, `status`,
`filename`, `mime_type`, `size_bytes`, `notes`.

Eksplisitt forbudt i `YearPlanMaterial`: `content_markdown`, `truth_passport`,
`quality_passport`, `sources`, `plan`, kildesnapshot, revisjonshistorikk. Dette
håndheves av en test som feiler hvis nye felt av denne typen legges til.

### 3.3 Funksjonskontrakt

```python
def project_package_materials(
    store: PlatformStore,
    package: TeachingPackage,
) -> YearPlan:
    """Projiser pakkens godkjente artefakter inn i period.materials.

    Idempotent, nøkkel (teaching_package_id, artifact_id).
    Eneste skrivevei for pakkeeide materialrader.
    """
```

Regler:

1. **Idempotent på `artifact_id`.** Finnes en rad med samme
   `(teaching_package_id, artifact_id)`, oppdateres den på plass. Det
   opprettes ikke en ny rad. Dagens `add_year_plan_material`
   ([store.py:455](Skoleverksted/backend/platform/store.py:455)) appender alltid
   og versjonerer per `kind`; projeksjonen kan derfor ikke bruke den uendret.
2. **Bare `approved`.** Artefakter i `needs_review`, `needs_revision`,
   `reviewed_with_issues` eller feilstatus projiseres aldri.
3. **Tilbaketrekking.** Går en tidligere godkjent artefakt tilbake til en
   ikke-godkjent status, settes den projiserte raden til `needs_revision` og
   `artifact_status` oppdateres. Raden slettes ikke, fordi læreren kan ha delt
   lenken. Filen forblir tilgjengelig, men merket.
4. **Filen deles, ikke kopieres.** Projeksjonen skriver filreferanse og
   `size_bytes`, ikke nye bytes, når filstoren tillater det. Kan den ikke dele,
   dokumenteres kopieringen eksplisitt som kjent duplisering av *bytes* — ikke
   av innholdstilstand.
5. **Skrivebeskyttelse.** `PATCH .../materials/{id}` avviser med `409` alle
   endringer på rader der `source_kind == "teaching_package"`, med ett unntak:
   `status: "approved" → "used"`. Det er lærerens markering av at materialet er
   brukt i klassen, og den tilhører årsplanen, ikke pakken.
6. **Kalles fra ett sted.** `POST /teaching-packages/{id}/approve` og fra
   artefakt-tilbaketrekking. Ikke fra jobbworkeren.

### 3.4 Hva læreren ser

En periode viser da tre visuelt adskilte grupper: manuelt opplastede
materialer, projiserte godkjente artefakter (med lenke til pakken), og en
henvisning til pakker som finnes men ikke er godkjent. Den siste gruppen er
bevisst *ikke* en materialrad — en ikke-godkjent pakke skal ikke se ut som et
læremiddel i årsplanen.

---

## 4. Durable-job-livssyklusen

### 4.1 Jobbtre

```
package_job    id = pkg:{package_id}
   ├── artifact_job  id = art:{package_id}:{artifact_id}
   ├── artifact_job  id = art:{package_id}:{artifact_id}
   └── render_job    id = rnd:{package_id}
```

Alle IDer er **deterministiske**, ikke tilfeldige. Det er det som gjør retry
idempotent: `enqueue` på samme `job_id` finner eksisterende rad og øker
`attempt` ([queue.py:114-116](Skoleverksted/backend/platform/queue.py:114)) i
stedet for å lage en parallell jobb.

`module` settes til `"platform"`, som er tillatt i `Job.module`
([models.py:62](Skoleverksted/backend/platform/models.py:62)). `kind` settes til
`"teaching_package"`, `"teaching_artifact"` eller `"teaching_render"`.

### 4.2 Livssyklus, steg for steg

| Steg | Handling | Varighet |
|---|---|---|
| 1 | `POST /teaching-packages` lagrer pakken med status `draft`. Ingen modellkall. | ms |
| 2 | `POST /{id}/generate`: **registrer alle jobber varig før noe arbeid starter** — `gate.enqueue(pkg:…)` og én `gate.enqueue(art:…)` per artefakt. Sett pakke til `planning`, artefakter til `planned`. | ms |
| 3 | Samme request returnerer `202` med `{package_id, package_job_id, artifact_job_ids[]}`. Ingen modellarbeid i request-tråden. | ms |
| 4 | Worker starter. Per artefakt: `with gate.claim(art_job_id, auto_complete=False)`, sett `generation_token = f"{art_job_id}:{attempt}"`, generer, verifiser, CAS-skriv (4.5), `gate.finish()` eller `gate.fail()`. | 3–8 min totalt |
| 5 | Ferdige artefakter blir synlige fortløpende — hver CAS-skriving er et commit-punkt. | fortløpende |
| 6 | Når alle artefaktjobber er terminale: `gate.finish(pkg:…)`, pakkestatus → `needs_review`. **Aldri `approved`.** | ms |
| 7 | Læreren reviewer, redigerer, verifiserer, godkjenner per artefakt, godkjenner pakken. Projeksjon skjer her. | lærertid |

Steg 3 er hele poenget med B4. Rekkefølgen «registrer varig, returner, arbeid
etterpå» er det som gjør at læreren kan navigere bort, at status kan hentes
senere, og at en restart ikke kan gi falsk suksess.

### 4.3 Gjenopptakelse etter reload og restart

- **Reload:** frontend lagrer `package_id` i URL-en. Statusen leses fra
  `GET /teaching-packages/{id}` (per-artefakt status) og
  `GET /jobs/{job_id}` (kø, progresjon, forsøk). Ingen polling-state ligger
  bare i minnet. Dette er kravet «frontend skal kunne gjenoppta
  polling/status etter reload».
- **Restart:** `DurableJobGate.__init__` kaller allerede
  `recover_incomplete_jobs()` ([queue.py:103](Skoleverksted/backend/platform/queue.py:103)).
  For TeachingPackage utvides gjenopprettingen til å måtte oversette til
  domenetilstand: enhver artefakt som står i `generating` uten en levende jobb
  settes til en **retryable feilstatus**, aldri `generated` og aldri
  `approved`. Kravet «restart skal ikke gi falsk suksess» er en test, ikke en
  hensikt.

### 4.4 Isolasjon av feil

Kravet «en feilet artefakt skal ikke ødelegge resten av pakken» realiseres
ved at hver artefakt har egen jobb, egen `claim`, egen `finish`/`fail` og eget
commit-punkt. Foreldrejobben aggregerer og fullfører når alle barn er
terminale — den fullfører altså «alle forsøkt», ikke «alle vellykket».
Pakkestatus etter aggregering er `needs_review` når minst én `required`-artefakt
er brukbar, ellers `needs_revision`.

Per-artefakt retry: `POST /{id}/artifacts/{artifact_id}/regenerate` gjør
`enqueue` på samme deterministiske `job_id`. Kjører den allerede, svarer
endepunktet `409` med den aktive `job_id`-en — samme kontrakt som
repair-låsen allerede beviste i produksjon (409 etter 504,
`REPAIR_JOB_INCIDENT.md`), men nå med varig status i stedet for et
prosessminne-dict.

### 4.5 Vern mot at en gammel jobb overskriver lærerens arbeid

Dette er den mest subtile av de fem kravene og trenger en mekanisme, ikke en
regel.

- Hver artefakt har `content_revision: int` (monoton) og
  `generation_token: str | None`.
- Når en worker gjør `claim`, leser den `(content_revision, generation_token)`
  og setter `generation_token` til sin egen `job_id:attempt`.
- **Lærerens redigering** bumper `content_revision`, nullstiller
  `truth_passport` og setter `generation_token = None`.
- Ved skriving gjør workeren en **compare-and-swap**: skriv bare hvis
  `generation_token` fortsatt er dens egen *og* `content_revision` er uendret.
  Ellers forkastes resultatet, artefakten får status `superseded`, og jobben
  avsluttes med en eksplisitt, ikke-alarmerende melding om at lærerens versjon
  ble beholdt.

Konsekvens: kravet «lærerens redigeringer skal ikke overskrives av en gammel
jobb» blir en observerbar tilstand (`superseded`) som kan testes, ikke et
tidsvindu man håper på.

### 4.6 Avbrudd

`POST /jobs/{job_id}/cancel` finnes allerede
([router.py:588](Skoleverksted/backend/platform/router.py:588)) og setter status
`cancelled`. Workeren sjekker avbruddsflagget ved hver artefaktgrense. Et
pågående modellkall avbrytes ikke midt i — det er samme gjenværende risiko som
`REPAIR_JOB_INCIDENT.md` punkt «Resterende risiko» dokumenterer, og den
arves bevisst i MVP. Forskjellen er at statusen nå er varig og sann.

### 4.7 Instrumentering (B3)

Målingene lagres i `Job.result_summary`
([models.py:69](Skoleverksted/backend/platform/models.py:69)), som allerede er
et fritt dict. Kun allowlistede, numeriske eller enum-verdier — ingen
kildetekst, ingen elev- eller lærerdata. Dette er samme dataminimeringskrav
som `PRODUCT_EXCELLENCE_EXECPLAN.md` punkt 8 stiller til telemetri.

| Felt | Nivå | Merknad |
|---|---|---|
| `queue_wait_ms` | artefaktjobb | `claim`-tidspunkt minus `enqueue`-tidspunkt |
| `generation_ms` | artefaktjobb | ren arbeidstid innenfor `claim` |
| `package_total_ms` | pakkejobb | første `enqueue` til siste terminale barn |
| `retry_count` | artefaktjobb | `attempt - 1`; finnes alt i `Job.attempt` |
| `failure_reason` | artefaktjobb | **enum-kode**, ikke modelltekst: `provider_timeout`, `provider_error`, `parse_failure`, `truth_verification_failed`, `source_grounding_failed`, `language_quality_failed`, `cancelled`, `superseded`, `internal_error` |
| `provider_latency_ms` | artefaktjobb | der leverandøren oppgir eller den kan måles rundt kallet |

`MAX_CONCURRENT_JOBS` forblir **1** (default i
[queue.py:99](Skoleverksted/backend/platform/queue.py:99)). P50/P95 rapporteres
først når det finnes nok observasjoner; til da er tallene `UKJENT` og skal
ikke fremstilles som et estimat.

---

## 5. Forholdet til eksisterende moduler

- **Gjenbruk, ikke gaffel.** Generering og verifikasjon skal gjenbruke
  `truth.py`, `quality.py`, `text_quality.py` og mønsteret i `compendium.py`.
  Sannhetslaget er fail-closed etter M1 i `PRODUCT_EXCELLENCE_EXECPLAN.md`
  punkt 9, og TeachingPackage skal ikke ha en egen kopi av den logikken.
- **Kompendium migreres ikke nå.** Kompendiumløpet fortsetter som i dag.
  Å flytte det til `DurableJobGate` er riktig, men det er en separat milepæl
  (`PRODUCT_EXCELLENCE_EXECPLAN.md` M2) og skal ikke pakkes inn i M1.
- **Temapakker.** `POST /theme-packs` lager i dag et prosjekt med tre lenker.
  Det overlapper konseptuelt med TeachingPackage, men røres ikke i M1.
  Konsolidering krever en beslutning om hvilken av dem som overlever.

---

## 6. Kjent gjenværende risiko i dette designet

| Risiko | Status | Håndtering |
|---|---|---|
| Read-modify-write av hele pakke-JSON kan tape samtidige endringer | arvet fra `store.py` | CAS på artefaktnivå reduserer, fjerner ikke; radbasert lagring er `not now` |
| Modellkall avbrytes ikke ved cancel | arvet fra `REPAIR_JOB_INCIDENT.md` | varig status er sann selv om ressursen brukes; dokumentert, ikke skjult |
| Ingen brukeridentitet/tenant | pilotblokker, `PRODUCT_EXCELLENCE_EXECPLAN.md` M3 | pakker arver samme eksponering som årsplaner; M1 forutsetter teknisk isolert enbruker-pilot |
| `MAX_CONCURRENT_JOBS = 1` gir kø ved to samtidige pakker | bevisst | `queue_wait_ms` måler kostnaden før grensen endres |
| Pakkeplanen er frosset ved bestilling; periodeendringer slår ikke gjennom | bevisst | synliggjøres i UI som «planen er basert på perioden slik den var <tidspunkt>» |
| Faktapassets dekningsgrad har vært 73 % i produksjon | `PRODUKSJONSBEVIST`, `REJECTED` | se `TRUTH-COVERAGE-01` i punkt 6.1 |

Det siste punktet er verdt å si tydelig: en streng `approved`-invariant gjør at
piloten kan ende med pakker som aldri blir godkjent. Det er riktig valg — men
det betyr at faktapassets dekningsgrad, ikke pakkemekanikken, blir den reelle
begrensningen på produktverdi.

### 6.1 TRUTH-COVERAGE-01 — strategisk risiko

**ID:** `TRUTH-COVERAGE-01`
**Status:** registrert, ikke løst. Eier: sannhetssporet, ikke TeachingPackage.

**Observed production evidence** (`PRODUKSJONSBEVIST`,
[PRODUCTION_VERIFICATION_REPORT.md:118](research/PRODUCTION_VERIFICATION_REPORT.md:118),
identisk produksjonsscenario på baseline `69b00d81e5a7`):

```
44 claims
32 verified
73 %
```

**Current approval threshold:** 80 %
(`verified_count / total >= 0.8` i
[truth.py:472](Skoleverksted/backend/platform/truth.py:472)).

**Consequence:** A technically correct TeachingPackage implementation may
remain unusable for approval if the truth pipeline cannot reliably reach the
quality gate. TP-M1 kan altså være ferdig og korrekt, og likevel produsere
pakker som aldri blir `approved`.

**Do not solve this inside TeachingPackage.** Terskelen senkes ikke (B6),
weighted claims innføres ikke, criticality scoring innføres ikke, og
truth-motoren endres ikke som del av TP-M1. Undersøkelsen er skilt ut i
[TRUTH_COVERAGE_RESEARCH_PLAN.md](research/TRUTH_COVERAGE_RESEARCH_PLAN.md),
som er `BLOCKED`.

**To presiseringer som hører til risikoen, men ikke svekker den:**

1. Tallet 73 % er et **aggregat over tre kapitler** i ett kompendium
   (100 % / 62 % / 56 %). Gaten i
   [truth.py:472](Skoleverksted/backend/platform/truth.py:472) evalueres
   **per artefakt**, ikke på aggregatet. For TP-M1, som har én artefakt, er
   det derfor per-artefakt-dekningen som avgjør — og spredningen mellom
   56 % og 100 % er en del av risikoen, ikke et argument mot den.
2. 80 % dekning er **nødvendig, men ikke tilstrekkelig** for
   `status == "verified"`. Samme betingelse krever også minst én konkret,
   validert kilde og `not unresolved_edits`. En undersøkelse av dekningsgrad
   alene forklarer derfor ikke alle ikke-grønne pass.
