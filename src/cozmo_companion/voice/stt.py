"""Escuta microfone — STT, latido, barulho alto."""

from __future__ import annotations

import json
import logging
import os
import queue
import struct
import threading
import time
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import sounddevice as sd
from vosk import KaldiRecognizer, Model

from cozmo_companion.core.ritmo import parece_latido
from cozmo_companion.voice.mic import nome_dispositivo, resolver_dispositivo
from cozmo_companion.voice.normalizar import normalizar_vosk
from cozmo_companion.voice.wake import contem_wake, parcial_wake_pronto

logger = logging.getLogger("cozmo.stt")

LIMIAR_RMS = int(os.environ.get("STT_RMS", "6"))
LOUD_RMS = int(os.environ.get("LOUD_RMS", "3200"))
EventoSom = Callable[[str, str | float], None]


def _rms(data: bytes) -> float:
    n = len(data) // 2
    if n == 0:
        return 0.0
    amostras = struct.unpack(f"{n}h", data)
    return (sum(s * s for s in amostras) / n) ** 0.5


VOSK_RATE = 16000


class Ouvinte:
    def __init__(
        self,
        modelo: Path,
        callback: Callable[[str], None],
        on_evento: Optional[EventoSom] = None,
        sample_rate: int = VOSK_RATE,
        device: Optional[int] = None,
        blocksize: int = 4000,
    ):
        if not modelo.is_dir():
            raise FileNotFoundError(f"Modelo Vosk não encontrado: {modelo}")

        self.callback = callback
        self.on_evento = on_evento
        self.device = device if device is not None else resolver_dispositivo()
        self.capture_rate = self._taxa_captura()
        self.capture_channels = self._canais_captura()
        self.sample_rate = VOSK_RATE
        self.blocksize = max(blocksize, int(self.capture_rate * 0.25))
        self._model = Model(str(modelo))
        self._rec = KaldiRecognizer(self._model, self.sample_rate)
        self._rec.SetWords(False)
        self._audio_q: queue.Queue[bytes] = queue.Queue(maxsize=32)
        self._stop = threading.Event()
        self._paused = threading.Event()
        self._thread: threading.Thread | None = None
        self._rms_limiar = LIMIAR_RMS
        self._loud_rms = LOUD_RMS
        self._ultimo_barulho = 0.0
        self._ultimo_wake_mic = 0.0
        self._ultimo_latido = 0.0
        self._ultimo_texto = ""
        self._ultimo_texto_em = 0.0
        self._ultimo_parcial = ""
        self._ultimo_parcial_em = 0.0
        self._pausa_stt_fala = os.environ.get("STT_PAUSE_DURING_TTS", "0") == "1"

    @property
    def device_nome(self) -> str:
        return nome_dispositivo(self.device)

    def _taxa_captura(self) -> int:
        try:
            if self.device is None:
                return VOSK_RATE
            info = sd.query_devices(self.device)
            return int(info.get("default_samplerate") or VOSK_RATE)
        except Exception:
            return VOSK_RATE

    def _canais_captura(self) -> int:
        try:
            if self.device is None:
                return 1
            info = sd.query_devices(self.device)
            return min(2, max(1, int(info.get("max_input_channels") or 1)))
        except Exception:
            return 1

    def _mono(self, data: bytes) -> bytes:
        if self.capture_channels < 2:
            return data
        arr = np.frombuffer(data, dtype=np.int16)
        if len(arr) < 2:
            return data
        stereo = arr.reshape(-1, 2)
        mono = stereo.max(axis=1).astype(np.int16)
        return mono.tobytes()

    def _para_vosk(self, data: bytes) -> bytes:
        data = self._mono(data)
        if self.capture_rate == self.sample_rate or not data:
            return data
        arr = np.frombuffer(data, dtype=np.int16).astype(np.float32)
        if len(arr) < 2:
            return data
        n_out = max(1, int(len(arr) * self.sample_rate / self.capture_rate))
        x_old = np.linspace(0.0, 1.0, len(arr), endpoint=False)
        x_new = np.linspace(0.0, 1.0, n_out, endpoint=False)
        out = np.interp(x_new, x_old, arr).astype(np.int16)
        return out.tobytes()

    def aplicar_perfil(self, rms: int, blocksize: int) -> None:
        # Modo jogo: limiar alto. Normal/base: respeita STT_RMS sem piso artificial.
        self._rms_limiar = rms if rms >= 50 else max(4, rms)
        del blocksize

    def ajustar_rms(self, rms: int) -> None:
        self._rms_limiar = max(4, rms)

    def _audio_cb(self, indata, frames, time_info, status) -> None:
        if status:
            logger.warning("STT status áudio: %s", status)
        if self._paused.is_set():
            return
        try:
            self._audio_q.put_nowait(bytes(indata))
        except queue.Full:
            pass

    def _emitir(self, tipo: str, valor: str | float) -> None:
        if self.on_evento:
            self.on_evento(tipo, valor)

    def _entregar_texto(self, txt: str, parcial: bool = False) -> None:
        txt = normalizar_vosk(txt.strip())
        if len(txt) < 2 or "<unk>" in txt.lower() or txt.lower() in ("unk", "<unk>"):
            return
        agora = time.monotonic()
        if txt == self._ultimo_texto and agora - self._ultimo_texto_em < float(
            os.environ.get("STT_COOLDOWN_S", "2.5")
        ):
            return
        if parcial:
            if txt == self._ultimo_parcial and agora - self._ultimo_parcial_em < 0.6:
                return
            if txt.startswith(self._ultimo_parcial) and len(txt) - len(self._ultimo_parcial) < 3:
                return
            self._ultimo_parcial = txt
            self._ultimo_parcial_em = agora
            logger.info("Ouviu (parcial): %s", txt)
        else:
            if self._ultimo_parcial and txt.startswith(self._ultimo_parcial):
                pass  # final confirma parcial — ok entregar
            self._ultimo_texto = txt
            self._ultimo_texto_em = agora
            self._ultimo_parcial = ""
            logger.info("Ouviu: %s", txt)
        self.callback(txt)

    def _loop(self) -> None:
        logger.info(
            "STT escutando [%s] captura=%dHz ch=%d vosk=%dHz rms>=%d",
            self.device_nome,
            self.capture_rate,
            self.capture_channels,
            self.sample_rate,
            self._rms_limiar,
        )
        with sd.RawInputStream(
            samplerate=self.capture_rate,
            blocksize=self.blocksize,
            dtype="int16",
            channels=self.capture_channels,
            device=self.device,
            callback=self._audio_cb,
        ):
            while not self._stop.is_set():
                if self._paused.is_set():
                    time.sleep(0.3)
                    continue
                try:
                    data = self._audio_q.get(timeout=0.4)
                except queue.Empty:
                    agora = time.monotonic()
                    if agora - self._ultimo_wake_mic > 45.0:
                        try:
                            from cozmo_companion.voice.mic import ativar_fonte

                            ativar_fonte()
                        except Exception:
                            pass
                        self._ultimo_wake_mic = agora
                    continue

                data = self._para_vosk(data)
                nivel = _rms(data)
                agora = time.monotonic()

                if nivel < self._rms_limiar:
                    continue

                if self._rec.AcceptWaveform(data):
                    txt = json.loads(self._rec.Result()).get("text", "").strip()
                    if parece_latido(txt) and agora - self._ultimo_latido > 6.0:
                        self._ultimo_latido = agora
                        self._emitir("latido", txt)
                    else:
                        self._entregar_texto(txt, parcial=False)
                else:
                    partial = json.loads(self._rec.PartialResult()).get("partial", "").strip()
                    min_parcial = int(os.environ.get("STT_PARTIAL_MIN", "2"))
                    if partial and len(partial) >= min_parcial:
                        if parece_latido(partial) and agora - self._ultimo_latido > 6.0:
                            self._ultimo_latido = agora
                            self._emitir("latido", partial)
                        elif parcial_wake_pronto(partial):
                            self._entregar_texto(partial, parcial=True)
                    elif (
                        nivel >= self._loud_rms
                        and agora - self._ultimo_barulho > 12.0
                        and not partial
                    ):
                        self._ultimo_barulho = agora
                        self._emitir("barulho", nivel)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._paused.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="CozmoSTT")
        self._thread.start()

    def pause(self) -> None:
        self._paused.set()
        while not self._audio_q.empty():
            try:
                self._audio_q.get_nowait()
            except queue.Empty:
                break

    def resume(self) -> None:
        self._paused.clear()

    def stop(self) -> None:
        self._stop.set()
        self._paused.clear()
        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None
