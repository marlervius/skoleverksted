# Skoleverksted product excellence exec-plan

**Status:** levende gjennomføringsplan

**Oppdatert:** 2026-08-08

**Produksjonsdom:** `REJECTED`

**Deployet release:** `ff725bb69978` (kandidaten, deployet 2026-08-06 13:09:58Z)

**Forrige P0:** A — repair execution / durable job architecture. **Løst på
kodenivå, ikke i produksjon.** Se punkt 15 for problemet og punkt 16 for
løsningen.

**Neste P0:** deploy av durable-repair-kandidaten og ny identisk Historie
VG2-kjøring. Se punkt 16.6.

**Primær wedge:** Historie VG2, én periode i årsplanen til et kildeforankret og lærergodkjent læringsark eller kort kompendium

**Første milepæl:** sikker, fail-closed redigering av setninger i sannhetslaget

## 1. Formål og sannhetsregler

Denne planen skal gjøre Skoleverksted til et verktøy en lærer kan stole på i et reelt arbeidsløp. Den er både beslutningslogg, prioriteringsgrunnlag og release-port. Den erstatter ikke de detaljerte hendelsesrapportene.

Alle påstander i planen merkes etter dette evidenshierarkiet:

1. `PRODUKSJONSBEVIST`: observert mot offentlig Vercel/Render med identifisert release.
2. `RUNTIME-TESTET`: kjørt i den dokumenterte Docker-runtime eller tilsvarende produksjonsnær runtime.
3. `LOKALT TESTET`: testet i lokal arbeidskopi, men ikke i produksjon.
4. `KODEBEVIST`: direkte lest i implementasjonen, men ikke demonstrert ende til ende.
5. `DOKUMENTERT`: rapportert i repoet; kan være historisk.
6. `UKJENT`: ingen gyldig måling eller observasjon. Ukjent skal aldri fremstilles som grønt.

## 2. Kontrollert utgangspunkt

| Felt | Verifisert tilstand 2026-08-03 | Evidens |
|---|---|---|
| Aktiv branch | `laerebokdesign-hefte` | lokal Git |
| Lokal HEAD / releasekandidat | `ff725bb6997879e74d60d1d539c57e18578f95ad` (`Document product excellence baseline`) | lokal Git |
| M1 kodecommit | `912007b` (`Make truth edits sentence-safe`) | lokal Git; ikke deployet |
| Kandidatens eksakte diffgrunnlag | `origin/main..HEAD`: `2e66ec7`, `22b80d9`, `912007b`, `ff725bb`; 11 filer, 809 innsettinger, 29 slettinger | lokal Git |
| `origin/main` og produksjonsrelease | `69b00d81e5a7d823eb284bc7aee37a8cac6f29ed` | lokal Git + offentlig readiness |
| Offentlig frontend | `https://skoleverksted.vercel.app` svarte 200 og viste felles inngang og produktkort | produksjonsobservasjon |
| Offentlig backend | readiness svarte 200, `status=ready`, alle readiness-sjekker sanne | produksjonsobservasjon 2026-08-03 |
| Produksjonslagring | SQLite på `/var/data/platform/skoleverksted.sqlite3` | readiness |
| Produksjonskø | `sqlite-local`; Redis ikke konfigurert | readiness |
| Produksjonskonfigurasjon | prompt `skoleverksted-v3`, tekstmodell `gemini-3.5-flash`, bildemodell `gemini-3.1-flash-image`, fingerprint `dc08f612a352` | readiness |
| Siste identiske produksjonsscenario | `084614b8247d413b8d1ba38cb6166fce`: 32/44 verifisert, 73 %, repair 504, retry 409, compile 409 | produksjonsrapportene |
| Produksjonsdom | `REJECTED` | `PILOT_GO_NO_GO.md` |

Arbeidskopien inneholdt allerede urelaterte endringer i MateMaTeX og fire utrackede strategidokumenter. De er ikke endret, slettet eller inkludert i denne milepælen.

## 3. Hva som faktisk virker

- En felles Next.js-frontend gir inngang til Fag, Norsk, Matematikk, årsplaner, kompendier, temapakker, prosjekter og historikk. Dette er synlig i produksjon.
- En felles FastAPI-inngang monterer de tre domenetjenestene under stabile prefikser og eksponerer readiness og request-ID. Dette er kode- og produksjonsbevist.
- Kompendiumløpet har disposisjon, kapittelgenerering, kildevisning, sannhetspass, lærerredigering, eksplisitt kapittelgodkjenning og compile-port. Porten blokkerte faktisk PDF/Word i produksjon da kravene ikke var møtt.
- Kildenes opprinnelse og fetch-status ble bevart i det identiske produksjonsscenarioet. Påstander uten godkjent evidens blir ikke automatisk grønne.
- Fag-verktøyet har et asynkront jobbforløp og kan levere elev-PDF og separat lærerrapport. Norsk har bakgrunnsjobber og delt passordbeskyttelse. Matematikk har bruker-/jobb-eierskap, server-side API-nøkkel og deterministiske kontrollører for blant annet matematikk og LaTeX.
- PDF/DOCX-renderere, strukturelle tekstkontroller, timeout og kapittellås har omfattende lokale tester.
- Kandidat-runtimen i det eksakte Docker-imaget bestod **398 tester og 2 hoppet over**. Frontend bestod 13 tester, typekontroll og produksjonsbygg. Lint er ikke operativ fordi ESLint-konfigurasjon mangler.

