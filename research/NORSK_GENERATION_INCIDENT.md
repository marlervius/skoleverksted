# Norsklæring: produksjonsfeil ved PDF-avslutning

## Rotårsak før retting

Den berørte flyten er `ScriptoriumFOV`-appen som monteres som `/api/norsk` i
Skoleverksted. Den bruker statuspolling, ikke SSE. I `generate_lesson_background`
og `generate_pdf_from_json_background` ble statusen satt til siste steg og vist
som «PDF klar» før `merge_progress` hadde lagret `pdf_bytes`. Dual- og
flernivåflytene hadde samme rekkefølgefeil for `zip_bytes`.

Frontendens terminalregel var `step === 4` (eller `step === 3` for
forhåndsvisning). Den forsøkte da umiddelbart å hente filen og satte aldri en
stabil artefaktmodell i state. Det fantes ingen delt terminalhendelse,
artefakt-ID, preview-/download-URL eller eksplisitt `completed`-status. En
statuspoll som traff race-vinduet kunne derfor hente `202 PDF not ready yet`.
Samtidig var automatisk blob-nedlasting den eneste brukerflaten; det fantes
ingen synlig «Last ned PDF» eller «Forhåndsvis PDF»-knapp.

## Produksjonsflyten som er bevist i kode

1. PDF-byggingen returnerer bytes fra Typst: ja, når `create_lesson_pdf`
   lykkes.
2. PDF-en lagres ikke som en egen fil; bytes lagres i minne eller Redis etter
   at steg 4 allerede er publisert.
3. Artefakt-ID: nei.
4. Terminalhendelse: nei; det finnes kun numerisk progress og melding.
5. Terminalmetadata/URL: nei; kun `filename` og binær payload etter merge.
6. Frontend mottar statuspollen, men tolker steg 4 direkte som ferdig.
7. Skjema-/eventnavn: ingen standardisert terminalhendelse å validere.
8. Exception etter steg 4: mulig ved lagring, validering eller første
   nedlasting; backendens generiske catch kan da overskrive til feil uten å
   knytte feilen til artefaktfasen.
9. Jobbstatus: den separate køstatusen kan fullføres, men progress-objektet
   har ingen terminal jobbstatus og kan derfor ikke brukes til recovery.
10. Automatisk nedlasting: ja; nettleserblokkering eller en kortvarig
    `202`-race etter steg 4 ga ingen alternativ knapp.

## Regresjonsbevis

`ScriptoriumFOV/backend/tests/test_generation_completion.py` gjenskaper den
observerte rekkefølgen og krever at artefaktet materialiseres før siste steg
publiseres. Testen er rød på baseline-koden.
