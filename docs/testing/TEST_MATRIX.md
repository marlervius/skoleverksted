# Sporbar testmatrise

| Kritisk funksjon | Testnivå | Test/kommando | Akseptansekriterium |
|---|---|---|---|
| Opprette/generere årsplan | API/integrasjon/E2E | `test_year_plan_api.py`, `test_year_planner.py` | fag, nivå, skoleår, mål og perioder lagres og kan åpnes igjen |
| Redigere/slette årsplan | API/regresjon | `test_year_plan_api.py`, store-tester | avbryt endrer ikke data; bekreftet sletting fjerner kun testdata |
| Overføre periode til produksjon | E2E | `test_teaching_package.py`, `test_vgs_packaging.py` | fag/nivå/tema/mål/ID følger med uten dobbeltvalg |
| Generere TeachingPackage | integrasjon | `test_teaching_package.py`, `test_presentation_quality_workflow.py` | alle obligatoriske artefakter og filer finnes; ingen foreldet overskriving |
| Lærerens artefaktgodkjenning | regresjon/API | `test_teaching_package.py` | godkjenning bindes til eksakt revisjon og overlever parentjobben |
| Truth Passport | enhet/evaluering | `test_truth.py`, `test_quality_gate.py`, `test_eval_suite.py` | kilde- og faktapåstand kontrolleres på endelig tekst |
| Karantene og ny kontroll | integrasjon | `test_quality_gate.py`, repair-tester | uverifisert tekst eksporteres ikke; lærerredigering krever ny kontroll |
| Timeout/cancellation | runtime/integrasjon | `test_quality_gate.py`, `test_repair_durability.py`, fakes | bounded return, cancellation stopper neste steg, terminal status sendes |
| Jobbstatus/restart/idempotens | integrasjon | `test_repair_durability.py`, `test_queue.py` | ingen evig «Genererer», dobbeltklikk gir samme/konfliktkontrollert jobb |
| PDF/DOCX/PPTX | dokument/visuell | `test_export_validation.py`, `scripts/test.ps1 -Suite docs` | gyldig container, tekst, geometri, ingen placeholder eller rå AI-rest |
| Matematikk | enhet/regresjon | `MateMaTeX/backend/tests/test_math_verifier.py`, pipeline | fasit er maskinverifisert; feil/udelt på null blokkeres |
| Kildeproveniens | kilde/regresjon | `test_history_fixtures.py`, compendium/Truth-tester | teacher/grounding/model-opphav beholdes og URL alene teller ikke som bevis |
| Frontend feil og fremdrift | komponent/type | Vitest + `tsc --noEmit` | forståelig feil, terminal status og ingen uendelig loading |
| Testisolasjon | miljø/sikkerhet | `test_test_environment.py`, `scripts/test.ps1` | `APP_ENV=test`, unik lokal lagring, remote/produksjonsdatabase avvist |

## Udekket eller miljøavhengig

Nettleserbasert E2E, WCAG-skjermleser-smoke, ekte NDLA/Grep/Wikimedia-respons,
PostgreSQL-restore og ekte modellvariasjon krever staging/ekstern koordinering.
De er eksplisitt periodiske gates, ikke falskt markert som grønne i lokal suite.
