"""Servidor de la profesora: corre en el PC de Deivid (RTX 3060) y hace todo el trabajo pesado.

La app de la laptop solo graba lo que dice la alumna, lo manda aquí, y reproduce la voz de la
profesora que le devolvemos. Mismo esquema que el Copiloto de Reuniones: WebSocket con token,
descubrimiento por UDP y los modelos cargados una sola vez al arrancar.

    python -m profesora.servidor [--config config/servidor.local.json]
"""
from __future__ import annotations

import argparse
import json
import logging
import secrets
import threading
from dataclasses import asdict
from pathlib import Path

import numpy as np
from websockets.exceptions import ConnectionClosed
from websockets.sync.server import ServerConnection, serve

from . import prompts, protocolo as p
from .almacen import Almacen
from .config import RAIZ, ConfigServidor
from .curriculo import UNIDADES, unidad
from .descubrimiento import run_discovery_responder
from .energia import allow_sleep, prevent_sleep
from .ia import IA, ErrorIA
from .obsidian import NotasObsidian
from .pronunciacion import calificar
from .transcriptor import Transcriptor
from .voz import FRECUENCIA_VOZ, Voz, frase_para_repetir

logger = logging.getLogger("profesora.servidor")
MAX_MENSAJES = 40             # historial que se le manda a la IA en cada turno
TAMANO_MAXIMO = 16 * 2**20     # una frase de 30 s a 16 kHz float32 son ~2 MB


class Motores:
    """Todo lo pesado, cargado una sola vez y compartido por las conexiones."""

    def __init__(self, config: ConfigServidor, ia=None, transcriptor=None, voz=None) -> None:
        self.config = config
        self.ia = ia or IA(config)
        self.transcriptor = transcriptor or Transcriptor(config.whisper_model, config.whisper_device,
                                                         config.whisper_compute_type)
        self.voz = voz or Voz(config)
        self.almacen = Almacen(config.ruta_datos())
        self.obsidian = NotasObsidian(config.obsidian_vault_path or None, config.obsidian_carpeta, config.nombre_alumna)
        # Una sola clase a la vez: si la laptop se reconecta, la nueva conexión toma el relevo.
        self.candado_clase = threading.Lock()

    def precargar(self) -> None:
        logger.info("Cargando Whisper (%s)...", self.config.whisper_model)
        self.transcriptor.load()
        logger.info("Precalentando la IA (%s)...", self.config.proveedor_ia)
        self.ia.calentar()


