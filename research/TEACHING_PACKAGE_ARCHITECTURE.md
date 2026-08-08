# Undervisningspakke – arkitektur

> Status: **FORSLAG – IKKE IMPLEMENTERT**
> Skrevet: 8. august 2026
> Gren: `claude/teaching-package-architecture-bzs4yk`
> Basis-commit: `ff725bb Document product excellence baseline`
> Gjeldende produksjonsgate: `research/PRODUCTION_VERIFICATION_REPORT.md` – dom **REJECTED**

Dette dokumentet beskriver hvordan en årsplanperiode kan bli til én koordinert
undervisningspakke. Alt i del 1 er verifisert mot faktisk kode i denne
arbeidskopien, ikke mot `status.md` eller andre researchdokumenter. Del 2 og
utover er forslag.

Ingen kode i denne planen skal implementeres før produksjonsgaten er lukket
eller eieren eksplisitt ber om parallellarbeid.

---

## DEL 1 – FAKTISK EKSISTERENDE ARKITEKTUR

### 1.1 Repostruktur og hvor ting faktisk kjører

Monorepoet inneholder fire Python-pakker og fire `frontend/`-kataloger, men
bare én av hver er i aktiv produksjonsbruk:

| Katalog | Rolle i dag |
|---|---|
| `Skoleverksted/backend` | Plattformlaget. `main.py` er den eneste FastAPI-inngangen. Monterer de tre fagappene og eksponerer `/api/platform`. |
| `VGS_KI/backend` | Fagmodulen «Fag & læring». Montert på `/api/fag`. |
| `ScriptoriumFOV/backend` | Norskmodulen. Montert på `/api/norsk`. |
| `MateMaTeX/backend` | Matematikkmodulen. Montert på `/api/matematikk`. |
| **`MateMaTeX/frontend`** | **Den samlede Next.js-appen.** Inneholder `/year-plans`, `/compendia`, `/fag`, app-shell og `lib/platform-api.ts`. |
| `Skoleverksted/frontend` | Tom bortsett fra `.env.example`. Ingen kode. |
| `VGS_KI/frontend`, `ScriptoriumFOV/frontend` | Eldre frittstående frontender. Ikke koblet til årsplanflyten. |

Konsekvens for denne funksjonen: all ny frontend hører hjemme i
`MateMaTeX/frontend/src/app/…`, ikke i `Skoleverksted/frontend`. Navnet er
misvisende, men å flytte appen er en egen oppgave og ikke en del av denne.

Verifisert i `Skoleverksted/backend/main.py:32-34,129-131` og
`MateMaTeX/frontend/src/app/year-plans/[id]/page.tsx`.

### 1.2 Hvordan årsplaner og perioder faktisk er modellert

`Skoleverksted/backend/platform/models.py:230-311`.

`YearPlan` er én flat Pydantic-modell. Periodene ligger **inne i** planen som
en liste, ikke som egne rader. Hele planen lagres som én JSON-blob i kolonnen
`year_plans.payload` (`store.py:156-167`). Det finnes ingen `periods`-tabell.

`YearPlanPeriod` har i dag:

```
id, order, title, theme,
week_start, week_end          # ISO-ukestrenger, f.eks. "2026-W38"
duration_weeks, lesson_count
overview                      # fritekst, ≤3000
learning_goals[≤12]
competency_goals[≤30]
key_concepts[≤20]             # bare navn, ingen definisjoner
suggested_activities[≤15]
assessment                    # én fritekststreng, ≤1200
teacher_notes                 # ≤3000, brukes i UI som etterpå-logg
status                        # not_started|in_progress|ready|completed|needs_revision
materials[≤100]
```

Viktige konsekvenser:

* All periodeskriving går gjennom `store.update_year_plan_period`, som leser
  hele planen, bytter én periode og skriver hele blobben tilbake
  (`store.py:429-453`). Det er last-write-wins på tvers av perioder allerede.
* En undervisningspakke kan derfor **ikke** ligge inne i periodeobjektet uten
  å gjøre den tapte-oppdatering-risikoen mye verre og payloaden mye større.
* `_academic_weeks` (`year_planner.py:52-59`) hardkoder norske ferieuker
  (hopper over uke 40, 8, 13, 14). Ukene er et forslag, ikke en kalender.

### 1.3 Hvordan materiale kobles til en periode i dag

`YearPlanMaterial` (`models.py:216-227`) er en ren filpost:
`id, title, kind, status, version, filename, mime_type, size_bytes, notes`.

`store.add_year_plan_material` (`store.py:455-492`):

* skriver bytes til `files_dir/<plan_id>/<material_id>.bin` med temp-fil +
  `replace()` (atomisk),
* setter `version = max(version for samme kind) + 1`,
* legger posten i `period.materials` og skriver hele planen på nytt,
* løfter periodestatus `not_started → in_progress` ved godkjent materiale.

`MaterialKind` inneholder allerede `"presentation"` (`models.py:19-29`).

**Dette er nøyaktig mønsteret oppdraget advarer mot.** Det finnes ingen
gruppering av filer, ingen felles plan, ingen kontekst-snapshot, ingen
kvalitetspass og ingen kobling tilbake til hva som genererte filen. Frontenden
utleder «grunnpakken er komplett» ved å telle `kind` i
`year-plans/[id]/page.tsx:307-312`.

I dag fylles `materials` på to måter:

1. Manuelt opplastet fra fagmodulen (frontend kaller `saveYearPlanMaterial`).
2. Automatisk når et kompendium godkjennes – `router.py:357-384` kopierer
   PDF-en inn i hver valgte periode som `kind="compendium"`.

### 1.4 Eksisterende generatorer som kan gjenbrukes

| Modul | Funksjon | Fil | Vurdering for pakken |
|---|---|---|---|
| Fag & læring | `generate_lesson_content` | `VGS_KI/backend/agents.py:881` | Lager fagtekst + arbeidsark + differensiering + språkøvelser i **ett** kall. Eier sin egen rendering. Kan ikke styres av en ekstern pakkeplan uten omskriving. |
| Fag & læring | `generate_prove_content` | `agents.py:2632` | Prøve med flervalg/kortsvar/langsvar/fasit/kriterier. Relevant for senere artefakt `prøve`, ikke MVP. |
| Fag & læring | `generate_sequence_content` | `agents.py:2872` | Øktplan/sekvens. **Nærmeste eksisterende slektning til `TeachingPackagePlan`.** Prompt og JSON-parser er verdt å lese, men den produserer et dokument, ikke en delbar plan. |
| Norsk | ScriptoriumFOV-agenter | `ScriptoriumFOV/backend/agents.py` | CEFR-tilpasning A1–B2. Reserveres til senere artefakt «språktilpasset versjon». |
| Matematikk | oppgavemotor + SymPy-verifikasjon | `MateMaTeX/backend/app/` | Den eneste maskinelt verifiserte oppgavemotoren i repoet. Skal brukes uendret når faget er matematikk. Ikke MVP (piloten er historie). |
| Plattform | `plan_compendium`, `generate_compendium_chapter`, `repair_compendium_chapter` | `platform/compendium.py` | **Det viktigste mønsteret å kopiere:** grounded Google-kall med `response_schema`, verifikasjonspass, deterministisk fallback, maskinlesbare feilstatuser. |
| Plattform | `audit_truth` | `platform/truth.py:298` | Klassifiserer og reviderer faktapåstander. Grense: krever 80–80 000 tegn. |
| Plattform | `inspect_markdown` | `platform/text_quality.py:58` | Deterministisk språkport (fragmenter, tomme overskrifter, HTML-rester). |
| Plattform | `build_quality_passport` | `platform/quality.py:8` | Deterministisk kvalitetspass med score og begrensninger. |
| Plattform | `resolve_image`, `discover_commons_images` | `platform/images.py` | Wikimedia Commons med lisensfiltrering (`_is_free_license`) og ferdig kreditstreng. Verifiserer nedlastede bytes. |
| Plattform | `markdown_to_typst`, `build_docx`, `safe_filename` | `platform/compendium_renderer.py` | Ferdige, testede byggesteiner for PDF og Word. |

