# Stop building — anti-roadmap

Dato: 2026-08-02  
Formål: beskytte produktfokus før Skoleverksted har bevist en gjentatt kjernejobb.

## Beslutning

I de neste pilotukene bygger vi ikke mer bredde enn det som trengs for Historie VG2-wedgen. Alt som ikke forbedrer tid til godkjent, kilde-/faktatillit, gjenbruk eller sikkerhet går i fryseren.

## Frys helt

### 1. Nye fag og agentmoduser

**Frys:** flere spesialagenter, nye fagmoduler og nye «AI crew»-varianter.  
**Hvorfor:** dagens kode har allerede fag, norsk, matematikk, temapakke, kompendium og prosjektflater (**BEKREFTET I KODEN**). Hver ny modul utvider eval-, support- og kvalitetsflaten før retention er bevist (**STERK INFERENS**).  
**Gjenåpnes når:** minst 3 av 5 pilotlærere lager ressurs nummer to og historiegolden-settet passerer avtalt terskel.

### 2. Mer avansert bilde-/designmodus

**Frys:** flere bildekilder, layoutvarianter, AI-bildestiler og visuelle effekter.  
**Hvorfor:** bilder kan være pedagogisk nyttige, men det er utestet om de driver ukentlig bruk; kilde- og reviewkostnad er reell (**UTESTET HYPOTESE**).  
**Gjenåpnes når:** lærere i piloten velger bilder som en tydelig del av den samme godkjenningsløkken.

### 3. Flere dokumenttyper og fri formatering

**Frys:** nye hefte-, oppgave-, appendix- og eksportvarianter utover én standardmal.  
**Hvorfor:** fleksibilitet fører til flere valg og gjør kvalitetsmåling vanskeligere.  
**Gjenåpnes når:** én standardtype har bevist tidssparing og gjenbruk.

### 4. Elevflater

**Frys:** elevkontoer, elevchat, elevprofil, adaptiv elevflyt og elevdata.  
**Hvorfor:** krever eget pedagogisk, juridisk og sikkerhetsmessig produkt; piloten kan bevises uten personopplysninger (**STERK INFERENS**).

### 5. LMS- og skoleintegrasjoner

