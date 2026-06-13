"""Watchdog de rodas — evita giro/ré infinito."""

from __future__ import annotations

import logging
import os
import time

import pycozmo

from cozmo_companion.core.charger import em_base, modo_botao

logger = logging.getLogger("cozmo.motors")

MAX_RODAS_S = float(os.environ.get("MOTOR_MAX_S", "2.5"))


class MotorWatchdog:
    """Para motores se ficarem ativos além do tempo seguro."""

    def __init__(self) -> None:
        self._desde = 0.0
        self._ultimo_stop = 0.0
        self._ultimo_cancel = 0.0

    _CANCEL_COOLDOWN = float(os.environ.get("MOTOR_CANCEL_COOLDOWN_S", "3.0"))

    def _rodando(self, cli: pycozmo.Client) -> bool:
        if cli.robot_moving:
            return True
        try:
            if abs(cli.left_wheel_speed.mmps) > 4 or abs(cli.right_wheel_speed.mmps) > 4:
                return True
        except AttributeError:
            pass
        return False

    def tick(
        self,
        cli: pycozmo.Client,
        *,
        na_base: bool,
        movimento_permitido: bool,
        rosto_procedural: bool = False,
    ) -> None:
        agora = time.monotonic()
        travado = na_base
        if not modo_botao():
            travado = travado or em_base(cli)
        if travado or cli.robot_picked_up:
            from cozmo_companion.core.motor_cozmo import _base_clip_sem_rodas_ativo

            rodando = self._rodando(cli)
            if _base_clip_sem_rodas_ativo(cli) and not rodando:
                return
            if rodando and not rosto_procedural:
                try:
                    cli.cancel_anim()
                except Exception:
                    pass
                logger.warning("Rodas ativas na base — parando animação e motores")
            cli.stop_all_motors()
            self._ultimo_stop = agora
            self._desde = 0.0
            return

        if movimento_permitido:
            self._desde = agora
            return

        if not self._rodando(cli):
            self._desde = 0.0
            return

        if self._desde <= 0:
            self._desde = agora
            return

        if agora - self._desde > MAX_RODAS_S and agora - self._ultimo_stop > 1.0:
            if agora - self._ultimo_cancel >= self._CANCEL_COOLDOWN:
                cli.cancel_anim()
                self._ultimo_cancel = agora
            cli.stop_all_motors()
            self._ultimo_stop = agora
            self._desde = 0.0
            logger.warning("Rodas paradas (watchdog %.1fs)", MAX_RODAS_S)
