"""Recuperação COZMO 01 / stall UDP — um único caminho (companion)."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from cozmo_companion.core.conexao import (
    MonitorRx,
    cozmo_alcanavel,
    nunca_desconectar_udp,
    permitir_reset_udp_cozmo01,
)
from cozmo_companion.core.governador import TickGovernador

if TYPE_CHECKING:
    from pycozmo import client as pycozmo_client

    from cozmo_companion.core.conexao import MedidorUdp

logger = logging.getLogger("cozmo.recovery")


@dataclass
class ResultadoRecuperacao:
    reset_udp: bool = False
    in_place: bool = False


def tx_saudavel_limite() -> int:
    return int(
        os.environ.get(
            "GOV_PPCLIP_DTX_OK",
            os.environ.get("COZMO_BASE_TX_STALL", "240"),
        )
    )


def stall_tx_base() -> int:
    return int(os.environ.get("COZMO_BASE_TX_STALL", "280"))


def prevent_dtx_base() -> int:
    return int(os.environ.get("COZMO01_PREVENT_DTX", "150"))


class RecuperadorCozmo01:
    """Contadores + decisão in-place vs reset UDP."""

    def __init__(self) -> None:
        self.stall_consecutivo = 0
        self.cozmo01_falhas = 0
        self._stall_desde = 0.0

    def atualizar_stall(
        self,
        cli: pycozmo_client.Client,
        g: TickGovernador,
        medidor: MedidorUdp,
        *,
        busy: bool,
        quieto: bool,
    ) -> None:
        drx, dtx, _ = medidor.amostra(cli)
        lim = tx_saudavel_limite()
        if g.rx_ok and (drx > 0 or dtx < lim):
            self.stall_consecutivo = 0
            self.cozmo01_falhas = 0
            self._stall_desde = 0.0
        elif not busy and not quieto and (not g.rx_ok or dtx >= lim):
            self.stall_consecutivo += 1
            if self._stall_desde <= 0:
                self._stall_desde = time.monotonic()

    def _cooldown_reset(self, *, emergencia: bool) -> float:
        if emergencia or self._stall_desde > 0:
            return float(os.environ.get("COZMO01_EMERG_COOLDOWN_S", "3"))
        return float(os.environ.get("COZMO01_RESET_COOLDOWN_S", "10"))

    def tick_base(
        self,
        cli: pycozmo_client.Client,
        g: TickGovernador,
        monitor: MonitorRx,
        medidor: MedidorUdp,
        *,
        busy: bool,
        quieto: bool,
        na_base: bool,
        ultimo_reconnect_udp: float,
        reconnect_udp: Callable[[], bool],
        recuperar_inplace: Callable[[], bool],
    ) -> ResultadoRecuperacao:
        """Um tick — ping, no máximo 1 seq in-place, reset UDP se RX não voltar."""
        if not na_base or not cozmo_alcanavel():
            return ResultadoRecuperacao()

        from cozmo_companion.core.motor_cozmo import (
            cortar_flood_udp_base,
            detectar_cozmo01_suspeito,
            ping_sessao_base,
            pulso_sync_base,
            recuperar_cozmo01_auto,
            rx_link_ok,
        )

        drx, dtx, _ = medidor.amostra(cli)
        agora = time.monotonic()
        reset_fails = max(1, int(os.environ.get("COZMO01_RESET_FAILS", "3")))
        reset_ticks = max(1, int(os.environ.get("COZMO01_RESET_STALL_TICKS", "2")))
        emergencia = not g.rx_ok and drx <= 0 and dtx >= stall_tx_base()
        if not g.rx_ok and self._stall_desde <= 0:
            self._stall_desde = agora
        stall_s = (
            agora - self._stall_desde
            if self._stall_desde > 0
            else 0.0
        )
        max_stall_s = float(os.environ.get("COZMO01_STALL_MAX_S", "10"))
        emerg_min_s = float(os.environ.get("COZMO01_EMERG_MIN_S", "4"))

        if drx <= 0 and dtx >= prevent_dtx_base():
            cortar_flood_udp_base(cli)
            pulso_sync_base(cli, forcado=True)
            ping_sessao_base(cli)

        if (busy or quieto) and not emergencia and stall_s < max_stall_s:
            return ResultadoRecuperacao()

        precisa = (
            not g.rx_ok
            or detectar_cozmo01_suspeito(cli)
            or (drx <= 0 and dtx >= prevent_dtx_base())
        )
        if not precisa:
            return ResultadoRecuperacao()

        # Ratio ruim mas governador ainda vê RX: uma seq leve (cooldown interno).
        if g.rx_ok and drx <= 0 and dtx >= prevent_dtx_base():
            if recuperar_cozmo01_auto(cli, monitor, medidor, forcar=False):
                logger.info(
                    "Preventiva OLED OK — drx=0 dtx=%d",
                    dtx,
                )
                return ResultadoRecuperacao(in_place=True)
            return ResultadoRecuperacao()

        cooldown = self._cooldown_reset(emergencia=emergencia)
        pode_reset = (
            permitir_reset_udp_cozmo01()
            and agora - ultimo_reconnect_udp >= cooldown
        )

        # RX morto: sequência in-place — só reset UDP após N falhas (evita COZMO 01 na tela).
        if not g.rx_ok and self.cozmo01_falhas < reset_fails:
            if recuperar_cozmo01_auto(cli, monitor, medidor, forcar=True):
                self.cozmo01_falhas = 0
                self._stall_desde = 0.0
                self.stall_consecutivo = 0
                logger.info(
                    "Recuperação OLED OK — RX voltou (dtx=%d)",
                    dtx,
                )
                return ResultadoRecuperacao(in_place=True)
            self.cozmo01_falhas += 1
            return ResultadoRecuperacao()

        deve_reset = pode_reset and (
            stall_s >= max_stall_s
            or self.cozmo01_falhas >= reset_fails
            or self.stall_consecutivo >= reset_ticks
            or (emergencia and stall_s >= emerg_min_s)
        )

        if deve_reset:
            logger.warning(
                "COZMO 01 — reset UDP (stall=%.0fs falhas=%d dtx=%d rx=STALL)",
                stall_s,
                self.cozmo01_falhas,
                dtx,
            )
            if reconnect_udp():
                self.stall_consecutivo = 0
                self.cozmo01_falhas = 0
                self._stall_desde = 0.0
                return ResultadoRecuperacao(reset_udp=True)
            return ResultadoRecuperacao()

        if nunca_desconectar_udp() and g.rx_ok:
            recuperar_inplace()
            return ResultadoRecuperacao(in_place=True)

        return ResultadoRecuperacao()
