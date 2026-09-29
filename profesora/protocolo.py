"""Formato de los mensajes entre el servidor (PC) y el cliente (laptop). Mismo estilo que el Copiloto:

1. El cliente abre el WebSocket y manda {"type": "hello"}; el servidor responde hello_ack.
   (Sin clave a propósito: solo se usa en la red de la casa.)
2. Cliente -> servidor:
   - JSON {"type": "control", "accion": ..., ...datos}
   - Binario: lo que dijo la alumna (una frase completa), audio PCM float32 mono a 16 kHz.
3. Servidor -> cliente:
   - JSON {"type": "evento", "evento": ..., ...datos}
   - Binario: la voz de la profesora, PCM int16 mono. Siempre llega justo después de un
     evento "audio" que dice la frecuencia y a qué mensaje pertenece.
"""
from __future__ import annotations

import json

import numpy as np

VERSION_PROTOCOLO = 1
FRECUENCIA_OIDO = 16000  # lo que espera Whisper

# Acciones del cliente
EMPEZAR = "empezar"            # {"continuar": bool}
HABLAR_TEXTO = "texto"         # {"texto": str}  (respuesta escrita)
TERMINAR = "terminar"          # genera el resumen de la clase
REPETIR = "repetir"            # {"despacio": bool, "texto": str opcional}
LISTAR_CLASES = "listar_clases"
VER_CLASE = "ver_clase"        # {"id": str}
ESTADO = "estado"

# Eventos del servidor
EV_INFO = "info"               # datos de la alumna y su progreso
EV_ESTADO = "estado"           # {"estado": "pensando"|"escuchando"|..., "mensaje": str}
EV_HISTORIAL = "historial"     # {"mensajes": [...]}  al continuar una clase que quedó abierta
EV_OIDO = "oido"               # {"texto": str}  lo que el servidor entendió que dijo
EV_PROFE = "profe"             # {"texto": str, "practica": str|None}
EV_AUDIO = "audio"             # {"frecuencia": int, "muestras": int}  -> sigue un mensaje binario
EV_RESULTADO = "resultado"     # resultado de la práctica de pronunciación
EV_RESUMEN = "resumen"         # la clase terminada (registro completo)
EV_CLASES = "clases"           # {"clases": [...]}
EV_CLASE = "clase"             # {"clase": {...}}
EV_ERROR = "error"             # {"mensaje": str}


class ErrorProtocolo(RuntimeError):
    pass


def hola(equipo: str) -> str:
    return json.dumps({"type": "hello", "protocol_version": VERSION_PROTOCOLO, "equipo": equipo})


def leer_hola(crudo: str) -> dict:
    datos = json.loads(crudo)
    if datos.get("type") != "hello":
        raise ErrorProtocolo("Se esperaba un saludo (hello) primero.")
    return datos


def hola_ack(ok: bool, error: str = "") -> str:
    return json.dumps({"type": "hello_ack", "ok": ok, "error": error})


def leer_hola_ack(crudo: str) -> dict:
    datos = json.loads(crudo)
    if datos.get("type") != "hello_ack":
        raise ErrorProtocolo("Se esperaba hello_ack.")
    return datos


def control(accion: str, **datos) -> str:
    return json.dumps({"type": "control", "accion": accion, **datos}, ensure_ascii=False)


def leer_control(crudo: str) -> dict | None:
    """El control recibido, o None si no es un control válido (se ignora)."""
    try:
        datos = json.loads(crudo)
    except json.JSONDecodeError:
        return None
    if datos.get("type") != "control" or not isinstance(datos.get("accion"), str):
        return None
    return datos


def evento(nombre: str, **datos) -> str:
    return json.dumps({"type": "evento", "evento": nombre, **datos}, ensure_ascii=False)


def leer_evento(crudo: str) -> dict:
    datos = json.loads(crudo)
    if datos.get("type") != "evento":
        raise ErrorProtocolo(f"Mensaje desconocido: {datos.get('type')!r}")
    return datos


def audio_a_bytes(pcm_float: np.ndarray) -> bytes:
    return np.asarray(pcm_float, dtype=np.float32).reshape(-1).tobytes()


def bytes_a_audio(datos: bytes) -> np.ndarray:
    return np.frombuffer(datos, dtype=np.float32)


def voz_a_bytes(pcm_float: np.ndarray) -> bytes:
    return (np.clip(np.asarray(pcm_float, dtype=np.float32), -1, 1) * 32767).astype("<i2").tobytes()


def bytes_a_voz(datos: bytes) -> np.ndarray:
    return np.frombuffer(datos, dtype="<i2").astype(np.float32) / 32767.0
