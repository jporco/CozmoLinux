"""Testes de normalização Vosk."""

import unittest

from cozmo_companion.voice.normalizar import normalizar_vosk
from cozmo_companion.voice.wake import extrair_pergunta


class TestNormalizar(unittest.TestCase):
    def test_oracao_vai_cosmo(self):
        self.assertEqual(normalizar_vosk("oração que horas são"), "cosmo que horas são")

    def test_extrair_apos_normalizar(self):
        t = normalizar_vosk("oração que horas sao")
        self.assertEqual(extrair_pergunta(t), "que horas são")


if __name__ == "__main__":
    unittest.main()
