# Test- og kvalitetsmiljø

Skoleverksted bruker eksisterende `pytest`-, Vitest- og Next-verktøy. Testprofilen
er eksplisitt isolert med `APP_ENV=test`, syntetisk modellnøkkel, unik lokal
tempmappe og SQLite-lagring per kjøring. Den kobler aldri til `DATABASE_URL`.

## Første gangs oppsett på Windows

Kjør fra repository-roten:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r .\Skoleverksted\backend\requirements-test.txt
Set-Location .\MateMaTeX\frontend
npm ci
Set-Location ..\..
```

Hvis `python`/`npm` ikke finnes i `PATH`, angi dem eksplisitt med `-PythonPath`
og `-NpmPath`.

## Kommandoer

```powershell
# Rask, deterministisk PR-suite: plattform + frontend-enhetstester
pwsh -File .\scripts\test.ps1 -Suite quick -PythonPath .\.venv\Scripts\python.exe

# Full lokal suite: alle backenddomener, TypeScript og produksjonsbygg
pwsh -File .\scripts\test.ps1 -Suite full -PythonPath .\.venv\Scripts\python.exe

# Dokument-/eksportkontroll og artefaktvalidering
pwsh -File .\scripts\test.ps1 -Suite docs -PythonPath .\.venv\Scripts\python.exe

# Deterministisk AI-/kvalitetsevaluering uten API-kall
pwsh -File .\scripts\test.ps1 -Suite ai -PythonPath .\.venv\Scripts\python.exe
```

Rapporter lagres i `output/test-runs/`. Midlertidige database-, temp- og
testfiler fjernes etter kjøringen med mindre `-KeepArtifacts` brukes.

Dokumenttesten krever at prosjektets dokumentverktøy er installert og i `PATH`
(`typst` for fag-/norsk-PDF og `pdflatex` for matematikk-PDF der den aktuelle
modulen bruker det). `scripts/validate_exports.py` kontrollerer PDF, DOCX og
PPTX strukturelt og geometrisk; dynamisk AI-tekst sammenlignes ikke piksel for
piksel.

Ekte modellkjøringer er manuelle/periodiske og bruker egne testnøkler. De skal
aldri inngå i PR-suiten. Se [TEST_STRATEGY.md](TEST_STRATEGY.md) og
[FAILURE_PLAYBOOK.md](FAILURE_PLAYBOOK.md).
