# Experiment backlog

Dato: 2026-08-02  
Formål: teste produkt-wedgen før bredere bygging.

## Prioriteringsmodell

Rangeringen bruker:

**Prioritetsscore = Impact × Confidence × Strategic leverage / Effort**

Alle tall er 1–5 og er foreløpige vurderinger, ikke målinger (**UTESTET HYPOTESE**). Confidence betyr hvor godt dagens kode-/markedsbevis støtter hypotesen, ikke sannsynlighet for at hypotesen er sann.

| Rang | Eksperiment | I | C | S | E | Score |
|---:|---|---:|---:|---:|---:|---:|
| 1 | Concierge: én Historie VG2-periode til godkjent ark | 5 | 3 | 5 | 2 | 37,5 |
| 2 | Tid og kontrollkostnad mot lærerens metode | 5 | 2 | 5 | 2 | 25,0 |
| 3 | Andre ressurs innen 14 dager | 5 | 2 | 5 | 2 | 25,0 |
| 4 | Claim-/kildetillit med blind golden set | 5 | 3 | 5 | 3 | 25,0 |
| 5 | One-period UX-test | 4 | 3 | 4 | 2 | 24,0 |
| 6 | Auth/tenant threat test | 5 | 4 | 5 | 4 | 25,0 |
| 7 | Latency/kostnadsobservasjon | 4 | 3 | 4 | 2 | 24,0 |
| 8 | Historie VG2 golden set | 5 | 3 | 5 | 4 | 18,75 |
| 9 | Alternativtest mot ChatGPT, NDLA og MagicSchool/Brisk | 4 | 2 | 4 | 3 | 10,67 |
| 10 | Kildeimport og lærerstyrt kildesett | 4 | 3 | 4 | 3 | 16,0 |
| 11 | Godkjent ressurs-gjenbruk | 4 | 2 | 5 | 3 | 13,33 |
| 12 | Pris-/betalingsintervju | 3 | 2 | 4 | 2 | 12,0 |
| 13 | Fagseksjonsdeling uten elevdata | 4 | 1 | 4 | 4 | 4,0 |
| 14 | Bildeverdi i historiehefter | 2 | 1 | 2 | 2 | 2,0 |
| 15 | Ny modellleverandør | 2 | 1 | 1 | 4 | 0,5 |

Score alene avgjør ikke rekkefølge: auth/tenant er en sikkerhetsport og må gjøres før data deles, selv om den ikke er et markeds-eksperiment.

## 1. Concierge: én Historie VG2-periode til godkjent ark

- **Hypotese:** En historielærer velger en periode, legger inn 1–3 kilder og får et ark som er nyttig nok til å godkjenne.
- **Billigste test:** 5–8 lærere, to perioder, teamet følger manuelt opp kildeutvalg og feil.
- **Nødvendig kodearbeid:** bruk eksisterende årsplan/kompendium; legg kun til logging og eventuelle blocker-fikser.
- **Brukerresearch:** observer startpunkt, valg og redigering; intervju etter første og andre ressurs.
- **Måling:** fullføring, tid til approval, antall redigeringer, årsak til avvisning.
- **Forventet læring:** om problemet er en «job to be done» eller bare en spennende demo.
- **Tidsbruk:** 2 uker.
- **Risiko:** teamet hjelper så mye at resultatet ikke generaliserer.
- **Prioritet:** 1.

## 2. Tid og kontrollkostnad mot lærerens metode

- **Hypotese:** Skoleverksted sparer netto tid selv når kildene må kontrolleres.
- **Billigste test:** læreren lager samme type ark på vanlig måte og i appen; mål faktisk arbeidstid.
- **Nødvendig kodearbeid:** event timestamps og enkel eksport av eventlogg.
- **Brukerresearch:** think-aloud med tre lærere.
- **Måling:** minutter til ferdig, minutter til faktasjekk, opplevd kvalitet 1–5.
- **Forventet læring:** om «rask generering» skjuler dyr review.
- **Tidsbruk:** 1 uke.
- **Risiko:** sammenligningen blir skjev på grunn av ulikt tema.
- **Prioritet:** 2.

## 3. Andre ressurs innen 14 dager

- **Hypotese:** Årsplanens «mangler materiale»-loop skaper naturlig retur.
- **Billigste test:** gi lærere en periode med tydelig neste anbefaling og følg opp uten ny feature.
- **Nødvendig kodearbeid:** måle first/second artifact og planperiode.
- **Brukerresearch:** kort intervju om hvorfor de kom eller ikke kom.
- **Måling:** 14-dagers second-artifact rate, gjenbruk, frafallspunkt.
- **Forventet læring:** ekte retention versus nyhetseffekt.
- **Tidsbruk:** 2–3 uker.
- **Risiko:** skolekalenderen forstyrrer.
- **Prioritet:** 3.

