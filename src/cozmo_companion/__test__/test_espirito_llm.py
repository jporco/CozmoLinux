"""Testes do espírito integrado ao catálogo LLM."""

import os
import unittest

from cozmo_companion.core.espirito import Acao, ContextoVida, Espirito, Humor
from cozmo_companion.voice.acoes_llm import AcaoEmocional, espirito_para_acao_emocional


class TestEspiritoLlm(unittest.TestCase):
    def test_fala_carinhoso(self):
        acao = espirito_para_acao_emocional(Humor.CARINHOSO.name, Acao.FALA.name)
        self.assertEqual(acao, AcaoEmocional.CARINHO)

    def test_explorar_mapeia(self):
        acao = espirito_para_acao_emocional(Humor.ANIMADO.name, Acao.EXPLORAR.name)
        self.assertEqual(acao, AcaoEmocional.EXPLORAR)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONPATH", "src")
    unittest.main()
