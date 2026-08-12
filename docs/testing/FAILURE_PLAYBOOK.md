# Failure playbook

## Alvorlighetsgrader

- **P0:** sikkerhet, datatap eller uverifisert innhold godkjennes. Stopp deploy,
  bevar request-ID og artefakter, og isoler berørte data.
- **P1:** sentral brukerreise, jobbterminal eller eksport er utilgjengelig.
  Stopp release og skriv regresjonstest før rettelse.
- **P2:** viktig kvalitets-, språk-, kilde- eller brukerproblem. Rett før neste
  pilot-/releasevindu eller dokumenter eksplisitt unntak.
- **P3:** kosmetikk eller mindre avvik. Planlegg uten å svekke porter.

## Standard prosedyre

1. Reproduser med syntetisk fixture og lagre suite-ID/request-ID, ikke elevtekst eller nøkler.
2. Skriv/oppdater regresjonstesten først. Marker forventet terminalstatus.
3. Finn rotårsaken i riktig lag: input, jobb, agentkontrakt, sannhet, kilde,
   renderer, API eller frontend.
4. Implementer minste sikre rettelse; aldri gjør et usikkert pass grønt for å
   få en suite til å bestå.
5. Kjør målrettet test, deretter `quick`, og til slutt relevant `full`/`docs`.
6. Dokumenter hva som ble rettet, hva som fortsatt er staging-avhengig og
   lenke til CI-artefakt/rendering ved visuelle feil.

## Vanlige feil

| Symptom | Første kontroll | Forventet sluttstatus |
|---|---|---|
| «Genererer» for alltid | jobbtabell, timeout, siste SSE-hendelse | `failed`, `cancelled` eller `needs_teacher_review` |
| Pass gjelder gammel tekst | `content_revision`/digest | eksport blokkert til ny kontroll |
| Kilde-URL finnes, men støtter ikke | source attempt/evidence | karantene eller lærergjennomgang |
| PDF/PPTX opprettes, men er dårlig | `validate_exports.py` + render | ingen frigivelse før teknisk/visuell kontroll |
| Godkjenning forsvinner etter jobben | parent/child CAS og approval history | lærerens beslutning overlever background worker |
| Test påvirker feil database | `APP_ENV`, `TEST_DATA_DIR`, `DATABASE_URL` | testprosessen avvises før store-oppretting |
