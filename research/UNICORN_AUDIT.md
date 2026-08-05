# Skoleverksted — Unicorn audit

Dato: 2026-08-02  
Scope: repositoryet i denne arbeidsmappen, dokumentasjonen i repoet, Git-historikken og offentlig research. Ingen applikasjonskode er endret i denne fasen.

## Evidensnøkkel

- **BEKREFTET I KODEN**: kan spores til en konkret fil, rute, modell eller test.
- **BEKREFTET I DOKUMENTASJON**: står i README, deploy-dokumentasjon eller statusfil, men er ikke nødvendigvis bevist i runtime.
- **EKSTERN KILDE**: offentlig kilde, lenket direkte.
- **STERK INFERENS**: konklusjon trukket fra flere bevis, men ikke målt med brukere.
- **UTESTET HYPOTESE**: må testes før produktet eller investeringen skaleres.

## Executive summary

Skoleverksted har en sterk idé i koblingen mellom årsplan, kildebelagt produksjon, lærerens godkjenning og gjenbruk. Koden viser at dette ikke bare er en landingsside: det finnes arbeidsflyter for årsplaner, kompendier, fag/norsk/matematikk, kilder, Truth Passport, Quality Passport, PDF-eksport, jobber og historikk (**BEKREFTET I KODEN**).

Samtidig er produktet bredere enn bevisene. Det finnes ingen dokumentert aktiv lærerbase, retention-måling, betalingstest eller ende-til-ende-produksjonsmåling (**UTESTET HYPOTESE**). Plattformlaget er eksplisitt uten autentisering og lagrer prosjekter, årsplaner og kompendier uten eier-/skolefelt (**BEKREFTET I KODEN**, Skoleverksted/backend/platform/store.py, models.py og router.py). Dagens overflate bør derfor ikke omtales som skoleklar flerbruker-SaaS, selv om deploy- og readiness-dokumentasjonen kan gi det inntrykket (**STERK INFERENS**).

Den riktige neste beslutningen er å stoppe breddebyggingen og pilotere én konkret løkke:

> Historielærer på VGS velger én periode i årsplanen, legger inn eller velger et konkret kildesett, får et kort, kildebelagt og redigerbart læringsark/fordypningshefte, godkjenner det og finner det igjen i årsplanen.

Dette er smalt nok til å måle ukentlig nytte, men bredt nok til å bevise den egentlige differensieringen: sporbar kvalitet og gjenbruk, ikke «enda en AI-generator».

## Endelig investeringsdom

### LOVENDE NISJEPRODUKT

