"""Testes do clima Bagé."""

import unittest
from unittest.mock import MagicMock, patch

from cozmo_companion.weather.bage import BageWeather, Clima


class TestBageWeather(unittest.TestCase):
    @patch.object(BageWeather, "temperatura", return_value=22.4)
    def test_texto_tela_com_cache(self, _temp: MagicMock) -> None:
        w = BageWeather()
        self.assertIn("22", w.texto_tela())

    @patch.object(BageWeather, "_buscar", return_value=None)
    def test_frase_sem_dados(self, _buscar: MagicMock) -> None:
        w = BageWeather()
        w._cache = None
        self.assertIn("Bagé", w.frase())


if __name__ == "__main__":
    unittest.main()
