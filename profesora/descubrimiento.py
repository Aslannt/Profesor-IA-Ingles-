"""Descubrimiento en la red local (tomado del Copiloto de Reuniones): la app de la laptop
encuentra el PC servidor sin escribir la IP a mano. Es un intercambio UDP aparte y solo
responde dentro de la red de la casa (el firewall solo abre el puerto en redes privadas).
"""

from __future__ import annotations

import json
import logging
import socket
import threading
import time

DISCOVERY_PORT = 8771  # el Copiloto usa 8766
DISCOVERY_MAGIC = "PROFESORA_INGLES_DISCOVER_V1"
REPLY_MAGIC = "PROFESORA_INGLES_HERE_V1"

logger = logging.getLogger(__name__)


def run_discovery_responder(ws_port: int, stop_event: threading.Event) -> None:
    """Server side: listens for discovery broadcasts and replies with this
    machine's hostname and websocket port. Meant to run in a daemon thread
    for the lifetime of the server process."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", DISCOVERY_PORT))
        sock.settimeout(0.5)
    except OSError as exc:
        logger.warning("Could not start LAN discovery responder: %s", exc)
        return

    hostname = socket.gethostname()
    with sock:
        while not stop_event.is_set():
            try:
                data, addr = sock.recvfrom(1024)
            except socket.timeout:
                continue
            except OSError:
                return
            if data.decode("utf-8", errors="ignore").strip() != DISCOVERY_MAGIC:
                continue
            reply = json.dumps({"magic": REPLY_MAGIC, "name": hostname, "port": ws_port})
            try:
                sock.sendto(reply.encode("utf-8"), addr)
            except OSError:
                pass


def discover_servers(timeout: float = 2.0) -> list[dict]:
    """Client side: broadcasts a discovery request and collects replies for
    `timeout` seconds. Returns a list of {"host", "port", "name"} dicts,
    one per responding server (deduplicated by host)."""
    found: dict[str, dict] = {}
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(0.3)
    except OSError as exc:
        logger.warning("Could not start LAN discovery: %s", exc)
        return []

    with sock:
        try:
            sock.sendto(DISCOVERY_MAGIC.encode("utf-8"), ("255.255.255.255", DISCOVERY_PORT))
        except OSError as exc:
            logger.warning("Could not send discovery broadcast: %s", exc)
            return []

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                data, addr = sock.recvfrom(1024)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                payload = json.loads(data.decode("utf-8"))
            except Exception:
                continue
            if payload.get("magic") != REPLY_MAGIC:
                continue
            host = addr[0]
            found[host] = {"host": host, "port": payload.get("port"), "name": payload.get("name", host)}

    return list(found.values())
