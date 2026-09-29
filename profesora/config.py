"""Configuración (JSON) del servidor y del cliente, con el mismo esquema del Copiloto de Reuniones.

- Desde el código fuente, los datos viven junto al proyecto.
- Instalada como .exe (PyInstaller), la app vive en Program Files (solo lectura),
  así que la configuración y los registros se guardan en %LOCALAPPDATA%.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


def _resolver_raices() -> tuple[Path, Path]:
    if getattr(sys, "frozen", False):
        paquete = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        base = os.environ.get("LOCALAPPDATA") or Path.home()
        return paquete, Path(base) / "ProfesoraDeIngles"
    aqui = Path(__file__).resolve().parent.parent
    return aqui, aqui


RAIZ_PAQUETE, RAIZ = _resolver_raices()


def preparar_datos_usuario() -> None:
    """En la app instalada, copia la configuración de fábrica a la carpeta del usuario la primera vez."""
    if RAIZ_PAQUETE == RAIZ:
        return
    for carpeta in ("config", "logs"):
        (RAIZ / carpeta).mkdir(parents=True, exist_ok=True)
    origen = RAIZ_PAQUETE / "config" / "cliente.json"
    destino = RAIZ / "config" / "cliente.json"
    if origen.exists() and not destino.exists():
        try:
            shutil.copyfile(origen, destino)
        except OSError:
            pass


def _cargar(cls, ruta: Path):
    if not ruta.exists():
        return cls()
    datos = json.loads(ruta.read_text(encoding="utf-8-sig"))  # tolera el BOM del Bloc de notas
    permitidos = set(cls.__dataclass_fields__)
    return cls(**{k: v for k, v in datos.items() if k in permitidos})


PUERTO_POR_DEFECTO = 8770  # el Copiloto usa 8765/8766


@dataclass(slots=True)
class ConfigServidor:
    nombre_alumna: str = "Katerin"
    nombre_profesora: str = "Lucía"
    # Opcional: algo de su vida para que los ejemplos le sirvan, p. ej.
    # "Tiene reuniones de trabajo en inglés por videollamada."
    contexto_alumna: str = ""

    # Cerebro: "ollama" (local, gratis) o "anthropic" (Claude en la nube).
    proveedor_ia: str = "ollama"
    ollama_url: str = "http://127.0.0.1:11434"
    # El mismo modelo del Copiloto: así los dos comparten la memoria de la tarjeta
    # gráfica en vez de que Ollama tenga que estar cambiando de modelo.
    ollama_model: str = "qwen3.5:9b"
    ollama_keep_alive: str = "30m"
    anthropic_model: str = "claude-opus-5-5"
    anthropic_api_key: str = ""  # vacío = se usa la variable de entorno ANTHROPIC_API_KEY

    # Oído: Whisper multilingüe (entiende español e inglés). "small" va bien en una RTX 3060;
    # "medium" entiende mejor acentos pero es un poco más lento.
    whisper_model: str = "small"
    whisper_device: str = "auto"
    whisper_compute_type: str = "auto"

    # Voz: "edge" (voces neuronales de Microsoft, muy naturales, necesita internet) o "kokoro" (local).
    motor_voz: str = "edge"
    voz_espanol: str = "es-CO-SalomeNeural"
    voz_ingles: str = "en-US-JennyNeural"
    velocidad_ingles: str = "-15%"
    kokoro_voz_espanol: str = "ef_dora"
    kokoro_voz_ingles: str = "af_heart"

    # Obsidian: se escribe en <vault>/<carpeta>. Vacío = no se usa Obsidian.
    obsidian_vault_path: str = ""
    obsidian_carpeta: str = "Inglés Katerin"

    carpeta_datos: str = "datos"
    server_host: str = "0.0.0.0"
    server_port: int = PUERTO_POR_DEFECTO

    @classmethod
    def cargar(cls, ruta: str | Path | None = None) -> "ConfigServidor":
        return _cargar(cls, Path(ruta) if ruta else RAIZ / "config" / "servidor.local.json")

    def ruta_datos(self) -> Path:
        ruta = Path(self.carpeta_datos)
        return ruta if ruta.is_absolute() else RAIZ / ruta


@dataclass(slots=True)
class ConfigCliente:
    # Ej: "ws://192.168.1.50:8770". Vacío = el asistente busca el PC en la red.
    remote_server_url: str = ""
    microfono_id: str = ""  # vacío = micrófono predeterminado de Windows

    frecuencia_captura: int = 48000
    bloque_segundos: float = 0.1
    # Umbral de volumen para considerar que está hablando, y cuánto silencio
    # esperar para saber que terminó (un aprendiz hace pausas largas pensando).
    umbral_voz: float = 0.012
    silencio_fin_segundos: float = 1.6
    silencio_fin_practica_segundos: float = 1.2
    espera_maxima_segundos: float = 10.0
    frase_maxima_segundos: float = 30.0

    conversacion_automatica: bool = True  # abrir el micrófono solo cuando la profe termina
    tamano_letra: int = 17
    mensaje_servidor_apagado: str = (
        "No me puedo conectar con la profesora. Revisa que el computador de Deivid esté prendido."
    )
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def ruta_por_defecto(cls) -> Path:
        return RAIZ / "config" / "cliente.json"

    @classmethod
    def cargar(cls, ruta: str | Path | None = None) -> "ConfigCliente":
        return _cargar(cls, Path(ruta) if ruta else cls.ruta_por_defecto())

    def guardar(self, ruta: str | Path | None = None) -> None:
        destino = Path(ruta) if ruta else self.ruta_por_defecto()
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
