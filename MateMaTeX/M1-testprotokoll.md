# M1 — Verifikasjonstest for MateMaTeX

**Tilhørende grunnloven §1 og kap. 10 (milepæl M1)**
Apexlab (Lervik KI-Tech ENK) · 18. juni 2026

---

## 0. Hva M1 svarer på

Grunnloven sier at «verifisert fasit» er vollgraven, og at M1 skal testes **før noe annet bygges**. Utviklingen har nå bygd håndhevingsapparatet (blokkering, merking, cache) — men ingen har målt tallet apparatet håndhever. M1 lukker det gapet.

M1 svarer på to spørsmål, i rekkefølge:

1. **Holder løftet?** For et representativt sett 1T- og R1-oppgaver: hvor stor andel (poengvektet) kan faktisk få det grønne merket «SymPy-verifisert»?
2. **Hvilket nivå lanseres først?** 1T eller R1 — avgjort av tallet, ikke av magefølelse (grunnloven kap. 12).

Resultatet mates tilbake i grunnloven kap. 10 (M1 bestått/ikke) og setter `LAUNCH_GRADES` til vinneren.

---

## 1. Den sentrale innsikten — to slags «ikke grønn»

En naiv test teller bare «verifiserbar / ikke». Det skjuler den viktigste distinksjonen, og den må M1 fange:

- **Genuint uverifiserbart** — SymPy kan i prinsippet ikke sjekke det (bevismetode, tolkning, modelloppsett). Fiks: hold det utenfor scope, eller merk ærlig. *Strukturelt tak.*
- **Falsk negativ** — svaret *er* riktig og sjekkbart, men verifikatoren bommer (annen men ekvivalent form, `simplify` gir opp, +C på integral, ± på røtter). Fiks: bedre verifikator. *Fiksbart tak.*

Hvis dekningen er lav fordi for mye er **falske negativer**, er det ikke et SymPy-problem — det er en skjørhet i sjekken din, og den kan fikses. Hvis den er lav fordi for mye er **genuint uverifiserbart**, må scope eller nivå endres. Disse to har helt ulik konsekvens. En test som ikke skiller dem, gir deg feil beslutning.

Derfor skåres hver deloppgave i **fire** utfall, ikke to:

| Utfall | Betydning | Teller som |
|---|---|---|
| `verified` | Sjekkbart, og verifikatoren bekreftet | Grønn |
| `false_negative` | Sjekkbart og riktig, men verifikatoren klarte ikke bekrefte | Fiksbart tak |
| `unverifiable` | SymPy kan i prinsippet ikke sjekke dette | Rødt (strukturelt) |
| `mismatch` | Verifikatoren fant en faktisk fasitfeil | Rødt (og §1-blokkering — bra!) |

«Realistisk tak» = `verified` + `false_negative`. Det er taket du kan nå hvis du gjør verifikatoren robust nok. «Grønn nå» er der du står i dag.

---

## 2. Metode — to lag

**Lag A · A priori-dekning (kveldsøkt, ingen kode).** Gå gjennom oppgavetype-taksonomien i kap. 4 og bekreft/korriger dommen for hvert nivå. Dette gir en hypotese og fanger åpenbare hull tidlig.

**Lag B · Empirisk dekning (selve M1).** Ta **ekte oppgaver**, la pipelinen (eller referansesjekken) produsere fasit, kjør verifikatoren, og skår hver deloppgave i ett av de fire utfallene. Dette er tallet som teller, fordi det måler hva koden *faktisk* gjør — ikke hva SymPy teoretisk kan.

Lag A uten Lag B er ønsketenkning. Lag B er M1.

---

## 3. Datagrunnlag

- **Kilde:** ekte eksamenssett fra Udir (eksamensoppgaver i 1T og R1 er offentlige). Disse er den hardeste, mest representative testen — de er poengsatte og dekker hele pensumbredden.
- **Mengde:** minst **3 hele sett per nivå** (Del 1 + Del 2), ≈ 40–60 deloppgaver per sett → 120–180 skårede deloppgaver per nivå. Nok til et stabilt prosenttall.
- **Vekting:** vekt etter **poeng**, ikke antall oppgaver. En 6-poengs modelleringsoppgave skal telle mer enn en 2-poengs regneoppgave. Skjemaet gjør dette automatisk.
- **Ærlig fotnote:** eksamen er tyngre på modellering/bevis enn et typisk arbeidsark. Siden MateMaTeX også lager arbeidsark (mer regnetunge), er det eksamensvektede tallet et **konservativt gulv** — den reelle dekningen for arbeidsark blir høyere. Bra: du tester mot det vanskeligste.

