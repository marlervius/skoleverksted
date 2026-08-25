# Norsklæring: jobb-, preview- og eksportkontrakt

Dette er den kanoniske kontrakten for Norsklæring. Frontend skal bruke
`job_status`/`status` fra `GET /generation-status/{generation_id}`; `step` er
kun fremdrift og kan aldri alene bety at jobben er ferdig.

## Livssyklus

En jobb starter som `running` og avsluttes alltid som én av:

- `completed`: artefaktet er bygget, validert og kildeporten er grønn.
- `needs_teacher_review`: kvalitetskontrollen har uavklarte påstander,
  manglende kilde eller en annen ordinær kvalitetsstopp. Dette er ikke en
  teknisk feil.
- `failed`: en teknisk feil, for eksempel ugyldig PDF eller worker-feil.
- `cancelled`: lærer eller system har avbrutt jobben.

`run_quality_pipeline` eier de begrensede revisjonsrundene og lagrer
`quality_documents`, `truth_passport`, `quality_rounds`, `quarantine` og
`quality_stop_reason`. `needs_teacher_review` er terminalt også når
`step == total_steps`.

## To artefaktflater

Lærerens gjennomgang bruker en separat, beskyttet artefakt:

- `preview_pdf_bytes`/`preview_zip_bytes` og `artifact.draft == true` kan
  hentes med `?preview=true`.
- Responsen har `Cache-Control: no-store`, `X-Preview-Draft: true` og
  `Content-Disposition: inline` for PDF. PDF-en er vannmerket
  `UTKAST – IKKE KILDEGODKJENT`.
- Preview-ruten omgår ikke kvalitetsporten; den viser eksplisitt et utkast for
  lærerens kontroll.

Endelig eksport bruker kun `pdf_bytes`/`zip_bytes`:

- `GET /download-pdf/{id}` og `GET /download-zip/{id}` krever grønn
  kildeport, korrekt `content_revision`/digest og eksplisitt lærerapproval.
- `/generation/{id}/approve` binder approval til akkurat den lagrede
  kvalitetsrevisjonen. En ny redigering må sendes gjennom en ny
  `generate-pdf-from-json`-jobb og får ny digest.
- ZIP eksporteres ikke som endelig artefakt før alle obligatoriske dokumenter
  er kildegodkjent.

## Frontend-flyt

`handlePreview` starter `POST /generate-lesson-json`, og `handleSubmit` starter
`/generate-lesson`, `/generate-dual-lesson` eller `/generate-multi-lesson`.
`generatePdfFromPreview` starter `POST /generate-pdf-from-json` etter at
læreren har redigert utkastet. Alle løp poller
`/generation-status/{generation_id}`.

Ved `needs_teacher_review` viser frontend amber lærergjennomgang, henter
`review_preview`, viser faktapass, nøyaktige påstander, årsaker og forsøkte
kilder, og lar læreren redigere/fjerne tekst før «Kjør kildekontroll på nytt».
Meldingen «Forhåndsvisning blokkert: innholdet er ikke kildegodkjent» er derfor
ikke en rød systemfeil.