### 1.5 Finnes PowerPoint-generering allerede? Ja – to steder

1. `MateMaTeX/backend/app/export/powerpoint.py` – `latex_to_pptx()`.
   Bruker `python-pptx`. Setter 13.333×7.5 tommer (16:9). Bruker
   standardmalens `slide_layouts[0]` og `[1]` (tittel + innholdsplassholder),
   strippet LaTeX med regex, løsninger i `notes_slide`.
   Eksponert som `POST /api/matematikk/export/pptx`
   (`app/export/router.py:359`). Testet i
   `MateMaTeX/backend/tests/test_export.py:139-161` – testene sjekker bare at
   det kommer `PK`-bytes ut, ikke pedagogisk eller visuell kvalitet.
2. `MateMaTeX/src/tools/pptx_exporter.py` – eldre variant i `src/`-treet, ikke
   koblet til den monterte appen.

Kvalitetsvurdering: `latex_to_pptx` er nettopp den «tekst flyttet inn i
lysbilder»-modellen oppdraget forbyr – `Title + placeholder` er hele
layoutstyringen. Den **skal ikke** gjenbrukes som renderer.

Den beviser derimot noe viktig: **`python-pptx` er allerede installert i
produksjonsimaget.** `Skoleverksted/backend/requirements.txt` inkluderer
`-r ../../MateMaTeX/backend/requirements.txt`, som har `python-pptx>=0.6.23`.

### 1.6 Hvordan PDF, Word og andre filer lagres og versjoneres

To renderingsstakker, begge tilgjengelige i imaget:

* **Typst** – CLI v0.14.2 installeres i `Dockerfile:20-29`, `TYPST_PATH`
  settes i `render.yaml`. Kalles via `VGS_KI/backend/pdf_service.compile_typst`
  (`pdf_service.py:18`). Brukt av kompendium-PDF og læringsark.
* **LaTeX** – `pdflatex` og `lualatex` for matematikk.
* **python-docx** – `compendium_renderer.build_docx`, `VGS_KI/backend/docx_service.py`.

Versjonering i dag:

| | Kompendium | Årsplanmateriell |
|---|---|---|
| Sti | `OUTPUT_DIR/compendia/<id>/v<N>.pdf\|docx` | `OUTPUT_DIR/year-plans/<plan>/<material_id>.bin` |
| Versjonsteller | `compendium.artifact_version` (int) | `material.version` per `kind` |
| Skrivemåte | temp + `replace()` | temp + `replace()` |
| Validering | `pdf.startswith(b"%PDF")`, `docx.startswith(b"PK")` (`store.py:654`) | ingen |
| Sjekksum | nei | nei |
| Opprydding | nei | nei |

Ingen av filene har innholdshash eller retensjonsregel. Gamle versjoner blir
liggende.

### 1.7 Hvordan jobbkø, historikk og kvalitetspass fungerer

**Jobbkø** – `platform/queue.py`, `DurableJobGate`:

* `BoundedSemaphore(MAX_CONCURRENT_JOBS)`, satt til **1** i `render.yaml`.
* Valgfri Redis-leie for flere instanser; faller trygt tilbake lokalt.
* Durable ledger i SQLite-tabellen `jobs`.
* `recover_incomplete_jobs()` kjøres i konstruktøren og setter alt som var
  under arbeid til `needs_review` + `retryable` etter restart (`store.py:288`).

Hvem bruker den: `VGS_KI/backend/job_manager.py:225`,
`ScriptoriumFOV/backend/main.py:599`, `MateMaTeX/backend/app/main.py:279,718`.

**Hvem bruker den ikke: plattformrutene.** `platform/router.py` kaller kun
`get_durable_job_queue()` for `cancel`. Alle kompendium- og
årsplanoperasjoner er synkrone HTTP-kall. Kompendiumreparasjon har en
hjemmesnekret tråd + `Event` + 120 s timeout (`router.py:75-118`) nettopp
fordi jobbkøen ikke ble brukt. Dette er registrert som medvirkende årsak i
`research/PRODUCTION_INCIDENT_CLOSURE.md` («Kompendiumrutene opprettet ikke
varige Job-rader»).

**Historikk** – `JobTelemetryMiddleware` (`platform/telemetry.py`) leser bare
svar under `/api/fag/`, `/api/norsk/`, `/api/matematikk/`
(`telemetry.py:30-34`). Plattformarbeid havner aldri i jobbhistorikken.

**Kvalitetspass** – to lag:

* `build_quality_passport` – deterministisk: innhold finnes, kilder,
  sporbare kildemarkører, kompetansemål, fasit, kompilering, duplikater,
  plassholdere, matematisk korrekthet. Score = vektet snitt
  (passed 100 / warning 55 / failed 0), `failed` slår ut alt.
* `audit_truth` – påstandsnivå med Google-grunning, statusene
  `verified|interpretation|disputed|time_sensitive|unsupported|
  verification_failed|source_unavailable|not_evaluated`, og handlingene
  `keep|qualify|remove`. Etter forensic-hendelsen er `remove` og `qualify`
  begrenset til hele setninger eller hele Markdown-linjer.

Godkjenningsporten for kompendium (`router.py:269-301, 340-388`) krever i
denne rekkefølgen: alle kapitler har innhold **og** `status="approved"` **og**
grønt faktapass → kildekvalitetssjekk → bygg PDF/DOCX → godkjenn.
Det er denne porten pakken skal arve, ikke en ny og svakere.

### 1.8 Hva mangler i dagens periodemodell

For å bygge en komplett undervisningspakke mangler perioden:

