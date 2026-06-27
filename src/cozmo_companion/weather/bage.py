"""Clima de Bagé via Open-Meteo (sem API key)."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass

import requests

logger = logging.getLogger("cozmo.weather")

BAGE_LAT = -31.3317
BAGE_LON = -54.1069
FUSO = "America/Sao_Paulo"


@dataclass
class Clima:
    temperatura_c: float
    atualizado_em: float


class BageWeather:
    def __init__(self) -> None:
        self.lat = float(os.environ.get("BAGE_LAT", BAGE_LAT))
        self.lon = float(os.environ.get("BAGE_LON", BAGE_LON))
        self.cidade = os.environ.get("BAGE_CIDADE", "Bagé-RS")
        self.tz = os.environ.get("BAGE_TZ", FUSO)
        self.cache_seg = float(os.environ.get("WEATHER_CACHE_S", 600))
        self._cache: Clima | None = None

    def _buscar(self) -> Clima | None:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": self.lat,
            "longitude": self.lon,
            "current": "temperature_2m",
            "timezone": self.tz,
        }
        try:
            r = requests.get(url, params=params, timeout=8)
            r.raise_for_status()
            temp = float(r.json()["current"]["temperature_2m"])
            return Clima(temperatura_c=temp, atualizado_em=time.time())
        except (requests.RequestException, KeyError, ValueError, TypeError) as exc:
            logger.warning("Clima indisponível: %s", exc)
            return None

    def clima(self) -> Clima | None:
        if self._cache and (time.time() - self._cache.atualizado_em) < self.cache_seg:
            return self._cache
        novo = self._buscar()
        if novo:
            self._cache = novo
        return self._cache

    def temperatura(self) -> float | None:
        c = self.clima()
        return c.temperatura_c if c else None

    def frase(self) -> str:
        t = self.temperatura()
        if t is None:
            return f"Não consegui ver a temperatura de {self.cidade} agora."
        graus = round(t)
        return f"Em {self.cidade} estão {graus} graus agora."

    def texto_tela(self) -> str:
        t = self.temperatura()
        if t is None:
            return f"{self.cidade} ?C"
        return f"{self.cidade} {round(t)}C"
