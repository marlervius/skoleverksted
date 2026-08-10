# Global kvalitetsport

## Formål

Alt KI-generert innhold går gjennom én server-side kontroll før det kan bli en
fil, en deling eller et godkjent læremiddel. Porten skiller mellom to beslutninger:

1. **Kildegodkjent**: den kontrollerte, eksakte tekstrevisjonen er grønn.
2. **Lærer-godkjent**: læreren har sett revisjonen og godkjent den samme SHA-256-hashen.

Frontendstatus er aldri autoritativ. Eksportendepunktet kontrollerer begge
beslutningene på nytt rett før bytes returneres.

## Felles livsløp

`generert → påstander klassifisert → kilder/matematikk kontrollert → rettet →
kontrollert på nytt → karantene ved sikker utelatelse → lærerreview → eksport`

Revisjonsløkken har maksimalt tre runder og stopper ved grønn status, manglende
fremgang eller rundetak. En rettelse teller aldri som verifisert før den nye
teksten er kontrollert. Den siste kontrollen gjelder alltid eksportkandidaten.

Påstander klassifiseres som fakta, sitat, tall, matematikk, lærerinput,
instruksjon, kreativ tekst eller tolkning. Fakta, sitater og tall krever en
observert kildeadresse. Matematikk har i tillegg deterministisk kontroll av
numeriske likheter. Modellrapporterte eller irrelevante URL-er oppgraderer ikke
en påstand.

## Karantene

En uløst hel setning kan tas ut av godkjent innhold. Originaltekst, plassering,
grunn, kildeforsøk, foreslått erstatning og konsekvens lagres i karantenelisten.
Karantenetekst må ikke finnes i PDF, DOCX, PPTX, ZIP eller delte ressurser.
Fragmenter som ikke kan fjernes entydig, blokkerer videre flyt og krever redigering.

Karantene er ikke en ansvarsfraskrivelse. Læreren bekrefter at utelatelsene er
lest og faglig vurdert; eksporten inneholder fortsatt bare kildegodkjent tekst.

## Revisjoner, godkjenning og migrering

- `TruthPassport.version == "2.0"` kreves ved godkjenning og eksport.
- `content_revision`, `approved_revision` og eksportens beregnede hash må være like.
- Redigering eller kildeendring opphever tidligere kontroll og lærergodkjenning.
- Eldre lagrede artefakter kan leses, men må verifiseres på nytt før bruk.
- Godkjenningsloggen beholder lærer, tidspunkt, dokumenthash, verifikasjonsstatus,
  kilder og utelatte påstander.

## Integrasjonskontrakt for nye generatorer

En ny generator må registreres i `GENERATOR_CONTRACTS`, kalle
`run_quality_pipeline`, lagre pass/runder/karantene og bare rendre
`approved_content`. En ny eksport må registreres i `EXPORT_CONTRACTS` og kalle
`require_export_ready` umiddelbart før filen eller delingen returneres.
Kontrakttesten feiler lukket for ukjente generator- og eksport-ID-er.

Ad hoc-eksport fra editorer bruker `verify_teacher_export`. Hvis kontrollen må
endre eller utelate noe, avvises ett-trinnseksporten slik at læreren først kan
se den reviderte teksten.

## Testkrav

Minstekravet dekker korrekt/feil fakta, sitat uten kilde, tall og ferskhet,
relevant og oppdiktet kilde, oppgave–fasit-samsvar, deterministisk matematikk,
retting + ny kontroll, karantene uten lekkasje, kilde lagt til av lærer,
redigering som opphever godkjenning, gamle pass og alle eksportfamilier.
