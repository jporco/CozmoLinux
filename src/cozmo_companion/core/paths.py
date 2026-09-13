"""Install root resolution — no hardcoded machine paths."""

from __future__ import annotations

import os
from pathlib import Path


def install_root() -> Path:
    raw = os.environ.get("COZMO_COMPANION_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    # src/cozmo_companion/core/paths.py -> repo root
    return Path(__file__).resolve().parents[3]


def data_dir() -> Path:
    return install_root() / "data"


def health_file(root: Path | None = None) -> Path:
    """Heartbeat fora do repositório quando configurado.

    O projeto pode estar em NTFS, onde um arquivo/rename corrompido não deve
    desativar silenciosamente o watchdog. ``expanduser`` permite usar ``~`` no
    EnvironmentFile do systemd sem depender de expansão pelo shell.
    """
    raw = os.environ.get("COZMO_HEALTH_FILE", "").strip()
    if raw:
        return Path(raw).expanduser()
    base = root / "data" if root is not None else data_dir()
    return base / "cozmo-saude.json"
