"""KDE NotificationManager RegisterWatcher — OLED mesmo com DND/silenciado."""

from __future__ import annotations

import logging
import threading
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from cozmo_companion.notifications.core.listener import Notificacao

logger = logging.getLogger("cozmo.notif")

_BUS_NAME = "org.cozmo.CompanionNotifWatcher"
_WATCHER_PATH = "/NotificationWatcher"
_WATCHER_IFACE = "org.kde.NotificationWatcher"
_NOTIF_SERVICE = "org.freedesktop.Notifications"
_NOTIF_PATH = "/org/freedesktop/Notifications"
_MANAGER_IFACE = "org.kde.NotificationManager"

try:
    import dbus
    import dbus.service
    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository import GLib

    _DBUS_OK = True
except ImportError:
    _DBUS_OK = False


def kde_watcher_disponivel() -> bool:
    return _DBUS_OK


def notificacao_from_kde_watcher(
    app_name: str,
    app_icon: str,
    summary: str,
    body: str,
    hints: dict | None,
) -> "Notificacao":
    """Monta Notificacao a partir do Notify do RegisterWatcher."""
    from cozmo_companion.notifications.core.listener import Notificacao

    app = str(app_name or "")
    if hints:
        desktop = hints.get("desktop-entry") or hints.get("desktop_entry")
        if desktop:
            app = str(desktop)
    return Notificacao(
        app=app,
        icone=str(app_icon or ""),
        titulo=str(summary or ""),
        corpo=str(body or ""),
    )


if _DBUS_OK:

    class _NotificationWatcherObject(dbus.service.Object):
        def __init__(
            self,
            callback: Callable[["Notificacao"], None],
            bus_name: dbus.service.BusName,
        ) -> None:
            super().__init__(bus_name, _WATCHER_PATH)
            self._callback = callback

        @dbus.service.method(_WATCHER_IFACE, in_signature="ususssasa{sv}i")
        def Notify(
            self,
            _nid: int,
            app_name: str,
            _replaces_id: int,
            app_icon: str,
            summary: str,
            body: str,
            _actions: list,
            hints: dict,
            _expire_timeout: int,
        ) -> None:
            hints_map = {str(k): v for k, v in (hints or {}).items()}
            notif = notificacao_from_kde_watcher(
                app_name, app_icon, summary, body, hints_map
            )
            logger.debug(
                "RegisterWatcher: app=%r titulo=%r",
                notif.app,
                (notif.titulo or "")[:40],
            )
            try:
                self._callback(notif)
            except Exception as exc:
                logger.debug("Callback RegisterWatcher: %s", exc)

        @dbus.service.method(_WATCHER_IFACE, in_signature="u")
        def CloseNotification(self, _nid: int) -> None:
            pass


    class OuvinteKdeWatcher:
        """Thread daemon — RegisterWatcher do Plasma (independe de DND/som KDE)."""

        def __init__(self, callback: Callable[["Notificacao"], None]) -> None:
            self._callback = callback
            self._thread: threading.Thread | None = None
            self._stop = threading.Event()
            self._ready = threading.Event()
            self._success = False
            self._loop: GLib.MainLoop | None = None
            self._bus: dbus.SessionBus | None = None
            self._bus_name: dbus.service.BusName | None = None
            self._watcher: _NotificationWatcherObject | None = None

        @property
        def ativo(self) -> bool:
            return (
                self._success
                and self._thread is not None
                and self._thread.is_alive()
            )

        def start(self) -> bool:
            if self._thread and self._thread.is_alive():
                return self._success
            self._stop.clear()
            self._ready.clear()
            self._success = False
            self._thread = threading.Thread(
                target=self._run,
                daemon=True,
                name="NotifKDE-Watcher",
            )
            self._thread.start()
            if not self._ready.wait(timeout=5.0):
                logger.warning("RegisterWatcher: timeout ao iniciar")
                self.stop()
                return False
            return self._success

        def stop(self) -> None:
            self._stop.set()
            loop = self._loop
            if loop is not None:
                loop.quit()
            bus = self._bus
            if bus is not None:
                try:
                    proxy = bus.get_object(_NOTIF_SERVICE, _NOTIF_PATH)
                    iface = dbus.Interface(proxy, _MANAGER_IFACE)
                    iface.UnRegisterWatcher()
                except Exception:
                    pass
            thread = self._thread
            if (
                thread
                and thread.is_alive()
                and thread is not threading.current_thread()
            ):
                thread.join(timeout=2.0)

        def _run(self) -> None:
            try:
                DBusGMainLoop(set_as_default=True)
                self._bus = dbus.SessionBus()
                self._bus_name = dbus.service.BusName(_BUS_NAME, bus=self._bus)
                self._watcher = _NotificationWatcherObject(
                    self._callback, self._bus_name
                )
                proxy = self._bus.get_object(_NOTIF_SERVICE, _NOTIF_PATH)
                iface = dbus.Interface(proxy, _MANAGER_IFACE)
                iface.RegisterWatcher()
                self._success = True
                logger.info(
                    "KDE RegisterWatcher ativo — OLED mesmo com notificações silenciadas"
                )
            except Exception as exc:
                self._success = False
                logger.warning("RegisterWatcher indisponível (%s)", exc)
                self._ready.set()
                return

            self._ready.set()
            self._loop = GLib.MainLoop()
            GLib.timeout_add(400, self._poll_stop)
            try:
                self._loop.run()
            finally:
                self._success = False

        def _poll_stop(self) -> bool:
            if self._stop.is_set():
                if self._loop is not None:
                    self._loop.quit()
                return False
            return True

else:

    class OuvinteKdeWatcher:  # type: ignore[no-redef]
        def __init__(self, callback: Callable[["Notificacao"], None]) -> None:
            self._callback = callback

        @property
        def ativo(self) -> bool:
            return False

        def start(self) -> bool:
            return False

        def stop(self) -> None:
            pass
