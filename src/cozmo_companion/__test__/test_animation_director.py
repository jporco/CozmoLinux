"""Diretor de animações por intenção/contexto."""

from __future__ import annotations

import unittest

from cozmo_companion.core.animation_director import AnimationDirector, AnimIntent
from cozmo_companion.core.anims import ContextoAnim


class TestAnimationDirector(unittest.TestCase):
    def test_notificacao_base_so_pool_seguro(self) -> None:
        disp = {
            "InterestedFace",
            "CodeLabBlink",
            "DriveOffCharger",
            "Hiccup",
        }
        pool = AnimationDirector().pool(disp, ContextoAnim.BASE, AnimIntent.NOTIFICATION)
        self.assertIn("InterestedFace", pool)
        self.assertNotIn("DriveOffCharger", pool)

    def test_rosto_visto_tem_curiosos(self) -> None:
        disp = {
            "LookInPlaceForFacesHeadMovePause",
            "InteractWithFaceTrackingIdle",
        }
        pool = AnimationDirector().pool(disp, ContextoAnim.MESA, AnimIntent.FACE_SEEN)
        self.assertTrue(pool)
        self.assertIn("LookInPlaceForFacesHeadMovePause", pool)

    def test_cliff_mesa_prefere_susto(self) -> None:
        disp = {"ReactToCliff", "ReactToPokeReaction"}
        self.assertEqual(
            AnimationDirector().first_available(disp, ContextoAnim.MESA, AnimIntent.CLIFF),
            "ReactToCliff",
        )

    def test_movimento_na_base_escolhe_reacao_visual_segura(self) -> None:
        disp = {"CodeLabCurious", "CodeLabAmazed", "DriveOffCharger"}
        pool = AnimationDirector().pool(disp, ContextoAnim.BASE, AnimIntent.MOTION)
        self.assertIn("CodeLabCurious", pool)
        self.assertNotIn("DriveOffCharger", pool)

    def test_som_tem_repertorio_diferente_do_idle(self) -> None:
        disp = {"CodeLabWhew", "Hiccup", "IdleOnCharger"}
        pool = AnimationDirector().pool(disp, ContextoAnim.BASE, AnimIntent.SOUND)
        self.assertIn("CodeLabWhew", pool)
        self.assertNotIn("IdleOnCharger", pool)


if __name__ == "__main__":
    unittest.main()
