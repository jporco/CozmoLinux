"""OLED na base — sem recursão ligar_oled ↔ modo_charger ↔ modo_proc."""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Evita RecursionError no teste (stack real).
sys.setrecursionlimit(800)


class TestOledSemRecursao(unittest.TestCase):
    def test_ligar_oled_base_nao_recursa(self) -> None:
        import cozmo_companion.core.motor_cozmo as motor

        cli = MagicMock()
        cli.animation_groups = {
            "IdleOnCharger": MagicMock(),
            "NeutralFace": MagicMock(),
            "InterestedFace": MagicMock(),
            "InteractWithFaceTrackingIdle": MagicMock(),
        }
        ac = cli.anim_controller
        ac.playing_animation = False
        ac.playing_audio = False
        ac.thread = None
        ac.queue.is_empty.return_value = True
        motor._charger_stream_sessao = False
        motor._charger_keeper_ativo = False
        motor._charger_worker_thread = None
        motor._ultimos_clips_base.clear()

        with patch.dict(
            os.environ,
            {
                "COZMO_BASE_OLED_MODE": "proc",
                "COZMO_BASE_OLED_CHARGER": "1",
                "COZMO_BASE_OLED_CHARGER_FULL": "1",
                "COZMO_CHARGER_PLAY_STREAM": "0",
                "COZMO_CHARGER_OLED_KEEPER": "1",
                "COZMO_BASE_OLED_ANIM_LOOP": "0",
                "COZMO_BASE_SEMPRE_CARGA": "1",
            },
        ):
            with patch(
                "cozmo_companion.core.charger.na_base_oled",
                return_value=True,
            ):
                with patch(
                    "cozmo_companion.core.charger.carga_firmware_pausada",
                    return_value=True,
                ):
                    with patch(
                        "cozmo_companion.core.charger.carregando",
                        return_value=False,
                    ):
                        with patch(
                            "cozmo_companion.core.charger.bateria_pct",
                            return_value=100,
                        ):
                            with patch(
                                "cozmo_companion.core.motor_cozmo.modo_charger_oled",
                                return_value=True,
                            ) as charger:
                                motor.ligar_oled_base(cli, forcar=True, preso_na_base=True)
        charger.assert_called_once()


if __name__ == "__main__":
    os.environ.setdefault("PYTHONPATH", "src")
    unittest.main()
