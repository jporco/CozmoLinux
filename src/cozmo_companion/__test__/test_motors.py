"""Testes do watchdog de motores."""

import os
import unittest
from unittest.mock import MagicMock

from cozmo_companion.core.motors import MotorWatchdog


class TestMotors(unittest.TestCase):
    def test_para_rodas_orfas(self):
        wd = MotorWatchdog()
        cli = MagicMock()
        cli.robot_picked_up = False
        cli.robot_moving = True
        cli.left_wheel_speed = MagicMock(mmps=20)
        cli.right_wheel_speed = MagicMock(mmps=20)

        wd.tick(cli, na_base=False, movimento_permitido=False)
        wd._desde = 0.0
        import time

        wd._desde = time.monotonic() - 5.0
        wd.tick(cli, na_base=False, movimento_permitido=False)
        cli.stop_all_motors.assert_called()

    def test_mesa_modo_botao_para_no_contato(self):
        """No carregador: rodas sempre param (fica na base carregando)."""
        wd = MotorWatchdog()
        cli = MagicMock()
        cli.robot_picked_up = False
        cli.robot_moving = True
        cli.left_wheel_speed = MagicMock(mmps=20)
        cli.right_wheel_speed = MagicMock(mmps=20)
        prev = os.environ.get("BASE_MODO_BOTAO")
        os.environ["BASE_MODO_BOTAO"] = "1"
        try:
            with unittest.mock.patch(
                "cozmo_companion.core.motors.em_base", return_value=True
            ):
                wd.tick(cli, na_base=True, movimento_permitido=True)
            cli.stop_all_motors.assert_called()
        finally:
            if prev is None:
                os.environ.pop("BASE_MODO_BOTAO", None)
            else:
                os.environ["BASE_MODO_BOTAO"] = prev


if __name__ == "__main__":
    os.environ.setdefault("PYTHONPATH", "src")
    unittest.main()