| Felt i `TeachingPackageContext` | Finnes i dag? | Kilde |
|---|---|---|
| `subject`, `level`, `school_year` | ✅ | fra `YearPlan` |
| `topic` | ✅ | `period.theme \|\| period.title` |
| `duration_weeks` | ✅ | `period.duration_weeks` |
| `available_lessons` | ✅ | `period.lesson_count` |
| `minutes_per_lesson` | ✅ | `plan.lesson_minutes` |
| `curriculum_goals` | ✅ | `period.competency_goals` |
| `learning_goals` | ✅ | `period.learning_goals` |
| `key_concepts` | ⚠️ delvis | bare navn, ingen elevvennlige definisjoner |
| `assessment_plan` | ⚠️ delvis | én fritekststreng, ikke strukturert (type, tidspunkt, kriterier) |
| **`prerequisite_knowledge`** | ❌ | finnes ikke |
| **`source_context`** | ❌ | ingen kilder på periodenivå. Kompendiet har `source_brief`, årsplanen har ingenting. |
| **`differentiation`** | ❌ | finnes bare inne i fagmodulens generatorprompt |
| **`language_level`** | ❌ | finnes bare i norskmodulen og `ThemePackRequest.norwegian_level` |
| **`teacher_notes` (didaktisk)** | ⚠️ | feltet finnes, men UI bruker det som etterpå-refleksjon («Hva fungerte?») |
| **tidligere godkjente materialer som kontekst** | ❌ | `materials` er filposter uten uttrekkbart innhold. Bare tittel/kind/notes kan brukes. |
| **bildepolicy** | ❌ | `image_mode` finnes på kompendium, ikke på periode |

Konklusjon: **fem felter må legges til**, og to må struktureres. Ingen av dem
krever migrasjon hvis de får defaultverdier – se 4.6.

---

## DEL 2 – FORESLÅTT DOMENEMODELL

### 2.1 Prinsipp

Undervisningspakken er en **egen førsteklasses entitet i egen tabell**, koblet
til `(year_plan_id, period_id)` med fremmednøkkel-lignende indeks. Den ligger
ikke inne i årsplanens JSON-blob. Grunnen er 1.2: periodeskriving overskriver
hele planen.

Én pakke = én kontrakt (`context`) + én kanonisk plan (`plan`) + N artefakter.
Alle artefakter leses ut av samme plan. Det skal ikke finnes fem uavhengige
AI-kall som hver finner på sitt eget undervisningsopplegg.

### 2.2 `TeachingPackageContext` – den pedagogiske kontrakten

Snapshottes fra perioden ved opprettelse, deretter redigerbar av læreren fram
til planen er laget. Etter det er den frosset for versjonen.

```python
class AssessmentPlanItem(BaseModel):
    kind: Literal["underveis", "innlevering", "muntlig", "prove", "annet"]
    description: str            # ≤600
    timing: str = ""            # "uke 40", "siste økt"
    criteria: list[str] = []    # ≤8

class PackageSource(BaseModel):
    title: str
    url: str = ""
    publisher: str = ""
    origin: Literal["teacher", "grounding", "model"] = "teacher"
    fetch_status: Literal["provided", "grounded", "model_reported",
                          "fetched", "source_unavailable"] = "provided"
    note: str = ""              # hva kilden skal brukes til

class TeachingPackageContext(BaseModel):
    subject: str
    level: str
    school_year: str
    topic: str
    duration_weeks: int         # 1..12
    available_lessons: int      # 1..120
    minutes_per_lesson: int     # 30..180
    curriculum_goals: list[str] # ordrett fra perioden, aldri omskrevet
    learning_goals: list[str]
    key_concepts: list[str]
    prerequisite_knowledge: list[str] = []
    assessment_plan: list[AssessmentPlanItem] = []
    source_context: list[PackageSource] = []
    differentiation: Differentiation = Differentiation()   # support / core / extension
    language_level: str = ""    # tom = ordinært fagnivå; ellers CEFR A1..B2
    image_mode: Literal["none", "commons", "ai"] = "none"
    teacher_notes: str = ""
    prior_material_titles: list[str] = []   # bare titler – ikke filinnhold
```

`PackageSource` gjenbruker feltnavnene fra `CompendiumSource` og `TruthSource`
med vilje, slik at `audit_truth(provided_sources=…)` kan ta dem uendret.

`prior_material_titles` er bevisst begrenset til titler. Å pumpe hele PDF-er
inn i prompten ville sprengt `audit_truth`-grensen på 80 000 tegn og gjort
provenienssporingen umulig.

### 2.3 `TeachingPackagePlan` – den kanoniske planen

Produseres av **ett** grunnet AI-kall og er den eneste sannheten alle
artefakter leser fra.

```python
class PlannedConcept(BaseModel):
    term: str
    student_explanation: str    # elevvennlig, ≤400
    example: str = ""
    visual_hint: str = ""       # hva slags visualisering som passer
    check_question: str = ""
    introduced_in_lesson: int   # 1-indeksert

class PlannedLesson(BaseModel):
    order: int
    title: str
    minutes: int
    learning_goal_refs: list[str]     # indeks-id til context.learning_goals
    sequence: list[str]               # kort didaktisk rekkefølge
    concepts_introduced: list[str]    # term-referanser
    examples: list[str]
    key_questions: list[str]
    activity: str
    check_of_understanding: str
    source_refs: list[str]            # id-er inn i plan.sources

class TeachingPackagePlan(BaseModel):
    version: str = "1.0"
    summary: str                       # 3–5 setninger
    what_students_learn: list[str]
    progression_rationale: str
    lessons: list[PlannedLesson]
    concepts: list[PlannedConcept]
    sources: list[PackageSource]
    misconceptions: list[str]
    differentiation_notes: DifferentiationNotes
    truth_passport: TruthPassport | None = None
    plan_hash: str                     # sha256 av kanonisk JSON, uten passport
```

`plan_hash` er hele koordineringsmekanismen: hver artefakt lagrer hvilken
plan-hash den ble bygget fra. Endres planen, blir alle artefakter merket
`needs_revision` uten at de slettes.

### 2.4 `TeachingPackage` og `TeachingArtifact`

```python
ArtifactType = Literal[
    # MVP
    "presentation", "student_sheet", "teacher_sheet", "tasks", "concept_sheet",
    # reservert, ikke implementert i MVP
    "quiz", "test", "answer_key", "source_collection", "timeline",
    "math_activity", "language_adapted", "homework", "deep_dive",
]

PackageStatus = Literal[
    "draft",             # kontrakt opprettet, læreren redigerer
    "planning",          # planjobb kjører
    "needs_review",      # plan eller artefakter venter på lærerkontroll
    "generating",        # én eller flere artefaktjobber kjører
    "needs_revision",    # noe er avvist av lærer eller konsistenskontroll
    "approved",          # lærer har eksplisitt godkjent
    "generation_failed", # planjobben feilet; ingen plan finnes
]

ArtifactStatus = Literal[
    "planned", "generating", "generated", "needs_review",
    "needs_revision", "approved",
    "generation_failed", "render_failed", "consistency_failed",
]

class ArtifactFile(BaseModel):
    format: Literal["pptx", "pdf", "docx"]
    filename: str            # deterministisk, se 5.4
    size_bytes: int
    sha256: str
    built_at: str

class TeachingArtifact(BaseModel):
    id: str
    package_id: str
    type: ArtifactType
    version: int = 1
    status: ArtifactStatus = "planned"
    source_snapshot: ArtifactSourceSnapshot   # plan_hash + context_hash + prompt_version
    content: dict[str, Any]                   # typet per artefakt, se del 3
    files: list[ArtifactFile] = []
    quality_passport: QualityPassport | None = None
    consistency_findings: list[ConsistencyFinding] = []
    error_message: str = ""
    created_at: str
    updated_at: str

class TeachingPackage(BaseModel):
    id: str
    project_id: str | None
    year_plan_id: str
    period_id: str
    version: int = 1
    status: PackageStatus = "draft"
    title: str
    context_snapshot: TeachingPackageContext
    plan: TeachingPackagePlan | None = None
    requested_artifacts: list[ArtifactType]
    artifacts: list[TeachingArtifact] = []
    quality_status: PackageQualityStatus       # se 2.5
    created_at: str
    updated_at: str
    approved_at: str | None = None
    approved_by_teacher: bool = False          # settes bare av godkjenn-endepunktet
```

