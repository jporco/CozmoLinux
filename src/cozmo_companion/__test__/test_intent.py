"""Testes de intenção de voz — wake word obrigatório."""

import os
import unittest

from cozmo_companion.voice.intent import (
    aceitar_sem_wake,
    parece_fala_dirigida,
    parece_pergunta,
    parece_ruido_tv,
)


class TestIntent(unittest.TestCase):
    def setUp(self):
        os.environ["WAKE_OBRIGATORIO"] = "1"

    def test_sem_wake_ignora(self):
        self.assertFalse(aceitar_sem_wake("casa", na_base=True))
        self.assertFalse(aceitar_sem_wake("com temperatura", na_base=False))

    def test_com_cozmo_aceita(self):
        self.assertTrue(aceitar_sem_wake("cozmo como vai", na_base=True))
        self.assertTrue(aceitar_sem_wake("cosmo", na_base=False))

    def test_pergunta_sem_wake(self):
        self.assertTrue(parece_pergunta("que horas são"))

    def test_tv_nao_e_pergunta(self):
        self.assertFalse(parece_pergunta("os próximos"))
        self.assertFalse(parece_pergunta("é extensão"))
        self.assertFalse(parece_fala_dirigida("olá muito bom"))

    def test_veja_e_tv(self):
        self.assertTrue(parece_ruido_tv("veja"))
        self.assertFalse(parece_fala_dirigida("veja"))
        self.assertTrue(parece_fala_dirigida("estou triste"))

    def test_fala_dirigida(self):
        self.assertTrue(parece_fala_dirigida("oi"))
        self.assertTrue(parece_fala_dirigida("estou triste"))
        self.assertTrue(parece_fala_dirigida("cozmo que horas são"))


if __name__ == "__main__":
    os.environ.setdefault("PYTHONPATH", "src")
    unittest.main()
