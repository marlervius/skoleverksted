# AI- og sluttprodukt-rubrikk

## Poeng

Hvert område gis 0–4 poeng: 0 = blokkert/farlig, 1 = vesentlig mangelfullt,
2 = delvis/ustabilt, 3 = godkjent med mindre merknader, 4 = dokumentert og
robust. En vurdering er ikke grønn dersom en hard gate feiler.

| Område | Vekt | Minimum |
|---|---:|---:|
| Faglig korrekthet og matematisk gyldighet | 20 | 4 |
| Kildedekning og konkret støtte per påstand | 15 | 4 |
| Samsvar med LK20, fag og nivå | 10 | 3 |
| Pedagogisk progresjon og læringsmål | 15 | 3 |
| Oppgaver/fasit/lærerveiledning henger sammen | 10 | 3 |
| Språk, begreper og elevvennlighet | 10 | 3 |
| Universell utforming og lesbarhet | 5 | 3 |
| Layout, eksport og fravær av AI-rester | 10 | 3 |
| Sporbarhet, revisjons-ID og læreransvar | 5 | 4 |

Vektet totalscore må være minst 80/100 for «quality passed». Faglig feil,
uverifisert faktapåstand, manglende fasit i en påkrevd pakke eller skjult
placeholder gir umiddelbart `failed`, uavhengig av totalscore.

## Målinger

Eval-settet rapporterer minst:

- stopp-rate for kjente feilpåstander
- feil-stopp-rate for korrekte påstander
- andel kildehenvisninger med faktisk støtte
- antall uverifiserte påstander som slipper gjennom (må være 0 i godkjent eksport)
- gjennomsnittlig revisjonsrunde og tid i sannhetslaget
- teknisk eksportstatus og antall layout-/placeholderfeil

AI-dommer kan gi et ekstra signal, men kan ikke overstyre deterministisk kilde-,
schema-, revisjons-, matematikk- eller læreransvarsgate.
