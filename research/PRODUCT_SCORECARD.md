# Skoleverksted product scorecard

**Oppdatert:** 2026-08-03

**Status:** baseline; de fleste produktmål er ennå `UKJENT`

**Pilotdom:** `REJECTED`

Scorecardet skiller mellom foreslått mål og faktisk observert verdi. Et mål er ikke bevis på at produktet oppfyller det. `Ukjent` er et funn og skal ikke fylles med antakelser.

## Evidensnøkler

- `PROD`: offentlig produksjonsobservasjon med releaseidentitet.
- `RUNTIME`: test i dokumentert Docker-runtime.
- `LOCAL`: lokal test eller reproduksjon.
- `CODE`: direkte implementasjonslesing.
- `DOC`: eksisterende rapport.
- `PILOT`: måling med navngitt pilotlærer og avtalt protokoll.

## Tillit og faglig kvalitet

| Metrikk | Foreslått mål / port | Nåverdi | Evidens | Eier | Neste måling |
|---|---|---|---|---|---|
| Konkrete påstander med godkjent evidens | Minst 80 % som maskinport; 100 % skal være evidensbelagt, kvalifisert eller eksplisitt uløst før sluttgodkjenning | 32/44 = **73 %** i siste identiske prodscenario | PROD/DOC: `084614...` | Produktkvalitet + fagreviewer | Kjør samme scenario etter autorisert deploy |
| Grønn claim uten observert/godkjent kilde | **0** | Koden avviser uobserverte URL-er; bare ett prodscenario bevist | CODE/LOCAL + begrenset PROD | Backend/platform | Negative prod-fixtures og artefaktreview |
| Lærerkilder med bevart opprinnelse og fetch-status | **100 %** | 3/3 lærer-URL-er ble `origin=teacher`, `fetch_status=provided` i scenariet | PROD/DOC | Backend/platform | Verifiser at de samme kildene vises i sluttfil |
| Systemintroduserte språkfragmenter | **0** | 0 flagget i ett prodscenario; bred manuell språkreview mangler | PROD/DOC | Produktkvalitet | Manuell kontroll av alle kapitler og sluttfiler |
| Utrygg automatisk mutasjon av delvis/gjentatt tekst | **0** | Punktumfeil reprodusert og rettet lokalt; 12 målrettede tester grønne | LOCAL | Backend/platform | Full suite, så identisk prodscenario |
| Matematiske svar kontrollert | 100 % av parsebare svar; 0 kjente feil i godkjent sett; uparsebare synliggjøres | Deterministiske kontrollører og tester finnes; fersk prod-generering `UKJENT` | CODE/RUNTIME | Matematikkfaglig eier | Fast fixture + manuell kontroll i produksjon |
| Udokumenterte påstander i godkjent sluttfil | **0** | `UKJENT`; ingen godkjent kompendiumsluttfil fra identisk scenario | DOC | Fagreviewer | Claim-til-fil-revisjon på PDF og DOCX |
| Kritiske fag-/språk-/layoutfeil i manuell review | **0** | `UKJENT` | — | Pilotleder + fagreviewer | To uavhengige reviewere, fast rubrikk |
| Godkjenning knyttet til eksakt versjon/digest | **100 %** | Kapittelstatus invalidiseres ved tekstendring; komplett artefaktdigest/reviewer-kjede `UKJENT` | CODE | Backend/platform | Journalfør reviewer, tidspunkt og digest |

## Pålitelighet og jobbkontroll

| Metrikk | Foreslått mål / port | Nåverdi | Evidens | Eier | Neste måling |
|---|---|---|---|---|---|
| Wedge-jobber med terminal durable status | **100 %** | Platform repair er synkron/prosesslokal; timeout ga 504 | CODE + PROD | Backend/platform | Durable jobbtest gjennom refresh og restart |
| Vellykket kapittelreparasjon innen grensen | ≥95 % i pilot; p95 under avtalt grense | 0/1 i dokumentert prodscenario; 504 etter 120 s | PROD/DOC | Backend/platform + drift | Minst 20 kontrollerte reparasjoner med resultatkode |
| Tvetydige/foreldreløse jobber | **0** | `UKJENT`; operation-ID og response request-ID kan avvike | CODE | Drift | Én ID fra UI-event til lagret resultat; restart-audit |
| Dobbelklikk/retry dupliserer kostbart arbeid | **0** | Kapittellås avviste én retry med 409; idempotens over restart `UKJENT` | PROD + CODE | Backend/platform | Samtidighets- og restarttest med samme idempotensnøkkel |
| Refresh kan gjenoppta venting | **100 %** | Kompendium-side har lokal loading; `IKKE OPPFYLT` | CODE | Frontend + backend | E2E refresh under outline/generate/repair/compile |
| Compile-feil har trygg recovery uten ny generering | **100 %** | Compile ble korrekt blokkert; vellykket recovery `UKJENT` | PROD/DOC | Backend/platform | Reparer → approve → compile samme versjon |
| Frontendstatus samsvarer med autoritativ ledger | **100 %** | Fag/Norsk/Matematikk og platform har forskjellige jobbmekanismer; samlet verdi `UKJENT` | CODE | Plattformarkitektur | Kontrakttest for accepted/running/terminal |
| Full runtime-regresjon | **100 % grønn** | Etter M1: **403 bestått, 2 hoppet over, 47 warnings** | RUNTIME | Produktkvalitet | Gjenta på hver eksakte releasekandidat |
| Frontend test/type/build/lint | Alle fire grønne | 13/13 test, type og build grønne; lint **ikke konfigurert** | LOCAL | Frontend | Legg til ikke-interaktiv ESLint-konfig og CI-gate |

## Lærertid og brukerreise

