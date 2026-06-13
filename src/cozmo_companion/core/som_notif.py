"""Som curto de notificação — delega para notifications.core.som (WAV + pipeline TTS)."""

from __future__ import annotations

import math

from pycozmo import protocol_encoder
from pycozmo.audio import u_law_encoding
from pycozmo import robot

FRAME_S = 1.0 / robot.FRAME_RATE
_SAMPLES = 744


def gerar_frame_beep(
    *,
    freq_hz: float = 880.0,
    amplitude: int = 14000,
    phase: float = 0.0,
) -> tuple[protocol_encoder.OutputAudio, float]:
    """Fallback sintético — sem espeak/paplay no PC."""
    sr = _SAMPLES / FRAME_S
    out = bytearray(_SAMPLES)
    for i in range(_SAMPLES):
        t = phase + i / sr
        sample = int(amplitude * math.sin(2.0 * math.pi * freq_hz * t))
        out[i] = min(255, max(0, u_law_encoding(sample)))
    return protocol_encoder.OutputAudio(samples=bytes(out)), phase + _SAMPLES / sr


def pacotes_beep_notif() -> list[protocol_encoder.OutputAudio]:
    """Rajada curta — usado só se assets/beep_notif.wav ausente."""
    import os

    n = max(1, int(os.environ.get("NOTIF_SOM_PACOTES", "4")))
    freq = float(os.environ.get("NOTIF_SOM_FREQ_HZ", "880"))
    amp = int(os.environ.get("NOTIF_SOM_AMP", "15000"))
    pkts: list[protocol_encoder.OutputAudio] = []
    phase = 0.0
    for i in range(n):
        f = freq * (1.0 + 0.08 * i)
        pkt, phase = gerar_frame_beep(freq_hz=f, amplitude=amp, phase=phase)
        pkts.append(pkt)
    return pkts


def tocar_som_notif(
    cli,
    *,
    manter_face: bool = True,
    volume: int | None = None,
) -> bool:
    from cozmo_companion.notifications.core.som import tocar_beep_notif

    return tocar_beep_notif(cli, manter_face=manter_face, volume=volume)
