"""Texto → áudio no Cozmo — ritmo 30 fps + ping UDP (evita COZMO 01)."""

from __future__ import annotations

import logging
import math
import os
import re
import struct
import subprocess
import tempfile
import time
import wave
from pathlib import Path
from typing import Callable

import pycozmo
from pycozmo import protocol_encoder
from pycozmo.audio import u_law_encoding
from pycozmo import robot

from cozmo_companion.voice.resposta import encurtar_fala

logger = logging.getLogger("cozmo.tts")

FRAME_S = 1.0 / robot.FRAME_RATE
CHUNK_PACOTES = int(os.environ.get("TTS_CHUNK_PACOTES", "3"))
CHUNK_PAUSA_S = float(os.environ.get("TTS_CHUNK_PAUSA_S", "1.4"))
PACOTE_MS = float(os.environ.get("TTS_PACKET_MS", "35"))
ESPEAK_RATE = int(os.environ.get("TTS_ESPEAK_RATE", "175"))


def _enviar_sinal_udp(
    cli: pycozmo.Client,
    pkt: protocol_encoder.OutputAudio,
    *,
    manter_face: bool = False,
) -> None:
    """Um pacote de áudio — na base ppclip: UDP direto (evita EOF na fila anim)."""
    from cozmo_companion.core.motor_cozmo import enviar_audio_fila, ping_oob, ppclip_base_ativo

    if ppclip_base_ativo(cli):
        try:
            cli.conn.send(pkt)
            time.sleep(max(FRAME_S * 2, 0.05))
        except Exception as exc:
            logger.debug("sinal UDP direto falhou (%s) — fallback fila", exc)
            enviar_audio_fila(cli, pkt, manter_face=manter_face)
    else:
        enviar_audio_fila(cli, pkt, manter_face=manter_face)
    if not manter_face:
        ping_oob(cli, 1)


def rx_estavel_pos_tts(cli: pycozmo.Client, rx_antes: int, segundos: float = 6.0) -> bool:
    """RX precisa subir e continuar — evita falso positivo pós-TTS."""
    fim = time.monotonic() + max(2.0, segundos)
    pico = rx_frames(cli)
    while time.monotonic() < fim:
        pulso_ping(cli, 1)
        rx = rx_frames(cli)
        if rx > pico:
            pico = rx
        time.sleep(0.45)
    return pico > rx_antes


def pulso_ping(cli: pycozmo.Client, vezes: int = 1) -> None:
    """Ping OOB — só quando a fila 30 fps não está ativa."""
    from cozmo_companion.core.motor_cozmo import ping_oob

    ping_oob(cli, vezes)


def rx_frames(cli: pycozmo.Client) -> int:
    conn = getattr(cli, "conn", None)
    recv = getattr(conn, "recv_thread", None) if conn else None
    return int(getattr(recv, "received_frames", 0) if recv else 0)


def estabilizar_pos_audio(cli: pycozmo.Client, rx_antes: int) -> bool:
    """Sinal curto: 1 pkt não obriga incremento de rx — basta sessão viva."""
    from cozmo_companion.core.conexao import conexao_ok, sessao_viva

    if os.environ.get("TTS_MODO", "sinal").strip().lower() == "sinal":
        time.sleep(0.4)
        if conexao_ok(cli) or sessao_viva(cli):
            return True
    tentativas = int(os.environ.get("TTS_RX_RETRY", "3"))
    for n in range(tentativas):
        pulso_ping(cli, 1)
        rx = rx_frames(cli)
        if rx > rx_antes:
            logger.debug("RX ok pós-TTS (+%d, tentativa %d)", rx - rx_antes, n + 1)
            return True
        time.sleep(0.35)
    if conexao_ok(cli):
        return True
    logger.warning("RX parado pós-TTS (%d→%d)", rx_antes, rx_frames(cli))
    return False


def _bytes_to_cozmo(byte_string: bytes, rate_correction: int, channels: int) -> bytearray:
    out = bytearray(744)
    n = channels * rate_correction
    bs = struct.unpack(f"{int(len(byte_string) / 2)}h", byte_string)[0::n]
    for i, s in enumerate(bs):
        out[i] = min(255, max(0, u_law_encoding(s)))
    return out


