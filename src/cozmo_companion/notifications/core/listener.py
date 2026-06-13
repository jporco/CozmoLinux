"""Escuta notificações KDE via dbus-monitor (sem bloquear PyCozmo)."""

from __future__ import annotations

import logging
import re
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Callable

logger = logging.getLogger("cozmo.notif")

_STRING_RE = re.compile(r'^   string "(.*)"$')


@dataclass(frozen=True)
class Notificacao:
    app: str
    titulo: str
    corpo: str


def _unescape_dbus(raw: str) -> str:
    s = (
        raw.replace("\\n", " ")
        .replace("\\t", " ")
        .replace('\\"', '"')
        .replace("\\\\", "\\")
        .strip()
    )
    if "\\u" in s or "\\x" in s or "\\" in s:
        s = re.sub(
            r"\\u([0-9a-fA-F]{4})",
            lambda m: chr(int(m.group(1), 16)),
            s,
        )
        s = re.sub(
            r"\\x([0-9a-fA-F]{2})",
            lambda m: chr(int(m.group(1), 16)),
            s,
        )
    return s


def parse_strings_notify(strings: list[str]) -> Notificacao | None:
    """Ordem freedesktop: app, ícone, título, corpo."""
    if not strings:
        return None
    app = strings[0]
    if len(strings) >= 4:
        titulo, corpo = strings[2], strings[3]
    elif len(strings) == 3:
        titulo, corpo = strings[1], strings[2]
    elif len(strings) == 2:
        titulo, corpo = strings[1], ""
    else:
        titulo, corpo = "", ""
    return Notificacao(
        app=_unescape_dbus(app),
        titulo=_unescape_dbus(titulo),
        corpo=_unescape_dbus(corpo),
    )


class OuvinteNotificacoes:
    """Thread daemon — repassa Notify do Plasma para callback thread-safe."""

    def __init__(self, callback: Callable[[Notificacao], None]) -> None:
        self._callback = callback
        self._proc: subprocess.Popen[str] | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="NotifKDE"
        )
        self._thread.start()
        logger.info("Ouvinte KDE (Central de Notificações) ativo")

    def stop(self) -> None:
        self._stop.set()
        proc = self._proc
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                pass

    def _loop(self) -> None:
        filtro = (
            "type='method_call',interface='org.freedesktop.Notifications',"
            "member='Notify'"
        )
        while not self._stop.is_set():
            try:
                self._proc = subprocess.Popen(
                    ["dbus-monitor", "--session", filtro],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                )
                if self._proc.stdout:
                    self._ler(self._proc.stdout)
            except OSError as exc:
                logger.warning("dbus-monitor indisponível: %s", exc)
            finally:
                proc = self._proc
                if proc and proc.poll() is None:
                    try:
                        proc.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                if not self._stop.is_set():
                    time.sleep(3.0)

    def _ler(self, stdout) -> None:
        coletando = False
        strings: list[str] = []

        for line in stdout:
            if self._stop.is_set():
                break
            if "method call" in line and "member=Notify" in line:
                coletando = True
                strings = []
                continue
            if not coletando:
                continue

            stripped = line.strip()
            m = _STRING_RE.match(line.rstrip("\n"))
            if m:
                strings.append(m.group(1))
                continue
            if stripped.startswith("int32 -1") or (
                stripped.startswith("array [") and strings
            ):
                self._emitir(strings)
                coletando = False
                strings = []

    def _emitir(self, strings: list[str]) -> None:
        notif = parse_strings_notify(strings)
        if not notif:
            return
        logger.debug(
            "Notify KDE: app=%r titulo=%r",
            notif.app,
            (notif.titulo or "")[:40],
        )
        try:
            self._callback(notif)
        except Exception as exc:
            logger.debug("Callback notificação: %s", exc)
