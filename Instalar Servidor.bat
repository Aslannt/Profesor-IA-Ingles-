@echo off
setlocal
title Profesora de Ingles - Instalacion del servidor
cd /d "%~dp0"

rem Instala el servidor de la profesora en ESTE PC (el de la RTX 3060).

rem Busca un Python compatible (3.11 a 3.14), prefiriendo las versiones mas probadas.
set "PY="
for %%v in (3.12 3.11 3.13 3.14) do (
    if not defined PY (
        py -%%v -c "print(1)" >nul 2>nul && set "PY=py -%%v"
    )
)
if not defined PY (
    python -c "import sys; sys.exit(0 if (3,11) <= sys.version_info[:2] <= (3,14) else 1)" >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo No encontre un Python compatible ^(se necesita 3.11, 3.12, 3.13 o 3.14^).
    echo Versiones que tiene este PC:
    py -0 2>nul
    python --version 2>nul
    echo Instala Python 3.12 desde https://www.python.org/downloads/ y vuelve a ejecutar este archivo.
    pause
    exit /b 1
)
echo Usando:
%PY% --version

if not exist ".venv" (
    echo Creando entorno virtual...
    %PY% -m venv .venv
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
echo   1. Abre "Iniciar Profesora (servidor).bat" y deja esa ventana abierta.
echo   2. Ejecuta packaging\construir_instalador_mama.ps1 para crear el instalador de la laptop.
echo   3. Opcional: instalar_autoarranque_servidor.ps1 para que arranque solo con Windows.
pause
