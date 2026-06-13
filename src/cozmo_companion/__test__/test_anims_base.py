"""Testes de filtro de animações na base."""

import os
import unittest
from unittest.mock import patch

from cozmo_companion.core.anims import (
    GRUPOS_CURIOSO,
    GRUPOS_SONO,
    escolher,
    filtrar_na_base,
    filtrar_por_contexto,
    filtrar_sono_na_base,
    pool_olhos_oled_base,
    permitido_sem_rodas_na_base,
    ContextoAnim,
)


class TestAnimsBase(unittest.TestCase):
    def test_body_pause_bloqueado(self):
        disp = {
            "LookInPlaceForFacesBodyPause",
            "LookInPlaceForFacesHeadMovePause",
            "NeutralFace",
            "IdleOnCharger",
        }
        pool = filtrar_na_base(GRUPOS_CURIOSO, disp)
        self.assertNotIn("LookInPlaceForFacesBodyPause", pool)
        self.assertIn("LookInPlaceForFacesHeadMovePause", pool)

    def test_pool_olhos_oled_prioridade(self):
        from cozmo_companion.core.anims import pool_variacao_oled_base

        disp = {
            "IdleOnCharger",
            "NeutralFace",
            "InterestedFace",
            "LookInPlaceForFacesHeadMovePause",
            "ReactToPokeReaction",
            "InteractWithFaceTrackingIdle",
            "CodeLabBlink",
            "LookInPlaceForFacesBodyPause",
            "DriveStuckOffCharger",
            "DizzyReactionSoft",
        }
        pool = pool_variacao_oled_base(disp)
        self.assertIn("IdleOnCharger", pool)
        self.assertIn("LookInPlaceForFacesHeadMovePause", pool)
        self.assertNotIn("ReactToPokeReaction", pool)
        self.assertNotIn("DriveStuckOffCharger", pool)
        self.assertNotIn("DizzyReactionSoft", pool)
        self.assertGreaterEqual(len(pool), 5)
        with patch.dict(os.environ, {"COZMO_BASE_POOL_SEGURO": "0"}):
            pool_largo = pool_variacao_oled_base(disp)
        self.assertIn("InteractWithFaceTrackingIdle", pool_largo)

    def test_permitido_bloqueia_drive(self):
        self.assertTrue(permitido_sem_rodas_na_base("IdleOnCharger"))
        self.assertTrue(permitido_sem_rodas_na_base("LookInPlaceForFacesHeadMovePause"))
        self.assertFalse(permitido_sem_rodas_na_base("DriveStuckOffCharger"))

    def test_sono_separado_do_acordado(self):
        disp = {
            "Sleeping",
            "GoToSleepSleeping",
            "NeutralFace",
            "LookInPlaceForFacesHeadMovePause",
        }
        pool = filtrar_sono_na_base(GRUPOS_SONO, disp)
        self.assertIn("Sleeping", pool)
        awake = filtrar_por_contexto(GRUPOS_CURIOSO, disp, ContextoAnim.BASE)
        self.assertNotIn("Sleeping", awake)

    def test_escolher_na_base_sem_drive(self):
        disp = {
            "LookInPlaceForFacesBodyPause",
            "NeutralFace",
            "LookInPlaceForFacesHeadMovePause",
        }
        nomes = {escolher(disp, GRUPOS_CURIOSO, na_base=True) for _ in range(30)}
        self.assertNotIn("LookInPlaceForFacesBodyPause", nomes)
        self.assertTrue(nomes <= {"NeutralFace", "LookInPlaceForFacesHeadMovePause"})


if __name__ == "__main__":
    os.environ.setdefault("PYTHONPATH", "src")
    unittest.main()
