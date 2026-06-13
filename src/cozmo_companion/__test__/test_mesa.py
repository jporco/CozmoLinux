"""Testes da navegação segura na mesa."""

import os
import unittest
from unittest import mock
from unittest.mock import MagicMock

from cozmo_companion.core.mesa import ExploradorMesa, MesaSegura, SensoresMesa, cliff_detectado


class TestMesa(unittest.TestCase):
    def test_sensores_zero_nao_disparam(self):
        cli = MagicMock()
        cli.robot_status = 0
        cli.robot_picked_up = False
        segura = MagicMock()
        segura._bloqueado = False
        segura.movimento_travado = lambda _cli: False
        s = SensoresMesa.__new__(SensoresMesa)
        s.cli = cli
        s._segura = segura
        s.cliff = [868, 0, 0, 0]
        s._baseline = [868, 0, 0, 0]
        s._amostras_chao = 5
        self.assertFalse(s.perigo_borda())

    def test_perigo_borda_baseline(self):
        cli = MagicMock()
        cli.robot_status = 0
        cli.robot_picked_up = False
        segura = MagicMock()
        segura._bloqueado = False
        segura.movimento_travado = lambda _cli: False
        s = SensoresMesa.__new__(SensoresMesa)
        s.cli = cli
        s._segura = segura
        s.cliff = [450, 460, 440, 455]
        s._baseline = [900, 900, 900, 900]
        s._amostras_chao = 5
        self.assertTrue(s.perigo_borda())

    def test_chao_ok(self):
        cli = MagicMock()
        cli.robot_status = 0
        segura = MagicMock()
        segura._bloqueado = False
        segura.movimento_travado = lambda _cli: False
        s = SensoresMesa.__new__(SensoresMesa)
        s.cli = cli
        s._segura = segura
        s.cliff = [850, 860, 840, 855]
        s._baseline = [900, 900, 900, 900]
        s._amostras_chao = 5
        self.assertFalse(s.perigo_borda())

    def test_colisao_parado_nao_dispara(self):
        cli = MagicMock()
        cli.robot_status = 0
        cli.robot_moving = True  # animação pode marcar moving
        cli.left_wheel_speed = MagicMock(mmps=0)
        cli.right_wheel_speed = MagicMock(mmps=0)
        cli.accel = MagicMock(x=2.0, y=1.0, z=9.8)
        segura = MesaSegura.__new__(MesaSegura)
        segura._bloqueado = False
        segura.cli = cli
        prev = (0.0, 0.0, 9.8)
        self.assertFalse(segura.colisao(prev))

    def test_explorador_parado_nao_recua(self):
        cli = MagicMock()
        cli.robot_status = 0
        cli.robot_picked_up = False
        cli.animation_groups = {}
        segura = MagicMock()
        segura._bloqueado = False
        segura.movimento_travado = lambda _cli: False
        segura.sensores = MagicMock()
        segura.sensores.perigo_borda.return_value = True
        segura.colisao.return_value = True
        segura.movimento_travado = lambda _cli: False
        exp = ExploradorMesa(segura)
        exp._estado = "off"
        exp.tick(cli)
        cli.drive_wheels.assert_not_called()

    def test_cliff_flag(self):
        from pycozmo import robot

        cli = MagicMock()
        cli.robot_status = robot.RobotStatusFlag.CLIFF_DETECTED
        self.assertTrue(cliff_detectado(cli))


    def test_modo_botao_mesa_no_contato(self):
        cli = MagicMock()
        cli.robot_status = 0
        cli.robot_picked_up = False
        segura = MesaSegura.__new__(MesaSegura)
        segura._bloqueado = False
        segura.cli = cli
        prev = os.environ.get("BASE_MODO_BOTAO")
        os.environ["BASE_MODO_BOTAO"] = "1"
        try:
            with mock.patch(
                "cozmo_companion.core.mesa.em_base", return_value=True
            ):
                self.assertFalse(segura.movimento_travado(cli))
        finally:
            if prev is None:
                os.environ.pop("BASE_MODO_BOTAO", None)
            else:
                os.environ["BASE_MODO_BOTAO"] = prev


if __name__ == "__main__":
    os.environ.setdefault("PYTHONPATH", "src")
    unittest.main()
