"""Configuração tipada dos limites críticos de rede/UDP.

O restante das env vars será migrado incrementalmente. Estes campos foram
centralizados primeiro porque defaults divergentes mudavam a recuperação do link.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class NetworkTuning:
    wifi_offline_retry_s: float
    base_tx_stall: int
    udp_delta_tx_sat: int
    proc_rx_stall_s: float
    rx_stall_parado_s: float

    @classmethod
    def from_env(cls) -> "NetworkTuning":
        return cls(
            wifi_offline_retry_s=float(os.environ.get("COZMO_WIFI_OFFLINE_RETRY_S", "20")),
            base_tx_stall=int(os.environ.get("COZMO_BASE_TX_STALL", "280")),
            udp_delta_tx_sat=int(os.environ.get("COZMO_UDP_DELTA_TX_SAT", "500")),
            proc_rx_stall_s=float(os.environ.get("COZMO_PROC_RX_STALL_S", "120")),
            rx_stall_parado_s=float(os.environ.get("COZMO_RX_STALL_PARADO_S", "18")),
        )


def network_tuning() -> NetworkTuning:
    """Leitura barata e dinâmica para manter patch.dict útil nos testes."""
    return NetworkTuning.from_env()
