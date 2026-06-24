"""Sons curtos de reacao ao ambiente no alto-falante do Cozmo."""

from __future__ import annotations

import logging
import os
import time

import pycozmo
from pycozmo import protocol_encoder

from cozmo_companion.core.som_notif import gerar_frame_beep
from cozmo_companion.voice.tts import (
    _enviar_sinal_udp,
    _respiro_udp,
    estabilizar_pos_audio,
    pulso_ping,
    rx_frames,
)

logger = logging.getLogger("cozmo.som")


_PADROES: dict[str, tuple[tuple[float, int], ...]] = {
    "susto": ((1320, 27000), (860, 23000), (1180, 26000), (720, 21000), (980, 21000)),
    "curioso": ((740, 22000), (980, 25000), (1240, 24000), (860, 21000)),
    "latido": ((520, 30000), (0, 0), (650, 30000), (0, 0), (520, 27000), (720, 24000)),
    "feliz": ((880, 22000), (1120, 25000), (1480, 24000), (1120, 22000), (920, 21000)),
}


def pacotes_som_reacao(tipo: str = "susto") -> list[protocol_encoder.OutputAudio]:
    """Gera pacotes u-law pequenos, sem depender de espeak/paplay."""
    padrao = _PADROES.get(tipo, _PADROES["curioso"])
    max_pkts = max(1, int(os.environ.get("SOM_REACAO_PACOTES", "6")))
    phase = 0.0
    pkts: list[protocol_encoder.OutputAudio] = []
    for freq, amp in padrao[:max_pkts]:
        pkt, phase = gerar_frame_beep(freq_hz=max(1.0, freq), amplitude=amp, phase=phase)
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
    boost = int(os.environ.get("SOM_REACAO_VOLUME_BOOST", "3500"))
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

    pausa = float(os.environ.get("SOM_REACAO_PAUSA_S", "0.035"))
    respiro = float(os.environ.get("SOM_REACAO_RESPIRO_S", "0.06"))
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
