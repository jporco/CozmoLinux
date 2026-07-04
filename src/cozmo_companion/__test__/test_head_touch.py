"""Testes de detecção de carinho na cabeça."""

import os
import unittest
from unittest.mock import MagicMock, patch

from cozmo_companion.core.head_touch import HeadPetDetector


class TestHeadPet(unittest.TestCase):
    def test_dedo_na_base_dispara_por_angulo_sem_exigir_accel(self):
        chamadas = []
        det = HeadPetDetector(lambda: chamadas.append(1))
        cli = MagicMock(robot_picked_up=False)
        cli.head_angle.radians = 0.2
        cli.accel.x, cli.accel.y, cli.accel.z = 0.0, 0.0, 9.8
        with patch.dict(
            os.environ,
            {
                "CARINHO_BASE_AND": "0",
                "CARINHO_BASE_ANG_MULT": "2.0",
                "CARINHO_COOLDOWN_S": "0",
            },
        ):
            det.update(cli, preso_na_base=True)
            cli.head_angle.radians = 0.34
            det.update(cli, preso_na_base=True)
        self.assertEqual(chamadas, [1])

    def test_head_pet_na_base(self):
        chamadas = []
        det = HeadPetDetector(lambda: chamadas.append(1))
        cli = MagicMock()
        cli.robot_picked_up = False
        cli.robot_status = 0x1000
        cli.head_angle.radians = 0.5
        cli.accel.x, cli.accel.y, cli.accel.z = 0, 0, 1
        det.update(cli, preso_na_base=True, em_sono=False)
        cli.head_angle.radians = 0.55
        det.update(cli, preso_na_base=True, em_sono=False)
        self.assertEqual(chamadas, [])

    def test_toque_acorda_dormindo(self):
        chamadas = []
        det = HeadPetDetector(lambda: chamadas.append(1))
        cli = MagicMock()
        cli.robot_picked_up = False
        cli.head_angle.radians = 0.2
        cli.accel.x, cli.accel.y, cli.accel.z = 0.0, 0.0, 9.8
        det.update(cli, preso_na_base=True, em_sono=True)
        cli.accel.x, cli.accel.y, cli.accel.z = 0.5, 0.3, 9.2
        det.update(cli, preso_na_base=True, em_sono=True)
        self.assertEqual(chamadas, [1])

    def test_anim_base_nao_dispara_carinho(self):
        chamadas = []
        det = HeadPetDetector(lambda: chamadas.append(1))
        cli = MagicMock()
        cli.robot_picked_up = False
        cli.head_angle.radians = 0.2
        cli.accel.x, cli.accel.y, cli.accel.z = 0.0, 0.0, 9.8
        det.update(cli, preso_na_base=True, cabeca_externa=True)
        cli.head_angle.radians = 0.35
        cli.accel.x = 0.5
        det.update(cli, preso_na_base=True, cabeca_externa=True)
        self.assertEqual(chamadas, [])

    def test_base_exige_angulo_e_accel(self):
        chamadas = []
        det = HeadPetDetector(lambda: chamadas.append(1))
        cli = MagicMock()
        cli.robot_picked_up = False
        cli.head_angle.radians = 0.2
        cli.accel.x, cli.accel.y, cli.accel.z = 0.0, 0.0, 9.8
        with patch.dict(os.environ, {"CARINHO_BASE_AND": "1", "CARINHO_COOLDOWN_S": "0"}):
            det.update(cli, preso_na_base=True, em_sono=False)
            cli.head_angle.radians = 0.5
            det.update(cli, preso_na_base=True, em_sono=False)
        self.assertEqual(chamadas, [])
        with patch.dict(os.environ, {"CARINHO_BASE_AND": "1", "CARINHO_COOLDOWN_S": "0"}):
            cli.head_angle.radians = 0.2
            cli.accel.x, cli.accel.y, cli.accel.z = 0.0, 0.0, 9.8
            det.update(cli, preso_na_base=True, em_sono=False)
            cli.head_angle.radians = 0.5
            cli.accel.x, cli.accel.y, cli.accel.z = 0.8, 0.6, 8.5
            det.update(cli, preso_na_base=True, em_sono=False)
        self.assertEqual(chamadas, [1])


if __name__ == "__main__":
    os.environ.setdefault("PYTHONPATH", "src")
    unittest.main()
