@echo off
rem Para probar la app de la alumna en este mismo PC, antes de pasarla a la laptop.
cd /d "%~dp0"
call .venv\Scripts\activate
pip install -q -r requirements-cliente.txt
python -m profesora.cliente
