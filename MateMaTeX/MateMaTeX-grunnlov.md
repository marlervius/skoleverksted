# MateMaTeX — Grunnlov

**Forretningsidé- og prinsippdokument**
Apexlab (Lervik KI-Tech ENK)

| | |
|---|---|
| Versjon | 1.0 |
| Dato | 18. juni 2026 |
| Status | Levende dokument |
| Eier | Marius |

---

## 0. Hvordan dette dokumentet skal brukes

Dette er grunnloven, ikke en idéskisse. Reglene her (§§ i kapittel 2) går foran alt annet. Når en beslutning, en feature-idé eller en kundeforespørsel kommer i konflikt med et prinsipp, **vinner prinsippet** — eller så endrer du grunnloven først, eksplisitt og datert. Du endrer den ikke i hodet midt i en kveldsøkt.

Alle endringer føres i kapittel 13 (Endringslogg) med dato og begrunnelse. Hvis du ikke kan begrunne en endring skriftlig, er den sannsynligvis bare dagsform.

---

## 1. Tesen

> MateMaTeX lager LK20-tilpassede matematikkoppgaver, arbeidsark og hele heldagsprøver/eksamener for norske VGS-lærere — med **maskinelt verifisert fasit**, levert som ferdig LaTeX/PDF, uten at en eneste personopplysning om en elev noensinne forlater lærerens maskin.

Alt produktet gjør, skal kunne forsvares mot denne setningen. Hvis en feature ikke styrker «LK20-tilpasset», «verifisert fasit», «sparer lærertid» eller «null elevdata» — er den sannsynligvis støy.

---

## 2. Kjerneprinsipper

### §1 — Fasiten er hellig
En lærer som blir brent av én feil fasit, slutter å stole på verktøyet for alltid. Derfor: **vi leverer aldri en fasit vi ikke kan stå inne for.**

- Alt som *kan* verifiseres maskinelt (SymPy: likninger, derivasjon, integrasjon, faktorisering, regning, funksjonsverdier) **skal** verifiseres før det går ut.
- Alt som *ikke* lar seg verifisere automatisk (geometriske bevis, modelleringsoppgaver, «vis at», tolkningsoppgaver, sannsynlighet med skjønn) skal **enten** holdes utenfor i starten, **eller** merkes tydelig som «lærerkontroll anbefales». Vi later aldri som om noe er verifisert når det ikke er det.
- Ærlig konsekvens: vollgraven gjelder bare den verifiserbare delen av pensum. Det er den delen vi bygger og selger først (se §5).

### §2 — Vi rører aldri elevdata
Produktet behandler **innhold**, ikke personer. Ingen elevnavn, ingen besvarelser, ingen identifiserbare opplysninger — verken inn eller ut.

Dette er ikke bare etikk; det er forretningsstrategi. Det fjerner kravet om DPIA, databehandleravtale og kommunal personvernvurdering, som er den veggen et ENK ikke kommer over. Den dagen noen foreslår en feature som tar inn elevdata, er svaret nei med mindre grunnloven endres med åpne øyne.

### §3 — LK20-native, ikke oversatt
De store (MagicSchool, Diffit, Brisk) er amerikanske og «brukbare hvis du prompter rundt standardvalgene». Det er nettopp gapet. MateMaTeX skal være kodet mot **norsk læreplan, norske kompetansemål, norsk eksamensstruktur og norsk notasjon** — ikke en oversettelse. Det er den ene tingen de aldri kommer til å gjøre godt, og den vi alltid skal gjøre best.

### §4 — Lærerens tid er produktet
Vi selger ikke «AI». Vi selger spart kveldstid. Hver feature måles i minutter en lærer slipper å bruke. Et fint dashbord som ikke sparer tid, er en kostnad, ikke en verdi.

### §5 — Smalt slår bredt
«All matte for alle nivåer» er en felle. Vi lanserer på **ett nivå/fag av gangen**, gjør det utmerket, og utvider først når det er betalende brukere som ber om det. Bredde er en belønning vi tjener oss til, ikke en startposisjon.

### §6 — Innhold ut, ikke en plattform inn
MateMaTeX leverer filer (PDF/LaTeX/Word) som læreren eier og bruker hvor de vil. Vi prøver ikke å bli «plattformen elevene logger inn på». Det er en annen, mye dyrere og mye mer personvernsbelastet forretning — og den åpner §2-veggen. Vi holder oss på innholds-siden.