`approved_by_teacher` er et eget felt og ikke utledet av statusen. Statusen
kan aldri bli `approved` uten at dette flagget settes av et eksplisitt
lærerkall. Det er den tekniske sikringen mot «AI ble ferdig, altså godkjent».

### 2.5 `PackageQualityStatus`

```python
class PackageQualityStatus(BaseModel):
    truth_status: str = "not_evaluated"     # fra plan.truth_passport
    verified_claims: int = 0
    total_claims: int = 0
    consistency_passed: bool = False
    consistency_findings: list[ConsistencyFinding] = []
    missing_artifacts: list[ArtifactType] = []
    blocking_reasons: list[str] = []        # tom liste = klar for godkjenning
```

### 2.6 Lagring

Ny tabell, ingen endring på eksisterende:

```sql
CREATE TABLE IF NOT EXISTS teaching_packages (
    id TEXT PRIMARY KEY,
    year_plan_id TEXT NOT NULL,
    period_id TEXT NOT NULL,
    status TEXT NOT NULL,
    version INTEGER NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_packages_period
    ON teaching_packages(year_plan_id, period_id);
CREATE INDEX IF NOT EXISTS idx_packages_updated
    ON teaching_packages(updated_at DESC);
```

Filer: `OUTPUT_DIR/teaching-packages/<package_id>/v<pkg_version>/<filnavn>`,
skrevet med samme temp + `replace()`-mønster som `store_compendium_artifacts`,
med samme magic-byte-validering (`%PDF`, `PK`) utvidet med `PK` for PPTX.

Én pakke per `(year_plan_id, period_id)` i MVP. Ny versjon av samme pakke
øker `version` og beholder forrige versjons filkatalog.

---

## DEL 3 – ARTEFAKTENE

### 3.1 Generell regel

Hvert artefakt bygges i to trinn:

1. **AI → strukturert innhold.** Kallet får plan + kontrakt og har eksplisitt
   forbud mot å innføre fakta, kilder eller begreper som ikke finnes i planen.
   Svaret valideres mot et `response_schema`, som i `compendium.py`.
2. **Deterministisk renderer → fil.** Ingen layout bygges fra fri AI-tekst.

Trinn 1 kan feile og gi fallback. Trinn 2 skal være rent og testbart: samme
input gir samme bytes (med unntak av tidsstempler, som normaliseres i test).

### 3.2 Presentasjon (`presentation`)

```python
SlidePurpose = Literal[
    "hook", "learning_goal", "activate_prior_knowledge", "explain", "example",
    "source", "visualize", "compare", "timeline", "concept", "discussion",
    "practice", "check_understanding", "summarize", "exit_ticket",
    "section_break", "sources_overview",
]

class SlideVisual(BaseModel):
    kind: Literal["none", "timeline", "comparison", "process", "table",
                  "chart", "image", "concept_map"]
    spec: dict[str, Any] = {}     # deterministisk datamodell, ikke fritekst
    alt_text: str = ""

class Slide(BaseModel):
    order: int
    purpose: SlidePurpose
    lesson_ref: int               # hvilken PlannedLesson slidet hører til
    title: str                    # ≤80 tegn
    content: list[str] = []       # maks 4 linjer, hver ≤120 tegn
    visual: SlideVisual = SlideVisual(kind="none")
    teacher_notes: TeacherNotes = TeacherNotes()
    source_refs: list[str] = []
    accessibility_text: str = ""

class TeacherNotes(BaseModel):
    say: str = ""                 # hva læreren kan si
    point: str = ""               # pedagogisk poeng
    questions: list[str] = []
    expected_response: str = ""
    common_misconception: str = ""
    follow_up: str = ""

class PresentationPlan(BaseModel):
    title: str
    audience: str
    lesson_sequence: list[int]
    slides: list[Slide]
```

`purpose` er en lukket enum. Verdier utenfor kontrakten avvises i validering –
modellen kan ikke finne opp slidetyper.

Strukturregelen er en **mal, ikke en tvang**: rendereren krever at hver økt har
minst `learning_goal`, minst én `explain` eller `example`, minst én
`practice` eller `discussion`, og avsluttes med `summarize`,
`check_understanding` eller `exit_ticket`. Rekkefølgen ellers er fri.
Flere økter → `section_break` mellom dem.

Harde grenser håndhevet deterministisk i rendereren (ikke bare i prompten):

* maks 4 punkter per slide, maks 120 tegn per punkt,
* tittel maks 80 tegn,
* ingen slide uten `purpose`,
* alt som ikke får plass innenfor tekstboksen etter måling (se 5.3) fører til
  `render_failed` med konkret beskjed, ikke til overflow i filen.

### 3.3 Elevark (`student_sheet`)

Arbeidsdokument, ikke slide-kopi:

```
intro (kort), sources[] (fulltekstutdrag eller lenke + hva som skal gjøres),
tasks[] (referanse til tasks-artefaktet der de overlapper),
tables[], concept_work[], note_space[], reflection_questions[]
```

Renderes til PDF (Typst, gjenbruker `markdown_to_typst`) og DOCX
(`build_docx`-mønsteret). Får notatfelt som faktiske linjer/bokser i Typst.

### 3.4 Lærerark (`teacher_sheet`)

Kort og praktisk. Maks to sider – håndheves ved å begrense feltlengder, ikke
ved å be modellen om å være kort:

```
learning_goals, prerequisites, time_plan (per økt: minutter + hva),
materials, recommended_order, key_questions, difficult_concepts,
common_misconceptions, differentiation (støtte/kjerne/fordypning),
assessment_options, sources
```

Ingen fritekst over 600 tegn per felt. Ingen pedagogisk essay-seksjon.

### 3.5 Oppgaver (`tasks`)

Regel fra oppdraget: ikke bygg en ny parallell oppgavearkitektur.

* `subject == "Matematikk"` → **deleger** til MateMaTeX-oppgavemotoren med
  SymPy-verifisert fasit. Pakken lagrer resultatet som artefakt, men eier ikke
  genereringen.
