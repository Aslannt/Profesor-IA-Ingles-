"""Lo que hace la app de la laptop por debajo de la ventana: conectarse al PC, grabar lo que dice
la alumna y reproducir la voz de la profesora. Sin nada de Qt, para poder probarlo solo.

La conexión y la reconexión siguen el mismo patrón del Copiloto de Reuniones (client.py).
"""
from __future__ import annotations

import logging
import math
import socket
import threading
import time
from typing import Callable

import numpy as np
from websockets.exceptions import ConnectionClosed
from websockets.sync.client import ClientConnection, connect

from .. import protocolo as p
from ..config import ConfigCliente
from ..descubrimiento import discover_servers

logger = logging.getLogger(__name__)

RECONEXION_MIN = 2.0
RECONEXION_MAX = 10.0


# ================================================================ conexión con el PC

class Conexion:
    """WebSocket con el servidor. Llama a `al_evento(dict)`, `al_audio(np.ndarray, frecuencia)` y
    `al_cambiar_conexion(conectado: bool, mensaje: str)` desde hilos de fondo."""

    def __init__(self, config: ConfigCliente, al_evento: Callable, al_audio: Callable,
                 al_cambiar_conexion: Callable, conectar=connect, buscar=None,
                 al_nueva_direccion: Callable[[str], None] = lambda url: None) -> None:
        self.config = config
        self._buscar = buscar if buscar is not None else discover_servers
        self.al_nueva_direccion = al_nueva_direccion
        self.al_evento = al_evento
        self.al_audio = al_audio
        self.al_cambiar_conexion = al_cambiar_conexion
        self._conectar = conectar
        self._ws: ClientConnection | None = None
        self._lock = threading.Lock()
        self._activa = threading.Event()
        self._audio_pendiente: dict | None = None

    @property
    def conectada(self) -> bool:
        return self._ws is not None

    def iniciar(self) -> None:
        self._activa.set()
        threading.Thread(target=self._bucle_conexion, daemon=True, name="conexion").start()

    def cerrar(self) -> None:
        self._activa.clear()
        with self._lock:
            ws, self._ws = self._ws, None
        if ws:
            try:
                ws.close()
            except Exception:
                pass

    def _abrir(self) -> ClientConnection:
        ws = self._conectar(self.config.remote_server_url, open_timeout=8, max_size=16 * 2**20)
        try:
            ws.send(p.hola(self.config.remote_token, socket.gethostname()))
            ack = p.leer_hola_ack(ws.recv(timeout=8))
            if not ack.get("ok"):
                raise RuntimeError(ack.get("error") or "El servidor rechazó la conexión.")
        except Exception:
            ws.close()
            raise
        return ws

    def _bucle_conexion(self) -> None:
        espera, intentos = RECONEXION_MIN, 0
        while self._activa.is_set():
            try:
                ws = self._abrir()
            except Exception as exc:
                intentos += 1
                logger.warning("No se pudo conectar (intento %d): %s", intentos, exc)
                if "token" in str(exc).lower():
                    self.al_cambiar_conexion(False, "La clave de conexión no es correcta. Pídele ayuda a Deivid.")
                else:
                    self.al_cambiar_conexion(False, self.config.mensaje_servidor_apagado)
                    if intentos % 3 == 0:
                        self._buscar_de_nuevo()
                time.sleep(espera)
                espera = min(espera * 1.5, RECONEXION_MAX)
                continue
            espera, intentos = RECONEXION_MIN, 0
            with self._lock:
                self._ws = ws
            self.al_cambiar_conexion(True, "Conectada")
            self._recibir(ws)  # vuelve cuando se cae la conexión
            with self._lock:
                if self._ws is ws:
                    self._ws = None
            if self._activa.is_set():
                self.al_cambiar_conexion(False, "Se perdió la conexión. Reconectando…")
                time.sleep(RECONEXION_MIN)

    def _buscar_de_nuevo(self) -> None:
        """Si el PC cambió de IP (el router le dio otra), lo encuentra de nuevo en la red."""
        try:
            encontrados = self._buscar(2.0)
        except Exception:
            return
        for s in encontrados:
            url = f"ws://{s['host']}:{s['port']}"
            if url != self.config.remote_server_url:
                logger.info("El servidor ahora está en %s", url)
                self.config.remote_server_url = url
                self.al_nueva_direccion(url)
            return

    def _recibir(self, ws: ClientConnection) -> None:
        try:
            for mensaje in ws:
                if isinstance(mensaje, bytes):
                    info, self._audio_pendiente = self._audio_pendiente, None
                    if info:
                        self.al_audio(p.bytes_a_voz(mensaje), int(info.get("frecuencia", 24000)))
                    continue
                try:
                    ev = p.leer_evento(mensaje)
                except Exception:
                    continue
                if ev["evento"] == p.EV_AUDIO:
                    self._audio_pendiente = ev
                else:
                    self.al_evento(ev)
        except ConnectionClosed:
            pass
        except Exception:
            logger.exception("Error recibiendo del servidor")

    def enviar_control(self, accion: str, **datos) -> bool:
        return self._enviar(p.control(accion, **datos))

    def enviar_audio(self, audio_16k: np.ndarray) -> bool:
        return self._enviar(p.audio_a_bytes(audio_16k))

    def _enviar(self, mensaje) -> bool:
        with self._lock:
            ws = self._ws
        if ws is None:
            return False
        try:
            ws.send(mensaje)
            return True
        except Exception as exc:
            logger.warning("No se pudo enviar: %s", exc)
            return False


