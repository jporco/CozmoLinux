"""Stream 30fps desligado em carga 100%% — keeper clip na base."""
from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch


class TestChargerStreamCheia(unittest.TestCase):
    def test_stream_off_em_carga_cheia(self) -> None:
        from cozmo_companion.core import motor_cozmo as mc

        cli = MagicMock()
        with patch.dict(
            os.environ,
            {
                "COZMO_CHARGER_PLAY_STREAM": "1",
                "COZMO_CHARGER_STREAM_NA_CHEIA": "0",
            },
            clear=False,
        ):
            with patch.object(mc, "base_oled_carga_cheia_ativo", return_value=True):
                self.assertFalse(mc._charger_play_stream(cli))

    def test_stream_on_se_explicito_na_cheia(self) -> None:
        from cozmo_companion.core import motor_cozmo as mc

        cli = MagicMock()
        with patch.dict(
            os.environ,
            {
                "COZMO_CHARGER_PLAY_STREAM": "1",
                "COZMO_CHARGER_STREAM_NA_CHEIA": "1",
            },
            clear=False,
        ):
            with patch.object(mc, "base_oled_carga_cheia_ativo", return_value=True):
                self.assertTrue(mc._charger_play_stream(cli))


if __name__ == "__main__":
    unittest.main()
