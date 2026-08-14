# Produksjonsfeil: sannhetssensoren stopper Norsklæring

## Symptom

Differensiert Norsklæring-materiale kunne bli stoppet som om arbeidsark,
språkeksempler, oppgaveinstruksjoner og refleksjonsspørsmål var eksterne
faktapåstander. Når jobben likevel ble ferdig uten godkjent kvalitetsstatus,
kunne terminalstatusen i tillegg bli tolket som godkjent, og frontend viste ikke
en brukbar lærerkontroll.

## Rotårsak

1. `generate_lesson_content()` sendte et samlet, utypet JSON-dokument til
   sannhetslaget. Sannhetsrevisoren hadde derfor ikke en pålitelig felt- eller
   variantgrense.
2. Innholdstyper var for grove. Manglende klassifisering falt tilbake til
   `fact`, slik at vanlig pedagogisk tekst ble kildepliktig.
3. Fordypningsprompten ba modellen om nye nyanser og perspektiver. Det åpnet
   for nye faktapåstander som ikke var del av den kanoniske teksten.
4. Jobbmanageren hadde fail-open-default for ukjent/manglende kvalitetsstatus.
   En manglende status kunne derfor eksponere en PDF som godkjent.
5. SSE-klienten håndterte bare `done` og `error`; `needs_teacher_review` ble
   ikke oversatt til et kontrollbilde.
6. Pakkestatus kunne bli `completed` selv om et barn hadde feilet.

## Endring

- La til et eksplisitt innholdsmanifest med `field_path`, `variant` og
  canonical/standard/støtte/fordypning. Eksterne faktapåstander bruker
  `external_factual_claim`; språkfaglige, fiktive, hypotetiske, instruktive og
  refleksive elementer har egne typer.
- Sannhetslaget teller bare evidenskrevende typer i kildegrad og aksepterer
  kildefritt materiale når det ikke inneholder eksterne faktapåstander.
  Ukjente typer faller fortsatt sikkert tilbake til ekstern faktapåstand.
- Differensieringsprompten kan ikke innføre nye navn, datoer, tall,
  institusjoner eller hendelser. En deterministisk kontrakt kontrollerer at
  kanonisk tekst, støtte og fordypning finnes og faktisk er forskjellige.
- Ukjent eller manglende jobbstatus blir alltid `needs_teacher_review`, og PDF
  lagres ikke som leverbar fil.
- Lærerkontrollen har API og frontend for påstandsvisning, feltredigering,
  «Fjern markert innhold» og «Kjør kontroll på nytt». En grønn ny kontroll
  bygger PDF før jobben skifter til `source_approved`.
- SSE-terminalen sender kontrollstatus, job-id, stoppårsak, karantene og
  variantfeil. Foreldrepakker får `needs_review` ved feil i et barn.
- La til strukturert logging for `fact_check_started/completed`,
  `claim_classified`, `revision_started/completed`, `claim_quarantined`,
  `package_completed` og `job_failed`. Loggene inneholder ikke full elevtekst.

## Verifikasjon

- `Skoleverksted/backend/tests`: 185 passed, 1 skipped (Typst mangler i
  runtime-miljøet).
- Norsklæring/job manager-regresjoner: 22 passed.
- Frontend: `npm run lint` og `npm run build` passerer.
- Python-kompilering og `git diff --check` passerer.

## Gjenværende risiko

Det er ikke kjørt en live Gemini/NDLA-produksjonsrunde i denne arbeidskopien,
fordi produksjonslegitimasjon ikke er tilgjengelig. Typst-basert PDF-layout må
verifiseres i deploymiljøet. Før utrulling bør én faktisk differensiert jobb
følges gjennom SSE, kontrollbildet, ny kontroll og PDF-download med
`request_id` i loggene.
