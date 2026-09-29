# Construye el instalador de la laptop de mamá con la dirección del PC y el token ya metidos,
# igual que build_mom_client.ps1 del Copiloto (así ella no tiene que configurar nada).
#
#   .\packaging\construir_instalador_mama.ps1
#
# Toma el token de config\servidor.local.json y la IP actual de este PC.
# Resultado: dist\ProfesoraDeIngles-setup.exe

$ErrorActionPreference = "Stop"
$Proyecto = Split-Path $PSScriptRoot -Parent
Set-Location $Proyecto

$Python = Join-Path $Proyecto ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "No existe .venv. Ejecuta primero 'Instalar Servidor.bat'." }
$ConfigServidor = Join-Path $Proyecto "config\servidor.local.json"
if (-not (Test-Path $ConfigServidor)) { throw "No existe config\servidor.local.json. Arranca el servidor una vez primero." }
$Servidor = Get-Content $ConfigServidor -Raw -Encoding UTF8 | ConvertFrom-Json
if ([string]::IsNullOrWhiteSpace($Servidor.server_token)) { throw "servidor.local.json no tiene server_token. Arranca el servidor una vez y se genera solo." }

# IP de este PC en la red de la casa (la de la conexión con puerta de enlace).
$Ip = (Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq "Up" } |
       Select-Object -First 1).IPv4Address.IPAddress
if (-not $Ip) { throw "No pude averiguar la IP de este PC." }
$Puerto = if ($Servidor.server_port) { $Servidor.server_port } else { 8770 }
Write-Host "PC servidor: ws://${Ip}:$Puerto" -ForegroundColor Cyan
Write-Host "Consejo: reserva esta IP en el router (DHCP) para que no cambie." -ForegroundColor Yellow

$Cliente = Get-Content (Join-Path $Proyecto "config\cliente.example.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$Cliente.remote_server_url = "ws://${Ip}:$Puerto"
$Cliente.remote_token = $Servidor.server_token
$Json = $Cliente | ConvertTo-Json -Depth 5
[System.IO.File]::WriteAllText((Join-Path $Proyecto "config\cliente.json"), $Json, (New-Object System.Text.UTF8Encoding $false))

Write-Host "[1/3] Instalando lo necesario para empaquetar..." -ForegroundColor Cyan
& $Python -m pip install -q -r requirements-cliente.txt pyinstaller
if ($LASTEXITCODE -ne 0) { throw "pip falló." }

Write-Host "[2/3] Empaquetando la app..." -ForegroundColor Cyan
& $Python -m PyInstaller packaging\profesora.spec --noconfirm --distpath dist --workpath build
if ($LASTEXITCODE -ne 0) { throw "PyInstaller falló." }

Write-Host "[3/3] Generando el instalador..." -ForegroundColor Cyan
$Iscc = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Iscc) { throw "Inno Setup no está instalado (winget install JRSoftware.InnoSetup)." }
& $Iscc "packaging\instalador.iss"
if ($LASTEXITCODE -ne 0) { throw "Inno Setup falló." }

Write-Host "Listo: $Proyecto\dist\ProfesoraDeIngles-setup.exe" -ForegroundColor Green
Write-Host "Pásalo a la laptop de tu mamá (USB, WhatsApp, Drive) y ábrelo: ya trae todo configurado." -ForegroundColor Green
