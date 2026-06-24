"""Testes — resolução de nome do app na notificação."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from cozmo_companion.notifications.core.apps import (
    nome_de_desktop,
    resolver_nome_app,
)
from cozmo_companion.notifications.core.listener import Notificacao


class TestNotifApps(unittest.TestCase):
    def test_desktop_telegram(self) -> None:
        nome = nome_de_desktop("org.telegram.desktop")
        if nome:
            self.assertIn("Telegram", nome)

    def test_resolver_por_icone(self) -> None:
        n = Notificacao(
            "Notificações Do Sistema",
            "firefox",
            "Nova aba",
            "corpo",
        )
        self.assertEqual(resolver_nome_app(n), "Firefox")

    def test_resolver_por_titulo(self) -> None:
        n = Notificacao("", "", "Discord — nova mensagem", "")
        self.assertEqual(resolver_nome_app(n), "Discord")

    def test_resolver_desconhecido(self) -> None:
        n = Notificacao("mensagem", "", "oi", "")
        self.assertEqual(resolver_nome_app(n), "???")


if __name__ == "__main__":
    unittest.main()