# ================================================================ audio

def remuestrear(muestras: np.ndarray, origen: int, destino: int) -> np.ndarray:
    muestras = np.asarray(muestras, dtype=np.float32)
    if origen == destino or len(muestras) == 0:
        return muestras
    largo = max(1, int(round(len(muestras) * destino / origen)))
    return np.interp(np.linspace(0, 1, largo, endpoint=False), np.linspace(0, 1, len(muestras), endpoint=False),
                     muestras).astype(np.float32)


def volumen(bloque: np.ndarray) -> float:
    return float(math.sqrt(float(np.mean(np.square(bloque, dtype=np.float64))))) if len(bloque) else 0.0


class DetectorFrase:
    """Decide cuándo empezó y cuándo terminó de hablar, a partir del volumen de cada bloque.

    - Los primeros bloques miden el ruido del cuarto, para no depender de un umbral fijo.
    - Termina cuando hay `silencio_fin` segundos de silencio después de haber hablado,
      o si nunca empezó a hablar en `espera_maxima` segundos (devuelve None).
    """

    def __init__(self, frecuencia: int, umbral: float, silencio_fin: float, espera_maxima: float,
                 frase_maxima: float) -> None:
        self.frecuencia = frecuencia
        self.umbral_minimo = umbral
        self.silencio_fin = silencio_fin
        self.espera_maxima = espera_maxima
        self.frase_maxima = frase_maxima
        self.ruido: list[float] = []
        self.previo: list[np.ndarray] = []  # un poquito de audio antes de empezar a hablar
        self.frase: list[np.ndarray] = []
        self.silencio = 0.0
        self.transcurrido = 0.0
        self.hablando = False
        self.terminado = False

    @property
    def umbral(self) -> float:
        # Si ya estaba hablando mientras se medía el ruido, no dejar que el umbral se dispare.
        base = min(float(np.median(self.ruido)) * 3, 0.05) if self.ruido else 0.0
        return max(self.umbral_minimo, base)

    def empujar(self, bloque: np.ndarray) -> bool:
        """Agrega un bloque. Devuelve True cuando la frase ya terminó."""
        duracion = len(bloque) / self.frecuencia
        self.transcurrido += duracion
        nivel = volumen(bloque)
        if not self.hablando:
            if self.transcurrido <= 0.3:
                self.ruido.append(nivel)
            self.previo = (self.previo + [bloque])[-3:]
            if nivel >= self.umbral and self.transcurrido > 0.3:
                self.hablando = True
                self.frase = list(self.previo)
            elif self.transcurrido >= self.espera_maxima:
                self.terminado = True
            return self.terminado
        self.frase.append(bloque)
        self.silencio = 0.0 if nivel >= self.umbral * 0.8 else self.silencio + duracion
        largo = sum(len(b) for b in self.frase) / self.frecuencia
        if self.silencio >= self.silencio_fin or largo >= self.frase_maxima:
            self.terminado = True
        return self.terminado

    def audio(self) -> np.ndarray | None:
        if not self.hablando or not self.frase:
            return None
        return np.concatenate(self.frase).astype(np.float32)


