@echo off
chcp 65001 >nul
title Profesora de Ingles
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo.
  echo  Falta instalar Python. Descargalo de https://www.python.org/downloads/
  echo  IMPORTANTE: marca la casilla "Add Python to PATH" al instalar.
  echo.
  pause
  exit /b
)

if not exist ".venv" (
  echo Preparando todo por primera vez, puede tardar unos minutos...
  python -m venv .venv
  call .venv\Scripts\activate.bat
  python -m pip install --upgrade pip >nul
  pip install -r requirements.txt
) else (
  call .venv\Scripts\activate.bat
)

if not exist ".env" (
  copy .env.example .env >nul
  echo.
  echo  Se creo el archivo de configuracion ".env". Se abrira ahora:
  echo  pon tu clave de Anthropic ^(o elige Ollama^), guarda y cierra el Bloc de notas.
  echo.
  notepad .env
)

python -m app.servidor
pause
