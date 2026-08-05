# Produkt-wedge: Historieverksted

Dato: 2026-08-02  
Status: pilotforslag, ikke bekreftet product-market fit.

## Én setning

For historielærere på VGS, først VG2, gjør Historieverksted én periode i årsplanen om til et kort, kildebelagt og lærer-godkjent læringsark eller fordypningshefte som kan brukes igjen neste skoleår.

## Nøyaktig målgruppe

- lærer i historie VG2
- underviser i en tekst- og kildetung periode
- bruker egen årsplan eller fylkets kompetansemål
- lager utskriftsvennlig materiale minst noen ganger per termin
- har ikke behov for elevkontoer i pilot
- kan teste med egne, offentlige eller institusjonsgodkjente kilder

Dette er et smalt startsegment, ikke en påstand om at historie er det største edtech-markedet (**STERK INFERENS**).

## Kjerneproblem

Læreren må samtidig avgrense temaet, velge kilder, skrive forståelig tekst, kontrollere påstander, lage oppgaver og finne igjen materialet senere. Generelle AI-verktøy gjør førsteutkastet raskt, men legger kontroll- og arkiveringsarbeidet tilbake hos læreren (**STERK INFERENS**). Skoleverksted har allerede kode for årsplaner, kompendier, kildepass og PDF, så akkurat denne jobben har høyest nåværende kodefit (**BEKREFTET I KODEN**).

## Løftet

> «Velg én periode. Gi oss et lite kildesett. På få minutter får du et review-klart ark med synlige kilder, usikkerhet og oppgaver — og neste gang slipper du å lage det fra null.»

«På få minutter» er en pilotmålsetting, ikke målt nå (**UTESTET HYPOTESE**).

## Startpunkt og sluttprodukt

### Startpunkt

1. Åpne Årsplan.
2. Velg én periode som mangler materiale.
3. Trykk «Lag læringsark».
4. Bekreft tema, målgruppe, lengde og 1–3 konkrete kildelenker.
5. Velg standardmal: læringstekst + begreper + kildeoppgaver + kort lærerfasit.

### Sluttprodukt

- HTML/Markdown-review med tydelige kapitler og claim-markører
- kildeliste med konkrete lenker og hentet dato
- Truth Passport med verified / needs review per claim
- lærerens redigeringer og godkjenning
- PDF som kan lastes ned
- materialet lagret på riktig periode
- versjonsnavn og «oppdater når kilde eller læreplan endres»

## Dette skal være med i piloten

- én fagfamilie: historie VG2
- én standard dokumenttype: læringsark/fordypningsark
- årsplanperiode som startpunkt
- kildelenker eller søkbart, tydelig avgrenset kildesett
- claim-level kildevisning
- lærerredigering, automatisk reparasjon som forslag og eksplisitt godkjenning
- PDF-eksport
- historikk på godkjent versjon
- enkel tilbakemelding: «sparte tid», «måtte rette mye», «ville brukt igjen»

## Dette skal eksplisitt ikke være med

- elevkontoer eller personlige elevopplysninger
- LMS/Google Classroom/Teams-integrasjoner
- alle VGS-fag samtidig
- bilder som premiss for verdi
- fri dokumentbygger med mange layoutvalg
- sosial markedsplass
- skoleadministrasjon, karakterbok eller vurderingssystem
- automatisk publisering uten lærerens godkjenning
- påstand om at grønt pass er sannhetsgaranti

## Det magiske øyeblikket

Læreren ser et ark der tre typiske feil er håndtert uten ekstra arbeid:

1. påstanden er avgrenset til kilden
2. kildehenvisningen peker til en faktisk side, ikke en hjemmeside
3. usikkerhet eller uenighet er synlig i teksten

Læreren kan klikke fra påstand til kilde, endre formulering og godkjenne. Deretter viser årsplanen at perioden er dekket.

## Kvalitetsterskel

En ressurs kan ikke merkes «godkjent» før:

- alle kapitler er ferdige
- alle nødvendige kilder er konkrete og tilgjengelige
- alle sentrale claims har evidence eller tydelig «må kontrolleres»
- ingen placeholders eller reparasjonsfeil står igjen
- PDF-kompilering er vellykket
- lærer har eksplisitt godkjent
- systemet viser hva det ikke har verifisert

Dette bygger på eksisterende compile-/approve-gater og truth-/quality-lag (**BEKREFTET I KODEN**), men selve historiske riktigheten må dokumenteres med golden set (**UTESTET HYPOTESE**).

