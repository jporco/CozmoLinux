"""Detecta jogo e reduz prioridade — voz e respostas continuam ativas."""

from __future__ import annotations

import logging
import os
import subprocess
import time
from dataclasses import dataclass
from enum import Enum, auto

logger = logging.getLogger("cozmo.perf")


class ModoPerf(Enum):
    NORMAL = auto()
    JOGO = auto()


@dataclass(frozen=True)
class Perfil:
    ouvir_mic: bool
    usar_llm: bool
    fala_proativa: bool
    tela_temp: bool
    loop_sleep: float
    proactive_mult: float
    tela_mult: float
    face_frame_s: float
    face_scan_chance: float
    stt_rms: int
    stt_blocksize: int
    nice_extra: int
    idle_mult: float
    ollama_tokens: int
    ollama_timeout: float
    ollama_threads: int


def _perfil_normal() -> Perfil:
    return Perfil(
        ouvir_mic=True,
        usar_llm=True,
        fala_proativa=os.environ.get("FALA_PROATIVA", "0") == "1",
        tela_temp=True,
        loop_sleep=float(os.environ.get("LOOP_SLEEP", "0.15")),
        proactive_mult=1.0,
        tela_mult=1.0,
        face_frame_s=float(os.environ.get("FACE_FRAME_S", "0.18")),
        face_scan_chance=float(os.environ.get("FACE_SCAN_CHANCE", "0.85")),
        stt_rms=int(os.environ.get("STT_RMS", "25")),
        stt_blocksize=int(os.environ.get("STT_BLOCKSIZE", "4000")),
        nice_extra=0,
        idle_mult=1.0,
        ollama_tokens=int(os.environ.get("OLLAMA_MAX_TOKENS", "70")),
        ollama_timeout=float(os.environ.get("OLLAMA_TIMEOUT_S", "30")),
        ollama_threads=int(os.environ.get("OLLAMA_THREADS", "2")),
    )


def _perfil_jogo() -> Perfil:
    return Perfil(
        ouvir_mic=True,
        usar_llm=True,
        fala_proativa=False,
        tela_temp=False,
        loop_sleep=float(os.environ.get("GAME_LOOP_SLEEP", "1.2")),
        proactive_mult=6.0,
        tela_mult=5.0,
        face_frame_s=float(os.environ.get("GAME_FACE_FRAME_S", "1.2")),
        face_scan_chance=float(os.environ.get("GAME_FACE_SCAN_CHANCE", "0.35")),
        stt_rms=int(os.environ.get("GAME_STT_RMS", "140")),
        stt_blocksize=int(os.environ.get("GAME_STT_BLOCKSIZE", "8000")),
        nice_extra=int(os.environ.get("GAME_NICE_EXTRA", "8")),
        idle_mult=float(os.environ.get("GAME_IDLE_MULT", "4")),
        ollama_tokens=int(os.environ.get("OLLAMA_GAME_MAX_TOKENS", "35")),
        ollama_timeout=float(os.environ.get("OLLAMA_GAME_TIMEOUT_S", "15")),
        ollama_threads=int(os.environ.get("OLLAMA_GAME_THREADS", "1")),
    )


PERFIS = {
    ModoPerf.NORMAL: _perfil_normal(),
    ModoPerf.JOGO: _perfil_jogo(),
}


class MonitorJogo:
    """Alterna modo normal ↔ jogo: menos CPU/GPU, mesma interação por voz."""

    def __init__(self) -> None:
        raw = os.environ.get(
            "GAME_PROCESSES",
            "Gw2-64.exe,gw2-64.exe,Guild Wars 2",
        )
        self.processos = [p.strip() for p in raw.split(",") if p.strip()]
        self.gpu_limite = int(os.environ.get("GAME_GPU_PERCENT", "70"))
        self.intervalo = float(os.environ.get("GAME_CHECK_S", "8"))
        self.exigir_gpu = os.environ.get("GAME_REQUIRE_GPU", "0") == "1"
        self._modo = ModoPerf.NORMAL
        self._proxima = 0.0
        self._jogo_streak = 0
        self._normal_streak = 0

    @property
    def modo(self) -> ModoPerf:
        return self._modo

    @property
    def perfil(self) -> Perfil:
        return PERFIS[self._modo]

    def _processo_jogo_ativo(self) -> bool:
        for nome in self.processos:
            try:
                r = subprocess.run(
                    ["pgrep", "-f", nome],
                    capture_output=True,
                    timeout=2,
                )
                if r.returncode == 0:
                    return True
            except (subprocess.SubprocessError, OSError):
                continue
        return False

    def _gpu_ocupada(self) -> bool:
        try:
            r = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=utilization.gpu",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if r.returncode != 0:
                return False
            for linha in r.stdout.strip().splitlines():
                if int(linha.strip()) >= self.gpu_limite:
                    return True
        except (subprocess.SubprocessError, OSError, ValueError):
            pass
        return False

    def em_jogo(self) -> bool:
        if not self._processo_jogo_ativo():
            return False
        if self.exigir_gpu:
            return self._gpu_ocupada()
        return True

    def tick(self) -> ModoPerf:
        agora = time.monotonic()
        if agora < self._proxima:
            return self._modo

        self._proxima = agora + self.intervalo
        em_jogo = self.em_jogo()
        if em_jogo:
            self._jogo_streak += 1
            self._normal_streak = 0
        else:
            self._normal_streak += 1
            self._jogo_streak = 0

        limiar = int(os.environ.get("GAME_MODE_STREAK", "2"))
        if self._modo == ModoPerf.NORMAL and self._jogo_streak >= limiar:
            novo = ModoPerf.JOGO
        elif self._modo == ModoPerf.JOGO and self._normal_streak >= limiar:
            novo = ModoPerf.NORMAL
        else:
            novo = self._modo

        if novo != self._modo:
            from cozmo_companion.core.debug_trace import dbg

            dbg(
                "H3",
                "perf.py:tick",
                "mode_switch",
                {"from": self._modo.name, "to": novo.name, "em_jogo": em_jogo},
            )
            self._modo = novo
            if novo == ModoPerf.JOGO:
                logger.info(
                    "Modo jogo — prioridade baixa, voz e respostas ativas"
                )
            else:
                logger.info("Modo normal — companheiro completo")

        return self._modo
