"""Garante uma única instância do companion — evita flood UDP / COZMO01."""

from __future__ import annotations

import atexit
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger("cozmo.singleton")

_lock_fh = None


def adquirir_instancia_unica() -> bool:
    """Retorna False se outro companion já está rodando."""
    global _lock_fh
    if os.environ.get("COZMO_ALLOW_MULTI", "0") == "1":
        return True
    path = Path(
        os.environ.get(
            "COZMO_LOCK_FILE",
            "/tmp/cozmo-companion.lock",
        )
    )
    try:
        import fcntl

        fh = open(path, "a+", encoding="utf-8")
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        fh.seek(0)
        fh.truncate()
        fh.write(str(os.getpid()))
        fh.flush()
        _lock_fh = fh

        @atexit.register
        def _liberar() -> None:
            global _lock_fh
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
                fh.close()
            except OSError:
                pass
            _lock_fh = None

        return True
    except OSError:
        pid = "?"
        try:
            pid = path.read_text(encoding="utf-8").strip() or "?"
        except OSError:
            pass
        logger.error(
            "Companion já em execução (pid %s, lock %s) — abortando duplicata",
            pid,
            path,
        )
        return False
