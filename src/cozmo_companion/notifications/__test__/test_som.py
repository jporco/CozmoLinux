"""Testes — beep notif no Cozmo (PC opcional)."""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

from cozmo_companion.notifications.core import som


class TestSomNotif(unittest.TestCase):
    def test_beep_pc_desliga_somente_por_config(self) -> None:
        with patch.dict(os.environ, {"NOTIF_PC_BEEP": "0", "NOTIF_PC_AUDIO": "0"}, clear=False):
            self.assertFalse(som._beep_pc())

    def test_beep_pc_exige_pc_audio_e_beep(self) -> None:
        with patch.dict(os.environ, {"NOTIF_PC_BEEP": "1", "NOTIF_PC_AUDIO": "0"}):
            self.assertFalse(som._beep_pc())
        with patch.dict(os.environ, {"NOTIF_PC_BEEP": "1", "NOTIF_PC_AUDIO": "1"}):
            with patch("shutil.which", return_value="/usr/bin/paplay"):
                with patch("subprocess.run") as run:
                    run.return_value.returncode = 0
                    run.return_value.stdout = "default-sink\n"
                    self.assertTrue(som._beep_pc())

    def test_beep_pc_desligado_por_padrao(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(som._beep_pc())

    def test_tocar_beep_nao_chama_pc_quando_desligado(self) -> None:
        cli = MagicMock()
        cli.anim_controller.queue.is_empty.return_value = True
        with patch.dict(os.environ, {"NOTIF_PC_BEEP": "0", "NOTIF_PC_AUDIO": "0"}):
            with patch.object(som, "_beep_pc") as beep_pc:
                with patch.object(som, "pacotes_beep_notif", return_value=[MagicMock()]):
                    with patch("cozmo_companion.core.charger.em_base", return_value=True):
                        with patch(
                            "cozmo_companion.core.motor_cozmo.ligar_oled_base",
                            return_value=True,
                        ):
                            with patch(
                                "cozmo_companion.core.motor_cozmo.modo_tts_preparar",
                                return_value=(True, True),
                            ):
                                with patch(
                                    "cozmo_companion.core.motor_cozmo.modo_tts_restaurar"
                                ):
                                    with patch(
                                        "cozmo_companion.voice.tts._enviar_sinal_udp"
                                    ):
                                        som.tocar_beep_notif(cli)
        beep_pc.assert_not_called()

    def test_tocar_beep_chama_pc_quando_ligado(self) -> None:
        cli = MagicMock()
        cli.anim_controller.queue.is_empty.return_value = True
        with patch.dict(os.environ, {"NOTIF_PC_BEEP": "1", "NOTIF_PC_AUDIO": "1"}):
            with patch.object(som, "_beep_pc") as beep_pc:
                with patch.object(som, "pacotes_beep_notif", return_value=[MagicMock()]):
                    with patch("cozmo_companion.core.charger.em_base", return_value=True):
                        with patch(
                            "cozmo_companion.core.motor_cozmo.ligar_oled_base",
                            return_value=True,
                        ):
                            with patch(
                                "cozmo_companion.core.motor_cozmo.modo_tts_preparar",
                                return_value=(True, True),
                            ):
                                with patch(
                                    "cozmo_companion.core.motor_cozmo.modo_tts_restaurar"
                                ):
                                    with patch(
                                        "cozmo_companion.voice.tts._enviar_sinal_udp"
                                    ):
                                        som.tocar_beep_notif(cli)
        beep_pc.assert_called_once()

    def test_pacotes_beep_usa_wav_ou_sintetico(self) -> None:
        pkts = som.pacotes_beep_notif()
        self.assertGreater(len(pkts), 0)
