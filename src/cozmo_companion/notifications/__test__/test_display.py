"""Testes — texto OLED de notificações."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from cozmo_companion.notifications.core.display import (
    linhas_oled_notif,
    segundos_tela_notif,
    texto_oled_combinado,
)
from cozmo_companion.notifications.core.listener import Notificacao


class TestNotifDisplay(unittest.TestCase):
    def test_linhas_so_app_padrao(self) -> None:
        n = Notificacao("Discord", "Nova mensagem", "corpo")
        with patch.dict(os.environ, {"NOTIF_OLED_DUPLO": "0"}):
            app, tit = linhas_oled_notif(n)
        self.assertEqual(app, "Discord")
        self.assertIsNone(tit)

    def test_linhas_nunca_titulo(self) -> None:
        n = Notificacao("Discord", "Nova mensagem", "corpo")
        with patch.dict(
            os.environ,
            {"NOTIF_OLED_DUPLO": "1", "NOTIF_TRECHO_TITULO": "1"},
        ):
            app, tit = linhas_oled_notif(n)
        self.assertEqual(app, "Discord")
        self.assertIsNone(tit)

    def test_combinado_so_app(self) -> None:
        n = Notificacao("Steam", "Update disponível", "")
        self.assertEqual(texto_oled_combinado(n), "Steam")

    def test_segundos_duas_linhas(self) -> None:
        with patch.dict(
            os.environ,
            {
                "NOTIF_OLED_APP_S": "5",
                "NOTIF_OLED_TITULO_S": "3",
                "NOTIF_TELA_S": "5",
            },
        ):
            a, b = segundos_tela_notif(duas_linhas=True)
        self.assertEqual(a, 5.0)
        self.assertEqual(b, 3.0)

    def test_segundos_uma_linha(self) -> None:
        with patch.dict(os.environ, {"NOTIF_OLED_APP_S": "4", "NOTIF_TELA_S": "5"}):
            a, b = segundos_tela_notif(duas_linhas=False)
        self.assertEqual(a, 4.0)
        self.assertEqual(b, 0.0)


if __name__ == "__main__":
    unittest.main()