Dette er ikke det samme som at hele produktet er pilotklart. Det beviser komponenter og sperrer, ikke et vellykket lærerforløp.

## 4. Tilstandsmatrise

| Område / flyt | Frontend | Backend og data | Testdekning | Produksjonsbevis | Dokumentert defekt / konsekvens | Konfidens |
|---|---|---|---|---|---|---|
| Fagmateriell | Veiviser, forhåndsvisning, eksplisitt godkjenn-og-lagre, kobling til årsplan | Egen jobbmanager, PDF og separat faktarapport | Bred lokal suite, PDF-fixtures | Side og proxy svarer; ingen fersk ekte generering i denne revisjonen | Ende-til-ende faglig kvalitet, tid og lærergodkjenning er ukjent | middels |
| Norsk | Stor én-sides arbeidsflate, forhåndsvisning, nivåvarianter og nedlasting | Bakgrunnsjobber, delt `APP_PASSWORD`, PDF/ZIP | Lokal suite | Side svarer; ingen fersk ekte generering | Delt passord er ikke brukeridentitet; kompleks flate kan gi høy kognitiv kostnad | middels |
| Matematikk | Genereringsveiviser, progresjon, resultat, deling | Eierskap på jobber, auth-avhengigheter, rate limit, matematiske og LaTeX-kontroller | Bred lokal suite | Estimat gjennom proxy svarte 200 i smoke | Faktisk generert oppgavesett og fasit er ikke produksjonsverifisert i denne revisjonen | middels |
| Årsplan | Opprett/generer, perioder og materialkoblinger | Durable JSON-modeller i SQLite | Plattformtester | Ruter/sider svarer | Read-modify-write av hele JSON-objekt kan gi tapte samtidige endringer; ingen eier | middels-høy |
| Kompendium | Disposisjon, kapittelvis redigering, sannhetspass, godkjenning, compile | Synkrone kall, JSON/SQLite, lokale kapittellåser | Omfattende lokale tester | Identisk scenario kjørt | 73 % evidens; repair 504; refresh/restart og vellykket sluttfil ikke bevist | høy |
| Temapakker | Oppretting og oversikt finnes | Plattformlagring og generering | Lokal rutetestdekning | Side svarer | Ikke knyttet til bevist, smal lærerjobb; øker produktbredden | middels |
| Prosjekter/historikk | Oversikt og gjenbruk av kontekst | Felles platform store/job telemetry | Lokale tester | Sider svarer | Plattformtelemetri observerer ikke platform-rutene; autoritativ status splittes mellom systemer | middels-høy |
| Deling | Matematikk har delingslenker og egen flate | Tokenbasert deling i matematikkmodulen | Lokale tester finnes | Ikke kontrollert i denne revisjonen | Plattformartefakter har ikke dokumentert tilgangsmodell; offentlig deling/utløp må pilottestes | lav-middels |
| Sannhet og kildeproveniens | Krav, kilder, utdrag, status og begrensninger vises | Grounding, URL-normalisering, coverage og fail-closed compile | Plattform- og fixturetester | Kildeopprinnelse bevist; 32/44 verifisert | Lokal kandidat kunne slette nabosetning ved punktumvariant; rettet i første milepæl, ikke produksjonsbevist | høy |
| Bilder | Valg mellom ingen, Commons og KI | Commons-host allowlist, type-/størrelsesgrenser, kreditering | Lokale tester | Ikke verifisert i sluttartefakt | Lisens, kreditering, motivtreff og feilmodus er ikke manuelt vurdert i produksjon | middels |
| PDF/DOCX | Nedlasting etter eksplisitte handlinger | Typst/DOCX-renderere; kompendium compile-port | Lokale renderer- og akseptansetester | Blokkering bevist; vellykket kompendiumfil mangler | Visuell QA, klasseromsutskrift og kildehenvisninger i sluttfil er ukjent | høy |
| Jobber/reparasjon | Tekstlig ventestatus; lokal side-state | Platform repair er synkron, 120 s timeout, daemontråd og prosesslokal lås | Timeout/lås testet | 504 + 409 bevist | Ingen durable platform-jobb, kansellering eller restart-recovery; operation-ID kan avvike fra response request-ID | høy |
| Deploy/readiness | Vercel betjener statiske sider | Render readiness med release/fingerprint/storage | Blueprint/readiness/smoke-tester | 200 og release identifisert | Readiness sier at avhengigheter finnes, ikke at kjerneflyten, auth eller datagjenoppretting virker | høy |

## 5. Kritisk lærerreise

Den smale reisen er: **årsplanperiode i Historie VG2 → valgt lærergrunnlag → redigerbart utkast → evidenskontroll → eksplisitt godkjenning → nedlastbar fil → lagret kobling til perioden**.