* Ellers → strukturert oppgavesett bundet til planen:
  `{ order, task_type, prompt, learning_goal_ref, concept_refs[],
     source_ref, level: støtte|kjerne|fordypning, expected_answer_sketch }`.
  `task_type` er en enum (`kildeanalyse`, `begrepsforklaring`, `sammenlign`,
  `drøft`, `tidslinje`, `kort_svar`, `flervalg`).

Konsistenskrav: hvert læringsmål i planen må ha minst én oppgave.

### 3.6 Begrepsark (`concept_sheet`)

Trekkes direkte fra `plan.concepts` – **ingen egen AI-generering av
begrepslisten**. AI-kallet får bare lov til å forbedre formuleringene, ikke
legge til eller fjerne begreper. Det gjør C1-konsistenskontrollen (5.1) triviell
å bestå og umulig å omgå.

Språknivå følger `context.language_level` når det er satt.

---

## DEL 4 – API OG FLYT

### 4.1 Endepunkter

Alle under `/api/platform`.

| Metode | Sti | Svar | Merknad |
|---|---|---|---|
| `POST` | `/year-plans/{plan_id}/periods/{period_id}/teaching-packages` | `201 TeachingPackage` | Bygger `context_snapshot` fra perioden. Status `draft`. 409 hvis pakke finnes. |
| `GET` | `/year-plans/{plan_id}/teaching-packages` | `200 TeachingPackageSummary[]` | Til årsplanoversikten. Lett payload. |
| `GET` | `/teaching-packages/{id}` | `200 TeachingPackage` | |
| `PATCH` | `/teaching-packages/{id}/context` | `200 TeachingPackage` | Bare lov i status `draft` eller `needs_revision`. |
| `POST` | `/teaching-packages/{id}/plan` | `202 {job_id}` | Kjører planjobb i `DurableJobGate`. |
| `PATCH` | `/teaching-packages/{id}/plan` | `200` | Lærerredigering av planen. Rekalkulerer `plan_hash` → artefakter merkes `needs_revision`. |
| `POST` | `/teaching-packages/{id}/artifacts` | `202 {job_ids[]}` | Body: `{types: ArtifactType[]}`. Én jobb per artefakt. |
| `POST` | `/teaching-packages/{id}/artifacts/{artifact_id}/regenerate` | `202 {job_id}` | Rører bare dette artefaktet. |
| `PATCH` | `/teaching-packages/{id}/artifacts/{artifact_id}` | `200` | Lærerredigering av `content`. Trigger ny render + konsistenskontroll. |
| `POST` | `/teaching-packages/{id}/approve` | `200 \| 409` | Krever at `quality_status.blocking_reasons` er tom. Setter `approved_by_teacher=True`. |
| `GET` | `/teaching-packages/{id}/artifacts/{artifact_id}/download/{format}` | fil | |
| `GET` | `/teaching-packages/{id}/download` | `application/zip` | Hele pakken. |

Autorisasjon: repoet har i dag ingen brukermodell (bevisst utsatt, jf.
`status.md` pkt. 1). Rutene arver derfor samme regime som kompendiene:
`APP_PASSWORD` / CORS-avgrensning. Det som **skal** håndheves nå er
*eierskapsintegritet*: `artifact_id` må tilhøre `package_id`, og `package_id`
må tilhøre `(plan_id, period_id)`. Dette testes i E-blokken i teststrategien
slik at vi ikke får kryss-pakke-tilgang når autentisering senere kommer på
plass.

### 4.2 Jobbintegrasjon

Dette blir **første plattformflate som bruker `DurableJobGate`**. Mønsteret:

```python
job = queue.enqueue(job_id, module="platform", kind="teaching_package_plan",
                    payload=context, project_id=package.project_id)
# bakgrunnstråd:
with queue.claim(job_id, auto_complete=False):
    ...arbeid...
queue.finish(job_id)   # eller queue.fail(job_id, melding)
```

`auto_complete=False` fordi vi vil skille «AI ferdig» fra «artefakt lagret og
konsistenskontrollert».

`Job.kind` blir `teaching_package_plan` eller
`teaching_artifact:<type>`. Det gir jobbhistorikken nok til instrumenteringen
i del 7 uten en egen jobbtabell.

**Feilisolasjon:** én artefakt = én jobb = én rad. En feilet PPTX-jobb setter
kun det artefaktets status til `generation_failed`/`render_failed`. Pakken og
alle andre artefakter er urørt. Pakkestatusen blir `needs_revision`, aldri
`generation_failed` (den er reservert for planfeil, der ingenting kan bygges).

**Konsekvens av `MAX_CONCURRENT_JOBS=1`:** fem artefakter kjører serielt. Med
grunnede kall på 20–60 sekunder hver blir en full pakke 3–8 minutter. Det er
akseptabelt for en asynkron flyt med synlig progresjon, men gjør synkrone
HTTP-kall utelukket. Se risiko R1.

### 4.3 Frontendflyt

Ny rute: `MateMaTeX/frontend/src/app/teaching-packages/[id]/page.tsx`,
med inngang fra periodekortet i `year-plans/[id]/page.tsx`.

1. Periodekortet får knappen **«Lag undervisningspakke»** i den eksisterende
   «Produser til denne perioden»-boksen. Finnes pakken allerede, viser kortet i
   stedet et sammendrag (versjon, status, hakeliste over artefakter, sist
   oppdatert) og **«Åpne pakken»**.
2. Klikk → pakkeside i status `draft` med kontrakten forhåndsutfylt fra
   perioden, redigerbar, og avkryssingsboksene for artefakter (fem MVP-typer
   avkrysset, reserverte typer synlige men deaktivert med forklaring).
3. **«Lag utkast»** → `POST /plan` → progresjon fra jobb-polling.
4. Planvisning: hva elevene skal lære, progresjon, økter, begreper, kilder,
   faktapass. Læreren kan redigere før artefakter bygges.
5. **«Generer valgte artefakter»** → én rad per artefakt med egen status,
   `[Forhåndsvis] [Rediger] [Generer på nytt]`.
6. Forhåndsvisning viser strukturen (12 slides, 4 sider, 8 oppgaver, 7
   begreper) **før** filene bygges – strukturen ligger i `artifact.content`,
   så det krever ingen filbygging.
7. **«Godkjenn pakken»** er deaktivert så lenge `blocking_reasons` ikke er tom,
   med hver blokkering listet som lesbar tekst.
8. Etter godkjenning: nedlasting av enkeltfiler og ZIP.

Tilgjengelighet (krav fra oppdraget, konkretisert):

* statusrader er `<li>` i en `<ul>` med `<h3>`-overskrift per artefakt –
  riktig headingstruktur, ikke divs;
* status kommuniseres med **ikon + tekst + farge**, aldri farge alene;
* jobbprogresjon i en `aria-live="polite"`-region;
* `[Rediger]` åpner en dialog med `role="dialog"`, `aria-modal`, fokusfelle og
  Escape-lukking;
* alle knapper er `<button>` med synlig `:focus-visible`-ring (finnes allerede
  i `globals.css`-mønsteret);
