"""Ações do guardian — restart, Wi-Fi, ajuste de config."""

from __future__ import annotations

import logging
import os
import subprocess
import time
from pathlib import Path

logger = logging.getLogger("cozmo.guardian.actions")

SERVICE = "cozmo-companion.service"


# Som de notificação: padrão só no Cozmo (PC desligado).
_NOTIF_PC_PADRAO = {
    "NOTIF_PC_BEEP": "0",
    "NOTIF_PC_BEEP_VOLUME": "65536",
    "NOTIF_PC_AUDIO": "0",
}


def escrever_override(root: Path, chaves: dict[str, str]) -> Path:
    dest = root / "config.guardian.env"
    merged = {**_NOTIF_PC_PADRAO, **chaves}
    linhas = ["# Gerado pelo Cozmo Guardian — som só no Cozmo\n"]
    for k, v in sorted(merged.items()):
        linhas.append(f"{k}={v}\n")
    dest.write_text("".join(linhas), encoding="utf-8")
    logger.info("Override guardian: %s", dest)
    return dest


def perfil_estavel(root: Path) -> None:
    escrever_override(
        root,
        {
            "ECO_CHANCE": "0",
            "STT_PAUSE_DURING_TTS": "1",
            "TTS_NA_BASE": "0",
            "FALA_PROATIVA": "0",
            "PROACTIVE_LLM": "0",
            "ESPIRITO_ATIVO": "0",
            "ESPIRITO_FALA": "0",
            "COZMO_SOMENTE_BASE": "0",
            "TTS_MAX_TOTAL_PACOTES": "18",
            "COZMO_KEEPALIVE_MAX": "2",
            "COZMO_RX_STALL_S": "5",
            "COZMO_MOTOR_STOP_CHARGE_S": "5.0",
            "COZMO_ANIM_CARGA_S": "120",
        },
    )


def perfil_normal(root: Path) -> None:
    dest = root / "config.guardian.env"
    if dest.is_file():
        dest.unlink()
        logger.info("Override guardian removido — perfil normal")


def reiniciar_companion() -> bool:
    """Só `start` se inativo — nunca `restart` (mata sessão UDP do Cozmo)."""
    from cozmo_companion.guardian.core.health import companion_via_lock

    if companion_via_lock():
        logger.info("Companion manual ativo (lock) — ignorando start systemd")
        return False
    try:
        st = subprocess.run(
            ["systemctl", "--user", "is-active", SERVICE],
            capture_output=True,
            text=True,
            timeout=5,
        )
        estado_svc = st.stdout.strip()
        if estado_svc in ("active", "activating", "reloading"):
            logger.info("Companion já %s — ignorando start", estado_svc)
            return False
        subprocess.run(
            ["systemctl", "--user", "start", SERVICE],
            check=True,
            timeout=30,
        )
        logger.warning("Companion iniciado pelo guardian (estava parado)")
        return True
    except (OSError, subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
        logger.error("Falha ao iniciar companion: %s", exc)
        return False


def reconectar_wifi(root: Path) -> bool:
    script = root / "conectar-cozmo.sh"
    if not script.is_file():
        return False
    try:
        env = os.environ.copy()
        env["COZMO_WIFI_SAFE"] = "1"
        proc = subprocess.run(
            ["/bin/bash", str(script)],
            capture_output=True,
            text=True,
            timeout=12,
            cwd=str(root),
            env=env,
        )
        ok = proc.returncode == 0
        logger.info("Wi-Fi Cozmo: code=%d", proc.returncode)
        return ok
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("Wi-Fi falhou: %s", exc)
        return False


def aguardar_servico(ativo: bool = True, timeout_s: float = 90.0) -> bool:
    fim = time.monotonic() + timeout_s
    while time.monotonic() < fim:
        try:
            r = subprocess.run(
                ["systemctl", "--user", "is-active", SERVICE],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if (r.stdout.strip() == "active") == ativo:
                return True
        except (OSError, subprocess.TimeoutExpired):
            pass
        time.sleep(2.0)
    return False