| Trinn | Nåværende støtte | Hvor læreren kan stoppe eller miste tillit | Nødvendig instrumentering / akseptanse |
|---|---|---|---|
| 1. Oppdage | Mange kort og tre toppverktøy på forsiden | For mange likeverdige innganger; wedge er ikke tydelig | Klikk fra forside til wedge, avbruddsrate, fem-sekunders forståelsestest |
| 2. Forstå | Produktkort og modultekster | Uklart hva som lagres, hva KI gjør og når noe er trygt | Kort løfte med eksempelartefakt, databruk og kvalitetsport |
| 3. Konfigurere | Mange fag-, nivå-, type-, bilde- og kildevalg | Høy beslutningskostnad før verdi; tekniske valg eksponeres | Tid og antall handlinger til gyldig start; anbefalte standardvalg |
| 4. Starte | Generer-knapper og noen async jobber | Dobbelklikk, nettverksfeil og dyr retry kan duplisere arbeid | Én idempotensnøkkel fra UI til jobb; accepted-event med request/operation-ID |
| 5. Vente | Fag/Norsk/Matematikk har jobbstatus; kompendium har lokal loading | Kompendium kan vente 120 s uten durable gjenfinning; refresh mister state | Durable jobbstatus, trinn, sist oppdatert, trygg refresh/reconnect og forventet ventetid |
| 6. Forstå status | Sannhetspass og noen vennlige feiltekster | Backend `detail` sendes ofte direkte; request-ID og repair-ID kan være forskjellige | Stabil feilkode, lærerforklaring, én korrelasjons-ID og anbefalt neste handling |
| 7. Redigere | Kapitteltekst kan redigeres manuelt | Ulagrede kompendiumendringer kan forsvinne ved navigasjon/refresh; hele JSON kan overskrives | Autosave/draft-versjon, dirty-state-varsel, optimistisk versjonskontroll og gjenoppretting |
| 8. Godkjenne | Kapittelapproval krever sannhetspass; Fag har eksplisitt lagring | Grønn strukturell status kan mistolkes som faglig kvalitet; manuell vurdering ikke journalført | Reviewer, tidspunkt, versjon, kontrolliste og eksplisitt forskjell mellom maskinkontroll og faglig godkjenning |
| 9. Laste ned | PDF/DOCX og andre formater finnes | Compile kan feile sent; vellykket kompendiumfil og layout er ikke produksjonsbevist | Compile-jobb, artefaktdigest, sidetall, visuell QA og trygg retry uten regenerering |
| 10. Gjenfinne | Historikk, prosjekter og årsplanmaterialer finnes | Ingen plattformeier/tenant; uklare regler for sletting, eksport og backup | Eier, søk, siste versjon, retention, eksport/sletting og restore-drill |

### Falske grønne tilstander som skal forbys

- `ready` må ikke tolkes som «pilotklar»; det betyr bare at runtime-avhengigheter er tilgjengelige.
- `verified` skal gjelde en identifisert claim-versjon og en observert, godkjent kilde, ikke bare en URL modellen oppga.
- `approved` skal ugyldiggjøres når teksten eller kildene endres.
- `completed` jobb skal bety at resultat og artefakt er durable og gjenfinnbare.
- En generert eller kompilert fil er ikke faglig godkjent før en lærer har godkjent akkurat den digest/versjonen.

## 6. Rangering av kvalitetsgjeld

Rangering bruker ordinære nivåer (`kritisk`, `høy`, `middels`, `lav`) for konsekvens, sannsynlighet, tillit og brukeromfang, justert for kostnad å verifisere eller rette. Det er en beslutningsregel, ikke et konstruert tallgrunnlag. Produksjonshendelser og mulig datatap rangeres foran estetikk.

| Rang | Risiko | Konsekvens × sannsynlighet × tillit × omfang / kostnad | Evidens | Beslutning |
|---|---|---|---|---|
| 1 | Sannhetsredigering kan mutere mer tekst enn modellen identifiserte | Kritisk tillits- og datatapkonsekvens; kandidatregresjon var deterministisk; liten, trygg retting | Lokalt reprodusert: remove med punktum slettet nabosetningen | Første milepæl, implementert lokalt og fail-closed |
| 2 | Kjerneartefakt når ikke kvalitetsporten og repair fullfører ikke | Høy lærer- og pilotkonsekvens; faktisk produksjonshendelse; treffer hele wedgen | 32/44 = 73 %, repair 504, ingen sluttfil | Neste produktmilepæl: durable reparasjon + samme scenario til reell lærerreview |
| 3 | Platform-ruter og data mangler bruker-/skoleeierskap | Kritisk personvern- og dataseparasjonsrisiko; alle platform-objekter berøres | `store.py` er eksplisitt auth-uavhengig; platform-routeren har ingen auth-avhengighet | Pilotblokkering før flere enn en kontrollert bruker/skole |
| 4 | Platform-generering/reparasjon er synkron og prosesslokal | Høy stabilitets- og kostnadsrisiko; refresh/restart/skalering kan gi tvetydig jobb | 120 s 504, daemontråd, prosesslokal lock, SQLite-local kø | Flytt wedge-jobbene til durable ledger/worker med én ID og idempotens |
| 5 | Sporbarhet slutter før komplett lærer-/artefaktkjede | Høy diagnose- og tillitskostnad; problemer tar lang tid å bevise | Platform-ruter mangler telemetry; response request-ID og operation-ID kan avvike; ingen sluttfil-evidens | Én eventkjede fra klikk til godkjent digest, uten elevdata eller hemmeligheter |