class SesionClase:
    """Una conexión de la laptop. La clase en curso se guarda en disco en cada turno, así que si
    se cae el wifi, al reconectar se puede continuar donde iba."""

    def __init__(self, motores: Motores, enviar_texto, enviar_binario) -> None:
        self.m = motores
        self.config = motores.config
        self._texto = enviar_texto
        self._binario = enviar_binario
        self.historial: list[dict] = []
        self.practicas: list[dict] = []

    # ------------------------------------------------------------ utilidades

    def evento(self, nombre: str, **datos) -> None:
        self._texto(p.evento(nombre, **datos))

    def info(self) -> None:
        progreso = self.m.almacen.progreso()
        self.evento(p.EV_INFO, alumna=self.config.nombre_alumna, profesora=self.config.nombre_profesora,
                    clase_numero=progreso["clases_completadas"] + 1, unidad_numero=progreso["unidad_actual"] + 1,
                    unidad_titulo=unidad(progreso["unidad_actual"])["titulo"], total_unidades=len(UNIDADES),
                    palabras_aprendidas=len(progreso["palabras_aprendidas"]),
                    hay_clase_en_curso=self.m.almacen.leer_en_curso() is not None)

    @property
    def practica_actual(self) -> str | None:
        if self.historial and self.historial[-1]["role"] == "assistant":
            return frase_para_repetir(self.historial[-1]["content"])
        return None

    def _mensajes_ia(self) -> list[dict]:
        mensajes = self.historial[-MAX_MENSAJES:]
        while mensajes and mensajes[0]["role"] != "assistant":
            mensajes = mensajes[1:]
        return [{"role": "user", "content": prompts.inicio_clase(self.config)}] + mensajes

    # ------------------------------------------------------------ acciones

    def manejar_control(self, msg: dict) -> None:
        accion = msg["accion"]
        if accion == p.EMPEZAR:
            self.empezar(bool(msg.get("continuar")))
        elif accion == p.HABLAR_TEXTO:
            self.respuesta_alumna(str(msg.get("texto", "")).strip())
        elif accion == p.REPETIR:
            texto = msg.get("texto") or next((m["content"] for m in reversed(self.historial)
                                               if m["role"] == "assistant"), "")
            if texto:
                self.hablar(str(texto), bool(msg.get("despacio")))
        elif accion == p.TERMINAR:
            self.terminar()
        elif accion == p.LISTAR_CLASES:
            self.evento(p.EV_CLASES, clases=self.m.almacen.listar_clases())
        elif accion == p.VER_CLASE:
            clase = self.m.almacen.leer_clase(str(msg.get("id", "")))
            if clase:
                self.evento(p.EV_CLASE, clase=clase)
        elif accion == p.ESTADO:
            self.info()

    def empezar(self, continuar: bool) -> None:
        guardada = self.m.almacen.leer_en_curso() if continuar else None
        if guardada:
            self.historial, self.practicas = guardada["historial"], guardada.get("practicas", [])
            self.evento(p.EV_HISTORIAL, mensajes=self.historial)
            if self.historial[-1]["role"] == "assistant":
                ultimo = self.historial[-1]["content"]
                self.evento(p.EV_PROFE, texto=ultimo, practica=frase_para_repetir(ultimo), repetido=True)
                self.hablar(ultimo)
                return
        else:
            self.m.almacen.borrar_en_curso()
            self.historial, self.practicas = [], []
        self.turno_profe()

    def turno_profe(self) -> None:
        self.evento(p.EV_ESTADO, estado="pensando", mensaje="Pensando…")
        sistema = prompts.sistema_clase(self.config, self.m.almacen.progreso())
        try:
            respuesta = self.m.ia.responder(sistema, self._mensajes_ia())
        except ErrorIA as exc:
            self.evento(p.EV_ERROR, mensaje=str(exc))
            return
        self.historial.append({"role": "assistant", "content": respuesta})
        self.m.almacen.guardar_en_curso(self.historial, self.practicas)
        self.evento(p.EV_PROFE, texto=respuesta, practica=frase_para_repetir(respuesta))
        self.hablar(respuesta)

    def hablar(self, texto: str, despacio: bool = False) -> None:
        self.evento(p.EV_ESTADO, estado="preparando_voz", mensaje="…")
        try:
            audio = self.m.voz.sintetizar(texto, despacio)
        except Exception:
            logger.exception("No se pudo generar la voz")
            self.evento(p.EV_ERROR, mensaje="No pude generar la voz (¿hay internet en el PC?). Lee el texto en pantalla.",
                        leve=True)
            self.evento(p.EV_ESTADO, estado="tu_turno", mensaje="Tu turno")
            return
        self.evento(p.EV_AUDIO, frecuencia=FRECUENCIA_VOZ, muestras=int(len(audio)))
        self._binario(p.voz_a_bytes(audio))

    def audio_alumna(self, audio: np.ndarray) -> None:
        frase = self.practica_actual
        self.evento(p.EV_ESTADO, estado="entendiendo", mensaje="Escuchando lo que dijiste…")
        try:
            oido = self.m.transcriptor.transcribir(audio, "en" if frase else "es")
        except Exception:
            logger.exception("Falló la transcripción")
            self.evento(p.EV_ERROR, mensaje="No pude entender el audio. Intenta otra vez.")
            return
        if frase:
            resultado = calificar(frase, oido.texto, oido.palabras)
            if not oido.texto:
                self.evento(p.EV_OIDO, texto="", practica=True)
                return
            self.practicas.append(resultado.a_dict())
            self.evento(p.EV_RESULTADO, **resultado.a_dict())
            self._agregar_alumna(resultado.para_la_profesora())
        else:
            if not oido.texto:
                self.evento(p.EV_OIDO, texto="", practica=False)
                return
            self.evento(p.EV_OIDO, texto=oido.texto, practica=False)
            self._agregar_alumna(oido.texto)

    def respuesta_alumna(self, texto: str) -> None:
        if texto:
            self._agregar_alumna(texto)

    def _agregar_alumna(self, texto: str) -> None:
        self.historial.append({"role": "user", "content": texto})
        self.m.almacen.guardar_en_curso(self.historial, self.practicas)
        self.turno_profe()

    def terminar(self) -> None:
        if sum(1 for m in self.historial if m["role"] == "user") < 2:
            self.m.almacen.borrar_en_curso()
            self.historial, self.practicas = [], []
            self.evento(p.EV_RESUMEN, clase=None, mensaje="La clase fue muy corta, no se guardó resumen.")
            return
        self.evento(p.EV_ESTADO, estado="resumiendo", mensaje="Preparando el resumen de tu clase…")
        progreso = self.m.almacen.progreso()
        sistema, pedido = prompts.pedido_resumen(self.config, progreso, self.historial)
        try:
            resumen = self.m.ia.responder_json(sistema, pedido, prompts.ESQUEMA_RESUMEN)
        except ErrorIA as exc:
            self.evento(p.EV_ERROR, mensaje=str(exc))
            return
        registro = self.m.almacen.guardar_clase(resumen, self.historial, self.practicas)
        self.m.obsidian.escribir_todo(registro, self.m.almacen.progreso(), self.m.almacen.listar_clases())
        self.historial, self.practicas = [], []
        self.evento(p.EV_RESUMEN, clase=registro)