## 4. Claim-/kildetillit med blind golden set

- **Hypotese:** Lærere forstår og stoler på claim-visningen uten å lese «grønt» som fasit.
- **Billigste test:** 30 ekspertmerkede claims; vis kilde, evidence og status i randomisert rekkefølge.
- **Nødvendig kodearbeid:** golden-set harness og eksport av claim-beslutning.
- **Brukerresearch:** fem historielærere og én fagperson.
- **Måling:** precision/recall på unsupported claims, lærerens vurdering, alvorlige misses.
- **Forventet læring:** om quality motor er et tillitsprodukt eller bare intern metadata.
- **Tidsbruk:** 2 uker.
- **Risiko:** golden set blir for enkelt.
- **Prioritet:** 4.

## 5. One-period UX-test

- **Hypotese:** En ny lærer finner fra årsplan til ferdig review uten forklaring.
- **Billigste test:** fem brukere, én CTA, skjermopptak og verbal protokoll.
- **Nødvendig kodearbeid:** ingen, bortsett fra instrumentering av frafall.
- **Brukerresearch:** 30 minutter per lærer.
- **Måling:** tid til riktig start, feilklikk, spørsmål, SUS-light.
- **Forventet læring:** hvilke valg som skal skjules.
- **Tidsbruk:** 3–4 dager.
- **Risiko:** testdata er for ryddig.
- **Prioritet:** 5.

## 6. Auth/tenant threat test

- **Hypotese:** En minimal eier-/skolemodell kan hindre krysslesing uten å blokkere pilotflyt.
- **Billigste test:** to testbrukere; prøv å gjette ID, laste ned, oppdatere og dele en ressurs.
- **Nødvendig kodearbeid:** implementer auth/tenant før data deles; dette er sikkerhetsarbeid, ikke bare test.
- **Brukerresearch:** én skoleleder/IT-ansvarlig gjennomgår datagrense.
- **Måling:** 0 cross-tenant reads/writes/downloads, testet med automatiske cases.
- **Forventet læring:** om arkitekturen tåler skolebruk.
- **Tidsbruk:** 1–2 uker.
- **Risiko:** midlertidig auth blir liggende for lenge.
- **Prioritet:** 6, men blokkering før flerbruker.

## 7. Latency/kostnadsobservasjon

- **Hypotese:** én periode kan genereres innen akseptabel tid og kostnad.
- **Billigste test:** logg 50 reelle jobs med inputstørrelse, modell, retries, duration og kostnad.
- **Nødvendig kodearbeid:** server-side telemetry, jobbstatus og budsjettvarsler.
- **Brukerresearch:** spør om ventetid versus kontrollverdi.
- **Måling:** p50/p95, failure rate, cost per approved artifact.
- **Forventet læring:** hvor mye automatisering som er bærekraftig.
- **Tidsbruk:** 1 uke + innsamling.
- **Risiko:** produksjonsvolumet er for lavt.
- **Prioritet:** 7.

## 8. Historie VG2 golden set

- **Hypotese:** systemet kan måles på kompetansemål, perioder og typiske kontroversielle claims.
- **Billigste test:** 50 claims fra middelalder, ideologier og kildearbeid med faglig fasit.
- **Nødvendig kodearbeid:** versionert eval-run, claim-level diff og regression gate.
- **Brukerresearch:** to historielærere lager fasit og alvorlighetsnivå.
- **Måling:** unsupported claim rate, citation precision, repair acceptance, alvorlige feil.
- **Forventet læring:** hvilke faglige mønstre systemet faktisk håndterer.
- **Tidsbruk:** 2–4 uker.
- **Risiko:** ekspertene er uenige; dette må modelleres som usikkerhet.
- **Prioritet:** 8.

## 9. Alternativtest

- **Hypotese:** læreren velger Skoleverksted for plan→kilde→godkjenning, ikke bare tekstkvalitet.
- **Billigste test:** samme tema gjennom Skoleverksted, generell modell, NDLA og ett lærer-AI-verktøy.
- **Nødvendig kodearbeid:** ingen i første runde; standardiser input og rubric.
- **Brukerresearch:** fem lærere rangerer nytte, tillit og kontrollkostnad.
- **Måling:** forced choice, willingness to switch, viktigste fordel.
- **Forventet læring:** om wedge-budskapet er differensiert.
- **Tidsbruk:** 1 uke.
- **Risiko:** verktøyene har ulik tilgang/pris.
- **Prioritet:** 9.

