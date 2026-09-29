"""Prueba de punta a punta: servidor real + cliente real por WebSocket, con la IA, el oído y la voz
simulados (sin GPU, sin internet, sin gastar)."""
import json
import queue
import socket
import threading
import time

import numpy as np
import pytest

from profesora import protocolo as p
from profesora.cliente.motor import Conexion
from profesora.config import ConfigCliente, ConfigServidor
from profesora.servidor import Motores, ServidorProfesora
from profesora.transcriptor import Palabra, Transcripcion

RESUMEN = {
    "titulo": "Saludos", "resumen": "Hoy aprendiste a saludar.",
    "palabras_nuevas": [{"en": "hello", "es": "hola", "pronunciacion": "jélou"}],
    "frases_nuevas": ["Nice to meet you = Mucho gusto"], "logros": ["Dijiste hello perfecto"],
    "dificultades_pronunciacion": ["La i larga de meet"], "tarea": "Saluda 3 veces",
    "notas_para_proxima_clase": "Repasar meet", "unidad_dominada": True,
}


class IAFalsa:
    def __init__(self):
        self.llamadas = []

    def calentar(self):
        pass

    def responder(self, sistema, mensajes):
        self.llamadas.append((sistema, mensajes))
        if len(mensajes) == 1:
            return "¡Hola Katerin! ¿Cómo te llamas?"
        if "Resultado de práctica" in mensajes[-1]["content"]:
            return "¡Muy bien! Sigamos."
        return "¡Qué lindo nombre! Ahora dilo tú: [repite]nice to meet you[/repite]"

    def responder_json(self, sistema, pedido, esquema):
        return dict(RESUMEN)


class OidoFalso:
    def load(self):
        pass

    def transcribir(self, audio, idioma, corto=False):
        if idioma == "en":
            return Transcripcion("nice to mit you", [Palabra("nice", .9), Palabra("to", .9), Palabra("mit", .4),
                                                      Palabra("you", .9)])
        return Transcripcion("me llamo Katerin", [])


class VozFalsa:
    def sintetizar(self, texto, despacio=False):
        return np.full(2400, 0.1, dtype=np.float32)


def puerto_libre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def entorno(tmp_path):
    puerto = puerto_libre()
    config = ConfigServidor(carpeta_datos=str(tmp_path / "datos"), obsidian_vault_path=str(tmp_path / "vault"),
                            server_port=puerto)
    ia = IAFalsa()
    motores = Motores(config, ia=ia, transcriptor=OidoFalso(), voz=VozFalsa())
    servidor = ServidorProfesora(motores, "127.0.0.1", puerto)
    listo = threading.Event()
    threading.Thread(target=servidor.servir, args=(listo,), daemon=True).start()
    assert listo.wait(5)
    yield puerto, motores, ia, tmp_path
    servidor.detener()


def cliente(puerto):
    eventos, conexiones = queue.Queue(), queue.Queue()
    c = Conexion(ConfigCliente(remote_server_url=f"ws://127.0.0.1:{puerto}"),
                 eventos.put, lambda a, f: eventos.put({"evento": "_audio", "muestras": len(a), "frecuencia": f}),
                 lambda ok, msg: conexiones.put((ok, msg)))
    c.iniciar()
    return c, eventos, conexiones


def esperar(eventos, nombre, limite=5):
    fin = time.time() + limite
    vistos = []
    while time.time() < fin:
        try:
            ev = eventos.get(timeout=0.2)
        except queue.Empty:
            continue
        vistos.append(ev["evento"])
        if ev["evento"] == nombre:
            return ev
    raise AssertionError(f"No llegó {nombre}; llegaron {vistos}")


