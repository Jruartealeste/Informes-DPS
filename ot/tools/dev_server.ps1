# Server de desarrollo de ot/ (Neon dev, .env) con log a archivo.
# Uso: pwsh ot/tools/dev_server.ps1   (desde cualquier carpeta)
# Log: ot/logs/dev-<fecha-hora>.log, uno por corrida (evita que dos corridas
# se pisen el mismo archivo). El reload vigila solo ot/app.
$ot = Split-Path -Parent $PSScriptRoot
if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) {
    Write-Host 'Ya hay un server escuchando en :8000, no levanto otro.'
    exit 1
}
$logs = Join-Path $ot 'logs'
New-Item -ItemType Directory -Force $logs | Out-Null
$log = Join-Path $logs "dev-$(Get-Date -Format 'yyyyMMdd-HHmmss').log"
Write-Host "Log: $log"
Set-Location $ot
& (Join-Path $ot '.venv\Scripts\python.exe') -m uvicorn app.main:app --reload --reload-dir app --port 8000 2>&1 | Tee-Object -FilePath $log
"=== fin $(Get-Date -Format 's') (exit $LASTEXITCODE) ===" | Tee-Object -FilePath $log -Append