## Målinger

### Primære mål

- **Time to approved artifact:** fra periodevalg til lærerens godkjenning. Mål: median <= 15 minutter i første pilot; stretch <= 5 minutter for review-klart utkast (**UTESTET HYPOTESE**).
- **Second-artifact rate:** andel lærere som lager og godkjenner ressurs nummer to innen 14 dager. Mål: >=60 % (**UTESTET HYPOTESE**).
- **Claim correction rate:** andel sentrale claims lærer endrer eller avviser. Mål: <15 % alvorlige korreksjoner på golden set; terskel må justeres etter baseline (**UTESTET HYPOTESE**).
- **Reuse rate:** andel godkjente ressurser som åpnes, kopieres eller oppdateres i neste periode/år. Mål: >=30 % i tidlig pilot (**UTESTET HYPOTESE**).

### Guardrails

- 0 eksponering av andre læreres data
- 0 publisering uten lærer approval
- tydelig modell-/kildekostnad per jobb
- 100 % av pilotdata kan eksporteres og slettes
- ingen elevdata

## Pilotopplegg

- 5–8 historielærere, helst fra én fagseksjon eller to nærliggende skoler
- to uker, minst to perioder per lærer
- concierge-opplegg: teamet observerer, hjelper med kildeutvalg og registrerer feil manuelt
- én felles onboarding på 30 minutter
- før-/etterintervju på tid, tillit og kontrollkostnad
- ingen elevdata og ingen automatisk deling
- bruk eksisterende app der det er mulig; ikke bygg ny funksjon før en observasjon viser konkret blokkering

### Suksesskriterier

Piloten fortsetter hvis alle disse er sanne:

1. minst 5 lærere fullfører første ressurs
2. minst 3 av 5 fullfører ressurs nummer to innen 14 dager
3. median tid til godkjenning er lavere enn lærerens normalmetode
4. lærerne kan forklare hva Truth Passport har og ikke har bevist
5. ingen alvorlig kilde- eller tilgangshendelse
6. minst to lærere sier eksplisitt at årsplan-gjenbruket er grunnen til at de kommer tilbake

### Kill criteria

Stopp eller bytt wedge hvis:

- færre enn 2 av 5 lager ressurs nummer to
- kontrollarbeidet ikke sparer tid etter to forsøk
- lærerne stoler mer på et generelt alternativ enn på claim-visningen
- kilde- eller tilgangsfeil ikke kan forklares og rettes
- pilotens kostnad per godkjent ressurs overstiger avtalt budsjett med >50 %
- lærerne primært ber om design, bilder eller LMS før de bruker kjerneløkken

## Ekspansjon hvis hypotesen bekreftes

1. samfunnsfag og religion på VGS med samme claim-/kildemotor
2. fagseksjonsbibliotek med roller og audit-logg
3. kildeoppdatering og år-til-år-versjonering
4. norsk-/språktilpasning som sekundær workflow
5. matematikk som separat verifiseringsadapter, ikke tvungen sammensmelting
6. API/partner først når kvalitet og sikkerhet er dokumentert

## Nåværende kodefit og gap

### Finnes allerede

- årsplan og perioder: MateMaTeX/frontend/src/app/year-plans/[id]/page.tsx
- kompendiumoppretting og godkjenning: MateMaTeX/frontend/src/app/compendia/new/page.tsx og compendia/[id]/page.tsx
- truth-/quality-pass: MateMaTeX/frontend/src/components/truth-passport.tsx og quality-passport.tsx
- compile-/approve-gater: Skoleverksted/backend/platform/router.py
- claim/source-modeller: Skoleverksted/backend/platform/models.py og truth.py

### Må lukkes før flerbrukerpilot

- platform-auth/tenant og autorisasjon
- asynkron status for lange platform-jobber
- golden set og historiefaglig evaluering
- backup/restore og sletting
- metrics for tid, kostnad, corrections og reuse
- én samlet pilotnavigasjon i stedet for å sende brukeren mellom generelle fagflater

## Personvernramme

- ingen elevdata i piloten
- bare lærerens arbeidsdata og offentlige/institusjonelle kilder
- dokumenter hvilke modellleverandører som mottar tekst/kildeinnhold
- gi eksport og sletting
- gjør DPIA-forberedelse før skoleeierpilot, i tråd med [Udirs personvernråd](https://www.udir.no/kvalitet-og-kompetanse/digitalisering-skole/kunstig-intelligens-i-skolen/personvern-ki/)

