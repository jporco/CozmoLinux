"""Proteções de sessão UDP — mutex de reconnect e circuit breaker."""

from __future__ import annotations

import os
import threading
import time


class GuardSessao:
    """Evita reconnect concorrente e flood de resets (COZMO 01 na tela)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._reconnect_em = 0.0
        self._falhas = 0
        self._circuito_aberto_ate = 0.0

    def cooldown_s(self) -> float:
        return float(os.environ.get("COZMO_RATIO_PREVENT_COOLDOWN_S", "25"))

    def max_falhas(self) -> int:
        return int(os.environ.get("COZMO_RECONNECT_MAX_FAIL", "3"))

    def circuito_s(self) -> float:
        return float(os.environ.get("COZMO_RECONNECT_CIRCUIT_S", "90"))

    def circuito_aberto(self) -> bool:
        return time.monotonic() < self._circuito_aberto_ate

    def pode_reconectar(self) -> bool:
        if self.circuito_aberto():
            return False
        return time.monotonic() - self._reconnect_em >= self.cooldown_s()

    def tentar_reconectar(self, *, forcar: bool = False) -> bool:
        """Adquire lock exclusivo; False = outro reconnect em curso ou cooldown."""
        if self.circuito_aberto():
            return False
        if not forcar and not self.pode_reconectar():
            return False
        ok = self._lock.acquire(blocking=False)
        if ok:
            self._reconnect_em = time.monotonic()
        return ok

    def liberar(self, *, sucesso: bool) -> None:
        try:
            if sucesso:
                self._falhas = 0
            else:
                self._falhas += 1
                if self._falhas >= self.max_falhas():
                    self._circuito_aberto_ate = time.monotonic() + self.circuito_s()
                    self._falhas = 0
        finally:
            if self._lock.locked():
                self._lock.release()
