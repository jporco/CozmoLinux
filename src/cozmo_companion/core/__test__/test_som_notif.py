"""Testes — beep notificação OutputAudio."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from cozmo_companion.core.som_notif import gerar_frame_beep, pacotes_beep_notif


class TestSomNotif(unittest.TestCase):
    def test_pacotes_beep_tamanho(self) -> None:
        with patch.dict(os.environ, {"NOTIF_SOM_PACOTES": "3"}):
            pkts = pacotes_beep_notif()
        self.assertEqual(len(pkts), 3)
        for p in pkts:
            self.assertEqual(len(p.samples), 744)

    def test_frame_beep_samples(self) -> None:
        pkt, _ = gerar_frame_beep()
        self.assertEqual(len(pkt.samples), 744)