Neste lag av gjeld er manglende backup/restore/retention, lost-update-vern i JSON-store, manglende frontend-lintkonfigurasjon, bred navigasjon og ukjent produkt/marked-fit. Ingen av disse skal skjules, men de slår ikke den dokumenterte datatapsregresjonen som første sikre endring.

## 7. Primær wedge

### Valg

**Historielærer på VG2 som velger én periode i en eksisterende årsplan og trenger et kildeforankret, redigerbart og utskriftsklart læringsark eller et kort kompendium, med eksplisitt faglig godkjenning.**

Dette er en testbar hypotese, ikke bevist product-market fit. Repoet inneholder ingen gyldige data om aktive lærere, gjenbruk, betaling eller retention.

### Beslutningsmatrise

| Kandidat | Konkrete brukerbehov | Differensiering mot generell KI/Word og innholdsbank | Nåværende bevis | Beslutning |
|---|---|---|---|---|
| Historie VG2, én årsplanperiode → kildebelagt artefakt | Samle lærerens plan, kilder, nivå, tekst, kildekontroll og fil i ett forløp | Verdien er sporbar kildebruk, revisjon og godkjenning, ikke bare tekstgenerering | Mest gjennomarbeidet sannhetspass og historisk produksjonsscenario | **Velg** |
| Generisk helårs-kompendium | Stor leveranse | Lang ventetid, mange feilflater og tung review før første verdi | 73 % og repair-feil i produksjon | Senere; bruk korte artefakter først |
| Generisk Fag-læringsark | Raskt materiale | Nærmere vanlig KI + dokumentmal uten bevist kilde-/årsplanloop | Teknisk moden, men fersk faglig prod-evidens mangler | Sekundær leveranse i wedgen |
| Norsk/FOV | Nivåtilpasset språkstøtte | Relevant, men egen kompleks jobb og målgruppe | Produktet finnes; wedgebevis mangler | Behold stabilt, ikke utvid nå |
| Matematikk | Verifiserte oppgaver og fasit | Sterk kontrollverdi, men annen brukerjobb og teknologistakk | Lokale kontrollører er sterke; produksjonskvalitet ukjent | Egen fremtidig wedge, ikke bland inn nå |
| Årsplan/temapakker alene | Planlegging | Ligner mal/planverktøy uten bevist gjennomføring til klasserom | UI og lagring finnes | Bruk som inngang, ikke eget hovedløfte |

### Ideell første bruker og nåværende arbeid

Første bruker er én navngitt Historie VG2-lærer i en kontrollert pilot. I dag finner læreren kompetansemål og kilder, lager disposisjon, ber en generell KI om tekst, flytter innhold til Word/Docs, kontrollerer påstander manuelt, redigerer, setter opp layout og lagrer filen separat fra årsplanen. Skoleverksted skal redusere disse håndoffene og gjøre det synlig hva som er maskinkontrollert, hva som er faglig vurdert og hvilken versjon som ble brukt.

### Konkret forbedring som må bevises

Fra én periode skal læreren kunne få et første redigerbart utkast med egne kilder, rette og godkjenne det, og laste ned en gjenfinnbar sluttfil uten å miste arbeid eller møte en tvetydig jobb. Alle konkrete påstander i sluttversjonen skal ha godkjent evidens eller være tydelig uavklart; den foreslåtte minimumsporten på 80 % alene er ikke et kvalitetsløfte for sluttfilen.

### Not now

- Ingen nye moduler, agenter, outputtyper eller designvarianter.
- Ingen markedsplass, sanntidssamarbeid, skoleomfattende deling eller LMS-integrasjon.
- Ingen full omskriving av backend eller ny databasestrategi før wedge-data krever det.
- Ingen «autonom godkjenning»; faglig læreransvar skal være eksplisitt.
- Ingen produksjonsdeploy før hele release-porten er grønn og autorisert.

## 8. Pilottrusselmodell