## 10. Kildeimport og lærerstyrt kildesett

- **Hypotese:** læreren vil heller velge kildene enn å overlate søket til agenten.
- **Billigste test:** tilby to moduser manuelt: lærerens URL-er versus systemets forslag.
- **Nødvendig kodearbeid:** stabil visning av source brief og konkrete URL-er.
- **Brukerresearch:** fem lærere.
- **Måling:** source acceptance, tid brukt, avvisningsgrunn.
- **Forventet læring:** hvor mye autonomi som faktisk skaper tillit.
- **Tidsbruk:** 1 uke.
- **Risiko:** lærerens kildesett er for lite.
- **Prioritet:** 10.

## 11. Godkjent ressurs-gjenbruk

- **Hypotese:** godkjente ark blir startpunkt for neste år eller parallellklasse.
- **Billigste test:** tilby «kopier og oppdater» manuelt i én seksjon.
- **Nødvendig kodearbeid:** versjon/snapshot, diff og planperiodelink.
- **Brukerresearch:** intervjuer etter to brukssykluser.
- **Måling:** reuse rate, tid spart, kildeoppdateringer.
- **Forventet læring:** om biblioteket blir en retention-motor.
- **Tidsbruk:** 1–2 uker.
- **Risiko:** lærere foretrekker filer i eksisterende system.
- **Prioritet:** 11.

## 12. Pris-/betalingsintervju

- **Hypotese:** lærere/fagseksjoner betaler for dokumentert spart tid og kildeansvar.
- **Billigste test:** vis ferdig pilotverdi og test tre prismodeller uten å bygge betaling.
- **Nødvendig kodearbeid:** ingen; senere må usage/cost være målt.
- **Brukerresearch:** 10 lærere, 3 seksjonsledere.
- **Måling:** willingness-to-pay, hvem som betaler, innkjøpshinder.
- **Forventet læring:** individuell versus seksjonsmodell.
- **Tidsbruk:** 1 uke.
- **Risiko:** hypotetiske priser overvurderes.
- **Prioritet:** 12.

## 13. Fagseksjonsdeling uten elevdata

- **Hypotese:** to lærere vil gjenbruke samme godkjente ressurs hvis ansvar og versjon er synlig.
- **Billigste test:** del tre PDF/claims manuelt i én seksjon før ekte sharing-funksjon.
- **Nødvendig kodearbeid:** auth/roller, immutable audit og delingskontroll senere.
- **Brukerresearch:** seksjonsintervju.
- **Måling:** reuse, endringer, konflikter om eierskap.
- **Forventet læring:** kollektiv retention.
- **Tidsbruk:** 2 uker.
- **Risiko:** deling blir gratis fildeling uten betalingsverdi.
- **Prioritet:** 13.

## 14. Bildeverdi i historiehefter

- **Hypotese:** faglig relevante bilder øker forståelse nok til å forsvare kostnad og review.
- **Billigste test:** A/B med ingen bilde, Commons-bilde og AI-bilde på samme ark.
- **Nødvendig kodearbeid:** bare hvis lærere velger bilder i pilot; ikke blokker wedge.
- **Brukerresearch:** fem lærere, eventuelt elevtest senere med samtykke.
- **Måling:** lærerens valg, tid, pedagogisk vurdering.
- **Forventet læring:** om bilder er kjerne eller pynt.
- **Tidsbruk:** 1 uke.
- **Risiko:** lisens-/kilde- og kvalitetssjekk spiser gevinsten.
- **Prioritet:** 14.

## 15. Ny modellleverandør

- **Hypotese:** en annen modell gir bedre claim-presisjon til lavere kostnad.
- **Billigste test:** offline replay på golden set med samme prompt/format.
- **Nødvendig kodearbeid:** adapter og regression gate.
- **Brukerresearch:** ingen før teknisk resultat.
- **Måling:** kvalitet, latency, cost, failure modes.
- **Forventet læring:** leverandøravhengighet versus reell gevinst.
- **Tidsbruk:** 1–2 uker.
- **Risiko:** ny modell skaper uverifiserte forskjeller.
- **Prioritet:** 15.

## Stopregel for backlog

Hvis eksperiment 1–4 ikke viser tydelig spart tid, andreukersbruk og bedre tillit, skal nye funksjoner settes på pause. Da tester vi en annen målgruppe eller jobb, ikke en lengre funksjonsliste.

