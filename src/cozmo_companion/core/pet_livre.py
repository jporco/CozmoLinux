"""Comportamento pet no modo livre, usando sensores sem movimento contínuo."""

from __future__ import annotations

import logging
import os
import random
import time
from dataclasses import dataclass

from pycozmo import lights, robot

from cozmo_companion.core.anims import (
    GRUPOS_CURIOSO,
    GRUPOS_MESA,
    GRUPOS_MESA_CARREGADOR,
    GRUPOS_REACAO,
)
from cozmo_companion.perception.events import PerceptionEvent, PerceptionEventKind

logger = logging.getLogger("cozmo.pet")


@dataclass(frozen=True)
class PetPlano:
    acao: str
    anims: tuple[str, ...] = ()
    camera_s: float = 0.0


class PetLivre:
    """Pequenas ações autônomas para parecer vivo na mesa.

    Não substitui o ExploradorMesa: ele só escolhe intenção. Rodas continuam
    curtas e protegidas por stop-on-cliff/sensores no explorador.
    """

    def __init__(self) -> None:
        self._proxima = time.monotonic() + random.uniform(4.0, 9.0)
        self._ultimo_evento = 0.0
        self._ultimo_rosto = 0.0
        self._ultimo_movimento = 0.0
        self._ultimo_led = 0.0
        self._movimento_interno_ate = 0.0

    @property
    def movimento_interno(self) -> bool:
        return time.monotonic() < self._movimento_interno_ate

    def entrar_modo_livre(self) -> None:
        agora = time.monotonic()
        self._proxima = agora + float(os.environ.get("PET_LIVRE_START_S", "1.2"))
        self._ultimo_evento = agora

    def registrar_evento(self, evento: PerceptionEvent) -> None:
        agora = time.monotonic()
        if evento.kind == PerceptionEventKind.FACE_SEEN:
            self._ultimo_rosto = agora
            self._proxima = min(self._proxima, agora + 1.0)
        elif evento.kind == PerceptionEventKind.MOTION_HINT:
            self._ultimo_movimento = agora
            self._proxima = min(self._proxima, agora + 1.5)

    def agendar_agora(self, atraso_s: float = 0.8) -> None:
        self._proxima = min(self._proxima, time.monotonic() + atraso_s)

    def _agendar(self, *, livre: bool, evento_recente: bool) -> None:
        if livre:
            lo = float(os.environ.get("PET_LIVRE_MIN_S", "4"))
            hi = float(os.environ.get("PET_LIVRE_MAX_S", "11"))
        else:
            lo = float(os.environ.get("PET_READY_MIN_S", "8"))
            hi = float(os.environ.get("PET_READY_MAX_S", "18"))
        if evento_recente:
            lo *= 0.55
            hi *= 0.75
        self._proxima = time.monotonic() + random.uniform(lo, max(lo + 1.0, hi))

    def escolher(self, *, livre: bool, no_carregador: bool, face_ativa: bool) -> PetPlano | None:
        agora = time.monotonic()
        if agora < self._proxima:
            return None
        evento_recente = (
            agora - self._ultimo_rosto < 8.0 or agora - self._ultimo_movimento < 6.0
        )
        self._agendar(livre=livre, evento_recente=evento_recente)

        if not livre:
            if not face_ativa and random.random() < 0.45:
                return PetPlano("camera", GRUPOS_MESA_CARREGADOR + GRUPOS_CURIOSO, 8.0)
            return PetPlano("anim", GRUPOS_MESA_CARREGADOR + GRUPOS_CURIOSO)

        if evento_recente and random.random() < 0.65:
            return PetPlano("anim", GRUPOS_REACAO + GRUPOS_CURIOSO)

        escolhas = ("explorar", "anim", "olhar", "gesto", "scan")
        pesos = (3.4, 2.6, 2.1, 1.8, 1.5)
        acao = random.choices(escolhas, weights=pesos, k=1)[0]
        if acao == "explorar":
            return PetPlano("explorar")
        if acao == "olhar":
            return PetPlano("camera", GRUPOS_CURIOSO, random.uniform(8, 14))
        if acao == "gesto":
            return PetPlano("gesto", GRUPOS_REACAO + GRUPOS_MESA)
        if acao == "scan":
            return PetPlano("scan", GRUPOS_CURIOSO)
        return PetPlano("anim", GRUPOS_MESA + GRUPOS_CURIOSO + GRUPOS_REACAO)

    def gesto_curto(self, cli) -> None:
        """Movimento sutil de cabeça/lift/luz, sem andar."""
        self._movimento_interno_ate = time.monotonic() + 2.0
        try:
            min_a = robot.MIN_HEAD_ANGLE.radians
            max_a = robot.MAX_HEAD_ANGLE.radians
            alvo = random.uniform(max(min_a, -0.18), min(max_a, 0.42))
            cli.set_head_angle(alvo, max_speed=random.uniform(6.0, 10.0))
        except Exception:
            pass
        try:
            baixo = robot.MIN_LIFT_HEIGHT.mm
            cli.set_lift_height(baixo + random.uniform(8, 34), max_speed=8.0)
        except Exception:
            pass
        self.piscar_luzes(cli)

    def scan_curto(self, cli) -> None:
        """Olha para os lados em duas etapas, sem deslocar."""
        self._movimento_interno_ate = time.monotonic() + 1.4
        try:
            cur = float(getattr(cli.head_angle, "radians", 0.0))
            delta = random.choice((-0.18, 0.18))
            alvo = max(robot.MIN_HEAD_ANGLE.radians, min(robot.MAX_HEAD_ANGLE.radians, cur + delta))
            cli.set_head_angle(alvo, max_speed=7.0)
        except Exception:
            pass
        self.piscar_luzes(cli)

    def piscar_luzes(self, cli) -> None:
        agora = time.monotonic()
        if agora - self._ultimo_led < 3.0:
            return
        self._ultimo_led = agora
        try:
            cor = random.choice((lights.blue_light, lights.green_light, lights.white_light))
            cli.set_center_backpack_lights(cor)
        except Exception:
            pass

    def apagar_luzes(self, cli) -> None:
        try:
            cli.set_backpack_lights_off()
        except Exception:
            pass
