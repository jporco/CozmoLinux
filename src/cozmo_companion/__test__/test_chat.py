"""Testes do chat inteligente — Ollama como cérebro."""

import os
import unittest
from unittest.mock import patch

from cozmo_companion.voice.chat import Chat, FALLBACKS


class TestChat(unittest.TestCase):
    def test_hora_instantanea(self):
        c = Chat()
        r = c.responder("que horas são", permitir_llm=False)
        self.assertRegex(r.lower(), r"\d")

    @patch.object(Chat, "_ollama")
    def test_ollama_para_conversa(self, mock_llm):
        mock_llm.return_value = "Beep! Tudo bem porco!"
        c = Chat()
        with patch.object(c, "_ollama_disponivel", return_value=True):
            r = c.responder("como você está hoje?", permitir_llm=True)
        mock_llm.assert_called()
        self.assertEqual(r, "Beep! Tudo bem porco!")

    @patch.object(Chat, "_ollama")
    def test_fallback_sem_ollama(self, mock_llm):
        mock_llm.return_value = None
        c = Chat()
        with patch.object(c, "_ollama_disponivel", return_value=False):
            r = c.responder("me conta uma piada", permitir_llm=True)
        self.assertIn(r, FALLBACKS)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONPATH", "src")
    unittest.main()
