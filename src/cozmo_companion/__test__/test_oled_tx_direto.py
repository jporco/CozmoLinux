"""OLED: envio direto só como fallback explícito."""
from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch


class TestOledTxDireto(unittest.TestCase):
    def test_keeper_usa_burst_oled_por_padrao(self) -> None:
        from cozmo_companion.core import motor_cozmo as mc

        cli = MagicMock()
        pkt = MagicMock()
        with patch.dict(os.environ, {"COZMO_OLED_DIRECT": "0"}, clear=False):
            with patch.object(mc, "keeper_base_ativo", return_value=True):
                with patch.object(mc, "_charger_keeper_ativo", False):
                    with patch.object(mc, "_burst_oled_display_image") as burst:
                        mc.enviar_oled(cli, pkt)
        burst.assert_called_once_with(cli, pkt)
        cli.conn.send.assert_not_called()

    def test_envio_direto_so_com_flag_explicita_fora_base_estavel(self) -> None:
        from cozmo_companion.core import motor_cozmo as mc

        cli = MagicMock()
        pkt = MagicMock()
        with patch.dict(os.environ, {"COZMO_OLED_DIRECT": "1"}, clear=False):
            with patch.object(mc, "base_oled_stable_only", return_value=False):
                mc.enviar_oled(cli, pkt)
        cli.conn.send.assert_called_with(pkt)
        cli.anim_controller.display_image.assert_not_called()

    def test_base_estavel_ignora_envio_direto_e_usa_burst(self) -> None:
        from cozmo_companion.core import motor_cozmo as mc

        cli = MagicMock()
        pkt = MagicMock()
        with patch.dict(os.environ, {"COZMO_OLED_DIRECT": "1"}, clear=False):
            with patch.object(mc, "base_oled_stable_only", return_value=True):
                with patch.object(mc, "_burst_oled_display_image") as burst:
                    mc.enviar_oled(cli, pkt)
        burst.assert_called_once_with(cli, pkt)
        cli.conn.send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
