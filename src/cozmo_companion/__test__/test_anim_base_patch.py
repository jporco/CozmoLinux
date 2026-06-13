"""Patch de anim na base — imobiliza corpo na dock."""

import os
import unittest

from cozmo_companion.core.anim_base_patch import (
    clip_imobilizar_na_base,
    instalar_play_anim_sem_rodas_na_base,
    ppclip_filtrar_pacotes_rodas,
)
from cozmo_companion.core.motor_cozmo import instalar_anim_id_seguro
from pycozmo import anim_encoder
from pycozmo import protocol_encoder
from pycozmo import anim as pycozmo_anim


class TestAnimBasePatch(unittest.TestCase):
    def test_remove_corpo_e_neutraliza_cabeca(self) -> None:
        kf_roda = anim_encoder.AnimBodyMotion(
            trigger_time_ms=0,
            duration_ms=500,
            radius_mm="STRAIGHT",
            speed=80.0,
        )
        kf_lift = anim_encoder.AnimLiftHeight(
            trigger_time_ms=0,
            duration_ms=200,
            height_mm=80,
            variability_mm=0,
        )
        kf_cabeca = anim_encoder.AnimHeadAngle(
            trigger_time_ms=0,
            duration_ms=200,
            angle_deg=25.0,
            variability_deg=5.0,
        )
        clip = anim_encoder.AnimClip(
            name="test",
            keyframes=[kf_roda, kf_lift, kf_cabeca],
        )
        limpo = clip_imobilizar_na_base(clip)
        self.assertEqual(len(limpo.keyframes), 1)
        cab = limpo.keyframes[0]
        self.assertIsInstance(cab, anim_encoder.AnimHeadAngle)
        self.assertLessEqual(abs(cab.angle_deg), 25)
        self.assertEqual(cab.variability_deg, 0.0)

    def test_ppclip_sem_drive_nem_lift(self) -> None:
        pp = pycozmo_anim.PreprocessedClip(
            {
                0: [
                    protocol_encoder.DriveWheels(lwheel_speed_mmps=50, rwheel_speed_mmps=50),
                    protocol_encoder.AnimLift(duration_ms=100, height_mm=50, variability_mm=0),
                    protocol_encoder.AnimHead(
                        duration_ms=100, angle_deg=0.0, variability_deg=0.0
                    ),
                ],
            }
        )
        filtrado = ppclip_filtrar_pacotes_rodas(pp)
        tipos = {type(p) for t in filtrado.keyframes.values() for p in t}
        self.assertNotIn(protocol_encoder.DriveWheels, tipos)
        self.assertNotIn(protocol_encoder.AnimLift, tipos)
        self.assertIn(protocol_encoder.AnimHead, tipos)

    def test_reinstalar_patch_mantem_anim_id_seguro(self) -> None:
        from unittest.mock import MagicMock

        cli = MagicMock()
        cli._cozmo_sem_rodas_patch = False
        cli._cozmo_anim_id_seguro = False
        cli._next_anim_id = 256
        usados: list[int] = []

        def core(_pp: object) -> None:
            usados.append(int(cli._next_anim_id))
            cli._next_anim_id = int(cli._next_anim_id) + 1

        cli.play_anim = lambda _n: None
        cli.play_anim_group = lambda _g: None
        cli.play_anim_ppclip = core
        cli._cozmo_ppclip_core = core
        instalar_play_anim_sem_rodas_na_base(cli, preso_na_base_fn=lambda: True)
        instalar_play_anim_sem_rodas_na_base(cli, preso_na_base_fn=lambda: True)
        pp = pycozmo_anim.PreprocessedClip(
            {0: [protocol_encoder.DisplayImage(image=b"\x01\x02")]}
        )
        cli.play_anim_ppclip(pp)
        self.assertEqual(usados, [1])


if __name__ == "__main__":
    os.environ.setdefault("PYTHONPATH", "src")
    unittest.main()
