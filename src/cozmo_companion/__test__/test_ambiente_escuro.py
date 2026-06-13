"""Detector de ambiente escuro — luminância da câmera."""

import os
import unittest
from unittest.mock import MagicMock

from PIL import Image

from cozmo_companion.core.ambiente_escuro import DetectorEscuro, luminancia_media


class TestAmbienteEscuro(unittest.TestCase):
    def test_luminancia_preto_e_branco(self) -> None:
        preto = Image.new("L", (32, 32), 0)
        branco = Image.new("L", (32, 32), 255)
        self.assertLess(luminancia_media(preto), 5)
        self.assertGreater(luminancia_media(branco), 250)

    def test_histerese_escuro(self) -> None:
        os.environ["COZMO_ESCURO_AUTO"] = "1"
        os.environ["COZMO_ESCURO_AMOSTRAS"] = "3"
        os.environ["COZMO_ESCURO_LIM"] = "40"
        os.environ["COZMO_ESCURO_CLARO"] = "60"
        det = DetectorEscuro()
        escuro = Image.new("L", (64, 48), 10)
        for _ in range(4):
            det.amostrar(escuro)
        self.assertTrue(det.escuro)

    def test_despertar_cancela_escuro(self) -> None:
        det = DetectorEscuro()
        det._escuro = True
        det.marcar_despertar(60.0)
        self.assertFalse(det.escuro)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONPATH", "src")
    unittest.main()