**Begrunnelse:** Kodebasen inneholder en tydelig vertikal arbeidsflyt som generiske AI-verktøy ikke leverer samlet: årsplan → periode → materiale → kilde-/faktapass → lærerrevisjon → godkjent ressurs (**BEKREFTET I KODEN**). Norsk skole har et reelt behov for lærerledelse, personvern og kildekritikk rundt KI (**EKSTERN KILDE**, [Udir: råd om KI i skolen](https://www.udir.no/kvalitet-og-kompetanse/digitalisering-skole/kunstig-intelligens-i-skolen/rad-om-kunstig-intelligens-skolen/), [Udir: personvern og KI](https://www.udir.no/kvalitet-og-kompetanse/digitalisering-skole/kunstig-intelligens-i-skolen/personvern-ki/)). Markedet er samtidig fullt av godt distribuerte alternativer (**EKSTERN KILDE**, [MagicSchool](https://www.magicschool.ai/pricing), [Brisk FAQ](https://www.briskteaching.com/faq), [Diffit](https://web.diffit.me/pricing), [Canva Education](https://www.canva.com/education/teachers/), [NDLA](https://ndla.no/nb/om/hvem-er-vi)).

Det finnes en plausibel nisje, men ikke sterke nok bevis for «kan bli stort» ennå. Oppgradering krever dokumentert andreukersbruk, lav kontrollkostnad, trygg flerbrukerarkitektur og en voksende kvalitets-/redigeringsdatabase som gjør produktet bedre for hver godkjente ressurs (**UTESTET HYPOTESE**).

## Den mest ubehagelige sannheten

Produktet er teknisk mer modent enn markedsbeviset, men mindre produksjonsklart enn overflaten antyder.

- **BEKREFTET I KODEN:** Plattformens sentrale API-ruter har ingen autentiseringsavhengighet. Store-modellen mangler user, school, tenant og eierskap. Frontendens platform-api kaller offentlig backend direkte, mens MATE-proxyen bare dekker matematikk.
- **BEKREFTET I DOKUMENTASJON:** README.md sier at skolepålogging er utsatt, og status.md beskriver produktet som samlet lærerplattform.
- **STERK INFERENS:** En lærer kan oppleve en overbevisende demo, men en skole kan ikke trygt dele dette på tvers av lærere før datagrense, sletting, backup og tilgang er løst.
- **BEKREFTET I KODEN:** Truth Passport verifiserer konkrete HTTPS-sider med hentet evidens og konfidens, men er ikke en uavhengig, deterministisk faktadommer. Evidensen og påstanden er fortsatt del av en modellstyrt pipeline.
- **BEKREFTET I KODEN:** Eval-suiten har fem syntetiske kvalitetstilfeller og mye mocking i truth-/kompendietestene. Den beviser strukturell kvalitet og fail-closed-logikk, ikke historisk sannhet i reell bruk.
- **UTESTET HYPOTESE:** Lærere vil betale for denne tryggheten og komme tilbake hver uke.

Dette er et argument for en smal kvalitetsworkflow, ikke for å kaste produktet.

## Systemkart: hva som faktisk finnes

### Brukerflater

- **BEKREFTET I KODEN:** aktiv frontend ligger under MateMaTeX/frontend.
- Ruter inkluderer /, /fag, /norsk, /matematikk, /compendia, /year-plans, /theme-pack, /projects, /history, /exercises, /templates, /shared og innstillinger.
- **BEKREFTET I KODEN:** forsiden fremhever årsplan, temapakke og kompendium før de tre fagmodulene.
- **BEKREFTET I KODEN:** sidebar har lang sekundærmeny; mobilbunnlinjen viser bare hjem, årsplan, fag og norsk. Matematikk, kompendier, prosjekter, historikk og temapakke ligger ikke der.
- **STERK INFERENS:** produktet oppleves som flere verktøy i én app før brukeren har forstått én kjernejobb.

### Plattform- og domene-API

- **BEKREFTET I KODEN:** Skoleverksted/backend/main.py monterer VGS, ScriptoriumFOV, MateMaTeX og felles /api/platform.
- **BEKREFTET I KODEN:** plattformrouteren har årsplan-, kompendium-, prosjekt-, jobb-, kilde-/kvalitetspass- og feedback-endepunkter.
- **BEKREFTET I KODEN:** VGS- og ScriptoriumFOV-flyt har egne jobber og til dels egne passord-/rate-limitmekanismer; plattformlaget har ingen tilsvarende auth dependency.
- **BEKREFTET I DOKUMENTASJON:** Render/Vercel-oppsett og render.yaml beskriver produksjonsmiljø med disk, helsesjekk, API-nøkler og køgrenser.
- **STERK INFERENS:** deploy-oppsettet er tilstrekkelig for en kontrollert pilot med én lærergruppe, men ikke et bevis på flerleietaker-sikkerhet eller skalerbar drift.

### Kvalitetsmotor

- **BEKREFTET I KODEN:** truth.py avviser generiske hjemmesider, krever konkrete HTTPS-kilder og kan sette passet rødt når verifisering mangler.
- **BEKREFTET I KODEN:** quality.py kontrollerer blant annet innholdslengde, kilder, sitatmarkører, kompetansemål, fasit, kompilering, duplikater og placeholders.
- **BEKREFTET I KODEN:** kompendium-kompilering blokkerer uferdige kapitler, manglende Truth Passport og manglende verifisering.
- **STERK INFERENS:** dette er den mest lovende produktkjernen, men den er foreløpig en prosess- og metadata-gate, ikke et bevis på at alle påstander er sanne.

## Nåværende styrker

1. **Plan til artefakt:** Årsplaner kan knyttes til perioder, og materialstatus kan vises i oversikten (**BEKREFTET I KODEN**, MateMaTeX/frontend/src/app/year-plans/[id]/page.tsx).
2. **Kildebevisst produksjon:** Kompendier lagrer kilder, claims og truth-pass (**BEKREFTET I KODEN**, Skoleverksted/backend/platform/models.py og truth.py).
3. **Lærer i kontrollsløyfen:** kapitler kan redigeres, automatisk repareres, oppgraderes og godkjennes (**BEKREFTET I KODEN**, MateMaTeX/frontend/src/app/compendia/[id]/page.tsx).
4. **Fail-closed-intensjon:** PDF kan blokkeres når kapitler mangler verifisering (**BEKREFTET I KODEN**, Skoleverksted/backend/platform/router.py).
5. **Fagspesifikk kvalitet:** matematikk har deterministisk SymPy-/fasitkontroll i tillegg til generering (**BEKREFTET I KODEN**).
6. **Produksjonsbevissthet:** health/readiness, Docker, Render, Vercel, køer og smoke-test finnes (**BEKREFTET I KODEN/DOKUMENTASJON**, readiness.py og production-smoke.yml).
7. **Riktig tillitsretning:** Udir anbefaler lærerledelse, profesjonsfellesskap, utprøving/evaluering og personvernvurdering (**EKSTERN KILDE**, [Udir](https://www.udir.no/kvalitet-og-kompetanse/digitalisering-skole/kunstig-intelligens-i-skolen/rad-om-kunstig-intelligens-skolen/)).

## Brutal svakhetsliste

### 1. Global dataflate

**BEKREFTET I KODEN:** Store er «deliberately independent of authentication», modellene har ingen eier-/tenantfelt, og router.py eksponerer list, create, update, download og feedback uten auth.  
**Konsekvens:** feil lærer kan i prinsippet se, endre eller laste ned en annen lærers data. Dette er pilotblokkering hvis mer enn én betrodd bruker deler miljøet.

### 2. Kvalitetspass kan gi falsk trygghet

**BEKREFTET I KODEN:** truth-pass bygger på hentet kilde-evidens og modellens strukturerte claims.  
**STERK INFERENS:** «grønt» betyr at pipeline-reglene er oppfylt, ikke at en fagperson eller flere uavhengige kilder har bekreftet hver påstand. UI-teksten må derfor ikke tolkes som fasitgaranti.

### 3. Synkrone plattformjobber

**BEKREFTET I KODEN:** plattformens outline/generate/repair/compile-ruter utfører arbeid direkte, mens den robuste køen primært brukes av domain-jobber.  
**STERK INFERENS:** lange genereringer og PDF-kompilering kan møte proxy-/server-timeout, gi doble klikk eller uklare statuser.

### 4. Bredde før bevis

**BEKREFTET I KODEN:** tre fag, årsplan, temapakke, kompendium, prosjekter, bilder, øvelser, deling og historikk finnes side om side.  
**UTESTET HYPOTESE:** ingen vet hvilken av disse som skaper gjentatt verdi.  
**Konsekvens:** hver ny funksjon øker support-, evaluerings- og kostnadsflaten før retention er bevist.

### 5. Fragmentert start

**BEKREFTET I KODEN:** command palette mangler årsplan, prosjekt og temapakke; mobilnavigasjon mangler flere kjerneflater; årsplan-materiale sender læreren videre til faggenerering.  
**STERK INFERENS:** det er vanskelig å vite «hva er neste riktige handling?» uten forkunnskap.

### 6. Lokal lagring og drift

**BEKREFTET I KODEN/DOKUMENTASJON:** SQLite eller Postgres er mulig, og genererte filer ligger lokalt på Render-disk i dagens blueprint. Object storage/backup er omtalt som senere opsjon.  
**STERK INFERENS:** en skole trenger eksplisitt backup, eksport, sletting og gjenoppretting før dette kan bli system-of-record.

### 7. Kvalitetsevalueringen er for liten

**BEKREFTET I KODEN:** eval-suiten har fem syntetiske cases; truth-/kompendietester bruker mockede kilder og klienter.  
**UTESTET HYPOTESE:** kvalitet i ekte historie-, norsk- og matematikkmateriale er høy nok til lærerens tillit.  
**Konsekvens:** bygg et lite, ekspertvurdert golden set før du markedsfører «til å stole på».

### 8. Readiness er ikke sikkerhet

**BEKREFTET I KODEN:** readiness sjekker nøkler, storage, kompilator og konfigurasjon.  
**STERK INFERENS:** ready betyr at tjenesten kan starte, ikke at datatilgang, kostnader, faktakvalitet eller personvern er godkjent.

## Dokumentasjon versus kode

| Tema | Dokumentasjon | Faktisk kode | Vurdering |
|---|---|---|---|
| Samlet lærerplattform | README.md/status.md beskriver én plattform | Felles shell finnes, men tre domene-backender og flere separate auth-/jobbflyt | **STERK INFERENS:** samlet produktflate, ikke samlet sikkerhetsmodell |
| Skoleklar drift | Render/Vercel-dokumenter beskriver deploy og health-check | Platform-ruter mangler auth, tenant og backupkontroll | **BEKREFTET I KODEN:** ikke skoleklar flerbruker |
| Faktakontroll | produktløftet vektlegger truth-pass | truth-pass validerer kildestruktur og evidens, ikke uavhengig sannhet | **STERK INFERENS:** god kontrollmekanisme, ikke garanti |
| Robust kø | job manager og readiness dokumenteres | plattform-generering skjer synkront | **BEKREFTET I KODEN:** ulik robusthet mellom domain og platform |
| Produksjonsstatus | status.md beskriver siste tester og deploy | gjeldende branch er laerebokdesign-hefte, mens render.yaml peker på main | **BEKREFTET I KODEN/GIT:** deploy kan ligge etter aktiv utvikling |

## Målgrupperangering

Skår 1–5 er en **STERK INFERENS** basert på kodefit, problemets hyppighet, salgbarhet og pilotbarhet. Den er ikke et brukerintervju.

| Rang | Segment | Problemfrekvens/smerte | Betaling/tilgang | Kodefit | Hvorfor nå / ikke nå |
|---|---|---:|---:|---:|---|
| 1 | Historielærer VGS2, kilde- og teksttunge perioder | 5/5 | 3/5 | 5/5 | Årsplan + kompendium + kildespor passer direkte; nå |
| 2 | Samfunnsfag-/religionslærer VGS | 4/5 | 3/5 | 4/5 | Samme kildebehov, men bredere begrepsrom; etter første pilot |
| 3 | Andre teksttunge VGS-fag | 4/5 | 3/5 | 3/5 | Kan ekspandere når golden set og workflow er bevist |
| 4 | Matematikklærer VGS | 4/5 | 3/5 | 4/5 | Sterk verifisering, men annen arbeidsflyt |
| 5 | Norsk-/andrespråkslærer | 4/5 | 2/5 | 3/5 | Reelt behov, men CEFR og domene-API gjør budskapet mindre skarpt |
| 6 | Skoleleder/skoleeier | 3/5 | 5/5 | 1/5 | Betaler mulig, men lang salgssyklus og flerbrukerkrav først |
| 7 | Elev/student direkte | 4/5 | 1/5 | 1/5 | Krever elevvern, pedagogikk og annen onboarding; ikke nå |

### Anbefalt målgruppe

**Historielærere på VGS, først VG2, som lager periodiske læringsark/fordypningshefter fra årsplan.**

Hvorfor: konkret kalenderstyrt jobb; høy verdi av kilder, perspektiver og lærerens kontroll; dagens kompendium- og årsplan-kode støtter nesten hele flyten; læreren kan teste uten elevdata; historiefaget gir et godt golden set; ekspansjon til samfunnsfag er naturlig.

## Anbefalt produkt-wedge

Detaljert spesifikasjon ligger i research/PRODUCT_WEDGE.md. Kortversjonen er:

**Historieverksted: fra årsplan til godkjent, kildebelagt læringsark.**

Startpunkt: én periode i årsplanen.  
Sluttprodukt: ett kort læringsark eller fordypningshefte som viser kilder, påstander, usikkerhet, lærerens redigeringer og PDF/Word.  
Ikke start med: elevkontoer, LMS, alle fag, bildebibliotek, temapakker eller generell «lag hva som helst».

## Det magiske øyeblikket

- **Før:** Lærer har en periode i årsplanen, flere kilder og en tom dokumentmal.
- **Input:** tema, nivå, læringsmål og ett til tre konkrete kildelenker.
- **System:** lager disposisjon, foreslår avgrensning, skriver utkast, knytter hver viktig påstand til kildested, markerer usikkerhet og viser en endrings-/kontrollvisning.
- **Mål:** første review-ready utkast innen fem minutter i pilot (**UTESTET HYPOTESE**; dagens latency er ikke systematisk målt).
- **Troverdighet:** ingen grønn status uten konkret kilde; røde/uklare claims går til lærer; PDF blokkeres når terskelen ikke er nådd (**BEKREFTET I KODEN**).
- **Neste handling:** læreren godkjenner og klikker «lag neste periode»; godkjent ressurs blir søkbar og teller mot årsplanens dekning.

Dette bør være én sammenhengende flyt, ikke en meny av agentmoduser.

## Kvalitetsmotoren som mulig hovedprodukt

«AI» er ikke moat. En mulig moat er en akkumulert, fagspesifikk kvalitetssløyfe:

1. **Datamodell:** tenant, user, plan, period, artifact, evidence, claim, review, approval, evaluation run og revision event.
2. **Evidence graph:** hver claim lagres mot konkret kilde, passasje, hentet dato, kildekvalitet, modellforslag og lærerens beslutning.
3. **Golden sets:** ekspertmerkede oppgaver per fag, nivå og dokumenttype; mål unsupported claim-rate, citation precision, repair acceptance og teacher override.
4. **Edit learning:** lærerens redigeringer og avvisninger blir mønstre for avgrensning og prompt-/regeltest.
5. **Godkjent gjenbruk:** ressurs som er godkjent i én plan kan foreslås på nytt med kildeendringer, læreplanendringer og versjonsdiff.
6. **Portabel kvalitet:** API og eksport av claims/kilder gjør kontrollen nyttig selv når teksten flyttes til LMS eller dokument.

**STERK INFERENS:** dette blir sterkere for hver godkjente ressurs fordi systemet får bedre domene-eval, bedre avgrensningsregler og bedre forslag til kilder. Det blir bare en moat hvis dataene er strukturerte, sammenlignbare og knyttet til lærerens faktiske beslutninger. En løs samling PDF-er er lett å kopiere.

### Minimumskjerne før moat-arbeid

- auth/tenant-grense
- asynkron jobbstatus for lange operasjoner
- immutable evidence/claim history
- reell faglig golden set
- eksport, backup og sletting
- metrics for tid, godkjenning, avvisning og gjenbruk

## Retention og vekst

### Ekte loops

- **Ukentlig:** neste årsplanperiode viser «mangler materiale» og gir ett klikk til ny kildebelagt produksjon (**UTESTET HYPOTESE**).
- **Per undervisningsperiode:** lærer oppdaterer forrige ark med ny kilde eller klasseerfaring og får versjonsdiff (**UTESTET HYPOTESE**).
- **Fagseksjon:** godkjente ressurser kan gjenbrukes av kolleger, men krever auth/deling og audit-logg først (**UTESTET HYPOTESE**).
- **Årlig:** neste års plan kan kopiere struktur, mens kilde- og læreplanendringer flagges (**UTESTET HYPOTESE**).

### Falsk retention

- flere bildegeneratorer
- flere dokumenttyper uten godkjenningsbruk
- stor template-meny
- «AI crew»-visualisering uten målbar kvalitetsgevinst

## Forretningsmodell og distribusjon

| Modell | Når den passer | Krav/risiko | Anbefaling |
|---|---|---|---|
| Gratis lærer → betalt lærer | rask pilot og selvbetjening | lav ARPU, support må være minimal | test først |
| Lærer → fagseksjon | naturlig gjenbruk og deling | tenant, roller, audit-logg | neste steg |
| Skole → skoleeier | større kontrakt | DPIA, SSO, innkjøp, backup, SLA | ikke før grunnmur |
| Partner med fylke/NDLA/læremiddel | tillit og distribusjon | lang forhandling, innholdsrettigheter | utforsk senere |
| API/white-label | skalerbar kvalitetsmotor | stabil API, support, ansvarslinje | langsiktig |
| Læremiddelprodusent | faglig produksjon i volum | lisens- og IP-risiko | etter kvalitetsevidence |

**EKSTERN KILDE:** Udir krever at skoleeier vurderer pedagogisk nytte opp mot personvernkonsekvenser og vurderer på nytt når modell eller bruk endres ([Udir personvern](https://www.udir.no/kvalitet-og-kompetanse/digitalisering-skole/kunstig-intelligens-i-skolen/personvern-ki/)). Skoleeier er derfor et annet produkt- og salgsløp, ikke bare en større plan.

## Teknisk/operasjonell vurdering

### Behold

- domene-backender som avgrensede fagadaptere
- felles platform-modeller og truth-/quality-lag
- deterministiske matematikktester
- smoke-test og readiness
- durable jobs for lange domain-operasjoner

### Ikke gjør nå

- full omskriving til én backend
- ny modellleverandør uten eval-bevis
- ny design system-rewrite
- Postgres/Redis/object storage som skaleringstegn før pilotbehov er målt

### Må gjøres før flerbrukerpilot

1. Plattform-auth med minste rollemodell og tenant/eier på alle records.
2. Autoriserte list/get/update/download-ruter, også delte lenker.
3. Asynkron jobbstatus for outline, chapter generation, repair og compile.
4. Claim-level evidence og lærerens beslutning i immutable historikk.
5. Golden set for historie VG2 med ekspertfasit og falsk-positiv måling.
6. Backup/restore, sletting, retention og kostnadsbudsjett.
7. Observability: tid til første verdi, modellkostnad, retries, feil, godkjenning og avvisning.
8. Brukerstatus som sier «venter», «trenger kilderevisjon», «ferdig» og hva læreren gjør nå.

## Premortem: Skoleverksted mislyktes om to år

| Risiko | Tidlig faresignal | Billig eksperiment | Kill criterion / pivot |
|---|---|---|---|
| 1. Éngangsbruk | Ingen andre godkjente ressurs innen 14 dager | 5 lærere, 2 uker, manuell oppfølging | <2 av 5 lager ressurs nummer to: stopp bredde |
| 2. Kontrollkostnad høyere enn spart tid | Lærer bruker >30 min på faktasjekk per ark | Tidsstudie mot egen metode | Median reviewtid > produksjonstid: ikke skaler |
| 3. Falsk trygghet | Grønt pass endres ofte av faglærer | Blind golden-set-test med 30 claims | >5 % alvorlige unsupported claims: fjern grønt språk |
| 4. For mange innganger | Brukere spør hvor de starter | Test én CTA og fem oppgaver | <4/5 finner start uten hjelp: skjul moduler |
| 5. Konkurrent kopierer | Brukere sammenligner bare pris/knapper | Alternativtest mot MagicSchool/Brisk/NDLA | Ingen preferanse for kilde-/planløkken: repositioner |
| 6. Personvern stopper salg | Skoleleder ber om DPIA før prøve | DPIA-forberedende workshop | Kan ikke forklare dataflyt/sletting: pause skoleinnsalg |
| 7. Kostnad/latency ødelegger | Timeout, retries eller dyrt ark | Logg 50 genereringer | >5 min eller over budsjett på >20 %: forenkle |
| 8. Data går tapt | Restore-test feiler eller PDF finnes bare på disk | Backup/restore av pilotdata | Ingen verifisert restore: ikke lagre viktig innhold |
| 9. Ingen kollektiv loop | Ingen deling/gjenbruk | Del tre godkjente ressurser manuelt | <1 gjenbruk etter måned: ikke bygg sosialt lag |
| 10. Kilder/læreplan endres | Materiale blir gammelt uten varsel | Simuler én kildeendring og lag diff | Ingen tydelig oppdateringshandling: prioriter versjonering |

## Prioritert beslutning

1. Pilotér Historie VG2-wedgen med eksisterende kompendium/årsplan/truth-flyt.
2. Mål tid til godkjent ressurs, unsupported claims, andreukersbruk og gjenbruk.
3. Løs auth/tenant, async status og backup før flere enn betrodde pilotbrukere.
4. Bruk resultatene til å velge mellom samfunnsfag-ekspansjon og annen wedge.
5. Ikke la funksjonsbredde bli substitutt for bevis på nytte.

## Kilder

- [Udir — Råd om kunstig intelligens i skolen](https://www.udir.no/kvalitet-og-kompetanse/digitalisering-skole/kunstig-intelligens-i-skolen/rad-om-kunstig-intelligens-skolen/)
- [Udir — Personvern og KI](https://www.udir.no/kvalitet-og-kompetanse/digitalisering-skole/kunstig-intelligens-i-skolen/personvern-ki/)
- [Udir — Spørsmål til Skole-Norge høsten 2025](https://www.udir.no/tall-og-forskning/finn-forskning/rapporter/2026/sporsmal-skole-norge-hosten-2025/)
- [Datatilsynet — Funn fra tilsyn med personvernet i skolen](https://www.datatilsynet.no/aktuelt/aktuelle-nyheter-2025/funn-fra-tilsyn-med-personvernet-i-skolen/)
- [MagicSchool pricing](https://www.magicschool.ai/pricing)
- [Brisk FAQ](https://www.briskteaching.com/faq)
- [Diffit pricing](https://web.diffit.me/pricing)
- [Canva Education](https://www.canva.com/education/teachers/)
- [Common Planner pricing](https://www.commonplanner.com/p/pricing/)
- [NDLA — hvem er vi](https://ndla.no/nb/om/hvem-er-vi)
- [OECD — AI adoption in the education system](https://www.oecd.org/content/dam/oecd/en/publications/reports/2025/12/ai-adoption-in-the-education-system_43251cf0/69bd0a4a-en.pdf)

Alle eksterne sider er konsultert 2026-08-02. Priser, modeller og produktvilkår må verifiseres på nytt før kommersielle beslutninger.

