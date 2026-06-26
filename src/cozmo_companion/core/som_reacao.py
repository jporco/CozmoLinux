"""Sons curtos de reacao ao ambiente no alto-falante do Cozmo."""

from __future__ import annotations

import logging
import math
import os
import time

import pycozmo
from pycozmo import protocol_encoder, robot

from cozmo_companion.voice.tts import (
    _enviar_sinal_udp,
    _respiro_udp,
    estabilizar_pos_audio,
    pulso_ping,
    rx_frames,
)

logger = logging.getLogger("cozmo.som")


_SAMPLES_POR_FRAME = 744
_FRAME_RATE = _SAMPLES_POR_FRAME * robot.FRAME_RATE

# (freq_hz, amplitude, frames). Mais frames por nota evita o "estalo" de
# um unico pacote e deixa o alto-falante do Cozmo soar mais parecido com bleeps
# expressivos do app original.
_PADROES: dict[str, tuple[tuple[float, int, int], ...]] = {
    "susto": (
        (1320, 30000, 2),
        (940, 28000, 3),
        (1240, 31000, 2),
        (760, 26000, 2),
    ),
    "curioso": (
        (620, 26000, 3),
        (820, 30000, 3),
        (1120, 31000, 4),
        (900, 25000, 2),
    ),
    "latido": (
        (360, 32700, 3),
        (520, 32700, 4),
        (0, 0, 1),
        (430, 32700, 3),
        (660, 32000, 4),
        (0, 0, 1),
        (520, 28500, 2),
    ),
    "feliz": (
        (760, 26000, 3),
        (980, 30000, 3),
        (1280, 31500, 4),
        (1040, 28500, 3),
        (1360, 30000, 3),
    ),
}


def _amostra_ulaw(valor: float) -> int:
    return pycozmo.audio.u_law_encoding(max(-32768, min(32767, int(valor)))) & 0xFF


def _frame_tom(freq_hz: float, amplitude: int, phase: float, *, fade_in: bool, fade_out: bool) -> tuple[protocol_encoder.OutputAudio, float]:
    if freq_hz <= 0 or amplitude <= 0:
        samples = bytes(_amostra_ulaw(0) for _ in range(_SAMPLES_POR_FRAME))
        return protocol_encoder.OutputAudio(samples=samples), phase

    step = 2.0 * math.pi * freq_hz / _FRAME_RATE
    raw = bytearray()
    for i in range(_SAMPLES_POR_FRAME):
        env = 1.0
        if fade_in:
            env = min(env, i / 96.0)
        if fade_out:
            env = min(env, (_SAMPLES_POR_FRAME - 1 - i) / 96.0)
        raw.append(_amostra_ulaw(math.sin(phase) * amplitude * max(0.0, env)))
        phase = (phase + step) % (2.0 * math.pi)
    return protocol_encoder.OutputAudio(samples=bytes(raw)), phase


def pacotes_som_reacao(tipo: str = "susto") -> list[protocol_encoder.OutputAudio]:
    """Gera uma frase sonora curta em u-law direto para o alto-falante do Cozmo."""
    padrao = _PADROES.get(tipo, _PADROES["curioso"])
    max_pkts = max(1, int(os.environ.get("SOM_REACAO_PACOTES", "14")))
    phase = 0.0
    pkts: list[protocol_encoder.OutputAudio] = []
    for freq, amp, frames in padrao:
        for frame in range(max(1, frames)):
            if len(pkts) >= max_pkts:
                return pkts
            pkt, phase = _frame_tom(
                freq,
                amp,
                phase,
                fade_in=frame == 0,
                fade_out=frame == frames - 1,
            )
            pkts.append(pkt)
    return pkts


def tocar_som_reacao(
    cli: pycozmo.Client,
    *,
    tipo: str = "susto",
    manter_face: bool = True,
    volume: int | None = None,
) -> bool:
    """Toca uma reacao curta pelo Cozmo e drena a sessao UDP."""
    from cozmo_companion.core.charger import em_base
    from cozmo_companion.core.motor_cozmo import (
        base_oled_loop_segurado,
        ligar_oled_base,
        manter_sono_ppclip,
        modo_sono_oled_ativo,
        modo_tts_preparar,
        modo_tts_restaurar,
        ping_oob,
        sono_oled_texto_ativo,
    )

    if os.environ.get("SOM_REACAO_ENABLED", "1") != "1":
        return False
    pkts = pacotes_som_reacao(tipo)
    if not pkts:
        return False

    na_base = em_base(cli)
    base_vol = volume if volume is not None else int(os.environ.get("COZMO_VOLUME", "62000"))
    boost = int(os.environ.get("SOM_REACAO_VOLUME_BOOST", "8000"))
    vol = max(30000, min(65535, base_vol + boost))
    try:
        cli.set_volume(vol)
    except Exception as exc:
        logger.debug("set_volume som reacao: %s", exc)

    rx_antes = rx_frames(cli)
    if manter_face and na_base and not sono_oled_texto_ativo():
        from cozmo_companion.core.charger import definir_oled_preso_na_base

        definir_oled_preso_na_base(True)
        if modo_sono_oled_ativo():
            manter_sono_ppclip(cli)
        elif not base_oled_loop_segurado():
            ligar_oled_base(cli, forcar=False, preso_na_base=True)
        face_was, anim_was = True, True
    else:
        face_was, anim_was = modo_tts_preparar(cli)

    pausa = float(os.environ.get("SOM_REACAO_PAUSA_S", "0.006"))
    respiro = float(os.environ.get("SOM_REACAO_RESPIRO_S", "0.025"))
    enviados = 0
    try:
        pulso_ping(cli, 2)
        for i, pkt in enumerate(pkts):
            _enviar_sinal_udp(cli, pkt, manter_face=manter_face and na_base)
            enviados += 1
            _respiro_udp(cli, respiro)
            if i < len(pkts) - 1:
                time.sleep(pausa)
        pulso_ping(cli, 1)
        estabilizar_pos_audio(cli, rx_antes)
        logger.info("Som reacao %s ok (%d pacotes, vol=%d)", tipo, enviados, vol)
        return enviados > 0
    except Exception as exc:
        logger.warning("Som reacao %s falhou: %s", tipo, exc)
        return False
    finally:
        modo_tts_restaurar(cli, face_was, anim_was, na_base=na_base)
        ping_oob(cli, 1)
