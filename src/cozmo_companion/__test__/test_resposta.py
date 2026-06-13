"""Testes de respostas curtas."""

import os
import unittest

from cozmo_companion.voice.resposta import encurtar_fala, resposta_rapida


class TestResposta(unittest.TestCase):
    def test_encurtar(self):
        longo = " ".join(["palavra"] * 30)
        self.assertLessEqual(len(encurtar_fala(longo).split()), 12)

    def test_oi_rapido(self):
        self.assertIsNotNone(resposta_rapida("oi"))

    def test_remove_lixo_acao(self):
        t = encurtar_fala("Tudo bem porco! Carinho.")
        self.assertNotIn("Carinho", t)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONPATH", "src")
    unittest.main()
