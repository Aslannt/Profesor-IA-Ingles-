"""El "cerebro" de la profesora: Ollama (local, en la GPU del PC) o Claude (nube)."""
from __future__ import annotations

import json
import logging
import re

import httpx

from .config import ConfigServidor

logger = logging.getLogger(__name__)


class ErrorIA(Exception):
    pass


class IA:
    def __init__(self, config: ConfigServidor) -> None:
        self.config = config

    # ------------------------------------------------------------ interfaz

    def responder(self, sistema: str, mensajes: list[dict]) -> str:
        """Siguiente intervención de la profesora."""
        texto = self._llamar(sistema, mensajes, 700, None)
        if not texto:
            raise ErrorIA("La profesora se quedó en blanco. Intenta otra vez.")
        return texto

    def responder_json(self, sistema: str, pedido: str, esquema: dict) -> dict:
        """Respuesta estructurada (el resumen de la clase)."""
        return extraer_json(self._llamar(sistema, [{"role": "user", "content": pedido}], 3000, esquema))

    def calentar(self) -> None:
        """Carga el modelo de Ollama en la GPU al arrancar, para que la primera respuesta no tarde."""
        if self.config.proveedor_ia != "ollama":
            return
        try:
            httpx.post(f"{self.config.ollama_url}/api/chat", timeout=120, json={
                "model": self.config.ollama_model, "messages": [{"role": "user", "content": "hola"}],
                "stream": False, "think": False, "keep_alive": self.config.ollama_keep_alive,
                "options": {"num_predict": 1}})
        except httpx.HTTPError as exc:
            logger.warning("No se pudo precalentar Ollama: %s", exc)

    def _llamar(self, sistema, mensajes, max_tokens, esquema) -> str:
        if self.config.proveedor_ia == "anthropic":
            return self._claude(sistema, mensajes, max_tokens, esquema)
        return self._ollama(sistema, mensajes, max_tokens, esquema)

    # ------------------------------------------------------------ Ollama

    def _ollama(self, sistema, mensajes, max_tokens, esquema) -> str:
        cuerpo = {
            "model": self.config.ollama_model,
            "messages": [{"role": "system", "content": sistema}] + mensajes,
            "stream": False,
            "think": False,  # respuestas rápidas, igual que en el Copiloto
            "keep_alive": self.config.ollama_keep_alive,
            "options": {"num_predict": max_tokens, "temperature": 0.6 if esquema is None else 0.2},
        }
        if esquema:
            cuerpo["format"] = esquema
        try:
            r = httpx.post(f"{self.config.ollama_url}/api/chat", json=cuerpo, timeout=180)
        except httpx.HTTPError as exc:
            raise ErrorIA("Ollama no está corriendo en el PC.") from exc
        if r.status_code == 404:
            raise ErrorIA(f"Falta descargar el modelo: ollama pull {self.config.ollama_model}")
        if r.status_code != 200:
            raise ErrorIA(f"Error de Ollama ({r.status_code}): {r.text[:200]}")
        texto = r.json().get("message", {}).get("content", "")
        return re.sub(r"<think>.*?</think>", "", texto, flags=re.S).strip()

    # ------------------------------------------------------------ Claude

    def _claude(self, sistema, mensajes, max_tokens, esquema) -> str:
        import anthropic

        cliente = anthropic.Anthropic(api_key=self.config.anthropic_api_key or None)
        modelo = self.config.anthropic_model
        opciones: dict = {}
        output_config: dict = {}
        if not modelo.startswith("claude-haiku"):  # Haiku 4.5 no tiene pensamiento adaptativo
            opciones["thinking"] = {"type": "adaptive"}
            output_config["effort"] = "medium" if esquema else "low"
        if modelo.startswith(("claude-opus-5", "claude-fable-5", "claude-sonnet-5-5")):
            # Si un filtro de seguridad rechaza algo por error, se reintenta con otro modelo.
            opciones["betas"] = ["server-side-fallback-2026-07-01"]
            opciones["fallbacks"] = "default"
        if esquema:
            output_config["format"] = {"type": "json_schema", "schema": esquema}
        if output_config:
            opciones["output_config"] = output_config
        try:
            respuesta = cliente.beta.messages.create(
                model=modelo, max_tokens=max(max_tokens * 4, 2000), system=sistema, messages=mensajes,
                cache_control={"type": "ephemeral"}, **opciones)
        except anthropic.AuthenticationError as exc:
            raise ErrorIA("La clave de Anthropic no es válida.") from exc
        except anthropic.RateLimitError as exc:
            raise ErrorIA("Demasiadas peticiones o sin saldo en Anthropic.") from exc
        except anthropic.APIStatusError as exc:
            raise ErrorIA(f"Error de Claude ({exc.status_code}): {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise ErrorIA("No hay conexión con Claude.") from exc
        if respuesta.stop_reason == "refusal":
            raise ErrorIA("La IA no pudo responder a eso.")
        return "".join(b.text for b in respuesta.content if b.type == "text").strip()


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
