"""Limites do PC (cérebro) — tráfego UDP e ritmo de comandos ao Cozmo."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class LimitesCerebro:
    """Valores lidos de config.env — uma fonte para ajuste fino."""

    udp_ratio_leve: float
    udp_ratio_max: float
    rx_stall_s: float
    post_reconnect_s: float
    udp_quiet_s: float
    tts_post_quiet_s: float
    tts_pre_quiet_s: float
    base_anim_min_s: float
    espirito_pos_anim_s: float
    tts_max_base: int
    tts_max_mesa: int
    tts_chunk_pacotes: int
    tts_chunk_pausa_s: float
    tts_grace_s: float


def limites() -> LimitesCerebro:
    return LimitesCerebro(
        udp_ratio_leve=float(os.environ.get("COZMO_UDP_RATIO_LEVE", "1.35")),
        udp_ratio_max=float(os.environ.get("COZMO_UDP_RATIO_MAX", "1.75")),
        rx_stall_s=float(os.environ.get("COZMO_RX_STALL_S", "12")),
        post_reconnect_s=float(os.environ.get("COZMO_POST_RECONNECT_S", "60")),
        udp_quiet_s=float(os.environ.get("COZMO_UDP_QUIET_S", "25")),
        tts_post_quiet_s=float(os.environ.get("COZMO_TTS_POST_QUIET_S", "28")),
        tts_pre_quiet_s=float(os.environ.get("COZMO_TTS_PRE_QUIET_S", "5")),
        base_anim_min_s=float(os.environ.get("BASE_ANIM_MIN_S", "14")),
        espirito_pos_anim_s=float(os.environ.get("ESPIRITO_POS_ANIM_S", "12")),
        tts_max_base=int(os.environ.get("TTS_MAX_PACOTES_BASE", "1")),
        tts_max_mesa=int(os.environ.get("TTS_MAX_PACOTES", "1")),
        tts_chunk_pacotes=int(os.environ.get("TTS_CHUNK_PACOTES", "1")),
        tts_chunk_pausa_s=float(os.environ.get("TTS_CHUNK_PAUSA_S", "4.0")),
        tts_grace_s=float(os.environ.get("TTS_UDP_GRACE_S", "18")),
    )