class Microfono:
    """Graba UNA frase y la entrega a 16 kHz. `al_nivel(0..1)` sirve para animar el botón."""

    def __init__(self, config: ConfigCliente) -> None:
        self.config = config
        self._parar = threading.Event()
        self._hilo: threading.Thread | None = None

    @property
    def grabando(self) -> bool:
        return bool(self._hilo and self._hilo.is_alive())

    def escuchar(self, practica: bool, al_terminar: Callable[[np.ndarray | None], None],
                 al_nivel: Callable[[float], None] = lambda n: None, al_error: Callable[[Exception], None] = print) -> None:
        if self.grabando:
            return
        self._parar.clear()
        self._hilo = threading.Thread(target=self._grabar, args=(practica, al_terminar, al_nivel, al_error),
                                      daemon=True, name="microfono")
        self._hilo.start()

    def terminar_ya(self) -> None:
        """La alumna tocó el botón: se envía lo que alcanzó a decir."""
        self._parar.set()

    def _grabar(self, practica, al_terminar, al_nivel, al_error) -> None:
        c = self.config
        detector = DetectorFrase(c.frecuencia_captura, c.umbral_voz,
                                 c.silencio_fin_practica_segundos if practica else c.silencio_fin_segundos,
                                 c.espera_maxima_segundos, c.frase_maxima_segundos)
        try:
            import soundcard as sc

            mic = sc.get_microphone(c.microfono_id) if c.microfono_id else sc.default_microphone()
            cuadros = max(256, int(c.frecuencia_captura * c.bloque_segundos))
            # Igual que en el Copiloto: se graba con los canales del dispositivo y se mezcla a mono aquí.
            with mic.recorder(samplerate=c.frecuencia_captura, blocksize=cuadros * 2) as grabadora:
                while not self._parar.is_set():
                    datos = np.asarray(grabadora.record(numframes=cuadros), dtype=np.float32)
                    bloque = datos.mean(axis=1) if datos.ndim == 2 else datos
                    al_nivel(min(1.0, volumen(bloque) * 12))
                    if detector.empujar(bloque):
                        break
        except Exception as exc:
            logger.exception("Error del micrófono")
            al_nivel(0.0)
            al_error(exc)
            return
        al_nivel(0.0)
        audio = detector.audio()
        al_terminar(remuestrear(audio, c.frecuencia_captura, p.FRECUENCIA_OIDO) if audio is not None else None)


class Parlante:
    """Reproduce la voz de la profesora en trozos cortos para poder interrumpirla."""

    def __init__(self) -> None:
        self._parar = threading.Event()
        self._hilo: threading.Thread | None = None

    @property
    def sonando(self) -> bool:
        return bool(self._hilo and self._hilo.is_alive())

    def reproducir(self, audio: np.ndarray, frecuencia: int, al_terminar: Callable[[bool], None]) -> None:
        """`al_terminar(completo)`: completo=False si se interrumpió."""
        self.detener()
        self._parar.clear()
        self._hilo = threading.Thread(target=self._sonar, args=(audio, frecuencia, al_terminar), daemon=True,
                                      name="parlante")
        self._hilo.start()

    def detener(self) -> None:
        self._parar.set()
        if self._hilo and self._hilo.is_alive() and self._hilo is not threading.current_thread():
            self._hilo.join(timeout=1.0)

    def _sonar(self, audio, frecuencia, al_terminar) -> None:
        completo = True
        try:
            import soundcard as sc

            trozo = int(frecuencia * 0.1)
            with sc.default_speaker().player(samplerate=frecuencia, channels=1) as reproductor:
                for i in range(0, len(audio), trozo):
                    if self._parar.is_set():
                        completo = False
                        break
                    reproductor.play(audio[i:i + trozo])
        except Exception:
            logger.exception("Error reproduciendo la voz")
        al_terminar(completo)
