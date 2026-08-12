param(
    [ValidateSet('quick', 'full', 'docs', 'ai')]
    [string]$Suite = 'quick',
    [string]$PythonPath = '',
    [string]$NpmPath = '',
    [switch]$KeepArtifacts
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runId = [guid]::NewGuid().ToString('N')
$runRoot = Join-Path $root (Join-Path 'tmp\test-runs' $runId)
$reportRoot = Join-Path $root 'output\test-runs'
$reportPath = Join-Path $reportRoot ("{0}-{1}.json" -f $Suite, $runId)
$summaryPath = Join-Path $reportRoot ("{0}-{1}-summary.json" -f $Suite, $runId)

New-Item -ItemType Directory -Force -Path $runRoot, $reportRoot | Out-Null

function Resolve-Executable([string]$Configured, [string[]]$Names, [string[]]$Candidates) {
    if ($Configured) {
        if (-not (Test-Path -LiteralPath $Configured)) { throw "Fant ikke kjørbar fil: $Configured" }
        return (Resolve-Path -LiteralPath $Configured).Path
    }
    foreach ($name in $Names) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command) { return $command.Source }
    }
    foreach ($candidate in $Candidates) {
        if (Test-Path -LiteralPath $candidate) { return $candidate }
    }
    throw "Fant ikke nødvendig verktøy. Angi parameteren eksplisitt."
}

$python = Resolve-Executable $PythonPath @('python.exe', 'py.exe') @(
    (Join-Path $root '.venv\Scripts\python.exe'),
    (Join-Path $root 'venv\Scripts\python.exe')
)
$npm = $null
if ($Suite -in @('quick', 'full')) {
    $npm = Resolve-Executable $NpmPath @('npm.cmd', 'npm.exe', 'npm') @()
}

$oldTemp = $env:TEMP
$oldTmp = $env:TMP
$oldAppEnv = $env:APP_ENV
$oldTestData = $env:TEST_DATA_DIR
$oldDb = $env:SKOLEVERKSTED_DB_PATH
$oldOutput = $env:OUTPUT_DIR
$oldDatabaseUrl = $env:DATABASE_URL
$oldLocalAppData = $env:LOCALAPPDATA
$oldXdgDataHome = $env:XDG_DATA_HOME
$oldCrewTelemetry = $env:CREWAI_DISABLE_TELEMETRY
$oldOtelDisabled = $env:OTEL_SDK_DISABLED
$status = 'passed'
$errorMessage = ''

try {
    $env:TEMP = $runRoot
    $env:TMP = $runRoot
    $env:APP_ENV = 'test'
    $env:TEST_DATA_DIR = $runRoot
    $env:SKOLEVERKSTED_DB_PATH = Join-Path $runRoot 'platform.sqlite3'
    $env:OUTPUT_DIR = Join-Path $runRoot 'output'
    $env:DATABASE_URL = ''
    $env:GOOGLE_API_KEY = 'test-key-not-used'
    $env:PYTHONPATH = $root
    $env:LOCALAPPDATA = Join-Path $runRoot 'localappdata'
    $env:XDG_DATA_HOME = Join-Path $runRoot 'xdg-data'
    $env:CREWAI_DISABLE_TELEMETRY = 'true'
    $env:OTEL_SDK_DISABLED = 'true'

    function Invoke-Checked($File, [string[]]$Arguments) {
        & $File @Arguments
        if ($LASTEXITCODE -ne 0) { throw "Kommando feilet ($LASTEXITCODE): $File $($Arguments -join ' ')" }
    }

    function Invoke-Frontend([string[]]$Arguments) {
        Push-Location (Join-Path $root 'MateMaTeX\frontend')
        try {
            & $npm @Arguments
            if ($LASTEXITCODE -ne 0) { throw "Frontendkommando feilet ($LASTEXITCODE): $npm $($Arguments -join ' ')" }
        }
        finally {
            Pop-Location
        }
    }

    switch ($Suite) {
        'quick' {
            Invoke-Checked $python @('-m', 'pytest', '-q', 'Skoleverksted/backend/tests')
            Invoke-Frontend @('test', '--', '--run')
        }
        'full' {
            Invoke-Checked $python @('-m', 'pytest', '-q', 'Skoleverksted/backend/tests')
            Push-Location (Join-Path $root 'VGS_KI\backend')
            try { Invoke-Checked $python @('-m', 'pytest', '-q', 'tests') } finally { Pop-Location }
            Push-Location (Join-Path $root 'ScriptoriumFOV\backend')
            try { Invoke-Checked $python @('-m', 'pytest', '-q', 'tests') } finally { Pop-Location }
            Push-Location (Join-Path $root 'MateMaTeX\backend')
            try { Invoke-Checked $python @('-m', 'pytest', '-q', 'tests') } finally { Pop-Location }
            Invoke-Checked $python @('scripts/compile_sources.py', 'Skoleverksted', 'VGS_KI/backend', 'ScriptoriumFOV/backend', 'MateMaTeX/backend/app')
            Invoke-Frontend @('test', '--', '--run')
            Invoke-Frontend @('run', 'lint')
            Invoke-Frontend @('exec', 'tsc', '--', '--noEmit')
            Invoke-Frontend @('run', 'build')
        }
        'docs' {
            Invoke-Checked $python @('scripts/render_teaching_package_fixture.py')
            Invoke-Checked $python @('scripts/validate_exports.py', '--path', 'output/teaching-package-fixture', '--report', $reportPath)
        }
        'ai' {
            Invoke-Checked $python @('scripts/run_quality_evaluation.py', '--report', $reportPath)
            Invoke-Checked $python @('-m', 'pytest', '-q', 'Skoleverksted/backend/tests/test_eval_suite.py', 'Skoleverksted/backend/tests/test_quality_gate.py')
        }
    }
}
catch {
    $status = 'failed'
    $errorMessage = $_.Exception.Message
    throw
}
finally {
    $summary = [ordered]@{
        suite = $Suite
        status = $status
        run_id = $runId
        generated_at = [DateTime]::UtcNow.ToString('o')
        error = $errorMessage
        app_env = 'test'
        test_data_dir = $runRoot
    }
    $summary | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $summaryPath -Encoding UTF8
    if (-not (Test-Path -LiteralPath $reportPath)) {
        $summary | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $reportPath -Encoding UTF8
    }
    $env:TEMP = $oldTemp
    $env:TMP = $oldTmp
    $env:APP_ENV = $oldAppEnv
    $env:TEST_DATA_DIR = $oldTestData
    $env:SKOLEVERKSTED_DB_PATH = $oldDb
    $env:OUTPUT_DIR = $oldOutput
    $env:DATABASE_URL = $oldDatabaseUrl
    $env:LOCALAPPDATA = $oldLocalAppData
    $env:XDG_DATA_HOME = $oldXdgDataHome
    $env:CREWAI_DISABLE_TELEMETRY = $oldCrewTelemetry
    $env:OTEL_SDK_DISABLED = $oldOtelDisabled
    if (-not $KeepArtifacts) {
        Remove-Item -LiteralPath $runRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
    Write-Host "Test report: $reportPath"
    Write-Host "Runner summary: $summaryPath"
}
