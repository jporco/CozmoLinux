"""Keepalive de rádio Wi-Fi — mantém o link com o Cozmo sempre quente.

O rádio (PC e/ou AP do Cozmo) entra em power-save com tráfego esparso: a latência
sobe de <1ms para 300-460ms e os frames de animação (30fps) passam a ser entregues
em rajada, estourando o buffer do firmware do robô → tela COZMO 01.

Em alguns firmwares/modos de base o tráfego UDP extra também pode provocar perda
de sessão e retorno para COZMO 01. Por isso este recurso é opt-in: só liga com
COZMO_RADIO_KEEPALIVE=1. O caminho padrão mantém apenas o fluxo OLED/pycozmo.
"""

from __future__ import annotations

import logging
import os
import socket
import threading
import time

logger = logging.getLogger("cozmo.radio")

_thread: threading.Thread | None = None
_stop = threading.Event()


def keepalive_ativo() -> bool:
    try:
        from cozmo_companion.core.motor_cozmo import base_oled_stable_only

        if base_oled_stable_only() and os.environ.get(
            "COZMO_STABLE_RADIO_KEEPALIVE",
            "0",
        ) != "1":
            return False
    except Exception:
        pass
    return os.environ.get("COZMO_RADIO_KEEPALIVE", "0") == "1"


def _loop(ip: str, porta: int, intervalo: float) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(False)
    pkt = b"\x00"
    try:
        while not _stop.is_set():
            try:
                sock.sendto(pkt, (ip, porta))
            except OSError:
                pass
            _stop.wait(intervalo)
    finally:
        sock.close()


def iniciar_keepalive_radio() -> bool:
    """Liga o keepalive (idempotente). True se ativo após a chamada."""
    global _thread
    if not keepalive_ativo():
        return False
    if _thread is not None and _thread.is_alive():
        return True
    ip = os.environ.get("COZMO_IP", "172.31.1.1")
    porta = int(os.environ.get("COZMO_RADIO_KEEPALIVE_PORT", "55001"))
    hz = float(os.environ.get("COZMO_RADIO_KEEPALIVE_HZ", "50"))
    hz = max(1.0, min(200.0, hz))
    intervalo = 1.0 / hz
    _stop.clear()
    _thread = threading.Thread(
        target=_loop,
        args=(ip, porta, intervalo),
        daemon=True,
        name="radio-keepalive",
    )
    _thread.start()
    logger.info(
        "Keepalive de rádio ON (%s:%d @ %.0fHz) — link quente, sem rajada/COZMO 01",
        ip,
        porta,
        hz,
    )
    return True


def parar_keepalive_radio() -> None:
    global _thread
    _stop.set()
    t = _thread
    if t is not None and t.is_alive():
        t.join(timeout=1.0)
    _thread = None
