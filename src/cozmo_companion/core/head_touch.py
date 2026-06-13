"""Detecta carinho / toque — acorda se estiver dormindo na base ou no carregador."""

from __future__ import annotations

import os
import time
from typing import Callable

import pycozmo

from cozmo_companion.core.charger import carregando, em_base, na_base

COOLDOWN_S = float(os.environ.get("CARINHO_COOLDOWN_S", "16"))
COOLDOWN_SONO_S = 2.5
LIMIAR_ANGULO = float(os.environ.get("CARINHO_LIM_ANG", "0.06"))
LIMIAR_ACCEL = float(os.environ.get("CARINHO_LIM_ACC", "0.35"))
LIMIAR_ANGULO_SONO = float(os.environ.get("CARINHO_LIM_ANG_SONO", "0.035"))
LIMIAR_ACCEL_SONO = float(os.environ.get("CARINHO_LIM_ACC_SONO", "0.22"))


def _base_ang_mult() -> float:
    return float(os.environ.get("CARINHO_BASE_ANG_MULT", "3.5"))


def _base_acc_mult() -> float:
    return float(os.environ.get("CARINHO_BASE_ACC_MULT", "2.8"))


def _base_exige_ambos() -> bool:
    return os.environ.get("CARINHO_BASE_AND", "1") == "1"


def _no_carregador(cli: pycozmo.Client) -> bool:
    return em_base(cli) or na_base(cli) or carregando(cli)


class HeadPetDetector:
    def __init__(self, callback: Callable[[], None]):
        self.callback = callback
        self._ultimo_angulo: float | None = None
        self._ultimo_accel = (0.0, 0.0, 0.0)
        self._ultimo_gatilho = 0.0

    def sincronizar_baseline(self, cli: pycozmo.Client) -> None:
        """Atualiza referência — evita falso positivo após anim/TTS/cabeça programática."""
        self._ultimo_angulo = cli.head_angle.radians
        self._ultimo_accel = (cli.accel.x, cli.accel.y, cli.accel.z)

    def _pode_disparar(self, cooldown: float) -> bool:
        return (time.monotonic() - self._ultimo_gatilho) >= cooldown

    def update(
        self,
        cli: pycozmo.Client,
        *,
        preso_na_base: bool = False,
        em_sono: bool = False,
        face_ativo: bool = False,
        cabeca_externa: bool = False,
    ) -> None:
        if cli.robot_picked_up or face_ativo or cabeca_externa:
            self.sincronizar_baseline(cli)
            return

        angulo = cli.head_angle.radians
        accel = (cli.accel.x, cli.accel.y, cli.accel.z)
        no_carga = _no_carregador(cli)

        if em_sono:
            lim_ang = LIMIAR_ANGULO_SONO
            lim_acc = LIMIAR_ACCEL_SONO
            cooldown = COOLDOWN_SONO_S
            exige_ambos = False
        elif preso_na_base:
            lim_ang = LIMIAR_ANGULO * _base_ang_mult()
            lim_acc = LIMIAR_ACCEL * _base_acc_mult()
            cooldown = COOLDOWN_S * 1.4
            exige_ambos = _base_exige_ambos()
        elif not no_carga:
            lim_ang = LIMIAR_ANGULO
            lim_acc = LIMIAR_ACCEL
            cooldown = COOLDOWN_S
            exige_ambos = False
        else:
            lim_ang = LIMIAR_ANGULO * 2.0
            lim_acc = LIMIAR_ACCEL * 1.6
            cooldown = COOLDOWN_S
            exige_ambos = False

        if self._ultimo_angulo is not None and self._pode_disparar(cooldown):
            delta_ang = abs(angulo - self._ultimo_angulo)
            delta_acc = max(abs(accel[i] - self._ultimo_accel[i]) for i in range(3))
            ang_ok = delta_ang >= lim_ang
            acc_ok = delta_acc >= lim_acc
            if exige_ambos:
                if ang_ok and acc_ok:
                    self._ultimo_gatilho = time.monotonic()
                    self.callback()
            elif ang_ok or acc_ok:
                self._ultimo_gatilho = time.monotonic()
                self.callback()

        self._ultimo_angulo = angulo
        self._ultimo_accel = accel
