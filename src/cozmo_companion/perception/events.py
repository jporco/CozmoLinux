"""Eventos de percepção produzidos pela câmera/sensores."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class PerceptionEventKind(str, Enum):
    LIGHT_LEVEL = "light_level"
    FACE_SEEN = "face_seen"
    FACE_LOST = "face_lost"
    MOTION_HINT = "motion_hint"


@dataclass(frozen=True)
class PerceptionEvent:
    kind: PerceptionEventKind
    timestamp: float = field(default_factory=time.monotonic)
    value: float | None = None
    data: dict[str, Any] = field(default_factory=dict)


EventSink = Callable[[PerceptionEvent], None]
