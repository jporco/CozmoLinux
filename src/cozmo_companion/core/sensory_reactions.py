"""Converte movimento físico do Cozmo em eventos emocionais discretos."""

from __future__ import annotations

import math
import os
import time
from collections import deque
from enum import Enum
from typing import Callable


class SensorReaction(str, Enum):
    PICKED_UP = "picked_up"
    SHAKE = "shake"
    PUT_DOWN = "put_down"


class MotionReactionDetector:
    """Detecta pegar, colocar e sacudir sem enviar nada ao robô.

    O detector exige vários picos próximos para não confundir uma animação ou
    uma mudança normal de orientação com uma sacudida humana.
    """

    def __init__(self, callback: Callable[[SensorReaction], None]) -> None:
        self.callback = callback
        self._picked: bool | None = None
        self._accel: tuple[float, float, float] | None = None
        self._shake_hits: deque[float] = deque(maxlen=8)
        self._ultimo_shake = 0.0

    def update(self, cli: object, *, agora: float | None = None) -> None:
        now = time.monotonic() if agora is None else agora
        picked = bool(getattr(cli, "robot_picked_up", False))
        acc = getattr(cli, "accel", None)
        atual = (
            float(getattr(acc, "x", 0.0)),
            float(getattr(acc, "y", 0.0)),
            float(getattr(acc, "z", 0.0)),
        )

        if self._picked is None:
            self._picked = picked
        elif picked != self._picked:
            self._picked = picked
            self._shake_hits.clear()
            self.callback(
                SensorReaction.PICKED_UP if picked else SensorReaction.PUT_DOWN
            )

        anterior = self._accel
        self._accel = atual
        if not picked or anterior is None:
            # Preso na base/carregador o acelerômetro capta o próprio ppclip
            # mexendo a cabeça (jerk contínuo indistinguível de um sacudir real
            # sem o robô sair do chão) — testado e causava disparo falso a
            # cada ciclo de cooldown. Mantém shake só com robot_picked_up.
            return

        jerk = math.sqrt(sum((atual[i] - anterior[i]) ** 2 for i in range(3)))
        limiar = float(os.environ.get("COZMO_SHAKE_JERK", "0.85"))
        janela = float(os.environ.get("COZMO_SHAKE_WINDOW_S", "1.25"))
        hits_min = max(2, int(os.environ.get("COZMO_SHAKE_HITS", "3")))
        cooldown = float(os.environ.get("COZMO_SHAKE_COOLDOWN_S", "5"))
        if jerk < limiar:
            return
        self._shake_hits.append(now)
        while self._shake_hits and now - self._shake_hits[0] > janela:
            self._shake_hits.popleft()
        if len(self._shake_hits) >= hits_min and now - self._ultimo_shake >= cooldown:
            self._ultimo_shake = now
            self._shake_hits.clear()
            self.callback(SensorReaction.SHAKE)
