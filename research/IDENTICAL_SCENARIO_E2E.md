# Identical scenario E2E

Status: `NOT RUN AFTER FIX`.

Dette dokumentet er bevisst opprettet før deploy. Det skal fylles med faktiske
produksjons-ID-er og artefakter etter at korrekt release er bekreftet i Render
og Vercel. Ingen lokal fixturekjøring kan erstatte dette.

## Inputkontrakt

* Fag: Historie VG2
* Tema: Den franske revolusjonen 1789–1799
* Omfang: 3 kapitler, omtrent 6 sider
* Kompetansemål: samme anonymiserte kontrakt som i
  `evaluations/history_vg2/french_revolution_1789_1799/input.json`
* Læreroppgitte kilder: samme URL-sett som i `sources.json`
* Differensiering: støtte- og fordypningsspørsmål
* Dokumenttype: kompendium/hefte
* Bildevalg: samme valg som originalkjøringen
* Kvalitetskrav: `rubric.md` og `COMPENDIUM_ACCEPTANCE_CRITERIA.md`

## Produksjonsidentitet

| ID/felt | Verdi |
|---|---|
| Request-ID | Ikke registrert |
| Prosjekt-ID | Ikke registrert |
| Kompendium-ID | Original: `838938c88e994320a64281aafc871ec8`; ny: ikke registrert |
| Kapittel-ID-er | Ikke registrert |
| Plan-/kapitteljobb-ID-er | Ikke registrert |
| Reparasjonsjobb-ID-er | Ikke registrert |
| Kompileringsjobb-ID | Ikke registrert |
| Promptversjon | Ikke verifisert i produksjon |
| Modell | Ikke verifisert i produksjon |

## Tidslinje

| Tid | Hendelse | Jobbstatus | Request-ID | Resultat |
|---|---|---|---|---|
| – | Ny produksjonskjøring | Ikke startet | – | Mangler deploybevis |

## Kildepropagering og truth

| Kilde | Mottatt | Lagret | `provided_sources` | Hentestatus | Koblet til påstand | Sluttprodukt |
|---|---|---|---|---|---|---|
| Lærerens kilde 1 | Ikke verifisert | Ikke verifisert | Ikke verifisert | Ikke verifisert | Ikke verifisert | Ikke verifisert |
| Lærerens kilde 2 | Ikke verifisert | Ikke verifisert | Ikke verifisert | Ikke verifisert | Ikke verifisert | Ikke verifisert |
| Lærerens kilde 3 | Ikke verifisert | Ikke verifisert | Ikke verifisert | Ikke verifisert | Ikke verifisert | Ikke verifisert |

Påstandsregisteret skal etter kjøring inneholde tekst, kilde, evidens,
konfidens, status og foreslått handling. Statusene må holdes adskilt:
`verified`, `undocumented`, `verification_failed`, `source_unavailable`,
`not_evaluated`, `interpretation`, `disputed` og `time_sensitive`.

## Tekst- og reparasjonssammenligning

Følgende artefakter mangler fortsatt: rå modelltekst, normalisert tekst, tekst
før/etter truth-revisjon, reparasjonsresultat og rendret PDF-/Word-tekst. De må
lagres med samme request-/jobb-ID uten hemmeligheter.

## Kompilering og manuell vurdering

PDF-status: ikke kjørt etter retting. Word-status: ikke kjørt etter retting.
Manuell vurdering av kapitler, kildeliste, forbehold, tabeller og spesialtegn:
ikke utført. PDF-blokkeringen skal fortsatt gjelde dersom ett kapittel ikke er
eksplisitt godkjent og truth-passet ikke er grønt.

## Avvik fra originalscenarioet

Ingen avvik kan godkjennes før ny kjøring er sammenlignet med originalens input,
modell/prompt, kilde-sett, bildevalg og dokumenttype. Inntil da er incidenten
åpen og dommen `REJECTED`.
