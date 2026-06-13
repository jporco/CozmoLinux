"""OLED na base: TX direto (≠ fila AnimationController)."""
from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch


class TestOledTxDireto(unittest.TestCase):
    def test_keeper_usa_conn_send(self) -> None:
        from cozmo_companion.core import motor_cozmo as mc

        cli = MagicMock()
        pkt = MagicMock()
        with patch.dict(os.environ, {"COZMO_OLED_DIRECT": "0"}, clear=False):
            with patch.object(mc, "keeper_base_ativo", return_value=True):
                with patch.object(mc, "_charger_keeper_ativo", False):
                    mc.enviar_oled(cli, pkt)
        cli.conn.send.assert_called_with(pkt)
        cli.anim_controller.display_image.assert_not_called()


if __name__ == "__main__":
    unittest.main()
