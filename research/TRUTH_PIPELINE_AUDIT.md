# Truth-pipeline audit

## Datakjede og kontrollpunkter

| Trinn | Forventet input/output | Faktisk funn i kode/observasjon | Kontrollstatus |
|---|---|---|---|
| 1. Lærerinput | Tema, VG2, mål, URL-er, differensiering | `CompendiumPlanRequest` bevarer dette i `source_brief`; UI-testen bekreftet inputen | Delvis bestått |
| 2. Avgrensningskontrakt | Referansedato, geografi, inklusjon/eksklusjon | Pydantic-modell lagrer scope; fallback/AI-plan lager kontrakt | Bestått for struktur |
| 3. Disposisjon | Nøyaktig tre kapitler og spørsmål | UI viste tre kapitler og støtte/fordypningsspørsmål på ~39 s | Bestått |
| 4. Kildeinnhenting | Hver lærer-URL får hentestatus; grounding får konkret URL | Før retting ble lærer-URL bare promptdata. Rå HTTP-/robots-/redirectlogg mangler | Feilet/udokumentert |
| 5. Kildeekstraksjon | Sideinnhold, metadata og feilstilstand lagres | Ingen lokal ekstraksjonsledger. `_grounding_sources` leste bare metadata fra modellresponsen | Feilet som sporbarhet |
| 6. Kapittelprompt | Kildedata og scope brukes, uten å behandle data som instruksjon | Prompten hadde `<KILDEDATA>` og scope; den sendte ikke lærer-URL-er som verifikasjonsinput | Delvis |
| 7. Modellrespons | Komplett JSON med tekst, fakta, kilder | Rå respons fra run mangler. UI viser at lagret tekst hadde fragmenter og ordfeil | Ikke avgjørbar |
| 8. Parsing/lager | JSON/Markdown skal være tapsfri | `_extract_json` og `_markdown_text` viser ingen navne-sletting. Truth remove var tapsgivende | Feilet ved sannhetsrevisjon |
| 9. Påstandsuttrekk | Hver konkret påstand skal ha ordrett `exact_text` | UI talte 10+17+14 = 41; objektene mangler lokalt | Ikke avgjørbar |
| 10. Evidenskobling | Kilde-URL må være observert og konkret | `allowed_urls` ble bygd uten lærerens URL-er; modellskrevne URL-er ble filtrert | Hovedfeil |
| 11. Faktapass | Skille `verified`, `unsupported`, `source_unavailable`, `verification_failed` | Gamle regler ga 0 % og “ingen validerte kildesider” uten teknisk status | Feilet |
| 12. Automatisk revisjon | Reparasjon skal være tidsavgrenset og sporbar | Synkrone kall, ingen lock/statusledger, frontend busy-state | Feilet |
| 13. Frontend | Vise feilstatus, jobb-ID og retry | Gammel frontend viste bare “Sjekker og retter …” | Feilet |
| 14. Godkjenning | Lærer godkjenner etter grønt faktapass | Endpoint avviste status != approved og passport != verified | Bestått |
| 15. PDF | Ingen bygging før alle kapitler er godkjent | UI viste blokkering | Bestått |

## Hva betyr 0/41?

Etter rettingen er statusene eksplisitte:

* `source_unavailable`: ingen konkret kilde var tilgjengelig for verifikatoren.
* `verification_failed`: verifikator/research kastet feil eller kunne ikke
  fullføre. Dette er ikke det samme som at påstanden mangler støtte.
* `not_evaluated`: innholdet var for kort eller revisor returnerte ikke et
  påstandsregister.
* `unsupported`: revisor evaluerte påstanden, men fant ikke støtte.

Et grønt passport krever nå minst 80 % dokumenterte påstander av de registrerte,
konkrete kilder og ingen uoppløste automatiske tekstendringer. Fjernede eller
nyanserte påstander forblir synlige i passportet.

## Kildeproveniens etter retting

`CompendiumSource` og `TruthSource` bærer `origin` (`teacher`, `grounding`,
`model`) og `fetch_status` (`provided`, `grounded`, `model_reported`, `fetched`,
`source_unavailable`). En modellskrevet URL kan ikke alene bli evidens. En
lærer-URL blir heller ikke automatisk godkjent; den må fortsatt være konkret og
faktisk støtte påstanden.