| Aktivum / grense | Trussel | Nåværende kontroll/evidens | Minimum før pilot |
|---|---|---|---|
| Årsplaner, kompendier og prosjekter | En bruker kan lese eller endre en annens data | Platform-router/store har ingen eier eller auth | Autentisert pilotbruker, owner/tenant på alle objekter, negative autorisasjonstester |
| Norskmodulen | Delt passord kan deles, logges eller ikke tilbakekalles per bruker | Bearer `APP_PASSWORD` | Unikt pilotprinsipal eller eksplisitt énbrukerisolasjon; ingen delt hemmelighet i nettleserlagring/logg |
| Matematikkjobber | IDOR på jobb/resultat/deling | `get_current_user` og owner-avhengigheter finnes | Integrasjonstest for annen bruker, tokenutløp og tilbakekalling |
| Plattformnedlastinger | Uautorisert dokumenttilgang via ID | Ingen platform-auth | Eierkontroll på metadata og filstrøm; tilfeldig ID er ikke tilgangskontroll |
| Delingslenker | Utilsiktet varig offentlig tilgang | Tokenflyt finnes i matematikk | Utløp, tilbakekalling, minimal metadata og pilotbeslutning om hva som kan deles |
| Lærerens kildetekst og opplastinger | Prompt injection, overstore/farlige filer, persondata | Pydantic-grenser og enkelte filgrenser finnes; ingen samlet data policy | MIME/signatur/size-kontroll, prompt-data-separasjon, personvernvarsel, ingen elevdata i pilot |
| Eksterne bilder/URL-er | SSRF, skadelig type, lisensbrudd | Commons HTTPS-host allowlist, type- og størrelsesgrenser, trygg frontendlenke | Behold allowlist; test redirect/DNS-grenser; synlig kreditering/lisens i sluttfil |
| Generert Markdown | XSS eller farlige lenker | React-tekstnoder, ingen raw HTML, bare HTTPS-lenker | Sikkerhetsregresjonstest for HTML/javascript/data-URL og rel-attributter |
| API-nøkler og passord | Lekkasjer i klient, readiness eller logger | Server-side proxy i matematikk; readiness viser bare boolsk tilstedeværelse | Secret scan av release; strukturerte logger uten prompt/kildetekst/secret; rotasjonsprosedyre |
| Dyre KI-endepunkter | Misbruk, kostnadseksplosjon, dobbelkjøring | Rate limit i domenemoduler; ingen synlig platform-rate limit/idempotens | Auth + per-bruker kvote + idempotens + kost/event + hard samtidighetsgrense |
| SQLite og lokale filer | Tap ved deploy/diskfeil, uklart sletteløp | Persistent Render-sti rapporteres | Kryptert backup, dokumentert restore-test, retention, eksport og sletting |
| Logger/telemetri | Person- eller kildedata lagres; feil forsvinner | Request-ID finnes; telemetry-feil svelges | Dataminimering, allowlistede felter, retention, varsel på telemetry-feil og én korrelasjons-ID |

## 9. Første implementerte milepæl

### Problem og reproduksjon

Den lokale kandidaten slettet nabosetningen når verifierens `exact_text` inneholdt avsluttende punktum:

```text
Før: Norge fikk en ny grunnlov i 1814. Sverige beholdt sin grunnlov.
Handling: remove("Norge fikk en ny grunnlov i 1814.")
Før retting: <tom tekst>
```

Uten punktum fungerte fjerningen, og kvalifisering med punktum ble stående uendret. Dette var en deterministisk lokal kandidatregresjon med direkte fare for skjult innholdstap.

### Beslutning

Automatisk endring tillates bare når `exact_text`:

- forekommer nøyaktig én gang;
- er en komplett setning med entydig start og slutt, uansett om modellen tok med sluttpunktum; eller
- er en komplett Markdown-overskrift/listelinje.

Delvise, manglende eller gjentatte treff blir stående urørt og registreres som begrensning for lærerreview. Sannhetslaget er dermed fail-closed.

### Berørte filer og akseptanse

- `Skoleverksted/backend/platform/truth.py`
- `Skoleverksted/backend/tests/test_truth.py`

Akseptanse:

- Full setning med punktum kan fjernes uten å fjerne neste setning.
- Samme setning uten punktum i `exact_text` får identisk resultat.
- Kvalifisering erstatter bare hele setningen og bevarer nabosetningen.
- Delvis treff og gjentatt tekst blir ikke endret.
- Eksisterende sannhetslagtester og hele monorepo-suiten må være grønne.

Målrettet resultat: **12 tester bestått**. Kandidat-imaget bestod **398 tester, 2 hoppet over** på tvers av plattform og alle tre domener; `compileall`, `py_compile`, frontendtest, typekontroll og produksjonsbygg bestod. Dette er runtime-bevis, ikke produksjonsbevis.

### Hvorfor denne milepælen går foran auth, jobbarkitektur og UX

Alle tre er større pilotblokkere, men denne feilen var konkret reproduserbar i deploykandidaten, kunne endre lærerens tekst stille og hadde en liten reverserbar retting. Den måtte fjernes før kandidaten i det hele tatt kunne vurderes for ny produksjonskjøring.

### Gjenværende risiko og rollback

Rettelsen gjør ingen semantisk vurdering av om erstatningsteksten er korrekt. Den garanterer bare at automatisk mutasjon har en entydig avgrensning. Den er ikke produksjonsverifisert. Rollback er å redeploye siste kjente produksjonsrelease `69b00d81e5a7`; ingen migrasjon eller produksjonsdata berøres.

## 10. Verifikasjonsprotokoll

### Lokal/runtime baseline

Kommandoene skal kjøres fra repo-roten. Docker-kjøringen monterer repoet read-only og bruker `/tmp` som arbeidskatalog, slik at testartefakter ikke endrer arbeidskopien.

```powershell
docker run --rm --mount "type=bind,source=C:\APP\VGS_samlet,target=/app,readonly" `
  -e GOOGLE_API_KEY=test-key-not-used -e PYTHONPATH=/app `
  -e PYTHONDONTWRITEBYTECODE=1 -e DISK_CACHE_DIR=/tmp/vgs-cache `
  -w /tmp skoleverksted-forensic:69b00d8-r1 `
  python -m pytest -q -p no:cacheprovider /app
```

Baseline før milepælen: **398 bestått, 2 hoppet over, 47 warnings**. De to tidligere feilene ved read-only repo var testharness-skriving til current working directory; `/tmp` gjør kjøringen reproduserbar uten å skrive i repoet.

Frontend:

```powershell
cd MateMaTeX/frontend
npm test -- --run
npx tsc --noEmit
$env:NEXT_PUBLIC_API_URL='http://localhost:8000'; npm run build
npm run lint
```

Baseline: **13/13 tester**, typekontroll og produksjonsbygg bestod. Lint-gaten er **ikke operativ**: Next åpner en interaktiv førstegangskonfigurasjon fordi ESLint-konfigurasjon mangler. Dette er en eksplisitt release-gjeld, ikke et bestått lintresultat.

### Produksjonssmoke 2026-08-03

- `scripts/production_smoke.py` med ett forsøk og uten generering bestod på forsøk 1.
- Offentlig frontend og sentrale sider svarte.
- Backend readiness svarte 200 og identifiserte fortsatt release `69b00d81e5a7` (`rndr-id=e42efd6a-0b2f-4353`, `Date=2026-08-03 14:53:12 GMT`).
- Matematikk-estimat gjennom beskyttet proxy svarte.

Smoken beviser kobling og grunnleggende tilgjengelighet. Den beviser ikke innholdskvalitet eller en fullført wedge-reise.

### Kandidatkontroll — 2026-08-03 16:54+02

- Kandidat: `ff725bb6997879e74d60d1d539c57e18578f95ad` på `laerebokdesign-hefte`.
- Kandidat-imaget ble bygget fra ren Git-archive-context som `skoleverksted-candidate:ff725bb`; digest er `sha256:d9fb7b5f4b4659aefdc729c34358b4e4d704716197f3ab96d3df7c32707c8792`.
- Docker-suiten bestod med 398 bestått og 2 hoppet over; Dockerfile `--check`, `compileall`, `py_compile`, frontend 13 tester, TypeScript og produksjonsbygg bestod.
- `npm run lint` er `not operational`: Next mangler ESLint-konfigurasjon og åpner interaktiv førstegangskonfigurasjon.
- Kandidaten er ikke pushet til Render-sporet og ingen deploy ble trigget. Render-sporet er `main`; Vercel production-branch er ikke dokumentert i repoet og må bekreftes i Vercel-prosjektet.
- Identisk Historie VG2-scenario ble derfor ikke kjørt på kandidaten. Siste produksjonsevidens er fortsatt 32/44 (73 %), repair 504, retry 409 og compile 409, uten PDF/Word.

## 11. Release- og produksjonsport

Ingen deploy er autorisert i denne leveransen. Kandidaten kan først vurderes når:

1. målrettede tester, full backend-suite, frontendtest, typekontroll og bygg er grønne;
2. diffen bare inneholder avtalte filer, og milepælen har egen commit;
3. auth/tenant-risikoen enten er rettet eller piloten er teknisk isolert til én eksplisitt bruker uten sensitive data;
4. kompendiumjobben har durable status/recovery og én korrelasjons-ID;
5. samme identiske scenario fullfører reparasjon, når gate, kompilerer PDF og DOCX og blir manuelt vurdert;
6. scorecardet har faktiske målinger for lærertid, tapte utkast, jobbsuksess og sluttartefakt;
7. en ansvarlig person gir eksplisitt produksjonsgodkjenning.

Når 1–7 er oppfylt, er den konkrete menneskelige handlingen å merge/pushe den identifiserte kandidaten til Render-sporede `main` etter eksplisitt menneskelig godkjenning. Forventet effekt er ny backend-release med kandidat-SHA i readiness. Risikoen er modell-/runtime-regresjon og datamutering. Rollback er redeploy av `69b00d81e5a7`; ingen force-push eller produksjonsdataendring er tillatt. Verifikasjon er readiness → smoke → identisk scenario → manuell PDF/DOCX-kontroll → oppdatert go/no-go.

## 12. Gjennomføringsrekkefølge

| Milepæl | Produktutfall | Port | Status |
|---|---|---|---|
| M0 Etabler sannhet | Repo, runtime, produksjonsrelease og gate er identifisert | Ingen uklare releasepåstander | Fullført |
| M1 Sikker sannhetsmutasjon | Ingen skjult nabosetningssletting; tvetydighet blir review | Full suite + eksplisitte regresjonstester | **Fullført og produksjonsbevist** 2026-08-07: `removed_claims` 0/0/0 mot baselines 0/5/3 |
| M2 Durable wedge-jobb | Læreren kan refresh/retry uten tvetydig eller duplisert arbeid | Restart-, idempotens-, timeout- og frontend-recoverytest | **Neste P0**; se punkt 15.5 |
| M3 Pilotisolasjon | Bare riktig pilotbruker kan lese/endre/laste ned egne data | Negative auth/IDOR-tester + backup/restore | Ikke startet |
| M4 Vellykket identisk scenario | ≥80 % minimumsport, alle sluttpåstander håndtert, repair fullfører | PDF/DOCX + manuell fag-/språk-/layoutreview | Ikke startet |
| M5 Smal lærerpilor | Wedge reduserer faktisk tid og etterarbeid uten tillitsbrudd | Scorecard med observerte lærerdata og null kritiske hendelser | Ikke startet |

## 13. Milepællogg

### 2026-08-03 — M1