### §7 — Ferdig og solgt slår nytt og kult
Den største risikoen for dette prosjektet er ikke konkurrentene. Det er at grunnleggeren starter noe nytt før dette er ferdig og betalt for. **Inntil MateMaTeX har 10 betalende brukere, er nye produktidéer forbudt.** De skrives ned i en parkeringsliste og ignoreres.

---

## 3. Problemet

Norske mattelærere bruker uforholdsmessig mye tid på å lage oppgaver, varianter, arbeidsark og særlig hele heldagsprøver og eksamenssett — med riktig notasjon, riktig vanskegrad og **riktig fasit**. AI-verktøy finnes, men:

1. De er ikke LK20-tilpasset.
2. De produserer matematiske feil i fasiten — som er verre enn ingen fasit, fordi det krever at læreren dobbeltsjekker alt.
3. De ser ikke ut som norske prøver (notasjon, struktur, del 1/del 2).

Smertepunktet er skarpest rundt **prøve- og eksamensproduksjon**, der både tidsbruk og krav til korrekthet er høyest. Det er der vi treffer hardest.

---

## 4. Kunden (ICP)

**Primær:** Mattelærer i norsk VGS som lager egne prøver og arbeidsark, er teknisk komfortabel nok til å bruke et nettverktøy, og er lei av å verifisere AI-fasit for hånd.

**Den som faktisk betaler — to spor:**
- **Validerings-sporet (start her):** enkeltlæreren, som tar det på eget kort fordi det sparer hen reelle timer. Lav pris, rask feedback, ingen innkjøpsprosess.
- **Penge-sporet (senere):** skolen/fagseksjonen, som kjøper sete-lisenser når nok lærere alt bruker det. Bottom-up adopsjon → skolen betaler. Vi prøver **ikke** å selge top-down til kommune via offentlig innkjøp som soloforetak — det er for tregt og for tungt i starten.

Realistisk markedsstørrelse er «noen tusen mattelærere i norsk VGS» — stort nok til en solid biinntekt, for lite til en venture-drøm. Det er greit. Det er en biinntekt vi bygger, ikke en enhjørning. (Eksakt TAM bør verifiseres mot SSB/Udir-tall før vi tar tunge beslutninger.)

---

## 5. Løsningen — og hva vi IKKE lager

**Det vi lager (MVP, ett nivå først):**
- Generering av oppgaver og arbeidsark med valgbart kompetansemål, tema og vanskegrad.
- Generering av komplette heldagsprøver/eksamenssett i norsk format (Del 1 / Del 2).
- SymPy-verifisert fasit på den verifiserbare delen.
- Eksport til PDF og LaTeX/Word, læreren eier filen.

**Det vi bevisst IKKE lager (anti-scope):**
- ❌ Noe som tar inn elevbesvarelser eller elevdata (§2).
- ❌ Retting/vurdering av elevarbeid (eget produkt, egen vegg — egen idé en annen dag).
- ❌ Elevinnlogging / elev-app / «læringsplattform» (§6).
- ❌ Alle fag og alle nivåer på en gang (§5).
- ❌ Uverifisert «vis at»- og bevisstoff presentert som om det er fasitsjekket (§1).

Anti-scopen er like viktig som scopen. Når du er fristet, les denne lista på nytt.

---

## 6. Vollgraven

Hvorfor overlever dette mot gratis MagicSchool og ChatGPT?

1. **Verifisert fasit.** Den eneste av disse som kan si «fasiten er maskinelt kontrollert» er deg. Det er det dyreste å kopiere og det viktigste for kunden.
2. **LK20-native.** Strukturell tilpasning til norsk læreplan og eksamensform, ikke et promptlag (§3).
3. **Norsk notasjon og PDF-kvalitet.** LaTeX-pipelinen din gir prøver som *ser ut som* ekte prøver. Lavt teknologisk forsprang isolert, men det summerer seg med de to over.

Ærlig: ingen av disse er en uovervinnelig vollgrav alene. Sammen, i en smal norsk nisje, er de nok til en forsvarbar biinntekt. Det holder.

---

## 7. Forretningsmodell

- **Individuell:** ca. kr 99/mnd eller kr 990/år. Dette er **for validering**, ikke for rikdom — det beviser betalingsvilje.
- **Skole/fagseksjon:** per-sete-lisens solgt til skolen når adopsjonen er der. Dette er hvor de reelle pengene ligger.
- **Gratis-nivå:** begrenset (f.eks. X genereringer/mnd) for å få folk inn — men aldri så generøst at ingen betaler.

Kostnadsdisiplin: API-kostnad per generering skal alltid være kjent og ligge godt under prisen. En generering som koster mer enn den smaker, fikses eller fjernes.