def _load_wav(caminho: Path) -> list[protocol_encoder.OutputAudio]:
    pkts: list[protocol_encoder.OutputAudio] = []
    try:
        wf = wave.open(str(caminho), "r")
    except EOFError as exc:
        raise RuntimeError("WAV vazio ou truncado") from exc
    with wf as w:
        sampwidth = w.getsampwidth()
        framerate = w.getframerate()
        if sampwidth != 2 or framerate not in (22050, 48000):
            raise ValueError(
                f"Formato inválido ({sampwidth * 8} bit, {framerate} Hz). "
                "Esperado: 16 bit, 22050 ou 48000 Hz."
            )
        ratediv = 2 if framerate == 48000 else 1
        channels = w.getnchannels()
        while True:
            try:
                frame_in = w.readframes(744 * ratediv)
            except EOFError:
                break
            if not frame_in:
                break
            frame_out = _bytes_to_cozmo(frame_in, ratediv, channels)
            pkts.append(protocol_encoder.OutputAudio(samples=frame_out))
    return pkts


def _amostra_ulaw(valor: float) -> int:
    return u_law_encoding(max(-32768, min(32767, int(valor)))) & 0xFF


def _frame_tom_sinal(
    freq_hz: float,
    amplitude: int,
    phase: float,
    *,
    fade_in: bool,
    fade_out: bool,
) -> tuple[protocol_encoder.OutputAudio, float]:
    samples_por_frame = 744
    if freq_hz <= 0 or amplitude <= 0:
        samples = bytes(_amostra_ulaw(0) for _ in range(samples_por_frame))
        return protocol_encoder.OutputAudio(samples=samples), phase

    sr = samples_por_frame / FRAME_S
    step = 2.0 * math.pi * freq_hz / sr
    ramp = 110.0
    out = bytearray(samples_por_frame)
    for i in range(samples_por_frame):
        env = 1.0
        if fade_in:
            env = min(env, i / ramp)
        if fade_out:
            env = min(env, (samples_por_frame - 1 - i) / ramp)
        sample = math.sin(phase) * amplitude * max(0.0, env)
        out[i] = _amostra_ulaw(sample)
        phase = (phase + step) % (2.0 * math.pi)
    return protocol_encoder.OutputAudio(samples=bytes(out)), phase


def _padrao_sinal(texto: str) -> tuple[tuple[float, int], ...]:
    t = texto.strip().lower()
    if t.startswith(("oi", "ola", "olá")):
        return ((740.0, 1), (980.0, 2), (1240.0, 1))
    if t.startswith("opa"):
        return ((620.0, 1), (880.0, 1), (1180.0, 2))
    if t.startswith(("tchau", "xau")):
        return ((1040.0, 1), (820.0, 1), (620.0, 2))
    if t.startswith(("tempo", "chuva", "grau")):
        return ((560.0, 1), (760.0, 1), (960.0, 1), (760.0, 1))
    if t.startswith(("hora", "sao", "são")):
        return ((960.0, 1), (760.0, 2), (960.0, 1))
    if t.startswith(("au", "ao")):
        return ((360.0, 2), (520.0, 2), (0.0, 1), (460.0, 1))
    return ((660.0, 1), (900.0, 1), (1120.0, 2))


def _pkts_sinal_sintetico(texto: str = "") -> list[protocol_encoder.OutputAudio]:
    """Bipes curtos no formato nativo do Cozmo, sem voz do PC/espeak."""
    limite = max(1, int(os.environ.get("TTS_SINAL_PACOTES", "6")))
    amp = max(3000, min(22000, int(os.environ.get("TTS_SINAL_AMP", "14500"))))
    phase = 0.0
    pkts: list[protocol_encoder.OutputAudio] = []
    for freq, frames in _padrao_sinal(texto):
        for frame in range(max(1, frames)):
            if len(pkts) >= limite:
                return pkts
            pkt, phase = _frame_tom_sinal(
                freq,
                amp if freq > 0 else 0,
                phase,
                fade_in=frame == 0,
                fade_out=frame == frames - 1,
            )
            pkts.append(pkt)
    return pkts


