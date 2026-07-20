"""Manutenção periódica — logs enxutos sem matar o companion."""

from __future__ import annotations

import logging
import os
import subprocess
import time
from pathlib import Path

from cozmo_companion.guardian.core.policy import EstadoGuardian

logger = logging.getLogger("cozmo.guardian.manutencao")


def manter_logs(root: Path, estado: EstadoGuardian) -> bool:
    """Roda limpar-logs.sh no máximo 1x por GUARDIAN_LOG_TRIM_S (padrão 24h)."""
    intervalo = float(os.environ.get("GUARDIAN_LOG_TRIM_S", "86400"))
    agora = time.monotonic()
    boot_grace = float(os.environ.get("GUARDIAN_LOG_TRIM_BOOT_GRACE_S", "600"))
    if (
        estado.ultimo_trim_log <= 0
        and boot_grace > 0
        and agora - estado.iniciado_em < boot_grace
    ):
        return False
    if estado.ultimo_trim_log > 0 and agora - estado.ultimo_trim_log < intervalo:
        return False

    script = root / "scripts" / "limpar-logs.sh"
    if not script.is_file():
        logger.warning("limpar-logs.sh ausente em %s", script)
        return False

    env = os.environ.copy()
    env.setdefault("COZMO_LOG_KEEP_LINES", "12000")

    try:
        r = subprocess.run(
            ["/bin/bash", str(script)],
            cwd=str(root),
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.error("Limpeza de logs falhou: %s", exc)
        return False

    estado.ultimo_trim_log = agora
    saida = (r.stdout or "").strip()
    if r.returncode == 0:
        logger.info("Logs: %s", saida.splitlines()[-1] if saida else "ok")
        return True
    logger.warning(
        "limpar-logs exit=%d stderr=%s",
        r.returncode,
        (r.stderr or "").strip()[:200],
    )
    return False
