"""Testes de detecção de pergunta sobre hora."""

import os
import unittest

from cozmo_companion.core import hora


class TestPerguntaHora(unittest.TestCase):
    def test_frases_validas(self):
        self.assertTrue(hora.pergunta_hora("cozmo que horas são"))
        self.assertTrue(hora.pergunta_hora("me diga a hora"))

    def test_nao_dispara_em_agora(self):
        self.assertFalse(hora.pergunta_hora("agora eu vou jogar"))
        self.assertFalse(hora.pergunta_hora("beep boop tô aqui"))


if __name__ == "__main__":
    os.environ.setdefault("PYTHONPATH", "src")
    unittest.main()