def _pkts_sinal_fallback() -> list[protocol_encoder.OutputAudio]:
    """Fallback sintético curto — sem espeak/paplay no PC."""
    return _pkts_sinal_sintetico("beep")


def _espeak_wav(caminho: Path, texto: str, voz: str) -> None:
    """Gera WAV via espeak/espeak-ng sem abrir a saída de áudio do PC."""
    bins = ("espeak-ng", "espeak")
    last_err: Exception | None = None
    for bin_name in bins:
        try:
            with caminho.open("wb") as out:
                subprocess.run(
                    [
                        bin_name,
                        "--stdout",
                        "-v",
                        voz,
                        "-s",
                        str(ESPEAK_RATE),
                        "-g",
                        "4",
                        texto,
                    ],
                    check=True,
                    stdout=out,
                    stderr=subprocess.PIPE,
                )
            if caminho.is_file() and caminho.stat().st_size > 44:
                return
            last_err = RuntimeError(f"{bin_name} não gerou WAV válido")
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            last_err = exc
    if last_err:
        raise RuntimeError(f"espeak indisponível ou falhou: {last_err}") from last_err
    raise RuntimeError("espeak indisponível")


def _respiro_udp(
    cli: pycozmo.Client,
    segundos: float,
    *,
    entre_rajadas: Callable[[], None] | None = None,
    servir: Callable[[], None] | None = None,
) -> None:
    """Espera drenagem do áudio + ping periódico."""
    if entre_rajadas:
        entre_rajadas()
    fim = time.monotonic() + max(0.35, segundos)
    intervalo = float(os.environ.get("TTS_PING_INTERVAL_S", "0.75"))
    while time.monotonic() < fim:
        pulso_ping(cli, 1)
        if servir:
            servir()
        restante = fim - time.monotonic()
        if restante <= 0:
            break
        time.sleep(min(intervalo, restante))


def _duracao_pkts(n: int) -> float:
    cauda = float(os.environ.get("TTS_TAIL_S", "0.35"))
    return n * FRAME_S + cauda


