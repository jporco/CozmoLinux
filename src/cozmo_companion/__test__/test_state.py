"""Estado central: base física vence modo livre."""

from __future__ import annotations

import unittest

from cozmo_companion.core.state import CozmoMode, HardwareSnapshot, decide_state


class TestCozmoState(unittest.TestCase):
    def test_livre_armado_no_carregador_nao_libera_rodas(self) -> None:
        s = decide_state(
            HardwareSnapshot(
                button_base=True,
                free_requested=True,
                on_charger=True,
                charging=True,
                picked_up=False,
                sleeping=False,
                quiet=False,
                rx_ok=True,
            )
        )
        self.assertEqual(s.mode, CozmoMode.FREE_READY)
        self.assertTrue(s.effective_base)
        self.assertFalse(s.wheels_allowed)

    def test_livre_fora_da_base_libera_movimento(self) -> None:
        s = decide_state(
            HardwareSnapshot(
                button_base=False,
                free_requested=True,
                on_charger=False,
                charging=False,
                picked_up=False,
                sleeping=False,
                quiet=False,
                rx_ok=True,
            )
        )
        self.assertEqual(s.mode, CozmoMode.FREE_EXPLORE)
        self.assertFalse(s.effective_base)
        self.assertTrue(s.movement_allowed)

    def test_recovery_bloqueia_extras(self) -> None:
        s = decide_state(
            HardwareSnapshot(
                button_base=False,
                free_requested=True,
                on_charger=False,
                charging=False,
                picked_up=False,
                sleeping=False,
                quiet=False,
                rx_ok=False,
                recovering=True,
            )
        )
        self.assertEqual(s.mode, CozmoMode.RECOVERY)
        self.assertFalse(s.camera_allowed)
        self.assertFalse(s.animation_allowed)


if __name__ == "__main__":
    unittest.main()
