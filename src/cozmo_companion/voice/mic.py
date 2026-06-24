"""Descobre microfone Fifine por nome — índice muda após reboot."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger("cozmo.mic")

_FIFINE = ("fifine", "k658")
_DEFAULT_LOCK = "/run/user/{uid}/porco-jarvis.mic"


def _nome_dispositivo(idx: int) -> str:
    import sounddevice as sd

    return str(sd.query_devices(idx).get("name", ""))


def _eh_fifine(nome: str) -> bool:
    n = nome.lower()
    return "fifine" in n or "k658" in n


def _tem_entrada(idx: int) -> bool:
    import sounddevice as sd

    try:
        return int(sd.query_devices(idx).get("max_input_channels") or 0) >= 1
    except Exception:
        return False


def _prioridade_fifine(nome: str) -> int:
    """Entrada real (PipeWire/ALSA) antes de nó hw que só aparece como saída."""
    n = nome.lower()
    if "estéreo analógico" in n or "stereo analógico" in n:
        return 0
    if "hw:" in n or "usb audio" in n:
        return 1
    if "usb" in n:
        return 2
    return 3


def _buscar_por_nome(*pedacos: str) -> Optional[int]:
    import sounddevice as sd

    pedacos = tuple(p.lower() for p in pedacos if p)
    candidatos: list[tuple[int, str]] = []

    for i, dev in enumerate(sd.query_devices()):
        if int(dev.get("max_input_channels") or 0) < 1:
            continue
        nome = str(dev.get("name", ""))
        nl = nome.lower()
        match = all(p in nl for p in pedacos) if pedacos else False
        if not match and pedacos:
            if any(p in nl for p in pedacos if p in _FIFINE) and _eh_fifine(nl):
                match = True
        if match:
            candidatos.append((i, nome))

    if not candidatos:
        return None
    candidatos.sort(key=lambda x: _prioridade_fifine(x[1]))
    return candidatos[0][0]


def mic_yield_locks() -> list[Path]:
    """Arquivos-lock: outro serviço com mic exclusivo (ex.: JARVIS)."""
    raw = os.environ.get("MIC_YIELD_LOCKS", "").strip()
    paths: list[Path] = []
    if raw:
        for parte in raw.split(","):
            p = parte.strip()
            if p:
                paths.append(Path(p.replace("{uid}", str(os.getuid()))))
    else:
        paths.append(Path(_DEFAULT_LOCK.format(uid=os.getuid())))
    extra = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    for nome in ("mic.lock", "mic-busy", "porco-jarvis.mic"):
        paths.append(Path(extra) / nome)
    # dedupe preserving order
    vistos: set[str] = set()
    out: list[Path] = []
    for p in paths:
        s = str(p)
        if s not in vistos:
            vistos.add(s)
            out.append(p)
    return out


def mic_ocupado_externo() -> bool:
    """True se outro processo reservou o microfone (lock file)."""
    for lock in mic_yield_locks():
        try:
            if lock.is_file():
                return True
        except OSError:
            continue
    return False


def ativar_fonte() -> None:
    """Acorda fonte PipeWire/Pulse do Fifine (fica SUSPENDED até alguém capturar)."""
    if mic_ocupado_externo():
        return
    import subprocess

    try:
        r = subprocess.run(
            ["pactl", "list", "sources", "short"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if r.returncode != 0:
            return
        for linha in r.stdout.splitlines():
            if "fifine" not in linha.lower() and "k658" not in linha.lower():
                continue
            idx = linha.split()[0]
            subprocess.run(
                ["pactl", "suspend-source", idx, "0"],
                capture_output=True,
                timeout=2,
            )
            subprocess.run(
                ["pactl", "set-source-mute", idx, "0"],
                capture_output=True,
                timeout=2,
            )
            logger.info("Fonte mic ativa: %s", linha.strip())
            return
    except (subprocess.SubprocessError, OSError) as exc:
        logger.debug("ativar_fonte: %s", exc)


def resolver_dispositivo() -> Optional[int]:
    """Sempre prefere Fifine/K658; ignora índice numérico errado."""
    raw = os.environ.get("MIC_DEVICE", "fifine").strip()
    hint = os.environ.get("MIC_NAME", "fifine").strip().lower()

    try:
        import sounddevice as sd
    except ImportError:
        return None

    # Nome explícito: MIC_DEVICE=fifine ou MIC_NAME=...
    alvo = raw.lower() if raw and not re.fullmatch(r"\d+", raw) else hint
    idx = _buscar_por_nome(alvo)
    if idx is not None:
        logger.info("Microfone [%d] %s", idx, _nome_dispositivo(idx))
        return idx

    # Fifine sempre ganha do índice fixo.
    idx = _buscar_por_nome("fifine")
    if idx is None:
        idx = _buscar_por_nome("k658")
    if idx is not None:
        logger.info("Microfone Fifine [%d] %s", idx, _nome_dispositivo(idx))
        return idx

    if raw.isdigit():
        idx = int(raw)
        try:
            nome = _nome_dispositivo(idx)
            if not _tem_entrada(idx):
                logger.error(
                    "MIC_DEVICE=%d (%s) sem canal de entrada — ignorando",
                    idx,
                    nome,
                )
            else:
                logger.warning(
                    "Fifine não encontrado; usando MIC_DEVICE=%d (%s)",
                    idx,
                    nome,
                )
                return idx
        except Exception:
            pass

    logger.warning("Fifine não encontrado — entrada padrão do sistema.")
    return None


def nome_dispositivo(device: Optional[int]) -> str:
    try:
        if device is None:
            return "padrão"
        return _nome_dispositivo(device)
    except Exception:
        return str(device)
