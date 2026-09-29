"""Arranque de la app de la laptop:  python -m profesora.cliente [--config ruta]"""
from __future__ import annotations

import argparse
import logging
import sys

from PySide6.QtWidgets import QApplication, QInputDialog, QLineEdit, QMessageBox

from ..config import RAIZ, ConfigCliente, preparar_datos_usuario
from ..descubrimiento import discover_servers
from ..energia import allow_sleep, prevent_sleep
from .ventana import Ventana


def _configurar_primera_vez(config: ConfigCliente, ruta) -> bool:
    """Si la app no trae el servidor ya configurado, lo busca en la red y pide la clave."""
    cambios = False
    if not config.remote_server_url:
        encontrados = discover_servers(timeout=3.0)
        if encontrados:
            s = encontrados[0]
            config.remote_server_url = f"ws://{s['host']}:{s['port']}"
            cambios = True
        else:
            url, ok = QInputDialog.getText(
                None, "Profesora de Inglés",
                "No encontré el computador de la profesora en la red.\n"
                "Escribe su dirección (ej: ws://192.168.1.50:8770):")
            if not ok or not url.strip():
                return False
            config.remote_server_url = url.strip()
            cambios = True
    if not config.remote_token:
        token, ok = QInputDialog.getText(None, "Profesora de Inglés", "Clave de conexión (te la da Deivid):",
                                         QLineEdit.Password)
        if not ok or not token.strip():
            return False
        config.remote_token = token.strip()
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
