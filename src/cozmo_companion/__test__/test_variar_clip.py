"""Variação de clip na base — anti-repetição e pesos."""

import os
import unittest
from unittest.mock import patch

from cozmo_companion.core.motor_cozmo import _escolher_clip_variar


class TestVariarClip(unittest.TestCase):
    def test_nao_repete_recentes(self) -> None:
        pool = [
            "IdleOnCharger",
            "NeutralFace",
            "InterestedFace",
            "LookInPlaceForFacesHeadMovePause",
            "ReactToPokeReaction",
        ]
        with patch.dict(os.environ, {"COZMO_BASE_VARIAR_ANTI_REPEAT": "2"}):
            escolhidos = {
                _escolher_clip_variar(
                    pool,
                    atual="IdleOnCharger",
                    recentes=["NeutralFace", "InterestedFace"],
                )
                for _ in range(40)
            }
        self.assertNotIn("IdleOnCharger", escolhidos)
        self.assertNotIn("NeutralFace", escolhidos)
        self.assertNotIn("InterestedFace", escolhidos)

    def test_intervalo_variar_15_28s(self) -> None:
        from cozmo_companion.core.motor_cozmo import _intervalo_variar_base_s

        with patch.dict(os.environ, {"COZMO_BASE_VARIAR_S": "22", "COZMO_BASE_VARIAR_JITTER_S": "6"}):
            vals = [_intervalo_variar_base_s() for _ in range(30)]
        self.assertTrue(all(15.0 <= v <= 28.0 for v in vals))

    def test_idle_peso_menor(self) -> None:
        pool = ["IdleOnCharger", "NeutralFace"]
        with patch.dict(os.environ, {"COZMO_BASE_IDLE_PESO": "0.01"}):
            hits = sum(
                1
                for _ in range(200)
                if _escolher_clip_variar(pool, atual=None, recentes=[])
                == "NeutralFace"
            )
        self.assertGreater(hits, 150)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONPATH", "src")
    unittest.main()