---

## 4. Oppgavetype-taksonomi (Lag A — schema å skåre mot)

Dom: **Full** = endelig svar SymPy-sjekkbart · **Delvis** = beregningen sjekkbar, men oppsett/argument er skjønn · **Ingen** = ikke SymPy-sjekkbart.

### 1T (VG1)

| Emne | Oppgavetype | Dom | Mekanisme | Felle å passe på |
|---|---|---|---|---|
| Algebra | faktorisering, brøk, kvadratsetn. | Full | `simplify(a-b)==0` | ulik form ≠ feil |
| Likninger | lineær, andregrad, sett | Full | `solve` / `linsolve`, sammenlign mengde | ±, dobbeltrot |
| Likninger | rasjonal, eksp./log | Full | `solve` | falske røtter (domene) må lukes |
| Funksjoner | nullpunkt, skjæring, topp/bunn | Full | `solve(f)`, `solve(f')` | — |
| Derivasjon | polynom, enkel | Full | `diff` | — |
| Optimering | anvendt ekstremalverdi | Delvis | `diff`+`solve` på oppsatt f | **oppsett fra tekst er skjønn** |
| Geometri | rettvinklet trig, sinus-/cosinussetn., areal | Full | numerisk sammenligning | avrunding, grader/radianer |
| Sannsynlighet | kombinatorikk, enkel ssh. | Full | `binomial`, beregning | **modellvalg/oppsett er skjønn** |
| Modellering | tekst → funksjon/modell | Delvis–Ingen | beregning ja, oppsett nei | — |
| Tolkning | «forklar», «tolk», «vurder» | Ingen | — | — |
| Graf | skisse/tegning | Ingen* | — | *nøkkelpunkter (nullpunkt, ekstremal) kan sjekkes separat |

### R1 (VG2)

| Emne | Oppgavetype | Dom | Mekanisme | Felle |
|---|---|---|---|---|
| Algebra | polynomdivisjon, faktorteorem | Full | `div`, `rem`, `factor` | — |
| Funksjoner | rasjonal/eksp./log-likninger | Full | `solve` | domene |
| Grenseverdier | grense, kontinuitet | Full | `limit` (ev. ensidig) | ±∞, ensidige |
| Derivasjon | produkt-, kvotient-, kjerneregel | Full | `diff` | — |
| Funksjonsdrøfting | ekstremal, vendepunkt, asymptoter | Full | `solve(f')`, `solve(f'')`, `limit` | fortegnsskjema-*fremstillingen* er Delvis |
| Vektorer | skalarprodukt, lengde, vinkel, parallell/ortogonal | Full | symbolsk | — |
| Vektorer | geometrisk resonnement («vis at … ligger på linje») | Delvis | påstand sjekkbar, argument ikke | — |
| Sannsynlighet | betinget, Bayes, kombinatorikk | Full | beregning gitt modell | **modelloppsett er skjønn** |
| «Vis at» | algebraisk identitet | Delvis→Full | `simplify(VS−HS)==0` bekrefter målet | beviset *som metode* graderes ikke |
| Bevis | direkte, kontrapositiv, induksjon | Ingen | hvert algebrasteg kan sjekkes, men ikke strukturen | — |
| Logikk | implikasjon, ekvivalens | Ingen | — | — |

**Hypotesen som følger av taksonomien:** 1T er mer uniformt Full; R1 har en reell tung blokk (bevis, logikk, vektorresonnement) som er Delvis/Ingen — og bevis er *eksplisitt vektlagt i R1-læreplanen*. Forvent at 1T skårer høyere på grønn dekning. M1 skal bekrefte med tall.

---

## 5. Skåringsrubrikk (Lag B)

For hver deloppgave:

1. La pipelinen/modellen produsere fasit (det endelige svaret + ev. mellomregning).
2. Kjør verifikatoren (`answer_check` i `m1_scorer.py`, eller din egen pipeline-sjekk).
3. Skår:
   - Bekreftet riktig → `verified`
   - Verifikatoren sa UNCERTAIN/feil, men du sjekket manuelt at svaret *er* riktig og sjekkbart → `false_negative`
   - Ingenting å sjekke (bevismetode, tolkning, oppsett) → `unverifiable`
   - Verifikatoren fanget en ekte fasitfeil → `mismatch`
4. Før inn én rad i `m1_skjema.csv`.