def test_clase_de_principio_a_fin(entorno):
    puerto, motores, ia, tmp = entorno
    c, eventos, conexiones = cliente(puerto)
    assert conexiones.get(timeout=5) == (True, "Conectada")
    info = esperar(eventos, p.EV_INFO)
    assert info["alumna"] == "Katerin" and info["clase_numero"] == 1 and not info["hay_clase_en_curso"]

    # Empieza la clase: la profe saluda y llega su voz.
    c.enviar_control(p.EMPEZAR, continuar=False)
    assert esperar(eventos, p.EV_PROFE)["texto"].startswith("¡Hola Katerin")
    audio = esperar(eventos, "_audio")
    assert audio["muestras"] == 2400 and audio["frecuencia"] == 24000

    # Contesta hablando (en español).
    c.enviar_audio(np.zeros(16000, dtype=np.float32))
    assert esperar(eventos, p.EV_OIDO)["texto"] == "me llamo Katerin"
    profe = esperar(eventos, p.EV_PROFE)
    assert profe["practica"] == "nice to meet you"

    # Práctica de pronunciación (en inglés): 'meet' sale como 'mit'.
    c.enviar_audio(np.zeros(16000, dtype=np.float32))
    res = esperar(eventos, p.EV_RESULTADO)
    niveles = {w["palabra"]: w["nivel"] for w in res["palabras"]}
    assert niveles == {"nice": "bien", "to": "bien", "meet": "casi", "you": "bien"}
    esperar(eventos, p.EV_PROFE)
    ultimo = ia.llamadas[-1][1][-1]["content"]
    assert ultimo.startswith("[Resultado de práctica") and "meet (casi" in ultimo

    # Terminar: resumen, progreso y notas de Obsidian.
    c.enviar_control(p.TERMINAR)
    clase = esperar(eventos, p.EV_RESUMEN)["clase"]
    assert clase["numero"] == 1 and clase["promedio_pronunciacion"] == res["puntaje"]
    progreso = motores.almacen.progreso()
    assert progreso["clases_completadas"] == 1 and progreso["unidad_actual"] == 1
    assert progreso["palabras_aprendidas"][0]["en"] == "hello"
    base = tmp / "vault" / "Inglés Katerin"
    assert (base / "Progreso de Katerin.md").exists() and (base / "Vocabulario.md").exists()
    nota = next((base / "Clases").glob("*.md")).read_text(encoding="utf-8")
    assert "# Clase 1: Saludos" in nota and "nice to meet you" in nota and "pronunciacion: " in nota

    c.enviar_control(p.LISTAR_CLASES)
    assert esperar(eventos, p.EV_CLASES)["clases"][0]["titulo"] == "Saludos"
    c.cerrar()


def test_se_retoma_la_clase_si_se_cae_la_conexion(entorno):
    puerto, motores, ia, _ = entorno
    c, eventos, conexiones = cliente(puerto)
    conexiones.get(timeout=5)
    c.enviar_control(p.EMPEZAR, continuar=False)
    esperar(eventos, "_audio")
    c.enviar_audio(np.zeros(16000, dtype=np.float32))
    esperar(eventos, "_audio")
    c.cerrar()

    c2, eventos2, conexiones2 = cliente(puerto)
    conexiones2.get(timeout=5)
    assert esperar(eventos2, p.EV_INFO)["hay_clase_en_curso"]
    llamadas_antes = len(ia.llamadas)
    c2.enviar_control(p.EMPEZAR, continuar=True)
    assert len(esperar(eventos2, p.EV_HISTORIAL)["mensajes"]) == 3
    assert esperar(eventos2, p.EV_PROFE)["repetido"]
    esperar(eventos2, "_audio")
    assert len(ia.llamadas) == llamadas_antes  # no gasta otra llamada a la IA
    c2.cerrar()


def test_clase_muy_corta_no_guarda_resumen(entorno):
    puerto, motores, *_ = entorno
    c, eventos, conexiones = cliente(puerto)
    conexiones.get(timeout=5)
    c.enviar_control(p.EMPEZAR, continuar=False)
    esperar(eventos, "_audio")
    c.enviar_control(p.TERMINAR)
    assert esperar(eventos, p.EV_RESUMEN)["clase"] is None
    assert motores.almacen.progreso()["clases_completadas"] == 0
    c.cerrar()


def test_si_el_pc_cambia_de_ip_lo_vuelve_a_encontrar(entorno):
    puerto, *_ = entorno
    guardadas, conexiones = [], queue.Queue()
    config = ConfigCliente(remote_server_url="ws://127.0.0.1:1")  # dirección vieja
    c = Conexion(config, lambda e: None, lambda a, f: None, lambda ok, m: conexiones.put(ok),
                 buscar=lambda t: [{"host": "127.0.0.1", "port": puerto, "name": "PC"}],
                 al_nueva_direccion=guardadas.append)
    import profesora.cliente.motor as motor
    motor.RECONEXION_MIN, antes = 0.05, motor.RECONEXION_MIN
    try:
        c.iniciar()
        fin = time.time() + 10
        while time.time() < fin and not c.conectada:
            time.sleep(0.05)
        assert c.conectada and guardadas == [f"ws://127.0.0.1:{puerto}"]
    finally:
        motor.RECONEXION_MIN = antes
        c.cerrar()
