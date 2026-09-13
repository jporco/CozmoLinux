"""Testes de filtro BASE / carregador / mesa."""

import os
import unittest

from cozmo_companion.core.anims import (
    GRUPOS_MESA,
    GRUPOS_REACAO,
    ContextoAnim,
    detectar_contexto_anim,
    escolher_ctx,
    filtrar_por_contexto,
)


class TestAnimsContexto(unittest.TestCase):
    def setUp(self):
        self.disp = {
            "Surprise",
            "ReactToPokeStartled",
            "ReactToPokeReaction",
            "ReactToCliff",
            "NeutralFace",
            "InterestedFace",
            "LookInPlaceForFacesHeadMovePause",
            "DriveOffCharger",
            "IdleOnCharger",
            "GoToSleepSleeping",
            "Hiccup",
        }

    def test_detectar_contexto(self):
        self.assertEqual(
            detectar_contexto_anim(preso_na_base=True, no_carregador=False),
            ContextoAnim.BASE,
        )
        self.assertEqual(
            detectar_contexto_anim(preso_na_base=False, no_carregador=False),
            ContextoAnim.CARREGADOR,
        )
        self.assertEqual(
            detectar_contexto_anim(preso_na_base=False, no_carregador=True),
            ContextoAnim.MESA,
        )

    def test_base_permite_surprise_sanitizado(self):
        pool = filtrar_por_contexto(GRUPOS_REACAO, self.disp, ContextoAnim.BASE)
        self.assertIn("Surprise", pool)
        self.assertIn("ReactToPokeReaction", pool)

    def test_carregador_permite_surprise_sanitizado(self):
        pool = filtrar_por_contexto(GRUPOS_MESA, self.disp, ContextoAnim.CARREGADOR)
        self.assertIn("Surprise", pool)
        self.assertNotIn("ReactToCliff", pool)
        self.assertIn("NeutralFace", pool)

    def test_mesa_permite_surprise(self):
        pool = filtrar_por_contexto(GRUPOS_REACAO, self.disp, ContextoAnim.MESA)
        self.assertIn("Surprise", pool)

    def test_base_bloqueia_drive(self):
        pool = filtrar_por_contexto(("DriveOffCharger", "NeutralFace"), self.disp, ContextoAnim.BASE)
        self.assertNotIn("DriveOffCharger", pool)
        self.assertIn("NeutralFace", pool)

    def test_escolher_ctx_mesa(self):
        for _ in range(10):
            nome = escolher_ctx(self.disp, GRUPOS_REACAO, ContextoAnim.MESA)
            self.assertIn(nome, ("Surprise", "ReactToPokeStartled", "ReactToPokeReaction", "InterestedFace"))

    def test_escolher_ctx_base_pode_usar_reacao_sanitizada(self):
        for _ in range(20):
            nome = escolher_ctx(self.disp, GRUPOS_REACAO, ContextoAnim.BASE)
            self.assertIn(nome, ("Surprise", "ReactToPokeStartled", "ReactToCliff", "ReactToPokeReaction", "InterestedFace"))


if __name__ == "__main__":
    os.environ.setdefault("PYTHONPATH", "src")
    unittest.main()