`mismatch` er ikke en fiasko for M1 — det er §1 som virker. Men noter dem: hyppig `mismatch` betyr at modellen lager mye gal matte, som er et eget problem (modell/prompt), uavhengig av dekning.

---

## 6. Terskler og handling

Poengvektet **grønn nå** per nivå:

| Bånd | Tolkning | Handling |
|---|---|---|
| **≥ 75 %** | Løftet holder klart | Lanser på nivået. Pitch: «fasit maskinelt verifisert». |
| **60–74 %** | Holder, men ikke for alt | Lanser, men **snevre temavalget** til høy-dekningsemnene, eller hev verifikatoren (se realistisk tak) først. Pitch: «verifisert på kjernepensum». |
| **45–59 %** | Grenseland | Fungerer bare med ærlig, snevrere posisjonering («for algebra, funksjoner og derivasjon»). Vurder om smerten/betalingsviljen rettferdiggjør det. |
| **< 45 %** | §10-drepekriteriet slår inn for nivået | Omdefiner til den verifiserbare kjernen, eller velg det andre nivået. Ikke lat som. |

**Sjekk alltid avstanden grønn-nå → realistisk-tak.** Er den stor (mye `false_negative`), er løsningen å fikse verifikatoren — billig og høy gevinst — ikke å skrote nivået.

---

## 7. 1T-vs-R1 — beslutningsregel

Velg nivået som maksimerer **grønn dekning × smerte/betalingsvilje**.

- Smerten er høyest i R1 (notasjon, vektorer, drøfting — der gratisverktøy feiler mest), jf. grunnloven kap. 8.
- Men dekningen er trolig høyest i 1T.
- **Ved tvil, vekt dekning tyngst.** Vollgraven *er* den verifiserte fasiten. Et nivå med 80 % dekning og middels smerte slår et nivå med 55 % dekning og høy smerte — for på 55 % undergraver du ditt eget kjernebudskap hver gang halve arket havner under «lærerkontroll».

Skriv den endelige avgjørelsen inn i grunnloven kap. 12 (lukk det åpne spørsmålet) og kap. 13 (endringslogg).

---

## 8. Prosedyre — steg for steg

1. **Lag A:** les kap. 4, korriger taksonomien om du er uenig i en dom. (~1 time)
2. Last ned 3 eksamenssett per nivå fra Udir.
3. **Lag B:** for hver deloppgave, kjør pipeline/verifikator og skår etter kap. 5. (~en kveld per nivå)
4. Fyll `m1_skjema.csv` (én rad per deloppgave).
5. Kjør `python3 m1_scorer.py m1_skjema.csv`.
6. Les av grønn-nå, realistisk-tak og per-emne-tabellen.
7. Anvend tersklene (kap. 6) og beslutningsregelen (kap. 7).
8. Oppdater grunnloven (kap. 10, 12, 13) og sett `LAUNCH_GRADES`.

---

## 9. Filene

- **`m1_scorer.py`** — referanseimplementasjon. `answer_check(fasit, kandidat, mode)` gjør robust ekvivalenssjekk (`mode`: `expr`, `integral` for «opp til konstant», `set` for løsningsmengder). Håndterer ulik form, implisitt multiplikasjon, og — viktig — vakt mot at fri prosa («vis at …») feiltolkes som et symbolprodukt og gir falsk `mismatch`. Kjør uten argument for hjelp; med CSV-sti for rapport.
- **`m1_skjema.csv`** — tomt skjema (kun kolonneoverskrifter) du fyller.
- **`m1_skjema_eksempel.csv`** — utfylt med dummy-rader så du ser formatet og rapporten. **Slett før du fyller ekte data.**

Referansesjekken er bevisst **frikoblet fra pipelinen** — M1-tallet skal måles uavhengig av koden som senere skal håndheve det. Hvis din egen pipeline-sjekk gir lavere tall enn referansen, har du funnet falske negativer å fikse.

---

## 10. Hva M1 *ikke* tester

For å unngå at tallet overtolkes:

- Det tester **dekning**, ikke om modellen lager *gode* oppgaver (vanskegrad, LK20-treff, pedagogisk kvalitet). Det er en annen test.
- Det tester den verifiserbare delens størrelse, ikke om elevene/lærerne liker produktet. Det avgjøres av M2–M3 (betalende brukere).
- Et høyt M1-tall garanterer ikke salg. Et lavt M1-tall garanterer derimot at vollgraven ikke finnes. M1 er en nødvendig, ikke tilstrekkelig, betingelse.
