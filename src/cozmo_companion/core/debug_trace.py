"""Debug NDJSON opcional — COZMO_DEBUG_TRACE=1 para ativar."""

from __future__ import annotations

import json
import os
import time
from typing import Any

from cozmo_companion.core.paths import data_dir

_LOG = os.environ.get(
    "COZMO_DEBUG_TRACE_LOG",
    str(data_dir() / "debug-trace.log"),
)
_SESSION = "cozmo"


def dbg(
    hypothesis_id: str,
    location: str,
    message: str,
    data: dict[str, Any] | None = None,
    *,
    run_id: str = "run",
) -> None:
    if os.environ.get("COZMO_DEBUG_TRACE", "0") != "1":
        return
    # region agent log
    try:
        with open(_LOG, "a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "sessionId": _SESSION,
                        "runId": run_id,
                        "hypothesisId": hypothesis_id,
                        "location": location,
                        "message": message,
                        "data": data or {},
                        "timestamp": int(time.time() * 1000),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    except OSError:
        pass
    # endregion
