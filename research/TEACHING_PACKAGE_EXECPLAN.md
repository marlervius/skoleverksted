# Undervisningspakke – ExecPlan

> Status: **VENTER PÅ GODKJENNING – INGEN KODE SKREVET**
> Skrevet: 8. august 2026
> Gren: `claude/teaching-package-architecture-bzs4yk`
> Arkitektur: `research/TEACHING_PACKAGE_ARCHITECTURE.md`
> Blokkert av: `research/PRODUCTION_VERIFICATION_REPORT.md` – dom **REJECTED**

Dette er kjøreplanen. Hver milepæl har eksplisitt omfang, konkrete filer,
kjørbare tester og en «ferdig når»-definisjon. Ingen milepæl er ferdig før
testene faktisk er kjørt og resultatet er skrevet inn i loggen nederst.

---

## Portregel

Implementering starter **ikke** før én av disse er sanne:

1. `research/PRODUCTION_VERIFICATION_REPORT.md` har dom `ACCEPTED`, eller
2. eieren ber eksplisitt om parallellarbeid.

Begrunnelse: gaten står på `REJECTED` med tre åpne funn – faktapass på 73 %
mot kravet 80 %, HTTP 504 på kompendiumreparasjon, og en kandidat som aldri er
deployet. Undervisningspakken arver hele sannhetskjeden fra nettopp denne
koden. Å bygge oppå en åpen gate ville gjort det umulig å si om et nytt
faktaproblem kommer fra pakken eller fra det uløste.

Én ting kan gjøres uten å røre gaten, om eieren vil ha framdrift nå:
**M0** under er ren dokumentasjon og fixtures, og deler ingen kodebaner med
produksjonsflyten.

---

## Milepæler

### M0 – Kontrakt og fixtures (kan kjøres før gaten lukkes)

**Omfang:** ingen produksjonskode. Bare testdata og en frosset kontrakt.

* `evaluations/history_vg2/french_revolution_1789_1799/teaching_package/`
  * `context.json` – forventet `TeachingPackageContext` snapshottet fra
    pilotperioden
  * `plan.golden.json` – håndskrevet, faglig gjennomlest `TeachingPackagePlan`
    med tre økter og sju begreper
  * `presentation.golden.json` – `PresentationPlan` avledet av planen
  * `consistency_cases.json` – for hver av C1–C8 ett bestått og ett feilende
    eksempel
* `research/TEACHING_PACKAGE_CONTRACT.md` – JSON-skjemaene som frosset
  kontrakt, slik at prompt og renderer kan utvikles mot samme sannhet

**Ferdig når:** en fagperson har lest `plan.golden.json` og bekreftet at det er
et undervisningsopplegg hun ville brukt. Dette er kvalitetsankeret for alt
under – uten et godt gullstandard-eksempel har vi ingenting å måle
AI-utkastet mot.

---

### M1 – Domenemodell og lagring

**Filer:**
* `Skoleverksted/backend/platform/models.py` – nye modeller fra
  arkitekturdokumentet del 2, samt fem nye felter på `YearPlanPeriod` med
  defaults
* `Skoleverksted/backend/platform/store.py` – `teaching_packages`-tabell,
  CRUD, filkatalog, `snapshot_period_context()`
* `Skoleverksted/backend/tests/test_teaching_package_store.py`

**Ikke i denne milepælen:** ingen AI, ingen rendering, ingen HTTP.

**Tester (A-blokken):** snapshot av alle 15 kontraktfelter, frysing,
versjonering, statusoverganger inkludert ulovlige, `plan_hash`-invalidering,
og en gammel `YearPlan`-payload uten de nye feltene som validerer med
defaults.

**Ferdig når:** hele backend-suiten er grønn og de nye testene dekker A-blokken.

---

### M2 – Designtokens og deterministiske renderere

**Filer:**
* `platform/design_tokens.py`
* `platform/presentation_renderer.py` – `PresentationPlan → PPTX`, blank
  layout, eksplisitt EMU-geometri, tekstestimator
* `platform/package_renderer.py` – elevark/lærerark/oppgaver/begrepsark til
  PDF (Typst) og DOCX, gjenbruker `markdown_to_typst` og `build_docx`-mønsteret
* `Skoleverksted/backend/tests/test_presentation_renderer.py`
* `Skoleverksted/backend/tests/test_package_renderer.py`

**Fortsatt ingen AI.** Rendererne mates fra `*.golden.json` fra M0. Det er
poenget: PPTX-kvaliteten kan bevises helt uten modellkall.

