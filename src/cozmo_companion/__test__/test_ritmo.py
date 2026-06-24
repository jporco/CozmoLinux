"""Testes do ritmo natural."""

import os
import unittest

from cozmo_companion.core.ritmo import RitmoNatural, parece_latido


class TestRitmo(unittest.TestCase):
    def test_latido(self):
        self.assertTrue(parece_latido("au au"))
        self.assertTrue(parece_latido("ao"))
        self.assertTrue(parece_latido("ao ao"))
        self.assertTrue(parece_latido("uau"))
        self.assertFalse(parece_latido("automóvel"))

    def test_parado_longo(self):
        r = RitmoNatural()
        acao, dur = r.escolher_proxima()
        self.assertIn(acao, ("parado", "busca_rosto", "anim", "eco", "explorar"))
        if acao == "parado":
            self.assertGreaterEqual(dur, 90)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONPATH", "src")
    unittest.main()
