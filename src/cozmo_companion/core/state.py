"""Estado central do Cozmo: modo lógico, contato físico e segurança."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CozmoMode(str, Enum):
    BASE_WAKE = "base_wake"
    BASE_SLEEP = "base_sleep"
    FREE_READY = "free_ready"
    FREE_EXPLORE = "free_explore"
    RECOVERY = "recovery"
    QUIET = "quiet"


@dataclass(frozen=True)
class HardwareSnapshot:
    """Leitura mínima usada para decidir políticas; não envia comando ao robô."""

    button_base: bool
    free_requested: bool
    on_charger: bool
    charging: bool
    picked_up: bool
    sleeping: bool
    quiet: bool
    rx_ok: bool
    recovering: bool = False

    @property
    def physical_base(self) -> bool:
        return self.on_charger or self.charging


@dataclass(frozen=True)
class SafetyState:
    mode: CozmoMode
    effective_base: bool
    movement_allowed: bool
    wheels_allowed: bool
    lift_allowed: bool
    camera_allowed: bool
    animation_allowed: bool

    @property
    def free_armed(self) -> bool:
        return self.mode in (CozmoMode.FREE_READY, CozmoMode.FREE_EXPLORE)


def decide_state(s: HardwareSnapshot) -> SafetyState:
    """Define contrato único: base física nunca usa rodas/lift."""

    effective_base = s.button_base or s.physical_base
    if s.recovering or not s.rx_ok:
        mode = CozmoMode.RECOVERY
    elif s.quiet:
        mode = CozmoMode.QUIET
    elif effective_base and s.free_requested:
        mode = CozmoMode.FREE_READY
    elif effective_base:
        mode = CozmoMode.BASE_SLEEP if s.sleeping else CozmoMode.BASE_WAKE
    elif s.picked_up:
        mode = CozmoMode.FREE_READY
    else:
        mode = CozmoMode.FREE_EXPLORE

    movement_allowed = (
        mode == CozmoMode.FREE_EXPLORE
        and not effective_base
        and not s.picked_up
        and s.rx_ok
    )
    camera_allowed = s.rx_ok and mode not in (CozmoMode.RECOVERY, CozmoMode.QUIET)
    animation_allowed = s.rx_ok and mode != CozmoMode.RECOVERY
    return SafetyState(
        mode=mode,
        effective_base=effective_base,
        movement_allowed=movement_allowed,
        wheels_allowed=movement_allowed,
        lift_allowed=movement_allowed,
        camera_allowed=camera_allowed,
        animation_allowed=animation_allowed,
    )