* animasjoner bak `@media (prefers-reduced-motion: reduce)` – den eksisterende
  `animate-spin`-spinneren må få en statisk fallback.

### 4.4 Årsplanintegrasjon

`GET /year-plans/{id}/teaching-packages` gir per periode:

```
{ period_id, package_id, version, status, artifact_types[],
  quality_summary, updated_at }
```

Frontenden slår dette sammen med planen den allerede har. Ingen endring i
`YearPlan`-modellen, ingen migrasjon.

### 4.5 Bakoverkompatibilitet med `period.materials`

Ved godkjenning kopieres pakkens filer også inn som `YearPlanMaterial` med
riktig `kind` (`presentation`, `worksheet`, `learning_sheet`, `assessment`,
`other`) og `notes` som peker på `package_id`. Grunn: dagens
«grunnpakken er komplett»-logikk og nedlastingsknapper i årsplan-UI leser
`period.materials`, og de skal ikke gå i stykker.

Kostnad: filene finnes to steder. Det aksepteres for MVP og noteres som
ryddeoppgave – riktig fiks er å la `materials` bli en visning over pakker, men
det er en endring i eksisterende, produksjonsverifisert kode og hører ikke
hjemme i denne slicen.

### 4.6 Datamigrasjonsbehov

**Ingen migrasjon av eksisterende data kreves.**

* Ny tabell opprettes idempotent i `_init_schema` (samme mønster som
  `compendia` fikk).
* De fem nye periodefeltene (`prerequisite_knowledge`, `source_context`,
  `differentiation`, `language_level`, `image_mode`) legges på
  `YearPlanPeriod` med defaultverdier. Pydantic fyller dem inn ved lesing av
  gamle payloads – `YearPlan.model_validate_json` på en gammel blob gir
  defaultene. Verifiseres med en test på en lagret payload uten feltene.
* `assessment` beholdes som streng for bakoverkompatibilitet.
  `assessment_plan: list[AssessmentPlanItem]` legges ved siden av; når den er
  tom, parses `assessment`-strengen til ett `AssessmentPlanItem` ved
  snapshotting.
* `MaterialKind` trenger ingen endring – `"presentation"` finnes.
* Ny filkatalog opprettes ved oppstart som `compendia_dir`.

---

## DEL 5 – KVALITET, KONSISTENS OG SANNHET

### 5.1 Konsistenskontroller

Ny modul `platform/package_consistency.py`, deterministisk, ingen AI. Kjøres
etter hver artefaktlagring og på nytt før godkjenning.

| Id | Kontroll | Alvorlighet |
|---|---|---|
| C1 | Hvert begrep i begrepsarket finnes i `plan.concepts`; hvert begrep som introduseres på en `concept`-slide finnes i begrepsarket | blokkerende |
| C2 | Hvert læringsmål i planen står i lærerarket og på minst ett `learning_goal`-slide | blokkerende |
| C3 | Hver `source_ref` i slides/oppgaver/elevark peker på en kilde i `plan.sources` | blokkerende |
| C4 | Hver kilde en `source`-slide ber elevene analysere, finnes eller lenkes i elevarket | blokkerende |
| C5 | Hvert læringsmål har minst én oppgave | advarsel |
| C6 | Ingen artefakttekst inneholder en påstand som faktapasset har i `removed_claims` | blokkerende |
| C7 | Alle artefakter har samme `plan_hash` | blokkerende |
| C8 | Antall økter i presentasjonen ≤ `context.available_lessons` | advarsel |

Begrepssammenligning normaliseres (casefold, trimming, norsk bøyning
håndteres ikke – begrepene kopieres fra samme kilde, så eksakt match er riktig
her og avdekker nettopp de tilfellene der en modell har omskrevet et begrep).

### 5.2 Sannhetspolicy

Én regel: **PowerPoint får ikke sin egen, svakere sannhetsmotor.**

* Faktakontroll skjer **på planen**, ikke per artefakt. `plan.summary`,
  `progression_rationale`, `concepts[].student_explanation`,
  `lessons[].examples` og `misconceptions` settes sammen til én prosatekst som
  sendes til `audit_truth(provided_sources=context.source_context)`.
  Resultatet er pakkens `TruthPassport`.
* Artefaktkall får forbud mot nye faktapåstander, og C6 håndhever det
  maskinelt mot `removed_claims`.
* Godkjenningsporten arver kompendiets terskel: faktapasset må være `verified`
  (≥80 % dokumenterte påstander) for at `blocking_reasons` skal bli tom.
* `_source_quality_notes` fra `compendium.py` gjenbrukes uendret på
  `plan.sources`, slik at Wikipedia/Scribd/søketreff-URL-er blokkerer på samme
  måte her som der.

Grensetilfelle som må håndteres: `audit_truth` avviser tekst under 80 tegn og
over 80 000 tegn. En plan for en kort periode kan være for kort. Da settes
status `not_evaluated`, og godkjenning blokkeres med teksten «Planen er for
kort til maskinell faktakontroll – kontroller innholdet manuelt og bekreft».
Læreren kan ikke overstyre til `verified`.

### 5.3 Layoutkvalitet i PPTX

`python-pptx` måler ikke tekst. Vi trenger derfor en egen deterministisk
tekstestimator: `estimate_text_height(text, font_size, box_width_emu,
font_metrics)` med en konservativ tegnbredde-tabell for den valgte fonten.
Overskrides boksen, feiler renderingen med `render_failed` og en konkret
melding om hvilken slide og hvilket felt. Det er dette som gjør
«ingen tekstvegger» til en test og ikke en intensjon.

Testet i C-blokken: for hvert slide skal `left + width ≤ slide_width - margin`
og estimert teksthøyde ≤ boksens høyde.

### 5.4 Deterministisk filnavngivning

Gjenbruker `safe_filename`-mønsteret fra `compendium_renderer.py:38`
(fjerner alt utenfor `[a-zA-Z0-9æøåÆØÅ_-]`, lowercase, maks 100 tegn):

```
Den-franske-revolusjonen-undervisningspakke.zip
  01-presentasjon.pptx
  02-elevark.pdf
  02-elevark.docx
  03-laererark.pdf
  04-oppgaver.pdf
  05-begrepsark.pdf
  kilder.md
  pakkeinfo.json      # pakke-id, versjon, plan_hash, faktapass, tidsstempel
```

Prefiksene `01`–`05` er faste per artefakttype, slik at ZIP-innholdet er
sorterbart og forutsigbart uavhengig av genereringsrekkefølge.

### 5.5 Designtokens

Ny modul `platform/design_tokens.py`:

```python
@dataclass(frozen=True)
class DesignTokens:
    primary: str        # "#3E8E9B"
    secondary: str      # "#8ED4D8"
    accent: str
    background: str     # "#FFFFFF"
    surface: str
    text: str           # "#1F2933"
    text_muted: str     # "#5A6572"
    border: str         # "#D8DDE5"
    heading_font: str
    body_font: str
    spacing: tuple[int, ...]   # 4,8,12,16,24,32,48
    border_width_pt: float
    slide_margin_emu: int
```