- Etablerte lokal og offentlig releaseidentitet.
- Kjørte reproduksjon og dokumenterte punktumregresjonen.
- Endret sannhetslaget til entydig, fail-closed setningsredigering.
- La til regresjonstester for punktum med/uten, kvalifisering, delvis treff og gjentatte treff.
- Målrettet test: 12 bestått.
- Eksakt kandidat-image: 398 bestått, 2 hoppet over; Dockerfile-check og syntaxkontroll bestått.
- Frontend: 13/13 tester, typekontroll og produksjonsbygg bestått; lint fortsatt ikke konfigurert.
- Kodecommit: `912007b` (`Make truth edits sentence-safe`).
- Produksjon: urørt, fortsatt release `69b00d81e5a7`, dom `REJECTED`.
- Manuell faglig vurdering: `pending teacher review`; ingen lærer har vurdert sluttartefakt.
- Neste høyest prioriterte arbeid: M2, men M3 må fullføres før flerbrukerpilot.

### 2026-08-07 — M1 deployet og verifisert i produksjon

- Pushet kandidaten `ff725bb` til `main` som fast-forward; CI grønn, Render
  deployet, readiness viser `ff725bb69978`.
- Korrigerte testgrunnlaget: baseline 396/2, kandidat 402/2 (ikke 398/2).
- Kjørte identisk scenario: 42/48 = 88 % mot baselines 32/44 = 73 %.
- M1 produksjonsbevist: null automatisk fjernet tekst mot baselines åtte.
- Reparasjon fortsatt ødelagt: 0 av 3 fullførte, og én mislykket reparasjon ble
  rapportert som HTTP 200.
- Ingen PDF, ingen Word, ingen manuell lærervurdering. Dom `REJECTED`.
- Neste P0 valgt etter at produksjonsresultatet forelå: A.

## 14. Beslutningsregel for videre arbeid

Hver ny endring skal knyttes til én observert lærerfriksjon eller én dokumentert risiko, ha eksplisitt akseptanse, test og rollback, og oppdatere denne loggen og scorecardet. Hvis en endring ikke forbedrer tillit, kjerneløp, lærertid, klarhet eller stabilitet for wedgen, skal den normalt ikke bygges nå.

## 15. Kandidatdeploy og isolert produksjonsverifikasjon — 7. august 2026

Kandidaten `ff725bb` er nå deployet og testet isolert mot det identiske
scenarioet. Dette avsnittet er autoritativt og overstyrer punkt 10–11 der de
er i konflikt.

### 15.1 Kontrollert deploy

`git push origin ff725bb…:refs/heads/main` ga fast-forward `69b00d8..ff725bb`.
Ingen force, ingen merge-commit, fire commits tilført. De fire lokale commitene
`266b1d2`, `53fd943`, `3bb1970` og `72e3e3c` — inkludert en reell
MateMaTeX-backendendring — ble holdt utenfor releasen.

CI-run `31104226437` ble grønn på alle fire jobber. Render deployet via
`autoDeployTrigger: checksPass`, og readiness flippet fra `69b00d81e5a7` til
**`ff725bb69978`** 2026-08-06 kl. 13:09:58Z. Config-fingerprint er uendret
`dc08f612a352`, så E2E-en kjørte mot samme prompt- og modellkonfigurasjon som
baseline.

Render-dashboardets deploy-ID og Vercels production-branch er fortsatt
`UKJENT`; miljøet hadde ingen dashboard-tokens.

### 15.2 Korreksjon av testgrunnlaget

Tallet «398 bestått, 2 hoppet over» i punkt 3, 10 og 13 er feil. Målt mot rene
worktrees i de eksakte imagene gir baseline `69b00d8` **396 bestått, 2 hoppet
over** og kandidat `ff725bb` **402 bestått, 2 hoppet over**. Differansen på +6
tilsvarer nøyaktig de seks nye testfunksjonene i `test_truth.py`.

### 15.3 Resultat av identisk scenario

Kompendium `0689cd00b57946779fbdc3e44f2c1cb7`, uendret inputkontrakt, uendret
80 %-terskel.

| Måling | Baseline | Kandidat |
|---|---|---|
| Påstander verifisert | 32/44 = 73 % | **42/48 = 88 %** |
| Laveste kapittel | 56 % | 85 % |
| `removed_claims` | 0 / 5 / 3 | **0 / 0 / 0** |
| Språkfragmenter | 0 | 0 |
| Lærerkilder `teacher`/`provided` | 3/3 | 3/3 |
| Reparasjoner fullført | 0 av 1 | **0 av 3** |
| Compile / PDF / Word | 409 / nei / nei | 409 / 404 / 404 |
| Manuell lærervurdering | umulig | umulig |

**M1 er produksjonsbevist.** Den gamle koden fjernet åtte påstanders tekst
automatisk i produksjon. Kandidaten fjerner ingenting og registrerer i stedet
det uavklarte som begrensning for lærerreview. Det var milepælens hele formål,
og hypotesen om at innstrammingen ville senke dekningen slo ikke til — den
steg med 15 prosentpoeng.

### 15.4 Ny defekt: falsk grønn reparasjonsrespons

Reparasjonen av kapittel 1 svarte HTTP 200 etter 75,94 s, men feilet internt.
Kapittelstatus gikk fra `needs_revision` til `source_grounding_failed`,
`revision_count` forble 0, `revision_summary` forble tom, og noten sier
«Automatisk retting kunne ikke fullføres.» `compendium.py` fanger unntaket,
setter feilstatus og returnerer likevel 200.

