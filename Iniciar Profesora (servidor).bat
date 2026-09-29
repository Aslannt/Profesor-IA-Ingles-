@echo off
setlocal enabledelayedexpansion
title Profesora de Ingles - Servidor
cd /d "%~dp0"

rem Arranca Ollama (si no esta corriendo) y el servidor de la profesora, para que la laptop de
rem mama se pueda conectar. Mismo esquema que "Iniciar Servidor.bat" del Copiloto.

set "OLLAMA_APP=%LOCALAPPDATA%\Programs\Ollama\ollama app.exe"
set "PYTHON=%~dp0.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo Falta instalar. Ejecuta primero "Instalar Servidor.bat".
    pause
    exit /b 1
)

rem Solo procesos de Python: el propio comando de PowerShell contiene el texto buscado y se encontraba a si mismo.
powershell -NoProfile -Command "if (Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*profesora.servidor*' }) { exit 0 } else { exit 1 }" >nul 2>&1
if %errorlevel%==0 (
    echo El servidor de la profesora ya esta corriendo. No hace falta iniciarlo de nuevo.
    pause
    exit /b 0
)

powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
if %errorlevel%==0 goto listo
if exist "%OLLAMA_APP%" (
    echo Iniciando Ollama...
    start "" /min "%OLLAMA_APP%"
)
set /a intentos=0
:esperar
powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
if %errorlevel%==0 goto listo
set /a intentos+=1
echo   Esperando a Ollama... (%intentos%/45)
if %intentos% GEQ 45 (
    echo Ollama esta tardando demasiado, se inicia el servidor igual.
    goto listo
)
timeout /t 1 /nobreak >nul
goto esperar

:listo
echo.
echo Iniciando la profesora (la primera vez descarga el modelo de Whisper, ~500 MB)...
echo NO CIERRES ESTA VENTANA mientras tu mama este en clase.
echo.
"%PYTHON%" -m profesora.servidor --config "%~dp0config\servidor.local.json"
echo.
echo El servidor se detuvo.
pause