| Metrikk | Foreslått mål / port | Nåverdi | Evidens | Eier | Neste måling |
|---|---|---|---|---|---|
| Tid fra årsplanperiode til første redigerbare utkast | Median ≤2 min for kort artefakt | Historisk outline ca. 39 s; komplett måling `UKJENT` | DOC | Produkt + frontend | Instrumentert wedgeoppgave med 5 pilotøkter |
| Tid fra start til godkjent, nedlastet artefakt | Median ≤15 min; ingen økt >30 min uten forståelig recovery | `UKJENT`; identisk kompendium fullførte ikke | — | Pilotleder | Observert oppgavetest, samme manus |
| Aktive lærerhandlinger til første utkast | ≤6 meningsfulle handlinger | `UKJENT` | — | Produktdesign | Instrumentert UI og observasjon |
| Andel økter med tapt utkast | **0 %** | Kompendium har ulagret lokal edit-state; faktisk rate `UKJENT` | CODE | Frontend | Refresh/navigasjonstest + pilottelemetri |
| Andel feil der læreren forstår neste handling | ≥90 % i brukerintervju; 100 % for kjente koder | Backendbody finnes; frontend for 504/409 ikke produksjonskontrollert | CODE/DOC | Produktdesign + frontend | Skjermtest av alle wedge-feilkoder |
| Manuell etterarbeidstid etter generering | Median ≤5 min, og lavere enn lærerens baseline | `UKJENT` | — | Pilotleder | Før/etter-måling med samme lærer og tema |
| Gjenfinning av siste godkjente versjon | 100 % innen 30 s | Historikk finnes; eier/versjonskjede og faktisk tid `UKJENT` | CODE | Frontend + backend | Gjenfinningsoppgave dagen etter |
| Forståelse av maskinkontroll versus faglig ansvar | 100 % kan forklare forskjellen | `UKJENT` | — | Produktkvalitet | Femsekunders- og teach-back-test |

## Drift, sikkerhet og sporbarhet

| Metrikk | Foreslått mål / port | Nåverdi | Evidens | Eier | Neste måling |
|---|---|---|---|---|---|
| Produksjonsrelease kan identifiseres | 100 % av readiness-responser | `69b00d81e5a7`, fingerprint `dc08f612a352` | PROD | Drift | Behold smoke per deploy |
| Klikk → request → jobb → resultat → artefakt har én korrelasjon | **100 %** | `IKKE OPPFYLT` for platform repair | CODE | Drift + backend | Propager samme ID og test loggkjeden |
| Platform-objekter med autentisert eier/tenant | **100 % før flerbrukerpilot** | **0 % dokumentert**; store er auth-uavhengig | CODE | Sikkerhet + backend | Skjema/migrasjon og negative auth-tester |
| Uautorisert kryssbrukertilgang | **0** | `UKJENT`; platform har ingen eierkontroll | CODE | Sikkerhet | IDOR-test for list/get/patch/download |
| Dyre platform-kall med kvote og idempotens | **100 %** | Ingen samlet platform-kontroll dokumentert | CODE | Backend + drift | Per-prinsipal rate/cost-test |
| Hemmeligheter i klient/readiness/logg | **0** | Readiness skjuler verdier; full release-loggscan `UKJENT` | LOCAL/CODE | Drift/sikkerhet | Secret scan + loggfixture |
| Backup med verifisert restore | Daglig backup; kvartalsvis restore; RPO/RTO avtales før pilot | `UKJENT` | — | Drift | Gjenopprett kopi av SQLite og filer i isolert miljø |
| Retention, eksport og sletting | 100 % dokumentert og testet | `IKKE OPPFYLT` for platform | CODE | Produkteier + personvern | Policy + API/operasjonstest |
| Telemetry-feil som er synlige for drift | 100 % varsles uten å stoppe brukerjobben | Middleware svelger feil; platform-ruter observeres ikke | CODE | Drift | Test og varsel på telemetry write failure |
| Produksjonssmoke etter deploy | 100 % | Bestod på forsøk 1 den 2026-08-03, uten generering | PROD | Drift | Kjør ved hver release og arkiver release-ID |

## Produktbevis

| Metrikk | Foreslått mål før skalering | Nåverdi | Evidens | Eier | Neste måling |
|---|---|---|---|---|---|
| Navngitte pilotlærere som fullfører wedgen | Minst 5, på minst 3 ulike tema | **0 dokumentert** | DOC | Produkteier | Rekrutter kontrollert pilot etter sikkerhetsport |
| Uke-4 gjenbruk blant pilotlærere | ≥60 % | `UKJENT` | — | Produkteier | Cohort-måling |
| Artefakter faktisk brukt eller eksplisitt planlagt brukt | ≥70 % av godkjente artefakter | `UKJENT` | — | Pilotleder | Kort oppfølging etter undervisning |
| Opplevd tillit etter faktisk review | Median ≥4/5, ingen kritisk tillitshendelse | `UKJENT` | — | Produktkvalitet | Standardisert spørsmålssett + hendelseslogg |
| Betalings-/innkjøpssignal | Minst ett konkret, dokumentert neste steg | `UKJENT` | — | Produkteier | Ikke mål før wedge og pilotkvalitet er bevist |

## Gjeldende beslutning

Produktet er **ikke pilotklart**. Tekniske sperrer fungerer delvis, men det finnes ingen vellykket produksjonsverifisert sluttartefakt for det identiske scenarioet, ingen durable platform-jobb, ingen plattformeier/tenant og ingen gyldige bruks-/retentiondata.

M1 er commit `912007b` og har full runtime-regresjon. Neste oppdatering skal bare endre scorecardet når en ny måling faktisk er utført; målverdier og antakelser skal ikke presenteres som resultater.
