# Skoleverksted product excellence exec-plan

**Status:** levende gjennomføringsplan

**Oppdatert:** 2026-08-03

**Produksjonsdom:** `REJECTED`

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
| Lokal HEAD før denne milepælen | `22b80d913bdd9f54ba8dc08025bba7814354f5d1` | lokal Git |
| M1 kodecommit | `912007b` (`Make truth edits sentence-safe`) | lokal Git; ikke deployet |
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
- Kandidatruntime før denne milepælen bestod 398 tester, med 2 hoppet over. Frontend bestod 13 tester, typekontroll og produksjonsbygg.

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

Målrettet resultat: **12 tester bestått**. Full runtime-regresjon etter endringen: **403 bestått, 2 hoppet over, 47 warnings**. De to endrede Python-filene bestod separat `py_compile`.

### Hvorfor denne milepælen går foran auth, jobbarkitektur og UX

Alle tre er større pilotblokkere, men denne feilen var konkret reproduserbar i deploykandidaten, kunne endre lærerens tekst stille og hadde en liten reverserbar retting. Den måtte fjernes før kandidaten i det hele tatt kunne vurderes for ny produksjonskjøring.

### Gjenværende risiko og rollback

Rettelsen gjør ingen semantisk vurdering av om erstatningsteksten er korrekt. Den garanterer bare at automatisk mutasjon har en entydig avgrensning. Den er ikke produksjonsverifisert. Rollback er å reversere milepælcommit-en; ingen migrasjon eller produksjonsdata berøres.

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
- Backend readiness svarte 200 og identifiserte release `69b00d81e5a7`.
- Matematikk-estimat gjennom beskyttet proxy svarte.

Smoken beviser kobling og grunnleggende tilgjengelighet. Den beviser ikke innholdskvalitet eller en fullført wedge-reise.

## 11. Release- og produksjonsport

Ingen deploy er autorisert i denne leveransen. Kandidaten kan først vurderes når:

1. målrettede tester, full backend-suite, frontendtest, typekontroll og bygg er grønne;
2. diffen bare inneholder avtalte filer, og milepælen har egen commit;
3. auth/tenant-risikoen enten er rettet eller piloten er teknisk isolert til én eksplisitt bruker uten sensitive data;
4. kompendiumjobben har durable status/recovery og én korrelasjons-ID;
5. samme identiske scenario fullfører reparasjon, når gate, kompilerer PDF og DOCX og blir manuelt vurdert;
6. scorecardet har faktiske målinger for lærertid, tapte utkast, jobbsuksess og sluttartefakt;
7. en ansvarlig person gir eksplisitt produksjonsgodkjenning.

Når 1–7 er oppfylt, er den konkrete menneskelige handlingen å slå sammen den identifiserte, testede commit-en til den Render-sporede branchen og trigge én kontrollert deploy. Forventet effekt er ny backend-release med den eksakte commit-SHA-en i readiness. Risikoen er modell-/runtime-regresjon og datamutering. Rollback er redeploy av `69b00d81e5a7`. Verifikasjon er readiness → smoke → identisk scenario → manuell PDF/DOCX-kontroll → oppdatert go/no-go. Eksakte deploykommandoer skal hentes fra den faktiske Render-konfigurasjonen når godkjenningen gis; de skal ikke gjettes nå.

## 12. Gjennomføringsrekkefølge

| Milepæl | Produktutfall | Port | Status |
|---|---|---|---|
| M0 Etabler sannhet | Repo, runtime, produksjonsrelease og gate er identifisert | Ingen uklare releasepåstander | Fullført |
| M1 Sikker sannhetsmutasjon | Ingen skjult nabosetningssletting; tvetydighet blir review | Full suite + eksplisitte regresjonstester | Implementert lokalt; produksjon ikke berørt |
| M2 Durable wedge-jobb | Læreren kan refresh/retry uten tvetydig eller duplisert arbeid | Restart-, idempotens-, timeout- og frontend-recoverytest | Ikke startet |
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
- Full monorepo-regresjon: 403 bestått, 2 hoppet over, 47 warnings.
- Frontend: 13/13 tester, typekontroll og produksjonsbygg bestått; lint fortsatt ikke konfigurert.
- Kodecommit: `912007b` (`Make truth edits sentence-safe`).
- Produksjon: urørt, fortsatt release `69b00d81e5a7`, dom `REJECTED`.
- Neste høyest prioriterte arbeid: M2, men M3 må fullføres før flerbrukerpilot.

## 14. Beslutningsregel for videre arbeid

Hver ny endring skal knyttes til én observert lærerfriksjon eller én dokumentert risiko, ha eksplisitt akseptanse, test og rollback, og oppdatere denne loggen og scorecardet. Hvis en endring ikke forbedrer tillit, kjerneløp, lærertid, klarhet eller stabilitet for wedgen, skal den normalt ikke bygges nå.
