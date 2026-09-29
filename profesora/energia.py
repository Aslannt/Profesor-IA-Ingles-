"""Evita que Windows se suspenda mientras hay una clase (tomado del Copiloto de Reuniones).
Se usa en los dos lados: en la laptop mientras la app está abierta, y en el PC mientras hay una
alumna conectada. Solo impide la suspensión del sistema, la pantalla sí se puede apagar.
Ojo: SetThreadExecutionState es por hilo; se debe llamar desde el hilo que dura toda la clase.
"""

from __future__ import annotations

import logging
import sys

logger = logging.getLogger(__name__)

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


def prevent_sleep() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
    except Exception:
        logger.exception("Could not prevent system sleep")


def allow_sleep() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
    except Exception:
        logger.exception("Could not restore normal sleep behavior")