**Frys:** Google Classroom, Teams, Canvas, SSO, karakterbok og automatisk publisering.  
**Hvorfor:** integrasjoner er en multiplikator først etter at én kjernejobb er uunnværlig. De bringer DPIA, innkjøp, rollemodell og support inn for tidlig (**EKSTERN KILDE**, [Udir personvern](https://www.udir.no/kvalitet-og-kompetanse/digitalisering-skole/kunstig-intelligens-i-skolen/personvern-ki/)).

### 6. Sosial markedsplass

**Frys:** offentlig ressursbibliotek, likes, feeds, creator economy og lærermarked.  
**Hvorfor:** deling mellom kolleger kan bli en sterk loop, men først etter privat, rollebasert gjenbruk og audit-logg (**UTESTET HYPOTESE**).

### 7. Mobil- og kosmetisk polish

**Frys:** full redesign, nye animasjoner og detaljpolish som ikke reduserer en målt blokkering.  
**Hvorfor:** den store UX-risikoen er ikke fargebruk; det er at læreren ikke vet hvilken jobb som skal startes.

## Skjul i pilotens grensesnitt

Dette kan fortsatt ligge i kode, men skal ikke konkurrere om oppmerksomheten:

- Norsk- og matematikkmodulene
- temapakke
- generiske prosjekter
- avanserte bildevalg
- øvelsesbank og malbibliotek
- offentlig deling
- «lag hva som helst»-CTA
- kompendium-typer som ikke er historisk læringsark/fordypning

**BEKREFTET I KODEN:** flere av disse flatene finnes allerede. Å skjule dem i pilot er produktpakking, ikke sletting.

## Utsett refaktoreringer

### Full backend-sammenslåing

Behold fagadaptere der de gir isolasjon. Refaktorer bare grensene som påvirker wedge: auth, jobs, claims, evidence og materialstatus. En total omskriving har ingen dokumentert brukergevinst ennå (**STERK INFERENS**).

### Postgres/Redis/object storage som mål i seg selv

Dagens SQLite/Render-disk er ikke tilstrekkelig for flerbrukerproduksjon, men migrer trinnvis etter backup-/restore- og pilotkrav. Ikke kjøp infrastruktur før dataflyt og volum er målt.

### Ny modellleverandør

Test på golden set først. Modellbytte uten regression-test gjør faktaløftet svakere.

### Nytt designsystem

Fiks bare startpunkt, status, review og neste handling. Ikke skriv om hele frontend.

## Ideer som høres flotte ut, men mangler bevis

- «Ett AI-crew for alt» — agentantall er ikke kvalitetsbevis.
- «All-in-one for hele skolen» — bredde kan skjule at ingen jobb er uunnværlig.
- «Grønt Truth Passport = fakta er sant» — dagens pass viser kildestruktur/evidens, ikke full uavhengig faktadom (**BEKREFTET I KODEN**).
- «Bilder gjør materialet bedre» — mulig, men ikke testet mot tids- og kvalitetskostnad.
- «Skoleledelsen betaler» — innkjøpsvilje, DPIA og salgssyklus er ikke målt.
- «Fagseksjonsdeling skaper nettverkseffekt» — målt gjenbruk mangler.
- «Flere eksportformater gir verdi» — først ett format som læreren faktisk bruker.
- «Mer autonom søking er bedre» — læreren kan ha høyere tillit når kildene er valgt eksplisitt.
- «Produksjons-readiness betyr skole-readiness» — health-check og nøkler er ikke tilgangskontroll eller personvern.

## Teknisk arbeid som faktisk må gjøres før pilot

### P0 — sikker datagrense

- autentisering på alle platform-ruter
- user/school eller tilsvarende tenant-felt på alle records
- autorisasjon for list/get/update/delete/download/feedback
- beskytt delte lenker og forhindre ID-gjetting
- automatiske cross-tenant regression-tester

**BEKREFTET I KODEN:** dette mangler i platformlaget i dag.

### P0 — pålitelig jobbflyt

- flytt outline, chapter generation, repair og compile til durable jobber
- returner job-id og eksplisitt status
- idempotency mot doble klikk
- timeout, retry og cancel med synlig årsak

**BEKREFTET I KODEN:** platform-ruter utfører nå lange operasjoner synkront selv om domain-jobbmanager finnes.

### P0 — faktisk sannhetsmåling

- golden set for historie VG2
- claim-level labels: supported, contradicted, ambiguous, missing source
- ekspertgjennomgang og alvorlighetsnivå
- regression gate i CI
- vis separat: «kilde funnet», «påstand støttet», «lærer godkjent»

### P0 — drift og personvern

- backup/restore-test
- retention og sletting
- eksport av lærerens data
- kostnads- og latencybudsjett
- logg uten kildetekst/persondata som ikke trengs
- DPIA-underlag før skoleeierpilot

### P1 — én wedge-opplevelse

- årsplanperioden skal være primært startpunkt
- standardmal med få valg
- review-visning med claim → evidence → edit
- godkjent ressurs tilbake i perioden
- «lag neste» etter approval
- instrumenter first artifact, second artifact, corrections, reuse og cost

## Exit-kriterium for anti-roadmapen

Åpne opp for ny bredde bare når piloten viser:

1. >=60 % second-artifact rate innen 14 dager
2. median netto spart tid mot lærerens metode
3. ingen alvorlige cross-tenant- eller datatapshendelser
4. målt claim-kvalitet over avtalt historiegolden-sett
5. minst to lærere som eksplisitt ber om neste periode eller oppdatering

Hvis kriteriene ikke nås, skal vi ikke «løse» det med flere funksjoner. Vi skal endre målgruppe, jobb eller løfte.

