"""Beep de notificação — alto-falante do Cozmo (PC opcional via NOTIF_PC_BEEP)."""

from __future__ import annotations

import logging
import os
import subprocess
import time
from pathlib import Path

import pycozmo
from pycozmo import protocol_encoder

from cozmo_companion.voice.tts import (
    _enviar_sinal_udp,
    _load_wav,
    _respiro_udp,
    estabilizar_pos_audio,
    pulso_ping,
    rx_frames,
)

logger = logging.getLogger("cozmo.notif.som")

_ASSETS = Path(__file__).resolve().parents[4] / "assets"
_BEEP_WAV = _ASSETS / "beep_notif.wav"


def _gerar_beep_wav(caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["espeak", "-q", "-v", "pt-br", "-s", "380", "-p", "80", "-a", "200", "-w", str(caminho), "bip"],
        check=True,
        capture_output=True,
    )


def pacotes_beep_notif() -> list[protocol_encoder.OutputAudio]:
    if not _BEEP_WAV.is_file():
        try:
            _gerar_beep_wav(_BEEP_WAV)
        except (OSError, subprocess.CalledProcessError):
            pass
        if not _BEEP_WAV.is_file():
            from cozmo_companion.core.som_notif import pacotes_beep_notif as sintetico

            return sintetico()
    pkts = _load_wav(_BEEP_WAV)
    if not pkts:
        from cozmo_companion.core.som_notif import pacotes_beep_notif as sintetico

        return sintetico()
    lim = max(1, int(os.environ.get("NOTIF_SOM_PACOTES", "3")))
    if len(pkts) < lim:
        base = list(pkts)
        while len(pkts) < lim and base:
            pkts.extend(base)
    return pkts[:lim]


def _pc_audio_permitido() -> bool:
    """Beep no PC só quando NOTIF_PC_AUDIO=1 e NOTIF_PC_BEEP=1."""
    if os.environ.get("NOTIF_PC_AUDIO", "0") == "1":
        return os.environ.get("NOTIF_PC_BEEP", "0") == "1"
    return False


def _beep_pc() -> bool:
    if not _pc_audio_permitido():
        return False
    import shutil

    if not _BEEP_WAV.is_file():
        try:
            _gerar_beep_wav(_BEEP_WAV)
        except (OSError, subprocess.CalledProcessError):
            return False
    vol = os.environ.get("NOTIF_PC_BEEP_VOLUME", "65536")
    wav = str(_BEEP_WAV)
    paplay = shutil.which("paplay")
    if paplay:
        cmd = [paplay, f"--volume={vol}", wav]
        try:
            sink = subprocess.run(
                ["pactl", "get-default-sink"],
                capture_output=True,
                text=True,
                timeout=2,
            ).stdout.strip()
            if sink:
                cmd = [paplay, f"--device={sink}", f"--volume={vol}", wav]
            if subprocess.run(cmd, capture_output=True, timeout=8).returncode == 0:
                logger.info("beep PC ok (paplay vol=%s)", vol)
                return True
        except (OSError, subprocess.TimeoutExpired):
            pass
    return False


def tocar_beep_notif(
    cli: pycozmo.Client,
    *,
    manter_face: bool = True,
    volume: int | None = None,
) -> bool:
    from cozmo_companion.core.charger import em_base
    from cozmo_companion.core.motor_cozmo import (
        ligar_oled_base,
        manter_sono_ppclip,
        modo_sono_oled_ativo,
        modo_tts_preparar,
        modo_tts_restaurar,
        ping_oob,
        sono_oled_texto_ativo,
    )

    pkts = pacotes_beep_notif()
    if not pkts:
        return False
    pc_ok = _beep_pc() if _pc_audio_permitido() else False

    na_base = em_base(cli)
    vol = max(62000, min(65535, volume or int(os.environ.get("COZMO_VOLUME", "62000"))))
    try:
        cli.set_volume(vol)
    except Exception as exc:
        logger.warning("set_volume beep: %s", exc)

    rx_antes = rx_frames(cli)
    if manter_face and na_base and not sono_oled_texto_ativo():
        from cozmo_companion.core.charger import definir_oled_preso_na_base

        definir_oled_preso_na_base(True)
        if modo_sono_oled_ativo():
            manter_sono_ppclip(cli)
        else:
            ligar_oled_base(cli, forcar=False, preso_na_base=True)
        face_was, anim_was = True, True
    else:
        face_was, anim_was = modo_tts_preparar(cli)

    pausa = float(os.environ.get("NOTIF_SOM_PAUSA_S", "0.04"))
    respiro = float(os.environ.get("NOTIF_SOM_RESPIRO_S", "0.1"))
    enviados = 0
    try:
        pulso_ping(cli, 2)
        for i, pkt in enumerate(pkts):
            _enviar_sinal_udp(cli, pkt, manter_face=manter_face and na_base)
            enviados += 1
            logger.info("play_audio notif pkt %d/%d", i + 1, len(pkts))
            _respiro_udp(cli, respiro)
            if i < len(pkts) - 1:
                time.sleep(pausa)
        pulso_ping(cli, 1)
        drain = float(os.environ.get("NOTIF_SOM_DRAIN_S", os.environ.get("TTS_DRAIN_S", "0.9")))
        fim = time.monotonic() + drain
        while time.monotonic() < fim:
            if cli.anim_controller.queue.is_empty():
                break
            pulso_ping(cli, 1)
            time.sleep(0.08)
        estabilizar_pos_audio(cli, rx_antes)
        logger.info(
            "play_audio notif beep ok (%d pacotes, vol=%d, base=%s, pc=%s)",
            enviados,
            vol,
            na_base,
            pc_ok,
        )
        return enviados > 0
    except Exception as exc:
        logger.warning("Beep notif falhou: %s", exc)
        return False
    finally:
        modo_tts_restaurar(cli, face_was, anim_was, na_base=na_base)
        ping_oob(cli, 1)
