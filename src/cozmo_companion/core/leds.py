"""Luzes do backpack — apagadas na base (rainbow fraco esporádico), piscando
colorido aleatório no modo livre. Nunca bloqueia; um passo por chamada."""

from __future__ import annotations

import colorsys
import os
import random
import time

from pycozmo import lights


def _cor(r: float, g: float, b: float) -> "lights.Color":
    return lights.Color(rgb=(int(r * 255), int(g * 255), int(b * 255)))


class LuzesBackpack:
    """Chamar tick(cli, na_base=...) periodicamente na thread principal."""

    def __init__(self) -> None:
        self._na_base_atual: bool | None = None
        self._proximo_evento = 0.0
        self._rainbow_ate = 0.0
        self._rainbow_hue = 0.0
        self._proximo_passo = 0.0

    @staticmethod
    def _apagar(cli) -> None:
        try:
            cli.set_backpack_lights_off()
        except Exception:
            pass

    def _passo_rainbow(self, cli) -> None:
        agora = time.monotonic()
        if agora < self._proximo_passo:
            return
        brilho = float(os.environ.get("COZMO_LED_BASE_BRILHO", "0.12"))
        r, g, b = colorsys.hsv_to_rgb(self._rainbow_hue, 1.0, max(0.02, min(1.0, brilho)))
        try:
            cli.set_all_backpack_lights(_cor(r, g, b))
        except Exception:
            pass
        self._rainbow_hue = (self._rainbow_hue + 0.05) % 1.0
        self._proximo_passo = agora + 0.12

    def _passo_aleatorio(self, cli) -> None:
        agora = time.monotonic()
        if agora < self._proximo_passo:
            return
        try:
            cli.set_all_backpack_lights(_cor(random.random(), random.random(), random.random()))
        except Exception:
            pass
        self._proximo_passo = agora + random.uniform(
            float(os.environ.get("COZMO_LED_LIVRE_MIN_S", "2.0")),
            float(os.environ.get("COZMO_LED_LIVRE_MAX_S", "5.0")),
        )

    def _agendar_proximo_rainbow(self, agora: float) -> None:
        self._proximo_evento = agora + random.uniform(
            float(os.environ.get("COZMO_LED_RAINBOW_MIN_S", "45")),
            float(os.environ.get("COZMO_LED_RAINBOW_MAX_S", "90")),
        )

    def tick(self, cli, *, na_base: bool) -> None:
        agora = time.monotonic()
        if na_base:
            if self._na_base_atual is not True:
                self._na_base_atual = True
                self._apagar(cli)
                self._rainbow_ate = 0.0
                self._agendar_proximo_rainbow(agora)
                return

            if self._rainbow_ate > 0:
                if agora >= self._rainbow_ate:
                    self._apagar(cli)
                    self._rainbow_ate = 0.0
                    self._agendar_proximo_rainbow(agora)
                else:
                    self._passo_rainbow(cli)
            elif agora >= self._proximo_evento:
                self._rainbow_hue = 0.0
                self._proximo_passo = 0.0
                self._rainbow_ate = agora + float(
                    os.environ.get("COZMO_LED_RAINBOW_DUR_S", "3.0")
                )
        else:
            if self._na_base_atual is not False:
                self._na_base_atual = False
                self._proximo_passo = 0.0
            self._passo_aleatorio(cli)