---

## 8. Go-to-market — de første 10

Målet er ikke «vekst». Målet er **10 betalende lærere**. Sånn kommer de:

1. Lanser smalt på ett nivå (kandidat: 1T eller R1 — der prøveproduksjon er hyppig og notasjonen er krevende nok til at gratisverktøy feiler).
2. Bruk ditt eget nettverk: kolleger på FOV/VGS, Trondheim Katedralskole-miljøet, lærergrupper du allerede er i.
3. Vis, ikke fortell: del en ferdig, vakker, verifisert prøve som en lærer kan bruke i morgen. Produktet selger seg på artefaktet, ikke på pitchen.
4. Norske lærer-fora og Facebook-grupper (matematikk VGS), men med innhold — ikke reklame.
5. Be hver tidlig bruker om én ærlig ting de skulle ønske var bedre. Bygg det. Be dem fortelle én kollega.

Vekst kommer etter de 10, ikke før.

---

## 9. Personvern og juss (bærende, ikke fotnote)

Konteksten: Datatilsynet gjorde tilsyn med 50 kommuner i 2025 og fant at mange digitale læringsverktøy tas i bruk uten risikovurdering, og at kommunen — ikke leverandøren — er behandlingsansvarlig. Dette er et minefelt for verktøy som rører elevdata.

**Vår posisjon (følger direkte av §2):**
- MateMaTeX behandler ikke personopplysninger om elever. Punktum.
- Dette skal stå **tydelig på nettsiden og i personvernerklæringen**, fordi det er et salgsargument: «ingen elevdata → ingen DPIA-bekymring for skolen».
- Lærerens egne kontodata (e-post, betaling) behandles minimalt og EU/EØS-hostet der det er praktisk mulig.
- Den dagen en feature frister med elevdata: stopp. Det endrer hele juridiske profilen og åpner veggen vi bevisst står bak.

---

## 10. Suksess- og drepekriterier

**Suksess (i rekkefølge):**
- M1: Verifikasjonen holder — SymPy dekker nok av det valgte nivået til at «verifisert fasit»-løftet er ekte. **Test dette aller først, før noe annet bygges.**
- M2: 1 betalende lærer som ikke er deg.
- M3: 10 betalende lærere.
- M4: Første skole/seksjon-lisens.

**Drepekriterier (ærlig — når innrømmer vi at det ikke funker):**
- Hvis verifikasjonen *ikke* holder — hvis for mye av pensum er uverifiserbart — faller hele vollgraven, og produktet må enten omdefineres til den verifiserbare kjernen eller legges ned. Ikke lat som.
- Hvis du etter lansering på ett nivå + aktiv oppsøking ikke får 10 betalende innen ~6 måneder, er betalingsvilje-tesen feil. Da justeres pris/segment én gang — og hvis det fortsatt ikke holder, parkeres prosjektet uten skam.

Et parkert prosjekt med en ærlig konklusjon er en suksess. Et zombieprosjekt du ikke tør avslutte, er ikke det.

---

## 11. Beslutningsregler

Når du vurderer å bygge noe nytt, still i rekkefølge:
1. Bryter det et prinsipp (§§1–7)? → Ikke gjør det.
2. Sparer det læreren målbar tid (§4)? → Hvis nei, nedprioritér.
3. Kan fasiten/output verifiseres (§1)? → Hvis nei, merk det ærlig eller hold det ute.
4. Krever det elevdata (§2)? → Nei betyr nei.
5. Er det innenfor det smale lanseringsnivået (§5)? → Hvis nei, parker til etter de 10.

---

## 12. Åpne spørsmål / parkeringsplass

*Ting vi har bestemt oss for å ikke bestemme ennå. Skrives ned her i stedet for å bygges.*

- Endelig navn/merkevare: MateMaTeX under Apexlab, eller noe annet? (Parkert — ikke kritisk for de 10 første.)
- Hvilket nivå lanseres først: 1T vs. R1? (Avgjøres av M1-testen: hvor holder verifikasjonen best.)
- Skal R2/S-matte med statistikk og sannsynlighet inn — og hvordan håndtere den uverifiserbare delen?
- Retteassistent som fremtidig produkt (egen vegg, egen grunnlov — **ikke nå**, jf. §7).

---

## 13. Endringslogg

| Dato | Versjon | Endring | Begrunnelse |
|---|---|---|---|
| 2026-06-18 | 1.0 | Opprettet | Grunnlov etablert ved oppstart |
