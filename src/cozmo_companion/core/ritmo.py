"""Ritmo natural — parado, busca rosto, animação ou eco; nunca robótico."""

from __future__ import annotations

import logging
import os
import random
import time
from collections import deque

logger = logging.getLogger("cozmo.ritmo")

ECO_CHANCE = float(os.environ.get("ECO_CHANCE", "0.10"))


def parece_latido(texto: str) -> bool:
    t = texto.lower().strip()
    if not t or len(t) > 24:
        return False
    if any(x in t for x in ("au au", "uau", "latido", "cachorro", "wow wow", "ham ham")):
        return True
    palavras = t.split()
    if palavras and all(p in ("au", "uau", "wow", "ham", "rrau", "raw", "gau") for p in palavras):
        return len(palavras) <= 3
    return t in ("au", "uau", "wow", "ham", "rrau")


class RitmoNatural:
    """Escolhe ações espaçadas — muito tempo parado, às vezes curioso."""

    def __init__(self) -> None:
        self._proxima = time.monotonic() + random.uniform(45, 120)
        self._parado_ate = 0.0
        self._ouvidos: deque[str] = deque(maxlen=8)
        self._ultimo_eco = 0.0
        self._acao_atual = "parado"

    @property
    def acao(self) -> str:
        return self._acao_atual

    @property
    def parado(self) -> bool:
        return time.monotonic() < self._parado_ate

    def registrar_fala(self, texto: str) -> None:
        t = texto.strip()
        if len(t) >= 3:
            self._ouvidos.append(t)

    def deve_ecoar(self) -> bool:
        agora = time.monotonic()
        if agora - self._ultimo_eco < 90:
            return False
        if not self._ouvidos:
            return False
        if random.random() > ECO_CHANCE:
            return False
        self._ultimo_eco = agora
        return True

    def texto_eco(self) -> str | None:
        if not self._ouvidos:
            return None
        return random.choice(list(self._ouvidos))

    def escolher_proxima(self) -> tuple[str, float]:
        """Retorna (ação, duração_s). Ações: parado, busca_rosto, anim, eco."""
        agora = time.monotonic()
        r = random.random()

        if r < 0.38:
            dur = random.uniform(90, 240)
            self._acao_atual = "parado"
            self._parado_ate = agora + dur
            self._proxima = self._parado_ate
            logger.debug("Ritmo: parado %.0fs", dur)
            return "parado", dur

        if r < 0.62:
            self._acao_atual = "anim"
            self._proxima = agora + random.uniform(45, 120)
            logger.debug("Ritmo: animação")
            return "anim", 0.0

        if r < 0.78:
            self._acao_atual = "explorar"
            self._proxima = agora + random.uniform(30, 90)
            logger.debug("Ritmo: explorar mesa")
            return "explorar", 0.0

        if r < 0.90:
            dur = random.uniform(8, 16)
            self._acao_atual = "busca_rosto"
            self._proxima = agora + dur + random.uniform(25, 70)
            logger.info("Ritmo: olhar rosto (~%.0fs)", dur)
            return "busca_rosto", dur

        if self._ouvidos and random.random() < 0.6:
            self._acao_atual = "eco"
            self._ultimo_eco = agora
            self._proxima = agora + random.uniform(120, 300)
            logger.info("Ritmo: repetindo o que ouviu")
            return "eco", 0.0

        dur = random.uniform(90, 240)
        self._acao_atual = "parado"
        self._parado_ate = agora + dur
        self._proxima = self._parado_ate
        return "parado", dur

    def tick(self) -> tuple[str, float] | None:
        if time.monotonic() < self._proxima:
            return None
        return self.escolher_proxima()

    def interromper_parado(self) -> None:
        """Quando alguém fala com ele, sai do modo parado."""
        self._parado_ate = 0.0
