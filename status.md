# Skoleverksted – prosjektstatus

> Sist oppdatert: 7. august 2026
> Deployet produksjonsrelease: `ff725bb69978` — se siste seksjon i dokumentet
> Status: aktiv utvikling og pilot-/testfase
> Repository: [marlervius/skoleverksted](https://github.com/marlervius/skoleverksted)
> Aktiv arbeidsgren ved siste publisering: laerebokdesign-hefte
> Siste publiserte commit: 1c36544 – «Close compendium forensic incident and harden verification»

Dette dokumentet beskriver hva Skoleverksted er, hva som er implementert, hvordan løsningene henger sammen, hva som er testet, og hva som bør gjøres før produktet kan brukes bredt i skolen.

## 1. Produktet kort fortalt

Skoleverksted er en samlet lærerplattform som erstatter tre separate arbeidsflyter med én felles app. Læreren velger arbeidsflate øverst i grensesnittet og kan lage, kvalitetssikre, lagre og gjenbruke undervisningsmateriell.

Produktløftet er:

- Læreren skal få et godt førsteutkast raskt.
- Fakta, kilder, kompetansemål, matematikk og kompilering skal kontrolleres maskinelt.
- Usikkerhet skal vises tydelig; innhold skal ikke presenteres som sikkert når det ikke er dokumentert.
- Læreren skal godkjenne materialet før det blir et ferdig elevprodukt.
- Alt som er godkjent, skal kunne lagres, versjoneres og knyttes til en årsplan.

Skolepålogging og organisasjonstilknytning er med vilje utsatt til produktet er validert i pilot. I testfasen brukes modulspesifikk sikkerhet og eventuelt en delt applikasjonspassordløsning.

## 2. De tre fagmodulene

| Arbeidsflate | Målgruppe | Hovedfunksjoner |
|---|---|---|
| **Fag & læring** | Lærere i videregående skole | Læringsark, fagtekster, differensiering, prøver, sekvensplaner, kilder, LK20-mål, bilder, PDF og Word |
| **Norsklæring** | Voksne og minoritetsspråklige som lærer norsk | CEFR-tilpassede læringsark fra A1 til B2, enkelt-/dobbelt-/flernivå, språkstøtte, bilder, PDF og ZIP |
| **Matematikk** | Norske VGS-lærere | LK20-oppgaver og prøver, LaTeX/PDF, maskinelt verifisert fasit, oppgavebank, differensiering og eksport |

### Fag & læring

Den eksisterende VGS-modulen lager utskriftsklare læringsressurser med:

- fagtekst, arbeidsark og valgfri fasit
- differensierte nivåer: støtte, standard og fordypning
- prøve med flervalg, kortsvar, langsvar, fasit og vurderingskriterier
- sekvens-/ukeplan med progresjon og vurderingsopplegg
- kildeforankring mot oppgitt kildetekst eller åpne NDLA-ressurser
- LK20-kobling via Udirs Grep-API
- faktarapport og redaktør-/kvalitetskontroll
- lærerstyrt forhåndsvisning og redigering før PDF bygges
- PDF- og Word-eksport

### Norsklæring

Norskmodulen støtter:

- nivåene A1, A2, B1 og B2, inkludert undernivå
- enkeltark, parallelle nivåer og flernivå-ZIP
- språktilpasning uten at faginnholdet skal forsvinne
- begrepsstøtte, skriverammer og ekstra språkaktiviteter
- forhåndsvisning som JSON før PDF-generering
- opplasting av eget bilde og kontrollert bildebruk
- lokal historikk og polling/SSE for lange jobber

### Matematikk

Matematikkmodulen er bygget rundt et strengere verifikasjonskrav:

- oppgaver og prøver for relevante VGS-nivåer
- SymPy-basert kontroll av numerisk og symbolsk fasit
- LaTeX-kompilering til PDF
- oppgavebank med søk, filtrering og bygging av prøve
- redigering, differensiering og flere eksportformater
- Word-, PowerPoint- og QR-eksport der arbeidsflyten støtter det
- deling og samarbeidsfunksjoner i backend
- levering skal blokkeres når fasiten er dokumentert feil; uparserbare uttrykk merkes for manuell kontroll

## 3. Den felles lærerflyten

### Kompendier, appendiks og fordypningshefter

Kompendiumfunksjonen er laget for materialer som er større og mer sammenhengende enn et vanlig læringsark, for eksempel:

- politiske ideologier på 1900-tallet
- Europas kongedømmer på 1400-tallet
- kriger i en historisk periode
- økonomi i middelalderen
- kildesamlinger, sammenligninger og tematiske appendiks

Flyten er:

1. Læreren beskriver tema, målgruppe, fag, nivå, omfang og ønsket dokumenttype.
2. Appen lager en avgrensningskontrakt og et redigerbart kapittelutkast.
3. Læreren godkjenner disposisjonen.
4. Kapitlene produseres ett og ett.
5. Hvert kapittel får kilde- og faktakontroll.
6. Kapitler med merknader kan revideres automatisk; læreren kan se hva som ble endret.
7. Læreren kan redigere, godkjenne eller sende kapitlet til ny revisjon.
8. Før kompilering kontrolleres at nødvendige kildekrav er oppfylt.
9. Appen bygger en versjonert PDF og Word-fil.
10. Ferdig materiale kan knyttes til perioder i en årsplan.

Kompendier støtter tematisk, kronologisk, referansebasert, sammenlignende, kildebasert og appendiks-lignende format. Dokumentet inneholder blant annet ramme for avgrensning, læringsmål, arbeidsmåte, kapittelspørsmål, kort oppsummert, begreper, videre arbeid, kildeliste og en beskrivelse av faktagrunnlaget.

### Årsplaner

Årsplanfunksjonen skal gi læreren en oversikt over hele skoleåret:

- fag, nivå, skoleår, timetall per uke og minutter per time
- antall undervisningsuker og perioder
- kompetansemål som læreren limer inn eller velger
- redigerbart tema, oversikt, læringsmål, begreper, aktiviteter og vurdering per periode
- realistisk fordeling av uker og timer
- AI-forslag med deterministisk reserveplan dersom AI-kallet feiler
- periodestatus: ikke startet, pågår, klar, ferdig eller må revideres
- lagring av godkjente læremidler på riktig periode
- versjon og status for hvert læremiddel

Årsplanen er et forslag, ikke en offisiell læreplantolkning. Den skal alltid kontrolleres mot lokale skoledager, ferier, eksamen og faktisk læreplandekning.

### Temapakker

En temapakke oppretter ett prosjekt med koordinerte arbeidsflater for:

- fagtekst og undervisningsforløp
- språktilpasset norskversjon
- matematikk/dataoppgaver
- valgfri vurdering og lærerveiledning

Temapakken lager en felles kvalitetspassport og lenker til de tre fagmodulene. Kilden læreren oppgir, følger prosjektet som felles kontekst.

### Prosjekter, historikk og jobber

Felles plattformfunksjoner gjør det mulig å:

- lagre prosjekter med tema, fag, nivå og kompetansemål
- hente frem tidligere produksjoner
- se jobber fra Fag, Norsk, Matematikk og plattformen i én historikk
- følge kø, fremdrift, resultat, begrensninger og eventuelle feil
- avbryte jobber
- gi enkel positiv/negativ tilbakemelding på et resultat
- beholde utkast lokalt i frontend ved bytte av arbeidsflate

## 4. Faktasikkerhet og kildepolicy

Dette er den viktigste delen av produktet. Skoleverksted forsøker å gjøre AI-generert undervisningsmateriale etterprøvbart, ikke bare velskrevet.

### Felles sannhetslag

Plattformen har et felles truth-/kildelag som registrerer:

- konkrete faktapåstander
- status: verifisert, tolkning, omstridt, tidssensitiv eller udokumentert
- foreslått handling: behold, kvalifiser eller fjern
- erstatningstekst når en formulering må nyanseres
- kildelenker og evidens
- konfidensnivå
- tidspunkt for når kilden ble hentet

Et grønt faktapass krever i praksis:

- en konkret kilde, ikke bare en generell hjemmeside
- dokumentasjon/evidens for påstanden
- tilstrekkelig konfidens
- ingen uavklarte endringer som må gjøres

Generiske hjemmesider og svake kildepekere skal ikke alene gjøre en påstand grønn. Kilde-URL-er normaliseres, sporing fjernes, og midlertidige søke-redirecter filtreres.

### Arbeidsdeling mellom AI og lærer

AI-crewet kan:

- identifisere påstander
- foreslå kilder og motargumenter
- oppdage manglende eller for brede kildehenvisninger
- foreslå presiseringer eller fjerne udokumenterte påstander
- vise før-/etter-tekst og et revisjonssammendrag

Læreren er fortsatt siste godkjenner. Et grønt pass er en dokumentasjonsstatus, ikke en absolutt garanti mot feil. PDF-en sier derfor eksplisitt at etterprøvbarhet ikke betyr at enhver formulering er uangripelig.

### Blokkering før ferdig dokument

Kompileringsendepunktet stopper kompendier når et kapittel har uløste kildeproblemer. Brukeren får en konkret melding om hva som må korrigeres. Dette hindrer at et dokument som appen selv har merket som uforsvarlig, blir presentert som ferdig.

## 5. Bilder

Bilder er et eksplisitt lærervalg, ikke en skjult AI-beslutning.

| Modus | Oppførsel |
|---|---|
| **Ingen bilder** | Dokumentet produseres uten bilde |
| **Frie bilder** | Bildecrew søker Wikimedia Commons, filtrerer lisens og henter metadata/kreditering |
| **Lag AI-bilde** | Google-bildegenerator lager normalt maksimalt én pedagogisk illustrasjon per PDF, og bildet merkes som KI-generert |

Bildecrewet lager en plan for hva bildet må vise, vurderer kandidater og forsøker å avvise misvisende, uklare eller pedagogisk svake bilder. Samtidig vises Commons-kandidater slik at læreren kan velge selv når den automatiske anbefalingen ikke er god nok.

Hvis Wikimedia Commons ikke gir et trygt treff, eller et bilde feiler nedlasting/visuell kontroll, skal dokumentet kunne fortsette uten bilde. Dette er bedre enn å sette inn et tilfeldig bilde. Kjente driftsproblemer er ratebegrensning (HTTP 429) hos Commons og at enkelte fagtemaer har få gode illustrasjoner.

## 6. Teknisk arkitektur

~~~text
MateMaTeX/frontend             Felles Next.js 14-app
  ├─ fag                        VGS-fagmodul
  ├─ norsk                      CEFR-/norskmodul
  ├─ matematikk                 LK20-matematikk
  ├─ compendia                  kompendier og appendiks
  ├─ year-plans                 årsplaner
  ├─ theme-pack                 temapakker
  ├─ projects                   felles prosjektoversikt
  └─ history                    felles jobbhistorikk

Skoleverksted/backend/main.py   Felles FastAPI-inngang
  ├─ /api/platform              prosjekter, årsplaner, kompendier, kvalitet
  ├─ /api/fag                   VGS-domenet (VGS_KI)
  ├─ /api/norsk                 Norsk-domenet (ScriptoriumFOV)
  └─ /api/matematikk            Matematikk-domenet (MateMaTeX/backend)

Skoleverksted/backend/platform  Felles plattformlag
  ├─ models.py                  Pydantic-kontrakter
  ├─ store.py                   SQLite/PostgreSQL-lager og filmetadata
  ├─ queue.py                   varig jobbledger og lokal/Redis-kapasitet
  ├─ repair.py                  varig kapittelreparasjon med lås, CAS og ledger
  ├─ truth.py                   kilde- og faktapass
  ├─ compendium.py              disposisjon, kapittelproduksjon og revisjon
  ├─ compendium_renderer.py     Typst/PDF og Word-kompilering
  ├─ images.py                  Commons- og Google-bildecrew
  ├─ year_planner.py            AI-/reserveplan for årsplaner
  └─ readiness.py               produksjonshelse og avhengighetsrapport
~~~

### Teknologistack

- Python 3.12
- FastAPI og Uvicorn
- Next.js 14 App Router, React 18 og TypeScript
- Tailwind CSS, Zustand, Lucide og Framer Motion
- Google Gemini via google-genai/CrewAI/LangChain der domenet krever det
- Typst for Fag/Norsk og kompendier
- TeX Live/pdfLaTeX og SymPy for Matematikk
- SQLite som standard plattformlager
- PostgreSQL som valgfritt delt produksjonslager
- Redis som valgfri distribuert jobblås
- Docker for backend og Vercel for frontend

## 7. Backend og lagring

### Plattformlager

SQLite er standard og ligger i produksjon på Render-disken under /var/data. Lageret inneholder blant annet prosjekter, kompendier, årsplaner, jobber, kvalitetspass, tilbakemeldinger og metadata om genererte filer.

DATABASE_URL kan brukes for PostgreSQL. Skjemaet opprettes automatisk, men genererte filer ligger fortsatt i OUTPUT_DIR inntil objektlagring er innført.

### Jobbkø

Jobber registreres varig før de starter. Ved omstart gjenopprettes uferdige jobber. Lokal kapasitet begrenses av MAX_CONCURRENT_JOBS og kompilering av MAX_CONCURRENT_COMPILES.

Når REDIS_URL er satt, brukes en distribuert Redis-lås i tillegg til den lokale begrensningen. SQLite-ledgeren er fortsatt autoritativ for jobbstatus. Dette er et mellomsteg før en eventuell separat worker-/køarkitektur.

### Feilhåndtering

- Backend legger request-id på svar og logg.
- Uventede feil returnerer strukturert JSON med kode, melding, request-id og om feilen kan forsøkes på nytt.
- Frontend mapper vanlige HTTP-, nettverks- og genereringsfeil til lærerrettede meldinger.
- Lange jobber bruker polling eller SSE avhengig av modul.
- Hvis AI eller bildecrew feiler, brukes deterministisk reserve der det er forsvarlig.

## 8. Frontend-ruter

Viktige sider i den aktive frontend-appen:

- / – forside og modulvelger
- /fag – Fag & læring
- /norsk – Norsklæring
- /matematikk – Matematikk
- /compendia, /compendia/new, /compendia/[id] – kompendier
- /year-plans, /year-plans/new, /year-plans/[id] – årsplaner
- /theme-pack – temapakker
- /projects, /projects/[id] – prosjektoversikt
- /history – lokal og felles jobbhistorikk
- /exercises – matematikkoppgavebank
- /templates – maler
- /settings – innstillinger
- /shared, /shared/[token] – deling
- /school – forberedt plass for skole-/organisasjonsflyt
- /personvern – personverninformasjon

Frontend har en sikker Markdown-forhåndsvisning som støtter overskrifter, avsnitt, lister, tabeller, sitater, kode og sikre HTTPS-lenker uten å gjengi rå HTML.

## 9. API-oversikt

Felles plattform-API ligger under /api/platform og har blant annet:

- GET/POST /compendia og POST /compendia/outline
- GET/PATCH /compendia/{id}
- kapitteloperasjoner: oppdater og produser
- POST /compendia/{id}/chapters/{chapter_id}/repair – starter varig jobb, svarer 202
- GET /compendia/{id}/chapters/{chapter_id}/repair – siste reparasjon for kapitlet
- GET /repair-jobs/{job_id} og /repair-jobs/{job_id}/events
- POST /compendia/{id}/compile og /approve
- GET /compendia/{id}/download/pdf|docx
- GET/POST /year-plans
- POST /year-plans/generate
- oppdatering av årsplan, perioder og lagrede læremidler
- GET/POST/PATCH /projects
- GET /jobs, GET /jobs/{id}, GET /queue
- POST /jobs/{id}/cancel
- POST /quality-passports
- POST /theme-packs
- GET /theme-packs/{project_id}/teacher-guide
- POST /feedback

Domene-API-ene beholder egne dokumentasjoner:

- /api/fag/docs
- /api/norsk/docs
- /api/matematikk/docs

## 10. Drift og deploy

### Render-backend

Root render.yaml beskriver en Docker-basert web service:

- service: skoleverksted-api
- Frankfurt-region
- Starter-plan
- 1 GB persistent disk på /var/data
- health check på /health/ready
- én jobb og én kompilering om gangen i pilotoppsettet
- deploy trigger etter at GitHub-kontroller passerer

Render trenger minst GOOGLE_API_KEY, APP_PASSWORD, MATE_API_KEY, FRONTEND_URL og ALLOWED_ORIGINS. GOOGLE_IMAGE_MODEL kan overstyre bilde-modellen. PostgreSQL og Redis er valgfrie senere steg.

### Vercel-frontend

Frontend deployes fra MateMaTeX/frontend som en vanlig Next.js-app, ikke som static export. Vercel Hobby passer til testfasen.

Viktige variabler:

~~~text
NEXT_PUBLIC_API_URL=https://<render-host>
BACKEND_INTERNAL_URL=https://<render-host>
MATE_API_KEY=<samme server-side nøkkel som Render>
~~~

MATE_API_KEY skal ikke prefikses med NEXT_PUBLIC_. Render må samtidig få den eksakte Vercel-produksjonsadressen i CORS-innstillingene.

### Helseendepunkter

- /health – liveness og grunnleggende lagerstatus
- /health/ready – Google-nøkkel, matematikk-/norsktilgang, lagring, Typst og pdfLaTeX
- /docs – felles OpenAPI

/health/ready viser ikke hemmeligheter. Den rapporterer status, manglende avhengigheter, lagringstype, Redis-status, runtime, modellnavn, promptversjon og et konfigurasjonsfingeravtrykk.

## 11. Miljøvariabler

| Variabel | Bruk |
|---|---|
| GOOGLE_API_KEY | Gemini for tekst og normalt bilder |
| GOOGLE_IMAGE_API_KEY | Valgfri separat nøkkel for bilder |
| GOOGLE_MODEL / PRIMARY_MODEL | Tekstmodell |
| GOOGLE_IMAGE_MODEL | Bildemodell, normalt gemini-3.1-flash-image |
| AI_TEMPERATURE | Kreativitetsnivå, normalt lavt (0.35) |
| PROMPT_VERSION | Sporbar versjon av prompt-/kvalitetsregler |
| MATE_API_KEY | Server-side beskyttelse av matematikk-API og Vercel-proxy |
| APP_PASSWORD | Midlertidig passord for Norsk-modulen |
| FRONTEND_URL / ALLOWED_ORIGINS | CORS og offentlig frontend |
| NEXT_PUBLIC_API_URL | Frontendens backendadresse |
| BACKEND_INTERNAL_URL | Server-til-server-adresse fra Vercel |
| SKOLEVERKSTED_DB_PATH | SQLite-fil |
| OUTPUT_DIR | PDF-er, Word-filer og jobbresultater |
| DATABASE_URL | Valgfri PostgreSQL |
| REDIS_URL | Valgfri distribuert jobblås |
| MAX_CONCURRENT_JOBS | Maks samtidige genereringsjobber |
| COMPENDIUM_REPAIR_LEASE_SECONDS | Hvor lenge en reparasjon kan reservere et kapittel, normalt 900 |
| MAX_CONCURRENT_COMPILES | Maks samtidige kompileringer |
| TYPST_PATH / PDFLATEX_PATH | Kompileringsverktøy |

## 12. Test- og verifikasjonsstatus

Ved siste komplette verifisering før denne statusfilen ble skrevet:

- Frontend npm test: **13 tester bestått**.
- Frontend npx tsc --noEmit: **bestått**.
- Frontend npm run build: **bestått** med Next.js 14.2.35.
- Plattform/backend: **73 tester bestått** med trygge lokale testvariabler.
- Utvalgte plattformtester: **24 tester bestått**.
- FastAPI-import og helse-smoketest: **bestått**, med HTTP 200 fra readiness i testoppsett.
- git diff --check: bestått for endringene som ble publisert.

En lokal Docker-ombygging feilet ved Docker-daemonens snapshot-eksport. Dette var en lokal daemon-/cachefeil, ikke en dokumentert applikasjonsfeil; kildekodebaserte tester og frontendbygg var fortsatt bestått.

Det bør fortsatt gjennomføres en ekte produksjonssmoke etter hver deploy: bytt mellom alle tre moduler, lag én liten jobb i hver, opprett en temapakke, opprett en årsplan, produser ett kompendium og kontroller PDF-/Word-nedlasting.

## 13. Kjente begrensninger og risikoer

### Høy prioritet

1. **Skolepålogging mangler.** APP_PASSWORD er bare en midlertidig pilotløsning. Før skolebruk må innlogging, roller, skole-/organisasjonstilhørighet og tilgang til egne data bygges ferdig.
2. **Fakta kan fortsatt feile.** Kvalitetspasset reduserer risiko, men erstatter ikke lærerens faglige kontroll eller en fullstendig kildekritisk vurdering.
3. **AI- og bildekvoter.** Google 429/quota, modellendringer og uventede leverandørfeil kan gjøre jobber langsomme eller mislykkes.
4. **Render med persistent disk er ett-instans-oppsett.** SQLite og lokal fil lagrer gjør horisontal skalering uegnet før PostgreSQL, Redis og objektlagring er tatt i bruk.

### Middels prioritet

5. **Wikimedia Commons er eksternt og ratebegrenset.** Kandidater kan mangle, være for komplekse eller bli avvist av bildekontrollen.
6. **Genererte filer ligger lokalt.** Ved større trafikk bør PDF-er, Word-filer og bilder flyttes til S3-kompatibel objektlagring.
7. **Domene-backendene er fortsatt delvis separate.** Plattformen har felles kontrakter, historikk og drift, men de gamle agent- og jobbmotorene er ikke fullstendig refaktorert til én intern pipeline.
8. **Forhåndsvisning er en sikker delmengde av Markdown.** Avansert Markdown/HTML/LaTeX som ikke støttes, må fortsatt kontrolleres i den endelige PDF-en.
9. **Lokale arbeidskopier kan inneholde urelaterte endringer.** Ved siste push stod disse to filene med lokale endringer og ble med vilje ikke tatt med:
   - MateMaTeX/backend/app/latex/preamble.py
   - MateMaTeX/backend/tests/test_hefte_design.py

## 14. Prioritert videre plan

### Før pilot med noen få lærere

- verifiser Render- og Vercel-miljøvariabler mot produksjonsadressene
- kjør end-to-end-smoketest i alle tre moduler
- test årsplan → periode → materiale → historikk
- test kompendium med både godt kildedekket og dårlig kildedekket innhold
- test Commons-kandidater, lærerens valg og reserve uten bilde
- dokumenter hva læreren alltid skal kontrollere før utdeling
- avklar de gamle urelaterte lokale endringene før neste samlede release

### Før bred skolebruk

- implementer skolepålogging og organisasjons-/rollemodell
- legg til prosjekt- og materialtilgang per lærer/skole
- innfør revisjonslogg som ikke kan overskrives
- vurder moderering, backup, sletting og personvernprosedyrer
- flytt filer til objektlagring og lager til PostgreSQL
- kjør Redis/worker-arkitektur for mer enn én backend-instans
- legg til overvåking, alarmer og kostnadsgrenser for AI-kall
- bygg systematiske evalueringssett per fag og nivå

### Produktforbedringer etter pilot

- lærerbibliotek med gjenbrukbare maler og faglige standarder
- bedre samarbeidsflyt og kommentarer mellom lærere
- eksport til LMS der det er ønskelig
- tydeligere visning av kildenes kvalitet og dato i elevproduktet
- støtte for flere åpne bildearkiv og lokal opplasting
- batch-produksjon fra flere årsplanperioder med eksplisitt godkjenning

## 15. Lokal oppstart

Fra repoets rot:

~~~powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
pip install -r .\\Skoleverksted\\backend\\requirements.txt
Copy-Item .\\Skoleverksted\\backend\\.env.example .\\.env
# Fyll inn GOOGLE_API_KEY og eventuelle lokale nøkler
uvicorn Skoleverksted.backend.main:app --reload --port 8000
~~~

I en ny terminal:

~~~powershell
Set-Location .\\MateMaTeX\\frontend
Copy-Item ..\\..\\Skoleverksted\\frontend\\.env.example .\\.env.local
npm install
npm run dev
~~~

Frontend åpnes på http://localhost:3000, backend på http://localhost:8000. Typst må finnes i PATH, og pdfLaTeX må være tilgjengelig for matematikkflyten.

## 16. Git-status

Den forrige samlede forbedringscommitten er publisert på:

~~~text
origin/laerebokdesign-hefte
cb486fc Forbedre kildekontroll og jobbstabilitet
~~~

Forensic-releasen er kommittert og publisert på aktiv branch og Render-tracked
`main`:

~~~text
1c36544 Close compendium forensic incident and harden verification
9d9ce24 Record forensic release evidence and deployment gate
5b72a05 Fix nested heading quality gate
~~~

Urelaterte lokale endringer i `MateMaTeX/backend/app/latex/preamble.py` og
`MateMaTeX/backend/tests/test_hefte_design.py`, samt fire urelaterte untracked
research-filer, er bevisst ikke inkludert.

## 17. Kort konklusjon

Skoleverksted har nå en fungerende felles produktkjerne for tre lærerrettede AI-apper, årsplaner, kompendier, temapakker, kvalitetspass og dokumenteksport. Den viktigste forskjellen fra en vanlig AI-tekstgenerator er at systemet prøver å gjøre kilder, usikkerhet, matematikkverifikasjon og lærerens godkjenning synlig i selve arbeidsflyten.

Produktet har et teknisk grunnlag for videre kontrollert utvikling, men er ikke
klart for lærerpilot. Produksjonsgaten er avvist, og autentisering,
datatilgang, durable jobber, backup, overvåking og faglig sluttkontroll må være
bevist før en pilot kan godkjennes.

## 19. Production verification gate – 3. august 2026

Production-verification-gaten er gjennomført som en releasebeslutning. Dommen er
fortsatt **REJECTED**, men av en annen og nå bevist grunn: release `5b72a05` er
deployet og readiness viser `5b72a0541a20`, men identisk produksjonskjøring
`084614b8247d413b8d1ba38cb6166fce` endte med 32/44 verifiserte påstander (73 %),
to kapitler i `needs_revision` og reparasjonstimeout.

I ferskt produksjonsimage bestod full monorepo-suiten **397 tester** med
**2 eksplisitte skips og 47 warnings** på 45,51 sekunder. Frontend bestod 13
Vitest-tester og Next-produksjonsbuild. De to tidligere VGS_KI-
pakkeimportfeilene er rettet uten å deaktivere tester. Produksjonssmoke bestod
også på forsøk 1, og Vercel-/Render-koblingen svarte 200.

Det som fortsatt mangler før en ekstern lærerpilot er Render-dashboardets
deploy-ID, rå/lagret/revidert response-ledger, en vellykket produksjons-
reparasjon, grønn identisk E2E-kjøring, ferdig PDF/Word og manuell faglig
vurdering. Se `research/PRODUCTION_VERIFICATION_REPORT.md`,
`research/ACCEPTANCE_MATRIX.md`, `research/PRODUCTION_INCIDENT_CLOSURE.md` og
`research/PILOT_GO_NO_GO.md` for den fullstendige gaten.

## 18. Forensic audit – mislykket kompendiumkjøring (2. august 2026)

Den siste identifiserbare produksjonskjøringen er kompendium
`838938c88e994320a64281aafc871ec8` (Historie VG2, fransk revolusjon,
tre kapitler). Lokal arbeidsflate inneholder ikke Render-database, rå
modellrespons, request-/jobb-ID-er eller serverlogger, så den deployede
kjøringen kan ikke rekonstrueres fullstendig uten ekstern loggtilgang.

Dokumenterte kodeårsaker var at lærerens kilde-URL-er ikke ble sendt videre som
`provided_sources` til sannhetslaget, at `str.replace()` kunne lage
setningsfragmenter når en påstand ble fjernet, og at reparasjon manglet timeout,
kapittellås, operation-ID og synlig feilstatus. Dette er rettet lokalt og
beskrevet i:

* `research/FAILED_COMPENDIUM_FORENSIC_AUDIT.md`
* `research/ROOT_CAUSE_LEDGER.md`
* `research/TRUTH_PIPELINE_AUDIT.md`
* `research/REPAIR_JOB_INCIDENT.md`
* `research/COMPENDIUM_ACCEPTANCE_CRITERIA.md`

Nye statuser skiller `verification_failed`, `source_unavailable`,
`not_evaluated`, `language_quality_failed`, `source_grounding_failed`,
`parse_failure` og `generation_incomplete` fra ordinær `needs_revision`.
Deterministisk tekstkontroll, kildeproveniens, 80 %-krav for grønt faktapass,
timeout/lås og frontend-feilmelding er implementert.

Frontendens 13 Vitest-tester og Next-produksjonsbuild består, og backendens
moduler består `compileall`. Fresh-image-suiten samler 397 bestått og 2 skips.
Den identiske produksjonskjøringen beviste lærer-kildepropagasjon
(`origin=teacher`, `fetch_status=provided`), ingen språkfragmenter og korrekt
compile-blokkering. Den beviste også at faktapasset bare nådde 73 %, og at
reparasjon fikk HTTP 504 etter 120 sekunder med en sporbar jobb-ID. Produktet
skal derfor fortsatt ikke kalles ferdig eller klart for ekstern historielærer.

## 20. Ny forensic closure-kandidat — 3. august 2026

Den siste lokale rettingen (`2e66ec7a5467f3fc23523930ec9ac51181e7c070`) gjør
`qualify`-revisjon fail-closed når modellens tekstutdrag bare er en del av en
setning eller punktlinje. Den globale frase-erstatningen er fjernet fra denne
banen, og regresjonstesten består.

Kandidatimagets digest er
`sha256:db88579d5240abd7b1381ad0cfae035a7f8d73cbe01a11963ab92e685da47858`.
Full backend-suite i image bestod med **398 passed, 2 skipped, 47 warnings**
på 28,96 sekunder. Frontend bestod med 13 tester, typecheck og produksjonsbuild.

Kandidaten er ikke publisert til deploybranch. Offentlig readiness svarte
HTTP 200 med release `69b00d81e5a7` og `rndr-id=e947f2ef-2374-426d`, som viser
at produksjonen fortsatt kjører forrige release. Identisk produksjonsscenario
er derfor ikke kjørt etter siste retting. Dommen er fortsatt **REJECTED**.

## 21. Product excellence M1 — 3. august 2026

Repo-, runtime- og produksjonssannhet er samlet i
`research/PRODUCT_EXCELLENCE_EXECPLAN.md`, mens mål, nåverdier, evidens og eiere
er samlet i `research/PRODUCT_SCORECARD.md`. Primær produktwedge er avgrenset til
Historie VG2: én årsplanperiode til et kildeforankret, redigerbart og eksplisitt
lærergodkjent læringsark eller kort kompendium. Dette er en hypotese som må
valideres med lærere; repoet har ikke dokumentert bruk, retention eller betaling.

Første milepæl retter en lokalt reprodusert kandidatregresjon der automatisk
`remove` med avsluttende punktum kunne slette nabosetningen. Commit
`912007b` (`Make truth edits sentence-safe`) tillater nå bare entydige hele
setninger eller hele Markdown-linjer. Delvise og gjentatte treff blir stående og
sendes til lærerreview.

Verifikasjon på commit-en:

* målrettet sannhetslag: **12 bestått**
* full read-only Docker-suite: **403 bestått, 2 hoppet over, 47 warnings**
* endrede Python-filer: `py_compile` bestått
* frontend: **13/13 tester**, typekontroll og produksjonsbygg bestått
* frontend-lint: **ikke operativ** fordi ESLint-konfigurasjon mangler

Offentlig smoke bestod på forsøk 1 uten generering. Readiness viser fortsatt
produksjonsrelease `69b00d81e5a7`, SQLite-lagring, `sqlite-local`-kø, ingen Redis
og config-fingerprint `dc08f612a352`. M1 er ikke deployet, produksjon er urørt,
og siste identiske scenario står fortsatt på 32/44 verifiserte påstander (73 %),
repair 504, retry 409 og compile 409. Dommen er derfor fortsatt **REJECTED**.

## 22. Release candidate gate — 3. august 2026, 16:54+02

Den entydige releasekandidaten er `ff725bb6997879e74d60d1d539c57e18578f95ad`
(`Document product excellence baseline`) på `laerebokdesign-hefte`. Den bygger
på kodecommit `912007bf5b4a68b736bbd14daa2011494bed266c`
(`Make truth edits sentence-safe`) og diffgrunnlaget
`origin/main..HEAD`: `2e66ec7`, `22b80d9`, `912007b`, `ff725bb` — 11 filer,
809 innsettinger og 29 slettinger.

Kandidat-imaget ble bygget fra ren Git-archive-context som
`skoleverksted-candidate:ff725bb`, digest
`sha256:d9fb7b5f4b4659aefdc729c34358b4e4d704716197f3ab96d3df7c32707c8792`.
Den eksakte Docker-suiten bestod med **398 tester og 2 skips**; `compileall` og
Dockerfile-check bestod. Frontend bestod med **13 tester**, TypeScript og
produksjonsbygg. `npm run lint` er `not operational` fordi ESLint-konfigurasjon
mangler og Next åpner interaktiv førstegangskonfigurasjon.

Arbeidskopien har fortsatt de urørte MateMaTeX-endringene i
`MateMaTeX/backend/app/latex/preamble.py` og
`MateMaTeX/backend/tests/test_hefte_design.py`, samt de fire utrackede
strategidokumentene `EXPERIMENT_BACKLOG.md`, `PRODUCT_WEDGE.md`,
`STOP_BUILDING.md` og `UNICORN_AUDIT.md`. De er ikke del av kandidaten.

Render følger `main` etter beståtte GitHub-checks. Offentlig readiness viste ved
siste kontroll HTTP 200, release `69b00d81e5a7`, `rndr-id=e42efd6a-0b2f-4353`
og tidspunkt `Mon, 03 Aug 2026 14:53:12 GMT`. Kandidaten er ikke pushet eller
deployet; Vercel production-branch og formelt Render deploy-ID er ikke bevist
fra repoet/offentlig respons. Merge/push til deploybranch krever derfor
eksplisitt menneskelig godkjenning.

Produksjonsdommen er fortsatt **REJECTED**. Kandidatens identiske Historie
VG2-scenario er ikke kjørt. Siste produksjonsscenario står på 32/44 (73 %),
kapittel 2/3 `needs_revision`, repair HTTP 504 etter 120 sekunder, retry HTTP
409, compile HTTP 409 og ingen PDF/Word-artefakter. Manuell vurdering er
`pending teacher review`. Rollback er redeploy av
`69b00d81e5a7d823eb284bc7aee37a8cac6f29ed`; ingen force-push, nøkkelrotasjon
eller produksjonsdataendring skal brukes.

---

## Produksjonsstatus 7. august 2026 — kandidaten er deployet

**Deployet release:** `ff725bb69978` (commit
`ff725bb6997879e74d60d1d539c57e18578f95ad`), erstattet `69b00d81e5a7`
6. august 2026 kl. 13:09:58Z.

**Dom: `REJECTED`.** Neste P0: durable reparasjonsjobb.

### Hva som ble bedre

Kandidatens eneste kodeendring gjorde sannhetslaget fail-closed: automatisk
tekstendring skjer bare når treffet er entydig, ellers flagges påstanden for
lærerens gjennomgang. Effekten i produksjon er målt:

- Sannhetsdekning: **42/48 = 88 %**, opp fra 32/44 = 73 %. Alle tre kapitler
  over 80 %-terskelen.
- Automatisk fjernet tekst: **0 påstander**, ned fra 8. Den gamle koden slettet
  tekst i skjul; det gjør den ikke lenger.
- Null språkfragmenter, 3/3 lærerkilder korrekt merket `teacher`/`provided`.

### Hva som fortsatt blokkerer

Reparasjonssteget fullfører ikke. I det identiske scenarioet feilet alle tre
forsøkene:

- Kapittel 2 og 3: HTTP 504 etter 120 sekunder.
- Kapittel 1: HTTP 200 etter 76 sekunder, men reparasjonen feilet internt og
  satte kapittelstatus til `source_grounding_failed`. En mislykket operasjon
  ble altså rapportert som suksess.

Uten fullført reparasjon blir ingen kapitler godkjent, compile blokkerer med
HTTP 409, og PDF og Word finnes ikke. Manuell faglig vurdering av sluttfil er
derfor fortsatt ikke gjennomført.

### Uverifiserte forhold

- Render-dashboardets deploy-ID, deploytidspunkt og status.
- Vercels konfigurerte production-branch og aktive deployment.
- Varig rå response- og reparasjonsledger i produksjon.
- Frontendens visning av 504, 409 og `source_grounding_failed`.

### Korrigerte tall

Tidligere dokumentert lokal testbaseline «398 bestått, 2 hoppet over» var feil.
Målt mot rene utsjekkinger i de eksakte imagene: baseline `69b00d8` gir **396
bestått, 2 hoppet over**, kandidat `ff725bb` gir **402 bestått, 2 hoppet
over**.

---

## 23. Durable compendium repair — 8. august 2026 (ikke deployet)

**Dom: fortsatt `REJECTED`.** Produksjonen kjører `ff725bb69978`. Denne
milepælen er lokalt og runtime-verifisert, ikke produksjonsverifisert.

### Hva som var galt

Den dokumenterte blockeren var ikke sannhetsdekningen — den er 42/48 = 88 % og
over 80 %-terskelen. Blockeren var reparasjonsutførelsen: 0 av 3 forsøk lyktes,
to endte i HTTP 504, ett svarte HTTP 200 mens det internt feilet, og en retry
fikk HTTP 409 uten at jobben kunne slås opp noe sted.

Rotårsaken var at HTTP-requesten eide modellarbeidet. Request-tråden blokkerte
til reparasjonen var ferdig, kapittellåsen lå i prosessminne, og det fantes
verken jobb-ID, varig status eller evidens.

### Hva som er gjort

Reparasjon er nå en varig jobb:

- `POST …/repair` returnerer **HTTP 202** med `job_id`, `operation_id` og
  `status_url` før noe modellkall skjer.
- Modellarbeidet kjører i en worker bak den eksisterende `DurableJobGate`.
- Jobb, lås og evidens ligger i to nye tabeller, `repair_jobs` og
  `repair_events`, med lease, recovery ved restart og opprydding av døde leaser.
- Write-back er beskyttet av compare-and-swap på kapittelteksten. En sen worker
  kan aldri overskrive nyere lærerredigering; jobben blir `superseded`.
- En jobb kan ikke bli `succeeded` uten fullført write-back. Kapittelstatus er
  et innholdsresultat og gjør ikke jobben grønn.
- Frontend viser jobbstatus, lar læreren forlate siden, gjenfinner jobben etter
  reload, tilbyr avbryt og konkret retry, og starter aldri en ny reparasjon
  automatisk.

Nye filer: `Skoleverksted/backend/platform/repair.py`,
`Skoleverksted/backend/tests/test_repair_durability.py`,
`research/REPAIR_DURABILITY_EXECPLAN.md`.

`COMPENDIUM_REPAIR_TIMEOUT_SECONDS` er fjernet fra `render.yaml` og erstattet av
`COMPENDIUM_REPAIR_LEASE_SECONDS` (standard 900).

### Målt

- Backend: **120 tester bestått** (hvorav 27 nye durability-tester).
- Frontend Vitest: **24 tester bestått** (opp fra 13).
- TypeScript og Next-produksjonsbygg: bestått.
- ASGI-test mot reell router: HTTP 202 på under ett sekund mens modellkallet
  fortsatt er blokkert; 409 ved parallell repair; idempotent replay; jobb funnet
  igjen etter reload; `succeeded` først etter write-back.

### Ikke verifisert

Ingen kjøring mot ekte Gemini. Ingen produksjonsdeploy. Ingen vellykket
produksjonsreparasjon, og dermed fortsatt ingen godkjente kapitler, ingen
PDF/Word og ingen manuell faglig sluttvurdering. Postgres-banen for de nye
tabellene er ikke kjørt.

### Neste

Deploy etter eksplisitt godkjenning, deretter det identiske Historie
VG2-scenarioet mot den nye kontrakten.
