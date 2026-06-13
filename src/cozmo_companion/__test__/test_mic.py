"""Testes de resolução do microfone Fifine."""

import os
import unittest
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


if __name__ == "__main__":
    os.environ.setdefault("PYTHONPATH", "src")
    unittest.main()
