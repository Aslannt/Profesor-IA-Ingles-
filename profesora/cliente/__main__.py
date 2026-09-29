"""Arranque de la app de la laptop:  python -m profesora.cliente [--config ruta]"""
from __future__ import annotations

import argparse
import logging
import socket
import sys

from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox

from ..config import PUERTO_POR_DEFECTO, RAIZ, ConfigCliente, preparar_datos_usuario
from ..descubrimiento import discover_servers
from ..energia import allow_sleep, prevent_sleep
from .ventana import Ventana


def _servidor_local_activo() -> bool:
    """¿Está el servidor corriendo en este mismo PC? (cuando se prueba todo en un solo equipo)"""
    try:
        with socket.create_connection(("127.0.0.1", PUERTO_POR_DEFECTO), timeout=1):
            return True
    except OSError:
        return False


def _configurar_primera_vez(config: ConfigCliente, ruta) -> bool:
    """Si la app no trae el servidor ya configurado, lo busca en la red (o en este mismo PC)."""
    cambios = False
    if not config.remote_server_url:
        encontrados = discover_servers(timeout=3.0)
        if encontrados:
            s = encontrados[0]
            config.remote_server_url = f"ws://{s['host']}:{s['port']}"
        elif _servidor_local_activo():
            config.remote_server_url = f"ws://127.0.0.1:{PUERTO_POR_DEFECTO}"
        else:
            url, ok = QInputDialog.getText(
                None, "Profesora de Inglés",
                "No encontré el computador de la profesora en la red.\n"
                "¿Está prendido y con el servidor abierto?\n\n"
                "Si sabes su dirección, escríbela (ej: ws://192.168.1.50:8770):")
            if not ok or not url.strip():
                return False
            config.remote_server_url = url.strip()
        cambios = True
    if cambios:
        config.guardar(ruta)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Profesora de Inglés (app de la alumna)")
    parser.add_argument("--config", default=None)
    args = parser.parse_args()

    preparar_datos_usuario()
    (RAIZ / "logs").mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                        handlers=[logging.FileHandler(RAIZ / "logs" / "cliente.log", encoding="utf-8")])

    app = QApplication(sys.argv)
    app.setApplicationName("Profesora de Inglés")
    ruta = args.config or ConfigCliente.ruta_por_defecto()
    config = ConfigCliente.cargar(ruta)
    if not _configurar_primera_vez(config, ruta):
        QMessageBox.information(None, "Profesora de Inglés", "Sin la conexión configurada no puedo abrir la clase.")
        return

    ventana = Ventana(config)
    ventana.conexion.al_nueva_direccion = lambda url: config.guardar(ruta)
    ventana.show()
    ventana.conexion.iniciar()
    prevent_sleep()  # que la laptop no se suspenda en medio de una clase
    try:
        app.exec()
    finally:
        allow_sleep()


if __name__ == "__main__":
    main()
