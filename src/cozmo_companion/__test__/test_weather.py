"""Testes do clima Bagé."""

import unittest
from unittest.mock import MagicMock, patch

from cozmo_companion.weather.bage import BageWeather, Clima


class TestBageWeather(unittest.TestCase):
    @patch.object(BageWeather, "temperatura", return_value=22.4)
    def test_texto_tela_com_cache(self, _temp: MagicMock) -> None:
        w = BageWeather()
        self.assertIn("Bagé-RS", w.texto_tela())
        self.assertIn("22", w.texto_tela())
        self.assertLessEqual(len(w.texto_tela()), 16)

    @patch.object(BageWeather, "_buscar", return_value=None)
    def test_frase_sem_dados(self, _buscar: MagicMock) -> None:
        w = BageWeather()
        w._cache = None
        self.assertIn("Bagé-RS", w.frase())

    @patch("cozmo_companion.weather.bage.requests.get")
    def test_busca_open_meteo_usa_bage_rs(self, get: MagicMock) -> None:
        resp = MagicMock()
        resp.json.return_value = {"current": {"temperature_2m": 9.2}}
        get.return_value = resp
        w = BageWeather()

        clima = w._buscar()

        self.assertIsNotNone(clima)
        _, kwargs = get.call_args
        params = kwargs["params"]
        self.assertEqual(params["latitude"], -31.3317)
        self.assertEqual(params["longitude"], -54.1069)
        self.assertEqual(params["timezone"], "America/Sao_Paulo")
        self.assertEqual(params["current"], "temperature_2m")


if __name__ == "__main__":
    unittest.main()
