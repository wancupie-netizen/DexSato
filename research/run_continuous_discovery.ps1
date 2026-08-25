$ErrorActionPreference="Stop"
Set-Location "C:\Users\Sufi\Documents\Projects\AlphaRadar"

$log=".\output\research\solana-discovery-phase0-seven-day\continuous-runtime.log"
$stamp=Get-Date -Format o

"[$stamp] MI v4.1 cycle start" | Add-Content $log
try {
    & python ".\research\continuous_discovery_runtime.py" --limit 20 2>&1 |
        Tee-Object -FilePath $log -Append
    $code=$LASTEXITCODE
    "[$(Get-Date -Format o)] MI v4.1 cycle exit=$code" | Add-Content $log
    exit $code
}
catch {
    "[$(Get-Date -Format o)] MI v4.1 runner error: $($_.Exception.Message)" | Add-Content $log
    throw
}