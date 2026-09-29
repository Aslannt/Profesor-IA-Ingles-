@echo off
setlocal
title Profesora de Ingles - Instalacion del servidor
cd /d "%~dp0"

rem Instala el servidor de la profesora en ESTE PC (el de la RTX 3060).
rem Mismo Python que el Copiloto de Reuniones (3.11).

where py >nul 2>nul
if errorlevel 1 (
    echo No se encontro Python. Instala Python 3.11 desde https://www.python.org/downloads/
    pause
    exit /b 1
)
py -3.11 -c "print(1)" >nul 2>nul
if errorlevel 1 (
    echo No se encontro Python 3.11. Instalalo desde https://www.python.org/downloads/
    pause
    exit /b 1
)

if not exist ".venv" (
    echo Creando entorno virtual...
    py -3.11 -m venv .venv
)
call .venv\Scripts\activate
python -m pip install --upgrade pip >nul
echo Instalando dependencias ^(Whisper, voz, etc.^). Puede tardar unos minutos...
pip install -r requirements-servidor.txt
if errorlevel 1 (
    echo La instalacion fallo. Revisa la conexion a internet e intenta de nuevo.
    pause
    exit /b 1
)

if not exist "config\servidor.local.json" (
    copy "config\servidor.example.json" "config\servidor.local.json" >nul
    echo Se creo config\servidor.local.json ^(revisa la ruta de tu vault de Obsidian^).
)

echo.
echo Descargando el modelo de IA en Ollama ^(el mismo del Copiloto, si ya lo tienes no descarga nada^)...
ollama pull qwen3.5:9b

echo.
echo Abriendo el firewall para la red de la casa ^(pedira permiso de administrador^)...
powershell -NoProfile -Command "Start-Process powershell -Verb RunAs -Wait -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File \"%~dp0abrir_firewall.ps1\"'"

echo.
echo Listo. Ahora:
echo   1. Abre "Iniciar Profesora (servidor).bat" una vez: genera la clave de conexion.
echo   2. Ejecuta packaging\construir_instalador_mama.ps1 para crear el instalador de la laptop.
echo   3. Opcional: instalar_autoarranque_servidor.ps1 para que arranque solo con Windows.
pause
