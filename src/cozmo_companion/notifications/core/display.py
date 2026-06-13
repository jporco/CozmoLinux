"""Texto OLED para notificações — só nome do app (dbus app_name)."""

from __future__ import annotations

import os

from cozmo_companion.notifications.core.listener import Notificacao
from cozmo_companion.notifications.core.policy import max_oled_chars, nome_app_oled


def linhas_oled_notif(notif: Notificacao) -> tuple[str, str | None]:
    """(nome do app, None) — sem título/corpo na OLED."""
    return nome_app_oled(notif), None


def texto_oled_combinado(notif: Notificacao) -> str:
    """Uma linha: apenas o app."""
    return nome_app_oled(notif)


def segundos_tela_notif(*, duas_linhas: bool) -> tuple[float, float]:
    """(seg app, seg título) — NOTIF_OLED_APP_S se uma tela."""
    if not duas_linhas:
        app_s = float(
            os.environ.get(
                "NOTIF_OLED_APP_S",
                os.environ.get("NOTIF_TELA_S", "4"),
            )
        )
        return app_s, 0.0
    total = float(os.environ.get("NOTIF_TELA_S", "4"))
    app_s = float(os.environ.get("NOTIF_OLED_APP_S", "3"))
    tit_s = float(os.environ.get("NOTIF_OLED_TITULO_S", str(max(2.0, total - app_s))))
    return app_s, tit_s
