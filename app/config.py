"""Configuración leída desde el archivo .env."""
import os
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")


def _env(nombre: str, defecto: str = "") -> str:
    return os.getenv(nombre, defecto).strip()


NOMBRE_ALUMNA = _env("NOMBRE_ALUMNA", "Katerin")
NOMBRE_PROFESORA = _env("NOMBRE_PROFESORA", "Lucía")

PROVEEDOR_IA = _env("PROVEEDOR_IA", "anthropic").lower()
ANTHROPIC_MODEL = _env("ANTHROPIC_MODEL", "claude-opus-5-5")
OLLAMA_URL = _env("OLLAMA_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = _env("OLLAMA_MODEL", "gemma3:12b")

MOTOR_VOZ = _env("MOTOR_VOZ", "edge").lower()
VOZ_ESPANOL = _env("VOZ_ESPANOL", "es-CO-SalomeNeural")
VOZ_INGLES = _env("VOZ_INGLES", "en-US-JennyNeural")
VELOCIDAD_INGLES = _env("VELOCIDAD_INGLES", "-15%")
KOKORO_VOZ_ESPANOL = _env("KOKORO_VOZ_ESPANOL", "ef_dora")
KOKORO_VOZ_INGLES = _env("KOKORO_VOZ_INGLES", "af_heart")

PUERTO = int(_env("PUERTO", "8000") or 8000)

DATOS = RAIZ / "datos"
CARPETA_CLASES = DATOS / "clases"
ARCHIVO_PROGRESO = DATOS / "progreso.json"
