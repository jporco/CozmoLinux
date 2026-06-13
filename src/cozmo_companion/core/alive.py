"""Comportamento vivo na base — gestos esparsos, sem sair da base."""

from __future__ import annotations

import logging
import os
import random
import time
from typing import TYPE_CHECKING

from pycozmo import robot

from cozmo_companion.core.motor_cozmo import angulo_cabeca_neutro
from cozmo_companion.core.anims import (
    GRUPOS_LATIDO,
    GRUPOS_REACAO,
    GRUPOS_SUSTO,
    ContextoAnim,
    escolher_ctx,
    filtrar_na_base,
)

if TYPE_CHECKING:
    import pycozmo

logger = logging.getLogger("cozmo.alive")

# Re-export para compatibilidade
GRUPOS_IDLE = (
    "NeutralFace",
    "InterestedFace",
    "LookInPlaceForFacesHeadMovePause",
    "InteractWithFaceTrackingIdle",
)


class VivoNaBase:
    """Gestos ocasionais — nunca movimento contínuo."""

    def __init__(self) -> None:
        self._ultimo_braco = 0.0
        self._braco_baixar_em = 0.0
        self._braco_seq: list[tuple[float, float]] = []
        self._ultimo_cabeca = 0.0

    def braco_notif(self, cli: "pycozmo.Client") -> None:
        """Dois toques rápidos — braço sobe/desce."""
        agora = time.monotonic()
        if agora - self._ultimo_braco < 2.0:
            return
        self._ultimo_braco = agora
        try:
            baixo = robot.MIN_LIFT_HEIGHT.mm
            self._braco_seq = [
                (agora + 0.0, baixo + 24),
                (agora + 0.18, baixo),
                (agora + 0.36, baixo + 20),
                (agora + 0.54, baixo),
            ]
        except (AttributeError, TypeError):
            pass

    def reagir_ouvir(self, cli: "pycozmo.Client") -> None:
        min_a = robot.MIN_HEAD_ANGLE.radians
        max_a = robot.MAX_HEAD_ANGLE.radians
        centro = angulo_cabeca_neutro()
        alvo = centro + random.uniform(-0.05, 0.10)
        cli.set_head_angle(max(min_a, min(max_a, alvo)))

    def tick_cabeca_base(self, cli: "pycozmo.Client") -> None:
        """Movimento sutil da cabeça — sem animação (não mata UDP)."""
        agora = time.monotonic()
        intervalo = float(os.environ.get("BASE_HEAD_MOVE_S", "22"))
        if agora - self._ultimo_cabeca < intervalo * random.uniform(0.85, 1.15):
            return
        self._ultimo_cabeca = agora
        min_a = robot.MIN_HEAD_ANGLE.radians
        max_a = robot.MAX_HEAD_ANGLE.radians
        centro = angulo_cabeca_neutro()
        alvo = centro + random.uniform(-0.04, 0.07)
        try:
            cli.set_head_angle(
                max(min_a, min(max_a, alvo)),
                max_speed=float(os.environ.get("BASE_HEAD_SPEED", "6.0")),
            )
        except (AttributeError, TypeError):
            pass

    def reagir_falar(self, cli: "pycozmo.Client") -> None:
        agora = time.monotonic()
        if agora - self._ultimo_braco < 6.0:
            return
        self._ultimo_braco = agora
        try:
            baixo = robot.MIN_LIFT_HEIGHT.mm
            cli.set_lift_height(baixo + random.uniform(6, 16))
            self._braco_baixar_em = agora + 1.2
        except (AttributeError, TypeError):
            pass

    def braco_susto_iniciar(self, cli: "pycozmo.Client") -> None:
        try:
            baixo = robot.MIN_LIFT_HEIGHT.mm
            cli.set_lift_height(baixo + random.uniform(38, 58))
            self._braco_baixar_em = time.monotonic() + 0.55
            self._ultimo_braco = time.monotonic()
        except (AttributeError, TypeError):
            pass

    def tick_braco(self, cli: "pycozmo.Client") -> None:
        agora = time.monotonic()
        if self._braco_seq:
            while self._braco_seq and agora >= self._braco_seq[0][0]:
                _, altura = self._braco_seq.pop(0)
                try:
                    cli.set_lift_height(altura)
                except (AttributeError, TypeError):
                    pass
            return
        if self._braco_baixar_em <= 0:
            return
        if agora >= self._braco_baixar_em:
            try:
                cli.set_lift_height(robot.MIN_LIFT_HEIGHT.mm)
            except (AttributeError, TypeError):
                pass
            self._braco_baixar_em = 0.0

    def tocar(
        self,
        cli: "pycozmo.Client",
        candidatos: tuple[str, ...],
        *,
        ctx: ContextoAnim = ContextoAnim.BASE,
    ) -> bool:
        grupos = set(cli.animation_groups.keys())
        nome = escolher_ctx(
            grupos,
            candidatos,
            ctx,
            sem_som_carga=ctx == ContextoAnim.BASE,
        )
        if not nome:
            return False
        from cozmo_companion.core.motor_cozmo import (
            _base_clip_sem_rodas_ativo,
            parar_rodas_apos_anim_base,
        )

        if not _base_clip_sem_rodas_ativo(cli):
            cli.cancel_anim()
            cli.stop_all_motors()
        cli.play_anim_group(nome)
        parar_rodas_apos_anim_base(cli)
        return True


def filtrar_animacoes_base(candidatos, grupos_disponiveis):
    return filtrar_na_base(candidatos, grupos_disponiveis)
