"""Testes do espírito autônomo."""

import os
import time
import unittest

from cozmo_companion.core.espirito import Acao, ContextoVida, Espirito, Humor


def _ctx(**kw) -> ContextoVida:
    base = dict(
        na_base=False,
        carregando=False,
        falando=False,
        llm_ocupado=False,
        dormindo=False,
        explorando=False,
        face_ativo=False,
        bateria_pct=80,
        grupos={"Surprise", "NeutralFace", "LookInPlaceForFacesHeadMovePause"},
    )
    base.update(kw)
    return ContextoVida(**base)


class TestEspirito(unittest.TestCase):
    def test_registrar_interacao_reduz_entedimento(self):
        e = Espirito()
        e._entedimento = 0.8
        e.humor = Humor.ENTEDIADO
        e.registrar_interacao()
        self.assertLess(e._entedimento, 0.8)
        self.assertNotEqual(e.humor, Humor.ENTEDIADO)

    def test_na_base_carregando_prefere_gesto(self):
        e = Espirito()
        e._proxima = 0
        planos = []
        for _ in range(30):
            e._proxima = 0
            p = e.tick(_ctx(na_base=True, carregando=True))
            if p:
                planos.append(p.acao)
        self.assertTrue(planos)
        self.assertTrue(
            any(
                a in planos
                for a in (Acao.GESTO, Acao.TELA, Acao.FALA, Acao.OLHAR, Acao.ANIM)
            ),
            f"ações seguras na carga: {planos}",
        )

    def test_fora_base_pode_explorar(self):
        e = Espirito()
        e.humor = Humor.ANIMADO
        e._entedimento = 0.8
        achou = False
        for i in range(80):
            e._proxima = 0
            p = e.tick(_ctx(na_base=False))
            if p and p.acao == Acao.EXPLORAR:
                achou = True
                break
        self.assertTrue(achou)

    def test_falando_nao_age(self):
        e = Espirito()
        e._proxima = 0
        self.assertIsNone(e.tick(_ctx(falando=True)))


if __name__ == "__main__":
    os.environ.setdefault("PYTHONPATH", "src")
    unittest.main()