**Tester (C-blokken):** gyldig PPTX, antall slides, geometri innenfor marger,
tekstestimat innenfor bokser, speaker notes til stede, kildeslide, determinisme
(samme input → identiske bytes), avvisning av ukjent `purpose`.

**Ferdig når:** `presentation.golden.json` gir en PPTX som et menneske åpner i
PowerPoint/LibreOffice og bedømmer mot designstandarden i oppdraget. Manuell
visuell kontroll er et krav her, ikke en bonus – ingen automatisk test fanger
«ser dette ut som noe en god lærer ville brukt».

---

### M3 – Plangenerering med sannhetskontroll

**Filer:**
* `platform/teaching_package.py` – `plan_teaching_package(context)`, ett
  grunnet Google-kall med `response_schema`, deterministisk fallback etter
  mønsteret i `year_planner.build_year_plan`
* integrasjon mot `audit_truth`, `inspect_markdown`, `_source_quality_notes`
* `Skoleverksted/backend/tests/test_teaching_package_plan.py`

**Tester:** AI-feil → deterministisk fallbackplan, ikke tom plan.
Kildeproveniens fra `context.source_context` til `plan.sources` med
`origin=teacher`/`fetch_status=provided`. For kort plan → `not_evaluated` og
blokkert godkjenning. Svak kilde → blokkering.

**Ferdig når:** ett ekte kall mot `gemini-3.5-flash` med pilotkonteksten
produserer en plan som sammenlignes manuelt mot `plan.golden.json`. Er avviket
stort, er det prompten som skal rettes, ikke gullstandarden.

---

### M4 – Artefaktgenerering og konsistens

**Filer:**
* `platform/teaching_package.py` – `generate_artifact(package, type)` for de
  fem MVP-typene, uten søketilgang, bundet til planen
* `platform/package_consistency.py` – C1–C8
* `Skoleverksted/backend/tests/test_package_consistency.py`
* `Skoleverksted/backend/tests/test_teaching_artifacts.py`

**Tester (B-blokken):** alle åtte kontroller med bestått og feilende fixture
fra M0. Begrep introdusert på slide finnes i begrepsark og brukes i oppgave.
Kilde en slide ber om analyse av, finnes i elevark. Ingen artefakt inneholder
en påstand fra `removed_claims`.

**Ferdig når:** alle fem artefakter bygges fra pilotplanen og C1–C8 passerer.

---

### M5 – Jobber, API og feilisolasjon

**Filer:**
* `platform/router.py` – de elleve endepunktene fra arkitekturdokumentet 4.1
* jobbintegrasjon mot `DurableJobGate` med `auto_complete=False`
* `Skoleverksted/backend/tests/test_teaching_package_api.py`

Dette er første plattformflate som bruker den varige jobbkøen. Kompendiene
gjør det fortsatt ikke; det er en kjent gjeld og ikke en del av denne slicen.

**Tester (D- og E-blokken):** PPTX-feil lar de fire andre artefaktene være
urørt. Bildefeil → bygg uten bilde. AI-feil, timeout, restart-recovery.
Eierskapsintegritet på tvers av pakker. 409 ved dobbel opprettelse. ZIP med
nøyaktig forventede filnavn.

**Ferdig når:** en simulert PPTX-feil midt i en femartefaktkjøring etterlater
fire grønne artefakter og én med synlig feilstatus som kan prøves på nytt.

---

### M6 – Frontend

**Filer (alle i `MateMaTeX/frontend/src/`):**
* `lib/platform-api.ts` – typer og kall
* `app/teaching-packages/[id]/page.tsx` – kontrakt, plan, artefaktliste,
  forhåndsvisning, godkjenning, nedlasting
* `app/year-plans/[id]/page.tsx` – «Lag undervisningspakke» / «Åpne pakken» og
  pakkesammendrag på periodekortet
* `__tests__/teaching-package.test.tsx`

**Tester (F-blokken):** hele flyten, deaktivert godkjenn-knapp med synlig
begrunnelse, status med ikon + tekst + farge, tastaturnavigasjon.

Tilgjengelighetskravene fra arkitekturdokumentet 4.3 er akseptansekriterier,
ikke etterarbeid.

**Ferdig når:** Vitest-suiten, typekontroll og produksjonsbygg er grønne.

---

### M7 – Vertikal pilot og kvalitetsgate

Ingen ny kode utover feilretting.

1. Full kjøring av pilotcasen mot ekte modell, i Docker-imaget.
2. Alle fem filer åpnes manuelt.
3. Pakken leses som ett undervisningsopplegg og bedømmes mot
   `rubric.md`-spørsmålet fra G-blokken.