Startverdiene er hentet fra fargene som allerede står i
`compendium_renderer.build_typst_document`, slik at presentasjonen og
dokumentene ser ut som samme produkt fra dag én. Én instans (`DEFAULT_TOKENS`)
konsumeres av PPTX-rendereren, Typst-byggeren og docx-byggeren.

Skoleprofilering senere = bytte tokeninstans. Ingen del av MVP.

### 5.6 Godkjenningsporten

`blocking_reasons` fylles av:

1. et etterspurt artefakt mangler eller har feilstatus,
2. en fil kan ikke åpnes (magic bytes + `Presentation()`/`Document()`-runde,
   for PDF `%PDF`-prefiks),
3. faktapasset er ikke `verified`,
4. en kilde mangler sporbarhet (`_source_quality_notes` gir treff),
5. en blokkerende konsistenskontroll feiler,
6. et artefakt har `render_failed`,
7. `approved_by_teacher` er ikke satt.

Punkt 7 gjør det umulig å nå `approved` uten et eksplisitt lærerkall.

---

## DEL 6 – ADR: PPTX-TEKNOLOGI

**Beslutning: `python-pptx`.**

### Kandidater

| Kriterium | python-pptx | PptxGenJS | Eksisterende `latex_to_pptx` |
|---|---|---|---|
| Passer backend | ✅ Python, som resten | ❌ krever Node i backend-imaget eller en ny tjeneste | ✅ |
| Allerede installert | ✅ `python-pptx>=0.6.23` i imaget | ❌ | ✅ |
| Tabeller | ✅ | ✅ | ikke brukt |
| Bilder | ✅ | ✅ | nei |
| SVG | ❌ må rasteriseres | ❌ samme | nei |
| Speaker notes | ✅ `slide.notes_slide` | ✅ | ✅ (bare fasit) |
| Hyperlenker | ✅ | ✅ | nei |
| Diagram | via egne former/bilder | via egne former/bilder | nei |
| Eksplisitt layoutkontroll | ✅ EMU-presis plassering | ✅ | ❌ bruker malplassholdere |
| Testbarhet | ✅ samme bibliotek leser filen tilbake | ⚠️ krever Node i testkjøringen | delvis |
| Lisens | MIT | MIT | – |
| Vedlikehold | modent, bredt brukt | aktivt | internt |

### Begrunnelse

Avgjørende er at hele sannhets- og kvalitetskjeden er Python i backend. Å
flytte PPTX-bygging til frontend/Node ville skilt filbyggingen fra
faktakontrollen og gitt nettopp den omveien rundt kvalitetskontrollen som
oppdraget forbyr. `python-pptx` er dessuten allerede en verifisert
avhengighet i produksjonsimaget, så valget legger ikke til noe nytt i
deploy-overflaten – det er den minste robuste løsningen.

### Konsekvenser

* **Bruk ikke standardmalens layouts.** `latex_to_pptx` bruker
  `slide_layouts[0]` og `[1]`; det er «Title + bullets»-fellen. Den nye
  rendereren bruker `slide_layouts[6]` (blank) og plasserer hver tekstboks
  eksplisitt fra `DesignTokens.spacing` og et 12-kolonners rutenett.
* **SVG må rasteriseres.** Deterministiske visualiseringer (tidslinje,
  sammenligning, prosess) bygges som SVG, kompileres til PNG @2× via Typst
  (allerede i imaget) og legges inn som bilde. SVG-kilden lagres i
  `artifact.content` slik at vi kan bytte til native vektor senere uten å
  regenerere med AI.
* `latex_to_pptx` og dens tester røres ikke. Matematikkeksporten fortsetter
  uendret.
* Ny modul: `platform/presentation_renderer.py`. Ingen import fra
  `MateMaTeX/backend/app/export/powerpoint.py`.

---

## DEL 7 – INSTRUMENTERING

Ny tabell `analytics_events` (samme JSON-payload-mønster som `feedback`):

```
id, event, package_id, artifact_type, duration_ms, outcome,
regenerated (bool), attempt, created_at
```

Hendelser:

```
teaching_package_started
teaching_package_plan_created
artifact_generated
artifact_regenerated
artifact_edited
artifact_approved
package_approved
package_downloaded
```

Regler:

* **Ingen elev- eller lærerinnhold.** Ingen `topic`, ingen `title`, ingen
  fritekst. Bare id-er, typer, varigheter og utfall. Dette er strengere enn
  `queue._safe_summary`, som lagrer `topic`/`theme` – for analyse trenger vi
  det ikke.
* `outcome` ∈ `{ok, ai_failed, render_failed, consistency_failed, timeout}`.
* `duration_ms` måles rundt jobben, ikke rundt HTTP-kallet.
* `regenerated=True` for hvert artefakt som bygges mer enn én gang i samme
  pakkeversjon – det er hovedmålet på om førsteutkastet faktisk holder.

Spørsmålet instrumenteringen skal svare på: *hvor mange artefakter må læreren
regenerere eller redigere før pakken godkjennes, og hvor lang tid tar hele
reisen?* Uten det tallet vet vi ikke om funksjonen sparer tid.

---

## DEL 8 – TESTSTRATEGI

Detaljert kjøreplan ligger i `research/TEACHING_PACKAGE_EXECPLAN.md`. Her er
dekningskravet.

### A. Domenemodell
* pakke opprettes fra årsplanperiode med korrekt snapshot av alle 15 feltene
* snapshot fryses: endring i perioden etterpå endrer ikke pakken
* gammel `YearPlan`-payload uten de nye periodefeltene validerer med defaults
* versjonering: ny pakkeversjon beholder forrige versjons filer
* alle statusoverganger, inkludert de ulovlige (409)
* regenerering av ett artefakt endrer ikke søsknenes `updated_at`
* `plan_hash` endres ved planredigering → artefakter blir `needs_revision`

### B. Konsistens
* C1–C8, hver med én bestått og én feilende fixture
* læringsmål propagerer til lærerark og slides
* begrep introdusert på slide finnes i begrepsark og brukes i minst én oppgave
* kildeproveniens (`origin=teacher`, `fetch_status=provided`) overlever fra
  `context.source_context` til `plan.sources` til artefaktenes `source_refs`
  til `kilder.md` – samme propagasjonsbevis som i den identiske
  produksjonskjøringen for kompendier
* pakke mister aldri `(year_plan_id, period_id)`

### C. PowerPoint
* gyldig PPTX: `PK`-prefiks og `Presentation(BytesIO(bytes))` åpner filen
* forventet antall slides = `len(plan.slides)`
* ingen slide bruker en layout utenfor den definerte
* geometri: hver form innenfor `slide_width/height` minus marg
* tekstestimat innenfor boksen for hvert tekstfelt
* speaker notes finnes på alle slides der `TeacherNotes` er utfylt
* kildeoversikt finnes som egen slide eller i notes
* determinisme: samme `PresentationPlan` → identiske bytes (tidsstempler
  normalisert i sammenligningen)
* `purpose` utenfor enum avvises i validering

