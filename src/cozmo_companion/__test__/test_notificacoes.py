"""Testes — notificações KDE."""

from __future__ import annotations

import os
import time
import unittest
from unittest.mock import patch

from cozmo_companion.notifications.core.listener import (
    Notificacao,
    parse_strings_notify,
)
from cozmo_companion.notifications.core.listener_kde_watcher import (
    notificacao_from_kde_watcher,
)
from cozmo_companion.notifications.core.policy import (
    ContextoNotif,
    deve_processar,
    nome_app_oled,
    texto_scroll,
    texto_tela,
    texto_trecho,
)


class TestNotificacoes(unittest.TestCase):
    def test_parse_strings_padrao(self) -> None:
        n = parse_strings_notify(["Discord", "", "Nova msg", "Oi porco"])
        assert n is not None
        self.assertEqual(n.app, "Discord")
        self.assertEqual(n.titulo, "Nova msg")

    def test_kde_watcher_desktop_entry(self) -> None:
        n = notificacao_from_kde_watcher(
            "Discord",
            "discord",
            "Ping",
            "corpo",
            {"desktop-entry": "org.telegram.desktop"},
        )
        self.assertEqual(n.app, "org.telegram.desktop")
        self.assertEqual(n.icone, "discord")
        self.assertEqual(n.titulo, "Ping")

    def test_texto_tela_app(self) -> None:
        n = Notificacao("org.telegram.desktop", "", "Chat", "")
        self.assertEqual(texto_tela(n), "Telegram")

    def test_texto_tela_sem_app_nao_usa_titulo(self) -> None:
        n = Notificacao("", "", "Alerta curto", "")
        self.assertEqual(texto_tela(n), "???")

    def test_texto_tela_titulo_com_app_conhecido(self) -> None:
        n = Notificacao("", "", "Alerta GW2", "")
        self.assertEqual(texto_tela(n), "GW2")

    def test_nome_app_notificacoes_do_sistema(self) -> None:
        n = Notificacao("Notificações Do Sistema", "", "titulo", "corpo")
        self.assertEqual(nome_app_oled(n), "???")

    def test_nome_app_kde_plasma_notifications(self) -> None:
        n = Notificacao("org.kde.plasma.notifications", "", "x", "y")
        self.assertEqual(nome_app_oled(n), "???")

    def test_nome_app_remove_prefixo_notificacao(self) -> None:
        n = Notificacao("notificação de Discord", "", "Nova mensagem", "corpo")
        self.assertEqual(nome_app_oled(n), "Discord")

    def test_nome_app_rejeita_mensagem_generica(self) -> None:
        n = Notificacao("mensagem", "", "titulo", "corpo")
        self.assertEqual(nome_app_oled(n), "???")

    def test_deve_processar_cooldown(self) -> None:
        ctx = ContextoNotif(
            falando=False,
            llm_ocupado=False,
            modo_udp_leve=False,
            na_base=True,
            carregando=False,
            ultima_em=time.monotonic(),
            agora=time.monotonic(),
            ultima_app="discord",
            ultima_titulo="Ping",
        )
        n = Notificacao("Discord", "", "Ping", "")
        with patch.dict(os.environ, {"NOTIF_ENABLED": "1", "NOTIF_COOLDOWN_S": "30"}):
            self.assertFalse(deve_processar(n, ctx))

    def test_deve_processar_repete_app_titulo_diferente(self) -> None:
        ctx = ContextoNotif(
            falando=False,
            llm_ocupado=False,
            modo_udp_leve=False,
            na_base=True,
            carregando=False,
            ultima_em=time.monotonic(),
            agora=time.monotonic(),
            ultima_app="discord",
            ultima_titulo="Ping",
        )
        n = Notificacao("Discord", "", "Nova msg", "")
        with patch.dict(os.environ, {"NOTIF_ENABLED": "1", "NOTIF_COOLDOWN_S": "30"}):
            self.assertTrue(deve_processar(n, ctx))

    def test_cursor_nao_ignorado_por_padrao(self) -> None:
        ctx = ContextoNotif(
            falando=False,
            llm_ocupado=False,
            modo_udp_leve=False,
            na_base=True,
            carregando=True,
            ultima_em=0.0,
            agora=time.monotonic(),
        )
        n = Notificacao("cursor", "", "Update pronto", "")
        with patch.dict(
            os.environ,
            {
                "NOTIF_ENABLED": "1",
                "NOTIF_IGNORE_APPS": "plasmashell,kded6",
            },
        ):
            self.assertTrue(deve_processar(n, ctx))

    def test_ignora_plasma(self) -> None:
        ctx = ContextoNotif(
            falando=False,
            llm_ocupado=False,
            modo_udp_leve=False,
            na_base=False,
            carregando=False,
            ultima_em=0.0,
            agora=time.monotonic(),
        )
        n = Notificacao("plasmashell", "", "x", "")
        with patch.dict(os.environ, {"NOTIF_ENABLED": "1"}):
            self.assertFalse(deve_processar(n, ctx))

    def test_texto_trecho_so_app(self) -> None:
        n = Notificacao("Discord", "", "Nova mensagem no servidor", "corpo longo ignorado")
        self.assertEqual(texto_trecho(n), "Discord")

    def test_texto_trecho_sem_app(self) -> None:
        n = Notificacao("mensagem", "", "", "Alerta curto")
        self.assertEqual(texto_trecho(n), "???")

    def test_texto_scroll_so_app(self) -> None:
        n = Notificacao(
            "org.kde.dolphin",
            "",
            "Arquivo copiado com sucesso para pasta",
            "detalhes extras",
        )
        self.assertEqual(texto_scroll(n), "Arquivos")

    def test_linhas_oled_so_app(self) -> None:
        from cozmo_companion.notifications.core.display import linhas_oled_notif

        n = Notificacao("Steam", "", "Update disponível", "baixando…")
        with patch.dict(os.environ, {"NOTIF_OLED_DUPLO": "0"}):
            app, tit = linhas_oled_notif(n)
        self.assertEqual(app, "Steam")
        self.assertIsNone(tit)

    def test_permitido_quando_ativo(self) -> None:
        ctx = ContextoNotif(
            falando=False,
            llm_ocupado=False,
            modo_udp_leve=False,
            na_base=True,
            carregando=True,
            ultima_em=0.0,
            agora=time.monotonic(),
        )
        n = Notificacao("Firefox", "", "Nova aba", "")
        with patch.dict(os.environ, {"NOTIF_ENABLED": "1", "NOTIF_NA_BASE": "1"}):
            self.assertTrue(deve_processar(n, ctx))


if __name__ == "__main__":
    unittest.main()
