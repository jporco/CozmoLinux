"""Testes do módulo alive."""

import os
import unittest

from cozmo_companion.core.alive import filtrar_animacoes_base


class TestAlive(unittest.TestCase):
    def test_bloqueia_drive_na_base(self):
        grupos = {"DriveOffCharger", "Sleeping", "LookInPlaceForFacesHeadMovePause"}
        filtrado = filtrar_animacoes_base(
            ("DriveOffCharger", "LookInPlaceForFacesHeadMovePause"),
            grupos,
        )
        self.assertIn("LookInPlaceForFacesHeadMovePause", filtrado)
        self.assertNotIn("DriveOffCharger", filtrado)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONPATH", "src")
    unittest.main()