class ServidorProfesora:
    def __init__(self, motores: Motores, host: str, puerto: int, token: str) -> None:
        self.m = motores
        self.host, self.puerto, self.token = host, puerto, token
        self._servidor = None

    def servir(self, listo: threading.Event | None = None) -> None:
        parar = threading.Event()
        threading.Thread(target=run_discovery_responder, args=(self.puerto, parar), daemon=True,
                         name="descubrimiento").start()
        try:
            with serve(self._conexion, self.host, self.puerto, max_size=TAMANO_MAXIMO) as servidor:
                self._servidor = servidor
                logger.info("Escuchando en ws://%s:%s", self.host, self.puerto)
                if listo:
                    listo.set()
                servidor.serve_forever()
        finally:
            parar.set()

    def detener(self) -> None:
        if self._servidor:
            self._servidor.shutdown()

    def _conexion(self, ws: ServerConnection) -> None:
        par = ws.remote_address
        try:
            hola = p.leer_hola(ws.recv(timeout=10))
        except Exception as exc:
            logger.warning("Conexión rechazada de %s: saludo inválido (%s)", par, exc)
            ws.close(code=4000, reason="expected hello")
            return
        if not secrets.compare_digest(str(hola.get("token", "")), self.token):
            logger.warning("Conexión rechazada de %s: token inválido", par)
            ws.send(p.hola_ack(False, "token inválido"))
            ws.close(code=4001, reason="unauthorized")
            return
        ws.send(p.hola_ack(True))
        logger.info("Conectada: %s (%s)", hola.get("equipo"), par)

        sesion = SesionClase(self.m, ws.send, ws.send)
        prevent_sleep()  # que el PC no se suspenda en plena clase
        try:
            sesion.info()
            for mensaje in ws:
                with self.m.candado_clase:
                    if isinstance(mensaje, str):
                        control = p.leer_control(mensaje)
                        if control:
                            sesion.manejar_control(control)
                    else:
                        sesion.audio_alumna(p.bytes_a_audio(mensaje))
        except ConnectionClosed:
            pass
        except Exception:
            logger.exception("Error atendiendo a %s", par)
        finally:
            allow_sleep()
            logger.info("Desconectada: %s", par)


def _asegurar_token(ruta: Path, config: ConfigServidor) -> str:
    """Si no hay token, genera uno y lo guarda en la configuración (para no tener que inventarlo)."""
    if config.server_token:
        return config.server_token
    datos = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else asdict(config)
    datos["server_token"] = secrets.token_urlsafe(24)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.warning("Se creó un token nuevo en %s. Pónselo también al cliente (cliente.json).", ruta)
    return datos["server_token"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Servidor de la Profesora de Inglés")
    parser.add_argument("--config", default=str(RAIZ / "config" / "servidor.local.json"))
    args = parser.parse_args()

    (RAIZ / "logs").mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                        handlers=[logging.StreamHandler(),
                                  logging.FileHandler(RAIZ / "logs" / "servidor.log", encoding="utf-8")])
    ruta = Path(args.config)
    config = ConfigServidor.cargar(ruta)
    token = _asegurar_token(ruta, config)

    motores = Motores(config)
    motores.precargar()
    if motores.obsidian.activo:
        logger.info("Notas de Obsidian en: %s", motores.obsidian.base)
    ServidorProfesora(motores, config.server_host, config.server_port, token).servir()


if __name__ == "__main__":
    main()
