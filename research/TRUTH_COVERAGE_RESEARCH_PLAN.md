# Truth coverage — forskningsplan

**Status:** `BLOCKED`. **Ikke aktivert. Ingen kode. Ingen policyendring.**

**Opprettet:** 2026-08-08

> ## Undersøkelsesgate: LUKKET
>
> Dette er en forskningsplan, ikke en arbeidsordre og ikke en
> implementeringsplan. Den åpnes bare ved eksplisitt beslutning, og tidligst
> etter at den eksisterende production verification gate er lukket.

Utspring: risiko `TRUTH-COVERAGE-01` i
[TEACHING_PACKAGE_ARCHITECTURE.md](research/TEACHING_PACKAGE_ARCHITECTURE.md)
punkt 6.1 og
[TEACHING_PACKAGE_EXECPLAN.md](research/TEACHING_PACKAGE_EXECPLAN.md) punkt 8.1.

---

## 1. Hva som ikke skal skje

Disse gjelder uavhengig av hva undersøkelsen senere måtte finne. De er
forutsetninger for at planen i det hele tatt finnes.

- **Ikke endre nåværende 80 %-policy.** Terskelen i
  [truth.py:472](Skoleverksted/backend/platform/truth.py:472) står.
- **Ikke implementere weighted claims.**
- **Ikke implementere criticality scoring.**
- **Ikke endre truth engine.**
- Ikke innføre `unknown`-as-pass, teacher bypass eller silent fallback som
  omvei rundt gaten.

En eventuell endring av metrikk eller terskel er en **egen beslutning etter**
undersøkelsen, ikke en del av den.

---

## 2. Utgangspunktet

`PRODUKSJONSBEVIST`,
[PRODUCTION_VERIFICATION_REPORT.md:118](research/PRODUCTION_VERIFICATION_REPORT.md:118),
identisk produksjonsscenario på baseline `69b00d81e5a7`:

| Måling | Verdi |
|---|---|
| Claims | 44 |
| Verified | 32 |
| Coverage | 73 % |
| Terskel for `verified` | 80 % |

Per kapittel: 100 % / 62 % / 56 %.

To ting må holdes fra hverandre i enhver senere analyse:

1. **73 % er et aggregat.** Gaten evalueres per artefakt/kapittel, ikke på
   aggregatet. Spredningen 56–100 % er selve fenomenet.
2. **80 % er nødvendig, men ikke tilstrekkelig.** Samme betingelse krever også
   minst én konkret validert kilde og `not unresolved_edits`
   ([truth.py:465-475](Skoleverksted/backend/platform/truth.py:465)). Et
   ikke-grønt pass er derfor ikke automatisk et dekningsproblem.

Motstridende evidens som må med i utgangspunktet, ikke skjules: samme rapport
måler kandidaten `ff725bb69978` til 42/48 = 88 % med per-kapittel 87/85/92
([PRODUCTION_VERIFICATION_REPORT.md:256-261](research/PRODUCTION_VERIFICATION_REPORT.md:256)).
Om 73 % er representativt eller et baseline-artefakt er et av spørsmålene
under, ikke en avklart forutsetning.

---

## 3. Spørsmål undersøkelsen senere kan stille

Ingen av disse er besvart. Rekkefølgen er ikke en prioritering.

| # | Spørsmål |
|---|---|
| Q1 | Hvorfor blir claims `unverifiable`? Fordelingen av årsaker, ikke bare antallet. |
| Q2 | Source retrieval failures — hvor stor andel av ikke-verifiserte claims skyldes at kilden ikke ble hentet, ikke at påstanden er gal? |
| Q3 | Claim granularity — genererer motoren mange små claims der én dekkende ville vært riktigere, eller omvendt? |
| Q4 | Duplicate/overlapping claims — teller samme faktum flere ganger mot nevneren? |
| Q5 | Claims som er tolkninger snarere enn faktiske påstander — hvor mange, og bør de i det hele tatt inngå i et faktaregister? |
| Q6 | Teacher-provided source coverage — hvor mye av dekningen avhenger av hvilke kilder læreren la inn? |
| Q7 | Evidence matching quality — er evidensen faktisk lest og matchet, eller matchet på overflate? |
| Q8 | Bør alle claims bidra likt til dekning? |
| Q9 | Critical versus non-critical claims — finnes det en meningsfull, deterministisk skillelinje, eller bare en gradvis? |
| Q10 | False positives og false negatives — hvor ofte er `verified` galt, og hvor ofte er `unsupported` galt? |
| Q11 | Er 80 % rå dekning riktig langsiktig metrikk i det hele tatt? |

Q10 er den som betyr mest for tilliten til produktet. En høyere dekningsgrad
oppnådd med flere false positives er en forverring, ikke en forbedring, og en
undersøkelse som bare måler dekning kan ikke se forskjellen.

---

## 4. Hva som må være på plass før planen kan aktiveres

| # | Forutsetning |
|---|---|
| F1 | Den eksisterende production verification gate er lukket. |
| F2 | Et datagrunnlag som er større enn ett kompendium og én kjøring. Én observasjon kan ikke bære en metrikkendring. |
| F3 | Manuell faglig fasit på et utvalg claims, slik at Q10 kan besvares. Uten fasit måler man bare motoren mot seg selv. |
| F4 | Eksplisitt beslutning om å åpne gaten. |

---

## 5. Hva et resultat kan være

Planen forplikter ikke til noe utfall. Legitime konklusjoner inkluderer:

- 80 % rå dekning er riktig metrikk og beholdes uendret;
- dekningsproblemet er i hovedsak et retrieval-problem og løses uten å røre
  metrikken;
- claim-registeret bør avgrenses til faktiske påstander, som endrer nevneren
  uten å endre terskelen;
- metrikken bør endres — som da er en **ny beslutning** med egen begrunnelse,
  eget evidenskrav og egen gate.

Utfallet «senk terskelen fordi produktet ellers ikke blir brukbart» er
eksplisitt ikke et legitimt resultat av denne undersøkelsen. Det er avgjort i
B6.

---

## 6. Beslutningslogg

| Dato | Beslutning | Kilde |
|---|---|---|
| 2026-08-08 | Planen opprettet som `BLOCKED` forskningsoppgave, ikke implementasjon | brukerbeslutning, B8 |
| 2026-08-08 | 80 %-policy, weighted claims, criticality scoring og truth engine er urørt | brukerbeslutning, B6 |
