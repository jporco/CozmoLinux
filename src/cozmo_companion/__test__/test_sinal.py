"""Testes do modo sinal (TTS mínimo + tela)."""

import os
import unittest

from cozmo_companion.voice.sinal import (
    comando_util,
    modo_sinal,
    parece_clima,
    parece_hora,
    sinal_para,
    texto_tela_de_fala,
)


class TestSinal(unittest.TestCase):
    def test_modo_sinal_default(self):
        os.environ.pop("TTS_MODO", None)
        self.assertTrue(modo_sinal())

    def test_hora(self):
        self.assertTrue(parece_hora("que horas são"))
        self.assertEqual(sinal_para("Cozmo que horas são", ""), "Hora")

    def test_clima(self):
        self.assertTrue(parece_clima("temperatura"))
        self.assertEqual(sinal_para("como está o tempo", ""), "Tempo")
        self.assertEqual(sinal_para("tempo", ""), "Tempo")

    def test_saudacao(self):
        s = sinal_para("oi cozmo", "")
        self.assertIn(s, ("Oi", "Opa", "Beep"))

    def test_primeira_palavra_llm(self):
        self.assertEqual(sinal_para("", "Massa demais porco!"), "Massa")

    def test_comando_util(self):
        self.assertTrue(comando_util("o tempo"))
        self.assertTrue(comando_util("temperatura"))
        self.assertFalse(comando_util("filme de ação com explosões"))

    def test_texto_tela(self):
        self.assertEqual(texto_tela_de_fala("Em Bagé estão 13 graus agora."), "Em Bagé estão 13")


if __name__ == "__main__":
    os.environ.setdefault("PYTHONPATH", "src")
    unittest.main()
