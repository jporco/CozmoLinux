"""Testes — OLED / marquee."""

from __future__ import annotations

import unittest

from cozmo_companion.display.face import _fonte, janelas_scroll, texto_para_pkt
from cozmo_companion.notifications.core.listener import _unescape_dbus


class TestDisplay(unittest.TestCase):
    def test_janelas_curtas(self) -> None:
        self.assertEqual(janelas_scroll("Oi"), ("Oi",))

    def test_janelas_longas(self) -> None:
        texto = "Notificacoes Do Sistema: alerta importante"
        fatias = janelas_scroll(texto)
        self.assertGreater(len(fatias), 1)
        self.assertTrue(all(len(f) <= 16 for f in fatias))

    def test_unicode_acentos_render(self) -> None:
        pkt = texto_para_pkt("Ação çã")
        self.assertIsNotNone(pkt)
        self.assertGreater(len(bytes(pkt.image)), 100)

    def test_fonte_nao_default(self) -> None:
        f = _fonte()
        self.assertNotEqual(type(f).__name__, "ImageFont")

    def test_unescape_dbus_unicode(self) -> None:
        self.assertEqual(_unescape_dbus("Notifica\\u00e7\\u00e3o"), "Notificação")
        self.assertEqual(_unescape_dbus("A\\xe7\\xe3o"), "Ação")

    def test_mostrar_guarda_mensagem_ativa(self) -> None:
        from unittest.mock import MagicMock

        from cozmo_companion.display.face import Tela

        t = Tela(MagicMock())
        t.mostrar("Primeira", segundos=10.0)
        t.mostrar("Segunda", segundos=5.0)
        self.assertEqual(t._texto_atual, "Primeira")

    def test_mostrar_forcado_substitui(self) -> None:
        from unittest.mock import MagicMock

        from cozmo_companion.display.face import Tela

        t = Tela(MagicMock())
        t.mostrar("Primeira", segundos=10.0)
        t.mostrar("Segunda", segundos=5.0, forcado=True)
        self.assertEqual(t._texto_atual, "Segunda")

    def test_ocupada(self) -> None:
        from unittest.mock import MagicMock
        import time

        from cozmo_companion.display.face import Tela

        t = Tela(MagicMock())
        self.assertFalse(t.ocupada())
        t.mostrar("Oi", segundos=10.0)
        self.assertTrue(t.ocupada())

    def test_envia_via_burst_manual(self) -> None:
        from unittest.mock import MagicMock, patch

        from cozmo_companion.display.face import Tela

        cli = MagicMock()
        t = Tela(cli)
        with patch(
            "cozmo_companion.core.motor_cozmo._oled_tx_direto",
            return_value=False,
        ):
            with patch(
                "cozmo_companion.core.motor_cozmo._burst_oled_display_image"
            ) as burst:
                with patch.dict(
                    "os.environ",
                    {
                        "COZMO_OLED_DIRECT": "0",
                        "COZMO_BASE_OLED_MODE": "anim",
                        "COZMO_BASE_PULSE_PROC": "0",
                        "COZMO_BASE_KEEPER_VIVO": "0",
                    },
                ):
                    t.mostrar("Teste", segundos=8.0)
        burst.assert_called()
        cli.anim_controller.display_image.assert_not_called()
        cli.conn.send.assert_not_called()

    def test_prioridade_bloqueia_baixa(self) -> None:
        from unittest.mock import MagicMock

        from cozmo_companion.display.face import Tela

        t = Tela(MagicMock())
        t.mostrar("Sono", segundos=10.0, prioridade="sono")
        t.mostrar("Notif", segundos=5.0, prioridade="notif")
        self.assertEqual(t._texto_atual, "Sono")


if __name__ == "__main__":
    unittest.main()
