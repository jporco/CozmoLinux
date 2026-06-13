"""Testes do chat com ações LLM."""

import os
import unittest
from unittest.mock import patch

from cozmo_companion.voice.acoes_llm import AcaoEmocional, RespostaCozmo
from cozmo_companion.voice.chat import Chat


class TestChatAcoes(unittest.TestCase):
    def test_responder_com_acao_triste_rapido(self):
        c = Chat()
        r = c.responder_com_acao("estou triste", permitir_llm=False)
        self.assertEqual(r.acao, AcaoEmocional.CONFORTO)
        self.assertTrue(len(r.fala) < 20)

    @patch.object(Chat, "_ollama_acoes")
    def test_responder_com_acao_llm(self, mock_acoes):
        mock_acoes.return_value = RespostaCozmo(
            fala="Força porco!",
            acao=AcaoEmocional.CONFORTO,
            tela="♥",
        )
        c = Chat()
        with patch.object(c, "_ollama_disponivel", return_value=True):
            r = c.responder_com_acao("como você está hoje", permitir_llm=True)
        self.assertEqual(r.fala, "Força porco!")


if __name__ == "__main__":
    os.environ.setdefault("PYTHONPATH", "src")
    unittest.main()