def falar(
    cli: pycozmo.Client,
    texto: str,
    voz: str = "pt-br",
    *,
    max_pkts: int | None = None,
    entre_rajadas: Callable[[], None] | None = None,
    servir: Callable[[], None] | None = None,
    cancelar: Callable[[], bool] | None = None,
    manter_face: bool = False,
    na_base: bool = False,
) -> int:
    """
    Envia áudio em lotes no ritmo do AnimationController (30 fps).
    Um pacote por frame — nunca flood na fila UDP.
    """
    texto = encurtar_fala(texto.strip(), max_palavras=5, max_chars=28)
    modo_sinal_ativo = (
        os.environ.get("TTS_MODO", "sinal").strip().lower() == "sinal"
    )
    if modo_sinal_ativo:
        # Texto já veio de sinal_para na fila — não re-sortear palavra.
        if not re.fullmatch(r"[A-Za-zÁÀÂÃÉÊÍÓÔÕÚÜÇáàâãéêíóôõúüç]{1,10}", texto):
            from cozmo_companion.voice.sinal import sinal_para

            texto = sinal_para("", texto)
        chunk = 1
        pausa = float(os.environ.get("TTS_CHUNK_PAUSA_S", "1.6"))
    else:
        chunk = max(1, min(4, int(os.environ.get("TTS_CHUNK_PACOTES", str(CHUNK_PACOTES)))))
        pausa = float(os.environ.get("TTS_CHUNK_PAUSA_S", str(CHUNK_PAUSA_S)))
    if not texto:
        return 0
    if modo_sinal_ativo and os.environ.get("TTS_SINAL_AUDIO", "0") != "1":
        logger.info("TTS sinal sem audio sintetico: %s", texto[:40])
        return 0

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        caminho = Path(tmp.name)

    from cozmo_companion.core.motor_cozmo import modo_tts_preparar, modo_tts_restaurar

    if manter_face:
        from cozmo_companion.core.motor_cozmo import (
            _clip_loop_vivo,
            base_oled_loop_segurado,
            ligar_oled_base,
        )
        from cozmo_companion.core.charger import definir_oled_preso_na_base

        definir_oled_preso_na_base(na_base)
        if not base_oled_loop_segurado() and not _clip_loop_vivo():
            try:
                ligar_oled_base(cli, forcar=False, preso_na_base=na_base)
            except Exception:
                pass
        face_was, anim_was = True, True
    else:
        face_was, anim_was = modo_tts_preparar(cli)
    if not modo_sinal_ativo and not manter_face and os.environ.get("TTS_FACE_OFF", "1") != "1":
        cli.anim_controller.enable_procedural_face(True)

    try:
        usar_sinal_sintetico = (
            modo_sinal_ativo
            and os.environ.get("TTS_SINAL_AUDIO", "0") == "1"
            and os.environ.get("TTS_SINAL_VOZ", "0") != "1"
        )
        try:
            if usar_sinal_sintetico:
                pkts = _pkts_sinal_sintetico(texto)
                logger.debug("TTS sinal sintético: %s (%d pacotes)", texto, len(pkts))
            else:
                _espeak_wav(caminho, texto, voz)
                pkts = _load_wav(caminho)
        except Exception as exc:
            logger.warning("WAV TTS indisponível (%s) — sinal sintético", exc)
            pkts = _pkts_sinal_fallback()
        if not pkts:
            logger.warning("Áudio vazio para: %s", texto[:50])
            return 0

        limite = (
            max_pkts
            if max_pkts is not None
            else int(os.environ.get("TTS_MAX_PACOTES", "8"))
        )
        if len(pkts) > limite:
            pkts = pkts[:limite]
        if os.environ.get("TTS_MODO", "sinal").strip().lower() == "sinal":
            lim_sinal = max(
                1,
                max_pkts
                if max_pkts is not None
                else int(os.environ.get("TTS_SINAL_PACOTES", "1")),
            )
            pkts = pkts[:lim_sinal]

        total = len(pkts)
        logger.info("Falando (%d pacotes, 1/frame): %s", total, texto[:80])

        rx_antes = rx_frames(cli)
        pulso_ping(cli, 2)
        enviados = 0

        if modo_sinal_ativo:
            for i, pkt in enumerate(pkts):
                if cancelar and cancelar():
                    logger.info("TTS interrompido (%d/%d pacotes)", i, total)
                    break
                _enviar_sinal_udp(cli, pkt, manter_face=manter_face)
                enviados += 1
                if servir and enviados % 4 == 0:
                    servir()
            _respiro_udp(
                cli,
                float(os.environ.get("TTS_SINAL_PAUSA_S", "0.8")),
                entre_rajadas=entre_rajadas,
                servir=servir,
            )
            pulso_ping(cli, 1)
            estabilizar_pos_audio(cli, rx_antes)
            return enviados

        i = 0
        while i < total:
            if cancelar and cancelar():
                logger.info("TTS interrompido (%d/%d pacotes)", i, total)
                break
            pkt = pkts[i]
            from cozmo_companion.core.motor_cozmo import base_oled_modo_direto, enviar_audio_fila

            if na_base and base_oled_modo_direto():
                enviar_audio_fila(cli, pkt)
            else:
                cli.anim_controller.play_audio([pkt])
            enviados += 1
            _respiro_udp(
                cli,
                _duracao_pkts(1),
                entre_rajadas=entre_rajadas,
                servir=servir,
            )
            i += 1
            if i < total:
                logger.info("TTS pausa UDP (%d/%d pacotes)", i, total)
                _respiro_udp(cli, pausa, entre_rajadas=entre_rajadas, servir=servir)

        pulso_ping(cli, 2)
        fim_espera = time.monotonic() + float(os.environ.get("TTS_DRAIN_S", "1.8"))
        while time.monotonic() < fim_espera:
            if cli.anim_controller.queue.is_empty():
                break
            pulso_ping(cli, 1)
            if servir:
                servir()
            time.sleep(0.1)
        estabilizar_pos_audio(cli, rx_antes)
        return enviados
    finally:
        modo_tts_restaurar(cli, face_was, anim_was, na_base=na_base)
        caminho.unlink(missing_ok=True)
