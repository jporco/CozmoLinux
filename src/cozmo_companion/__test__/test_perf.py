"""Testes do modo performance."""

import os
import unittest

from cozmo_companion.core.perf import ModoPerf, PERFIS


class TestPerf(unittest.TestCase):
    def test_jogo_mantem_voz_e_llm(self):
        jogo = PERFIS[ModoPerf.JOGO]
        self.assertTrue(jogo.ouvir_mic)
        self.assertTrue(jogo.usar_llm)
        self.assertFalse(jogo.fala_proativa)
        self.assertGreater(jogo.loop_sleep, PERFIS[ModoPerf.NORMAL].loop_sleep)
        self.assertGreater(jogo.nice_extra, 0)

    def test_jogo_menos_tokens(self):
        jogo = PERFIS[ModoPerf.JOGO]
        normal = PERFIS[ModoPerf.NORMAL]
        self.assertLess(jogo.ollama_tokens, normal.ollama_tokens)
        self.assertLess(jogo.ollama_threads, normal.ollama_threads)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONPATH", "src")
    unittest.main()
