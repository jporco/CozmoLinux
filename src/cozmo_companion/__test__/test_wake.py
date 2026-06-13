"""Testes da wake word Cozmo."""

import os
import unittest

from cozmo_companion.voice.wake import WakeWord, extrair_pergunta


class TestWakeWord(unittest.TestCase):
    def test_extrair_na_mesma_frase(self):
        self.assertEqual(
            extrair_pergunta("cozmo qual a temperatura em bagé"),
            "qual a temperatura em bagé",
        )

    def test_só_cozmo(self):
        self.assertIsNone(extrair_pergunta("cozmo"))

    def test_cosmo_vosk(self):
        """Vosk transcreve 'cozmo' como 'cosmo'."""
        self.assertEqual(
            extrair_pergunta("cosmo qual a temperatura em bagé"),
            "qual a temperatura em bagé",
        )
        perguntas = []
        w = WakeWord(ao_pergunta=perguntas.append)
        self.assertTrue(w.processar("cosmo que horas são"))
        self.assertEqual(perguntas, ["que horas são"])

    def test_oracao_vosk_alias(self):
        from cozmo_companion.voice.wake import contem_wake, extrair_pergunta, parcial_wake_pronto

        self.assertTrue(contem_wake("oração"))
        self.assertEqual(extrair_pergunta("oração que horas são"), "que horas são")
        self.assertFalse(contem_wake("que oração"))
        self.assertTrue(contem_wake("que oração que horas são"))
        self.assertEqual(
            extrair_pergunta("que oração que horas são"),
            "que horas são",
        )
        self.assertFalse(parcial_wake_pronto("oração"))
        self.assertTrue(parcial_wake_pronto("oração que horas são"))
        perguntas = []
        w = WakeWord(ao_pergunta=perguntas.append)
        self.assertTrue(w.processar("oração que horas são"))
        self.assertEqual(perguntas, ["que horas são"])
        perguntas.clear()
        self.assertTrue(w.processar("que oração que horas são"))
        self.assertEqual(perguntas, ["que horas são"])
        perguntas.clear()
        self.assertTrue(w.processar("oração"))
        self.assertTrue(w.processar("qual a temperatura"))
        self.assertEqual(perguntas, ["qual a temperatura"])

    def test_pergunta_depois(self):
        perguntas = []
        w = WakeWord(ao_pergunta=perguntas.append)
        self.assertTrue(w.processar("cozmo"))
        self.assertTrue(w.aguardando)
        self.assertTrue(w.processar("que horas são"))
        self.assertEqual(perguntas, ["que horas são"])


if __name__ == "__main__":
    os.environ.setdefault("PYTHONPATH", "src")
    unittest.main()
