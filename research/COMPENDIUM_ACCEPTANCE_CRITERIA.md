# Compendium acceptance criteria

Dette er stop-kriteriene for den identiske Historie VG2-kjøringen og
regresjonene. En lokal grønn test med mocks erstatter ikke en ny komplett
deployet ende-til-ende-kjøring.

## Identisk scenario

Fixture: `evaluations/history_vg2/french_revolution_1789_1799/`.

Kjør med samme fag, nivå, tema, tre kapitler, cirka seks sider, kompetansemål,
de tre kilde-URL-ene og støtte-/fordypningskrav. Logg kompendium-ID,
request-/operation-ID, promptversjon, modell, alle statusoverganger og hent-/
verifikasjonsresultater uten hemmeligheter.

## Bestått når alle punkter er oppfylt

1. Alle tre kapitler passerer strukturell språkkontroll.
2. Ingen fragmenter, tomme overskrifter eller manglende subjekter finnes.
3. Kritiske faglige feil er enten rettet med evidens eller fjernet/merket.
4. Hver kildelenke har tydelig `provided`, `grounded`, `fetched` eller
   `source_unavailable`-status.
5. `verification_failed`, `source_unavailable` og `not_evaluated` blandes ikke
   med `unsupported`.
6. Minst 80 % av konkrete, kontrollerbare påstander har identifisert evidens.
7. Alle resterende påstander har synlig og riktig usikkerhetsstatus.
8. Reparasjon fullfører eller feiler synlig innen 120 sekunder med jobb-ID.
9. Læreren kan se endringslisten og hva som ble bevart/fjernet.
10. PDF blir tilgjengelig først etter eksplisitt lærergodkjenning av alle
    kapitler.
11. Ingen skjulte exception-/timeout-/parsingfeil finnes i loggen.
12. Eksisterende backend- og frontendtester består.

## Regresjoner

Kjør samme pipeline med:

* industrialiseringen i Norge;
* imperialisme og kolonialisme;
* årsakene til første verdenskrig;
* den russiske revolusjonen;
* en historisk kontrovers med flere forsvarlige tolkninger.

Ingen av disse skal avhenge av fransk revolusjon-tekst eller hardkodede
person-/stednavn. Kvalitetsporten skal være strukturell og kildeproveniens skal
fungere likt.

## Nåværende teststatus

* `python -m compileall` for backend-modulene: bestått med bundled Python.
* Frontend `npm test`: 5 testfiler, 13 tester bestått.
* Frontend `npm run build`: bestått med Next.js type-/produksjonskontroll.
* Separate backendpakker i produksjonsnær Docker-runtime: 397 tester bestått,
  2 eksplisitte skips (Skoleverksted 87, VGS_KI 75, ScriptoriumFOV 53,
  MateMaTeX 181). Full monorepo-innsamling består også med 397 bestått,
  2 skips og 47 warnings etter at VGS_KI-testenes pakkeimporter ble korrigert.
  Dette er `TESTET I RIKTIG RUNTIME`, ikke produksjonsbevis.
* Samme modell-/Render-E2E er kjørt mot release `5b72a0541a20` med kompendium
  `084614b8247d413b8d1ba38cb6166fce`: 44 påstander, 32 verifiserte (73 %),
  lærer-URL-er propagert som `teacher/provided`, språkport bestått og
  compile-port blokkert. 80 %-kravet og vellykket reparasjon er ikke bestått;
  dette er en åpen blokkering, ikke grønn akseptanse.
