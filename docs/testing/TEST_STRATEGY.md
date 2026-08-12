# Teststrategi

## Mål og kvalitetsporter

Kvalitetslaget er fail-closed, men bounded: usikkert faktainnhold kan ikke
bli kildegodkjent, og ingen modell-, revisjons- eller jobbsløyfe kan vente
ubestemt. En merge eller produksjonsdeploy skal stoppes ved:

- P0/P1-feil, datatap, tilgangsbrudd eller kjent uverifisert faktapåstand i et godkjent produkt
- ikke-terminal jobbstatus, manglende cancellation eller overskredet samlet tidsbudsjett
- foreldet/manglende sannhetspass, feil innholdsrevisjon eller uautorisert eksport
- ugyldig PDF/PPTX/DOCX, manglende fag-/nivå-/målproveniens eller grønn frontend/backend-build som ikke er reproduserbar

## Nivåer

| Nivå | Hva kontrolleres | Verktøy og frekvens |
|---|---|---|
| Enhet | Regler, modeller, sanitization, sannhetsstatus, matematikk | pytest/Vitest, hver PR |
| Integrasjon | Store, jobbqueue, kvalitetspass, modulkontrakter | pytest med midlertidig SQLite og fakes, hver PR |
| API/kontrakt | Statuskoder, valideringsfeil, request-ID, SSE/jobblivssyklus | FastAPI-ruter og TestClient, hver PR |
| Frontend | reducer, polling, API-mapping, eksporterings- og feiltilstander | Vitest/TypeScript, hver PR |
| E2E-smoke | Årsplan → periode → TeachingPackage → godkjenning → projeksjon | deterministisk backend-E2E, hver PR; nettleser-smoke i staging |
| AI-agent | struktur, ansvar, provenance, bounded repair, cancellation | fakes hver PR; ekte modell periodisk |
| Fakta/kilde | kilde finnes, relevans, konkret støtte, endelig revisjon | curated eval-set + Truth Gate, hver PR og periodisk |
| Dokument | OOXML/PDF, tekst, geometry, placeholders, kilder | `validate_exports.py`, dokumentkjøring/manual |
| Visuell | renderede sider/slides, stabile maler og layoutgrense | artefakter ved feil, staging/manual |
| Ytelse/stabilitet | tid til første fremdrift, totalbudsjett, samtidighet, restart | liten kontrollert lasttest, periodisk |
| Sikkerhet/personvern | tilgang, IDOR, XSS/SSRF/path traversal, logger | negative regresjonstester, hver PR og før pilot |
| Tilgjengelighet | tastatur, fokus, status, kontrast, redusert bevegelse | lint/static + manuell/screenreader-smoke, staging |

## Deterministiske testdobler

`Skoleverksted/backend/tests/doubles.py` dekker gyldig svar, ugyldig JSON,
tomt/delvis svar, feil fag/nivå, hallusinasjon, manglende/irrelevant/404-kilde,
timeout, 429, 500, treg/aldri-avsluttende respons, gjentatt feil, nye usikre
påstander etter revisjon, prompt injection og cancellation. Source-, dokument-
og jobbstream-dobler holder alle data syntetiske.

## Modelltester

Ekte AI er et supplement, aldri eneste dommer. En ekte modellkjøring må ha:

- egen testnøkkel, eksplisitt kostnadsbudsjett og maks antall kall
- request-timeout, samlet suite-timeout og maksimalt to revisjonsrunder
- syntetisk innhold, ingen elevdata og rapportering av hash/struktur fremfor full tekst
- deterministiske regler, kilde-/schema-/matematikkontroller før eventuell AI-vurdering

## Rapportering

Alle suites skriver status, suite-ID, tidspunkt og feil til `output/test-runs/`.
Ved dokumentfeil bevares renderede filer med `-KeepArtifacts`; CI skal laste
opp disse som artefakter. Full rapport skal minst angi teststatus, kritiske
feil, reiser, kvalitets-/kildemålinger, ytelse, flakiness og gjenværende risiko.