Dette er nøyaktig den typen falsk grønn tilstand punkt 5 forbyr. En klient kan
ikke skille en mislykket reparasjon fra en vellykket på HTTP-nivå.

### 15.5 Dom og neste P0

**Dom: `REJECTED`.** Reparasjon, kompilering, PDF, Word og manuell
lærervurdering mangler.

**Neste P0: A — repair execution / durable job architecture.**

Begrunnelsen er at alle gjenstående ikke-beståtte kriterier (C03, C08, C09,
C11, A04, A08, A10) er nedstrøms av at reparasjonen ikke fullfører. Alternativ
B er avkreftet av data: sannhetsdekningen består nå porten. Alternativ C er
reelt, men den observerte observabilitetsfeilen — 200 på en mislykket
reparasjon — er selv et symptom på at reparasjonen ikke har en jobbmodell med
egen terminalstatus. C løses derfor riktigst som en del av A, ikke før den.

Konkret akseptanse for A:

1. Reparasjon opprettes som en durable jobb med egen ID, status og eier, skilt
   fra HTTP-forespørselens levetid.
2. En mislykket reparasjon returnerer aldri en suksessstatus; jobben får
   terminalstatus `failed` med årsak.
3. Læreren kan refreshe eller miste nettforbindelsen og finne igjen jobben.
4. Idempotensnøkkel fra UI hindrer dobbeltarbeid; 409 beholdes for aktiv jobb.
5. Reparasjon som overskrider tidsgrensen kanselleres i stedet for å fortsette
   i en daemontråd.
6. `revision_summary` fylles ved fullført reparasjon slik at læreren ser hva
   som ble endret.
7. Samme identiske scenario kjøres på nytt og skal fullføre minst én
   reparasjon, nå compile, produsere PDF og Word og bli manuelt vurdert.

## 16. Durable repair execution — 8. august 2026

Dette avsnittet lukker P0 A på kodenivå. Det overstyrer punkt 15 der de er i
konflikt om *hvorfor* reparasjon feilet, men ikke om produksjonsstatus:
produksjonen er urørt og dommen er fortsatt `REJECTED`.

### 16.1 Rotårsak, presist

Reparasjonen feilet ikke fordi den manglet en tidsgrense. Den feilet fordi
**HTTP-requesten eide modellarbeidet**. Request-tråden blokkerte på
`done.wait(120)` i `router.py`, låsen lå i en `dict` i prosessminne, og verken
jobb-ID, status eller evidens ble lagret noe sted. Alle tre observerte
produksjonssymptomene — 504, 409 uten eier, og HTTP 200 med intern feil — følger
av dette ene designvalget.

### 16.2 Ny livssyklus

Egne jobbstatuser, adskilt fra kapittelstatus:
`queued → running → succeeded | failed_retryable | failed_terminal | cancelled | superseded`.

`succeeded` krever modellrespons, vellykket parsing, gjennomført kilde-/
sannhetskontroll, gyldig CAS-token, fullført write-back og konsistent ledger.
Kapittelstatus (`generated`, `source_grounding_failed`, …) er et innholdsresultat
og kan ikke gjøre en jobb grønn eller rød alene.

Full tilstandsmaskin, restart-tabell og lås-livssyklus:
`research/REPAIR_DURABILITY_EXECPLAN.md`.

### 16.3 Kontrakt

`POST …/repair` returnerer **202** med `job_id`, `operation_id` og `status_url`
før noe modellkall skjer. Status leses via `GET /repair-jobs/{id}`, evidens via
`GET /repair-jobs/{id}/events`, gjenfinning etter reload via
`GET …/chapters/{id}/repair`. `GET /jobs/{id}`, `GET /queue` og
`POST /jobs/{id}/cancel` er gjenbrukt; hver repair speiles i den eksisterende
jobbledgeren.

### 16.4 Vern mot de tre farlige utfallene

| Fare | Vern |
|---|---|
| Falsk suksess | terminal status settes først etter fullført write-back |
| Overskrevet lærerarbeid | CAS på innholds-hash + `revision_count` → `superseded` |
| Permanent låst kapittel | lease + `recover_incomplete_repair_jobs()` + `expire_stale_repair_leases()` |

### 16.5 Evidens

Backend 120 bestått, ny durability-suite 27 bestått, frontend 24 bestått,
typecheck og produksjonsbygg bestått. En ASGI-test mot den reelle ruteren viser
202 på under ett sekund mens modellkallet fortsatt er blokkert.

Alle modellkall i testene er stubbet. Ingenting av dette er kjørt mot ekte
Gemini eller i produksjon.

### 16.6 Neste P0

Deploy durable-repair-kandidaten etter eksplisitt godkjenning, og kjør det
identiske Historie VG2-scenarioet på nytt. PASS krever at repair execution er
varig, observerbar, gjenopprettbar, ikke-destruktiv og korrekt representert i
UI/API — ikke at modellen alltid løfter kapitlet over kvalitetsporten. Et
faglig for svakt kapittel skal rapporteres som truth-resultat, ikke som
infrastrukturfeil.