### D. Feil
* PPTX-jobb feiler → elevark, lærerark, oppgaver og begrepsark er urørte og
  beholder statusen sin
* ekstern bildekilde feiler → artefaktet bygges uten bilde (samme
  fallbackmønster som `render_compendium:744-755`)
* AI-kall feiler → deterministisk fallback for plan; `generation_failed` for
  artefakt, aldri en tom fil
* jobb-timeout → `failed` + `retryable`, pakken beholdes
* restart midt i generering → `recover_incomplete_jobs` setter jobben til
  `needs_review`, artefaktet vises som avbrutt og kan prøves på nytt
* regenerering etter feil lykkes uten manuell opprydding

### E. API
* eierskap: artefakt-id fra pakke A mot pakke B → 404
* pakke-id som ikke tilhører oppgitt `(plan_id, period_id)` → 404
* ugyldig `year_plan_id` / `period_id` → 404
* godkjenning med tomme `blocking_reasons` → 200; ellers 409 med lesbar grunn
* nedlasting av artefakt som ikke er bygget → 404
* ZIP inneholder nøyaktig de forventede filnavnene
* dobbel pakkeopprettelse på samme periode → 409

### F. Frontend (Vitest, samme oppsett som de 13 eksisterende testene)
* opprette pakke, velge artefakter, forhåndsvise, generere, se status,
  regenerere, godkjenne, laste ned
* godkjenn-knappen er deaktivert med synlig begrunnelse når noe blokkerer
* status har både ikon, tekst og farge
* tastaturnavigasjon gjennom artefaktlisten og dialogen

### G. Manuell pedagogisk kontroll (kan ikke automatiseres)
Én ekte kjøring av pilotcasen, lest av et menneske med spørsmålet: *henger
dette sammen som ett undervisningsopplegg?* Snapshot- og enhetstester teller
ikke som kvalitetsbevis for dette punktet.

---

## DEL 9 – RISIKOER

| Id | Risiko | Konsekvens | Tiltak |
|---|---|---|---|
| R1 | `MAX_CONCURRENT_JOBS=1` serialiserer fem artefaktjobber | full pakke tar 3–8 min; én lærer blokkerer alle andre | Asynkron flyt med synlig køposisjon fra dag én. Mål faktisk varighet i pilot før vi vurderer å heve grensen. |
| R2 | `audit_truth` er begrenset til 80 000 tegn og krever ≥80 tegn | plan kan falle utenfor i begge ender | Faktakontroll på planen, ikke på summen av artefaktene. Eksplisitt `not_evaluated`-håndtering som blokkerer godkjenning. |
| R3 | `python-pptx` måler ikke tekst | tekstvegger og overflow slipper gjennom | Egen deterministisk tekstestimator + geometritest (5.3, C-blokken). |
| R4 | SQLite med én skriver og flere artefaktjobber | låsekonflikt | `busy_timeout=30000` er allerede satt; `_lock` i `PlatformStore` serialiserer skriving i prosessen. Test med parallelle artefaktjobber. |
| R5 | Årsplanens JSON-blob er last-write-wins | pakke inne i planen ville forverret tapte oppdateringer | Egen tabell (2.6). Ingen pakkedata i `year_plans.payload`. |
| R6 | Dobbeltlagring av filer (pakke + `period.materials`) | forvirring, diskbruk | Bevisst valg for bakoverkompatibilitet (4.5). Notert som ryddeoppgave. |
| R7 | Seks AI-kall per pakke | kostnad og feilrate multipliseres | Ett grunnet kall (planen), fem billigere ikke-grunnede artefaktkall som bare omformer planen. |
| R8 | Modellen finner opp kilder i artefaktkall | brudd på sannhetspolicy | Artefaktkall har ikke søketilgang og kan bare referere `plan.sources` via id. C3 håndhever det. |
| R9 | Produksjonsgaten er `REJECTED` | ny funksjon kan skjule uløste feil | Ingen implementering før gaten er lukket. Denne planen leveres som dokument. |
| R10 | Plattformrutene har ingen autentisering ennå | pakker er tilgjengelige for alle med API-adressen | Samme regime som kompendiene i dag; eierskapsintegritet testes nå slik at senere auth kan slås på uten omskriving. |
| R11 | Ingen frontend-lint (ESLint-konfig mangler, jf. `status.md`) | ny frontendkode får svakere kontroll | Nevnes i ExecPlan; ikke en blokker for denne funksjonen, men bør rettes. |

---

## DEL 10 – ÉN KONKRET VERTIKAL MVP

**Pilotcase: Historie VG2, «Den franske revolusjonen 1789–1799», tre
undervisningsuker.**

Valget er ikke tilfeldig: `evaluations/history_vg2/french_revolution_1789_1799/`
inneholder allerede `input.json` med lærer-URL-er (SNL, Britannica, Udir),
kompetansemål, differensieringsprofil, `sources.json`, `rubric.md` og
`expected_structure.json`. Det er samme case som produksjonshendelsen ble
diagnostisert på, så vi kan sammenligne kildepropagasjon direkte mot et kjent
resultat.

Slicen skal levere, ende til ende:

1. Årsplan for Historie VG2 med en periode uke 38–40.
2. «Lag undervisningspakke» → kontrakt forhåndsutfylt fra perioden, med de tre
   lærer-URL-ene i `source_context`.
3. Én `TeachingPackagePlan` med tre økter, 7 begreper og faktapass.
4. Fem artefakter fra samme plan: presentasjon, elevark, lærerark, oppgaver,
   begrepsark.
5. Alle åtte konsistenskontroller kjørt og synlige.
6. Eksplisitt lærergodkjenning som faktisk kan blokkeres.
7. Nedlasting av enkeltfiler og ZIP.
8. Manuell lesing av hele pakken med spørsmålet fra G-blokken.

Ikke i slicen: batch over flere perioder, quiz, prøve, fasit, kildesamling,
tidslinjeartefakt, matematikkaktivitet, språktilpasset versjon, hjemmearbeid,
fordypningsoppgave, LMS, Google Slides, samarbeid, skolebranding,
gjenbruksbibliotek.

**Gjenbruk til nytt skoleår** er forberedt i datamodellen –
`context_snapshot` og `plan` er selvstendige og inneholder ingen
plan-id-avhengigheter utover `year_plan_id`/`period_id`, så en kopieringsrutine
kan lages senere ved å skrive en ny pakke med ny periodekobling og samme
innhold. Rutinen bygges ikke nå.

---

## Åpne spørsmål til eier

1. **Skal pakkegodkjenning kreve grønt faktapass, eller skal læreren kunne
   godkjenne med dokumentert forbehold?** Planen antar grønt kreves, som for
   kompendier. Det er strengt og vil blokkere pakker der planen er for kort
   for maskinell kontroll.
2. **Skal filene dobbeltlagres i `period.materials` (4.5)?** Anbefalingen er ja
   for MVP, for å ikke bryte dagens årsplan-UI.
3. **Er tre til åtte minutter per pakke akseptabelt** med dagens
   `MAX_CONCURRENT_JOBS=1`, eller skal vi heve grensen før pilot?
