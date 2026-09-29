# Hace que el servidor de la profesora arranque solo al iniciar sesión en Windows
# (tarea programada, igual que install_server_autostart_windows.ps1 del Copiloto).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path (Join-Path $PSScriptRoot ".venv\Scripts\python.exe"))) { throw "Ejecuta primero 'Instalar Servidor.bat'." }
if (-not (Test-Path (Join-Path $PSScriptRoot "config\servidor.local.json"))) { throw "Falta config\servidor.local.json." }

$Nombre = "Profesora de Ingles - Servidor"
$Accion = New-ScheduledTaskAction -Execute (Get-Command powershell.exe).Source `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$(Join-Path $PSScriptRoot 'servidor_oculto.ps1')`""
$Disparador = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$Ajustes = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Days 365)
Register-ScheduledTask -TaskName $Nombre -Action $Accion -Trigger $Disparador -Settings $Ajustes `
    -Description "Arranca el servidor de la Profesora de Inglés al iniciar sesión." -Force | Out-Null
Write-Host "Autoarranque instalado: $Nombre" -ForegroundColor Green
Write-Host "Probarlo ya: Start-ScheduledTask -TaskName `"$Nombre`""
