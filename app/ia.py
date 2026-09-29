"""Conexión con el "cerebro" de la profesora: Claude (nube) u Ollama (local)."""
import json
import re

import httpx

from . import config


class ErrorIA(Exception):
    pass


# ---------------------------------------------------------------- Claude (Anthropic)

def _opciones_claude(modelo: str) -> dict:
    """Parámetros según el modelo: Haiku 4.5 no tiene pensamiento adaptativo ni 'effort'."""
    if modelo.startswith("claude-haiku"):
        return {}
    opciones = {"thinking": {"type": "adaptive"}}
    # Si el filtro de seguridad rechaza algo por error, se reintenta con otro modelo automáticamente.
    if modelo.startswith(("claude-opus-5", "claude-fable-5", "claude-sonnet-5-5")):
        opciones["betas"] = ["server-side-fallback-2026-07-01"]
        opciones["fallbacks"] = "default"
    return opciones


def _claude(system: str, mensajes: list, max_tokens: int, esquema: dict | None) -> str:
    import anthropic

    cliente = anthropic.Anthropic()
    modelo = config.ANTHROPIC_MODEL
    opciones = _opciones_claude(modelo)
    output_config = {}
    if "thinking" in opciones:
        # Conversación: respuestas rápidas. Resumen: un poco más de reflexión.
        output_config["effort"] = "medium" if esquema else "low"
    if esquema:
        output_config["format"] = {"type": "json_schema", "schema": esquema}
    if output_config:
        opciones["output_config"] = output_config
    try:
        respuesta = cliente.beta.messages.create(
            model=modelo,
            max_tokens=max_tokens,
            system=system,
            messages=mensajes,
            cache_control={"type": "ephemeral"},  # reutiliza las instrucciones: más barato y rápido
            **opciones,
        )
    except anthropic.AuthenticationError as e:
        raise ErrorIA("La clave ANTHROPIC_API_KEY no es válida. Revisa el archivo .env") from e
    except anthropic.RateLimitError as e:
        raise ErrorIA("Demasiadas peticiones o sin saldo en la cuenta de Anthropic. Intenta en un momento.") from e
    except anthropic.APIStatusError as e:
        raise ErrorIA(f"Error de Claude ({e.status_code}): {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise ErrorIA("No hay conexión con Claude. Revisa el internet.") from e

    if respuesta.stop_reason == "refusal":
        raise ErrorIA("La IA no pudo responder a eso. Intenta decirlo de otra forma.")
    return "".join(b.text for b in respuesta.content if b.type == "text").strip()


# ---------------------------------------------------------------- Ollama (local)

def _ollama(system: str, mensajes: list, max_tokens: int, esquema: dict | None) -> str:
    cuerpo = {
        "model": config.OLLAMA_MODEL,
        "messages": [{"role": "system", "content": system}] + mensajes,
        "stream": False,
        "options": {"num_predict": max_tokens, "temperature": 0.6},
    }
    if esquema:
        cuerpo["format"] = esquema
    try:
        r = httpx.post(f"{config.OLLAMA_URL}/api/chat", json=cuerpo, timeout=300)
    except httpx.HTTPError as e:
        raise ErrorIA("No encuentro Ollama. ¿Está abierto? (https://ollama.com)") from e
    if r.status_code == 404:
        raise ErrorIA(f"El modelo {config.OLLAMA_MODEL} no está descargado. Ejecuta: ollama pull {config.OLLAMA_MODEL}")
    if r.status_code != 200:
        raise ErrorIA(f"Error de Ollama ({r.status_code}): {r.text[:200]}")
    texto = r.json().get("message", {}).get("content", "")
    return re.sub(r"<think>.*?</think>", "", texto, flags=re.S).strip()


# ---------------------------------------------------------------- interfaz común

def responder(system: str, mensajes: list, max_tokens: int = 1500) -> str:
    """Siguiente intervención de la profesora."""
    motor = _ollama if config.PROVEEDOR_IA == "ollama" else _claude
    texto = motor(system, mensajes, max_tokens, None)
    if not texto:
        raise ErrorIA("La IA respondió vacío. Intenta otra vez.")
    return texto


def responder_json(system: str, pedido: str, esquema: dict) -> dict:
    """Respuesta estructurada (se usa para el resumen de la clase)."""
    motor = _ollama if config.PROVEEDOR_IA == "ollama" else _claude
    texto = motor(system, [{"role": "user", "content": pedido}], 8000, esquema)
    return extraer_json(texto)


def extraer_json(texto: str) -> dict:
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        inicio, fin = texto.find("{"), texto.rfind("}")
        if inicio != -1 and fin > inicio:
            try:
                return json.loads(texto[inicio:fin + 1])
            except json.JSONDecodeError:
                pass
    raise ErrorIA("No se pudo generar el resumen. Intenta de nuevo.")