4. Konsistens verifiseres for hånd, ikke bare av C1–C8: sier presentasjonen og
   elevarket faktisk det samme?
5. Instrumenteringstall registreres: antall regenereringer, total varighet.
6. Resultatet skrives inn i loggen nederst i dette dokumentet – også hvis det
   er dårlig.

**Ferdig når:** en historielærer kan bruke pakken i en time uten å skrive om
innholdet. Ikke før.

---

## Rekkefølge og avhengigheter

```
M0 ──> M1 ──> M2 ──> M3 ──> M4 ──> M5 ──> M6 ──> M7
        │      │              │
        └──────┴──────────────┘   M2 og M3 kan gå parallelt etter M1
```

M2 før M3 er et bevisst valg: rendererne kan bevises på gullstandarden helt
uten AI, så vi vet at kvalitetsproblemer senere kommer fra planen og ikke fra
filbyggingen.

---

## Testkommandoer

```bash
# Backend, i imaget (samme runtime som produksjon)
docker compose run --rm backend python -m pytest Skoleverksted/backend/tests -q

# Bare de nye
docker compose run --rm backend python -m pytest \
  Skoleverksted/backend/tests/test_teaching_package_store.py \
  Skoleverksted/backend/tests/test_presentation_renderer.py \
  Skoleverksted/backend/tests/test_package_renderer.py \
  Skoleverksted/backend/tests/test_teaching_package_plan.py \
  Skoleverksted/backend/tests/test_package_consistency.py \
  Skoleverksted/backend/tests/test_teaching_artifacts.py \
  Skoleverksted/backend/tests/test_teaching_package_api.py -q

# Full suite (basislinje 403 bestått, 2 hoppet over per commit 912007b)
docker compose run --rm backend python -m pytest -q

# Frontend
cd MateMaTeX/frontend && npm test && npx tsc --noEmit && npm run build
```

Regresjonskrav: full backend-suite skal ikke gå ned fra 403 bestått, og
frontendens 13 eksisterende tester skal fortsatt bestå.

---

## Definisjon av ferdig for hele funksjonen

Funksjonen er ikke ferdig før alle disse er sanne:

- [ ] alle nødvendige filer eksisterer og kan åpnes programmatisk
- [ ] faktakontroll er bestått etter gjeldende policy, ikke en ny og svakere
- [ ] alle kilder er sporbare fra kontrakt til `kilder.md`
- [ ] ingen konsistenskontroll feiler
- [ ] ingen layoutfeil i PPTX, verifisert både maskinelt og visuelt
- [ ] læreren har godkjent eksplisitt, og godkjenning kunne blitt blokkert
- [ ] én feilet artefakt ødelegger ikke pakken
- [ ] instrumenteringen viser faktisk tidsbruk
- [ ] den komplette lærerreisen fra årsplan til nedlastet ZIP er demonstrert
      på ekte data, ikke bare i tester

---

## Utenfor omfang

Ikke bygg i denne funksjonen: automatisk generering av hele årsplanens
materiell, batch over flere perioder, LMS-integrasjon, Google Slides,
samarbeid mellom lærere, marketplace, elevkontoer, presentasjon direkte til
elev, avansert skolebranding, AI-avatar, video, animasjonsmotor, nye generelle
agentrammeverk, gjenbruksbibliotek for nytt skoleår.

Kjent gjeld som **ikke** ryddes her, men bør noteres:

* kompendiumrutene bruker fortsatt ikke `DurableJobGate`
* `JobTelemetryMiddleware` ser fortsatt ikke plattformruter
* filer dobbeltlagres i `period.materials` (bevisst, se arkitektur 4.5)
* frontend-lint er ikke operativ (ESLint-konfig mangler)
* `Skoleverksted/frontend` er tom mens appen ligger i `MateMaTeX/frontend`

---

## Logg over faktiske resultater

Fylles ut etter hver milepæl. Skriv det faktiske utfallet, også når det er
dårlig.

| Milepæl | Dato | Commit | Testresultat | Faktisk utfall |
|---|---|---|---|---|
| M0 | – | – | – | ikke startet |
| M1 | – | – | – | ikke startet |
| M2 | – | – | – | ikke startet |
| M3 | – | – | – | ikke startet |
| M4 | – | – | – | ikke startet |
| M5 | – | – | – | ikke startet |
| M6 | – | – | – | ikke startet |
| M7 | – | – | – | ikke startet |
