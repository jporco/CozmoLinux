"""Toggle botão BASE↔MESA — fila, OLED curto, sem tela estática longa."""

from __future__ import annotations

import os
import time
import unittest
from unittest.mock import MagicMock, patch

from cozmo_companion.core.charger import BaseGuard, modo_botao
from cozmo_companion.core.companion import Companion
from cozmo_companion.core.fila_cozmo import FilaCozmo


class TestToggleBotao(unittest.TestCase):
    def test_modo_botao_ativo(self):
        with patch.dict(os.environ, {"BASE_MODO_BOTAO": "1"}):
            self.assertTrue(modo_botao())

    def test_fila_vazia_inicial(self):
        gov = MagicMock()
        fila = FilaCozmo(
            gov,
            tocar_grupo=MagicMock(),
            mostrar_oled=MagicMock(),
            executar_sinal=MagicMock(return_value=True),
            executar_som=MagicMock(return_value=True),
            na_base=lambda: True,
            usa_procedural=lambda: True,
        )
        self.assertTrue(fila.vazia)

    def test_alternar_nao_dispara_explorador_no_carregador(self):
        g = BaseGuard()
        cli = MagicMock()
        cli.robot_status = 0x1000
        cli.battery_voltage = 4.0
        cli.robot_moving = False
        cli.robot_picked_up = False
        cli.left_wheel_speed = MagicMock(mmps=0)
        cli.right_wheel_speed = MagicMock(mmps=0)
        prev = os.environ.get("BASE_MODO_BOTAO")
        os.environ["BASE_MODO_BOTAO"] = "1"
        try:
            g._preso_na_base = True
            g._ultimo_toggle_botao = 0.0
            g.alternar_modo_botao(cli)
            self.assertTrue(g.preso_na_base)
            self.assertTrue(g._mesa_escolhida)
        finally:
            if prev is None:
                os.environ.pop("BASE_MODO_BOTAO", None)
            else:
                os.environ["BASE_MODO_BOTAO"] = prev

    def test_quieto_base_anim_so_pos_reconnect(self):
        app = MagicMock(spec=Companion)
        app._pos_tts_ativo = lambda: False
        app._ultimo_reconnect_udp = time.monotonic() - 5.0
        with patch.dict(os.environ, {"COZMO_POST_RECONNECT_S": "22"}):
            quieto = Companion._quieto_base_anim(app)
        self.assertTrue(quieto)
        app._ultimo_reconnect_udp = time.monotonic() - 30.0
        with patch.dict(os.environ, {"COZMO_POST_RECONNECT_S": "22"}):
            quieto2 = Companion._quieto_base_anim(app)
        self.assertFalse(quieto2)


if __name__ == "__main__":
    unittest.main()
