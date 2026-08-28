$ErrorActionPreference = "Stop"

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$collector = Join-Path $PSScriptRoot "phase0_seven_day_collector.py"
$outputDirectory = $env:DEXSATO_DISCOVERY_STORAGE_DIR
if ([string]::IsNullOrWhiteSpace($outputDirectory)) {
    $outputDirectory = Join-Path $repositoryRoot "output\research\solana-discovery-phase0-seven-day"
}
$logFile = Join-Path $outputDirectory "collector.log"

New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null

$python = Get-Command python.exe -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command python -ErrorAction SilentlyContinue
}
if (-not $python) {
    throw "Python executable was not found."
}

Push-Location $repositoryRoot
try {
    & $python.Source `
        $collector `
        --output-dir $outputDirectory `
        --env-file (Join-Path $repositoryRoot ".env.phase0.local") `
        *>> $logFile

    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
