"""Testes das ações físicas decididas pelo LLM."""

import os
import unittest

from cozmo_companion.voice.acoes_llm import (
    AcaoEmocional,
    inferir_acao_do_usuario,
    parse_resposta_bruta,
    resolver_acao,
    grupos_para_acao,
)


class TestAcoesLlm(unittest.TestCase):
    def test_parse_formato_ollama(self):
        bruto = "FALA: Ei porco, tô aqui!\nACAO: carinho"
        r = parse_resposta_bruta(bruto)
        self.assertEqual(r.fala, "Ei porco, tô aqui!")
        self.assertEqual(r.acao, AcaoEmocional.CARINHO)
        self.assertEqual(r.tela, "<3")

    def test_parse_sem_acao(self):
        r = parse_resposta_bruta("Beep boop, tudo bem!")
        self.assertIn("Beep", r.fala)
        self.assertEqual(r.acao, AcaoEmocional.NADA)

    def test_inferir_triste(self):
        self.assertEqual(
            inferir_acao_do_usuario("estou triste hoje"),
            AcaoEmocional.CONFORTO,
        )
        self.assertEqual(
            inferir_acao_do_usuario("me sinto sozinho"),
            AcaoEmocional.TRISTE,
        )

    def test_resolver_fallback_usuario(self):
        r = parse_resposta_bruta("FALA: Força porco!\nACAO: nada")
        acao = resolver_acao(r, "estou triste")
        self.assertEqual(acao, AcaoEmocional.CONFORTO)

    def test_inferir_dormir(self):
        self.assertEqual(
            inferir_acao_do_usuario("vai dormir cozmo"),
            AcaoEmocional.DORMIR,
        )

    def test_espirito_mapeamento(self):
        from cozmo_companion.voice.acoes_llm import espirito_para_acao_emocional

        self.assertEqual(
            espirito_para_acao_emocional("BRINCALHAO", "ATITUDE"),
            AcaoEmocional.DANCAR,
        )
        self.assertEqual(
            espirito_para_acao_emocional("SONOLENTO", "TELA"),
            AcaoEmocional.DORMIR,
        )

    def test_grupos_carinho(self):
        g = grupos_para_acao(AcaoEmocional.CARINHO)
        self.assertIn("ReactToPokeReaction", g)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONPATH", "src")
    unittest.main()
