# Lo usa la tarea programada: arranca Ollama y el servidor sin ventana. Registro en logs\.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$Python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$Config = Join-Path $PSScriptRoot "config\servidor.local.json"
New-Item -ItemType Directory -Force -Path (Join-Path $PSScriptRoot "logs") | Out-Null
$Registro = Join-Path $PSScriptRoot "logs\arranque.log"

$OllamaApp = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama app.exe"
try { Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 2 | Out-Null }
catch {
    if (Test-Path $OllamaApp) { Start-Process $OllamaApp -WindowStyle Minimized }
    for ($i = 0; $i -lt 45; $i++) {
        Start-Sleep -Seconds 1
        try { Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 2 | Out-Null; break } catch {}
    }
}

Add-Content $Registro "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Iniciando servidor de la profesora"
$Proceso = Start-Process -FilePath $Python -ArgumentList @("-m", "profesora.servidor", "--config", $Config) `
    -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $PSScriptRoot "logs\servidor.out.log") `
    -RedirectStandardError (Join-Path $PSScriptRoot "logs\servidor.err.log")
Wait-Process -Id $Proceso.Id
Add-Content $Registro "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] El servidor terminó (código $($Proceso.ExitCode))"
exit $Proceso.ExitCode
