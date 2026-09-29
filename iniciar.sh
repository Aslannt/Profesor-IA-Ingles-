#!/usr/bin/env bash
# Lanzador para Mac / Linux
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  echo "Preparando todo por primera vez..."
  python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -r requirements.txt
fi
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Se creó el archivo .env: ponle tu clave de Anthropic (o elige Ollama) y vuelve a ejecutar."
  exit 0
fi
exec .venv/bin/python -m app.servidor
