"""Testes do rastreamento de rosto."""

import os
import unittest

import numpy as np
from PIL import Image

from cozmo_companion.core.face_watch import FaceWatch
from cozmo_companion.perception.events import PerceptionEventKind


class TestFaceWatch(unittest.TestCase):
    def test_suavizacao(self):
        fw = FaceWatch.__new__(FaceWatch)
        fw._smooth_x = 0.0
        fw._smooth_y = 0.0
        fw._suavizar(1.0, -0.5)
        self.assertGreater(fw._smooth_x, 0.0)
        self.assertLess(fw._smooth_y, 0.0)
        fw._suavizar(1.0, -0.5)
        self.assertGreater(fw._smooth_x, fw._smooth_y)

    def test_evento_luz(self):
        eventos = []
        fw = FaceWatch.__new__(FaceWatch)
        fw._event_sink = eventos.append
        fw._detector_luz = None
        fw._cascade = None
        fw._na_base = True
        img = Image.new("L", (32, 32), 80)
        fw._analisar_imagem(img, luz_apenas=True)
        self.assertEqual(eventos[-1].kind, PerceptionEventKind.LIGHT_LEVEL)
        self.assertEqual(eventos[-1].value, 80.0)

    def test_evento_movimento(self):
        eventos = []
        fw = FaceWatch.__new__(FaceWatch)
        fw._event_sink = eventos.append
        fw._prev_motion_frame = None
        fw._frames_janela = 4
        fw._motion_hits = 0
        fw._na_base = False
        fw._emitir_movimento(np.asarray(Image.new("L", (32, 32), 0)))
        fw._emitir_movimento(np.asarray(Image.new("L", (32, 32), 255)))
        fw._emitir_movimento(np.asarray(Image.new("L", (32, 32), 0)))
        self.assertTrue(any(e.kind == PerceptionEventKind.MOTION_HINT for e in eventos))


if __name__ == "__main__":
    os.environ.setdefault("PYTHONPATH", "src")
    unittest.main()
