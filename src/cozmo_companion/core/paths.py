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
