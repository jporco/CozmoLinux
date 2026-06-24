"""Testes de resolução do microfone Fifine."""

import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from cozmo_companion.voice import mic


class TestMic(unittest.TestCase):
    @patch("sounddevice.query_devices")
    def test_prefere_entrada_real_sobre_hw_sem_canais(self, mock_qd):
        mock_qd.return_value = [
            {"name": "Fifine K658 Microphone Estéreo analógico", "max_input_channels": 2},
            {"name": "Fifine K658 Microphone: USB Audio (hw:2,0)", "max_input_channels": 0},
        ]
        idx = mic._buscar_por_nome("fifine")
        self.assertEqual(idx, 0)

    @patch("sounddevice.query_devices")
    def test_prefere_usb_quando_tem_entrada(self, mock_qd):
        mock_qd.return_value = [
            {"name": "Fifine K658 Microphone Estéreo analógico", "max_input_channels": 2},
            {"name": "Fifine K658 Microphone: USB Audio (hw:2,0)", "max_input_channels": 1},
        ]
        idx = mic._buscar_por_nome("fifine")
        self.assertEqual(idx, 0)

    def test_mic_ocupado_externo_lock(self) -> None:
        with patch.object(mic, "mic_yield_locks", return_value=[Path("/tmp/cozmo-test.mic")]):
            with patch.object(Path, "is_file", return_value=True):
                self.assertTrue(mic.mic_ocupado_externo())

    def test_mic_livre_sem_lock(self) -> None:
        with patch.object(mic, "mic_yield_locks", return_value=[Path("/tmp/cozmo-test.mic")]):
            with patch.object(Path, "is_file", return_value=False):
                self.assertFalse(mic.mic_ocupado_externo())


if __name__ == "__main__":
    os.environ.setdefault("PYTHONPATH", "src")
    unittest.main()
