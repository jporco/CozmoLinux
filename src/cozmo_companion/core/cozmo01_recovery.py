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
    cozmo_rota_ap,
    nunca_desconectar_udp,
    permitir_reset_udp_cozmo01,
)
from cozmo_companion.core.config import network_tuning
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
            str(network_tuning().base_tx_stall),
        )
    )


def stall_tx_base() -> int:
    return network_tuning().base_tx_stall


def prevent_dtx_base() -> int:
    return int(os.environ.get("COZMO01_PREVENT_DTX", "150"))


def reset_udp_permitido_no_modo_atual() -> bool:
    """Reset UDP só fora do OLED estável, salvo override explícito.

    No modo estável a tela deve continuar com keeper/clip e recuperação in-place.
    Disconnect UDP é o caminho que faz o firmware mostrar COZMO 01.
    """
    if not permitir_reset_udp_cozmo01():
        return False
    from cozmo_companion.core.motor_cozmo import base_oled_stable_only

    if not base_oled_stable_only():
        return True
    return os.environ.get("COZMO_BASE_STABLE_ALLOW_RESET", "0") == "1"


class RecuperadorCozmo01:
    """Contadores + decisão in-place vs reset UDP."""

    def __init__(self) -> None:
        self.stall_consecutivo = 0
        self.cozmo01_falhas = 0
        self._stall_desde = 0.0
        self._ultimo_pulso_stall = 0.0

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
            oled_frame_recente,
            oled_charger_vivo,
            ping_sessao_base,
            pulso_sync_base,
            recuperar_cozmo01_auto,
            rx_link_ok,
            rx_morto_s,
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

        # Throttle dos pulsos de recuperação: floodar ping/sync a cada tick afoga o
        # firmware e mantém o RX morto (captura tcpdump: 120 pkt/s sustentado). Um
        # pulso esparso deixa o link drenar e o RX volta sem reset.
        intervalo_pulso = float(os.environ.get("COZMO_BASE_STALL_PULSO_S", "1.5"))
        pode_pulsar = agora - self._ultimo_pulso_stall >= intervalo_pulso

        if drx <= 0 and dtx >= prevent_dtx_base() and pode_pulsar:
            self._ultimo_pulso_stall = agora
            cortar_flood_udp_base(cli)
            pulso_sync_base(cli, forcado=True)
            ping_sessao_base(cli)

        rx_morto = rx_morto_s()
        keeper_dead_max = float(os.environ.get("COZMO01_KEEPER_RX_DEAD_MAX_S", "8"))
        # Um keeper/frame recente só é sinal útil se o TX ainda está baixo.
        # No HW5 observado, tela "viva" com drx=0 e dtx alto é falso ACK:
        # o firmware continua aceitando envio por um tempo, mas o RX já travou.
        keeper_pode_segurar = dtx < stall_tx_base()
        if (
            not g.rx_ok
            and keeper_pode_segurar
            and (oled_charger_vivo(cli) or oled_frame_recente())
            and rx_morto < keeper_dead_max
        ):
            if agora - self._ultimo_pulso_stall >= intervalo_pulso:
                self._ultimo_pulso_stall = agora
                pulso_sync_base(cli, forcado=True)
                ping_sessao_base(cli)
            return ResultadoRecuperacao(in_place=True)

        # Failsafe: RX morto contínuo (relógio do tick principal, NÃO zerado pelas
        # preventivas) acima do teto → reset duro. Sem isso o flood fica preso minutos
        # quando uma preventiva "recupera" e zera os contadores a cada tick.
        teto_morto = float(os.environ.get("COZMO01_RX_DEAD_MAX_S", "12"))
        if cozmo_rota_ap():
            teto_morto = max(
                teto_morto,
                float(os.environ.get("COZMO01_RX_DEAD_ROUTE_S", "20")),
            )
        rx_morto_suficiente = rx_morto >= teto_morto
        if (
            not g.rx_ok
            and rx_morto_suficiente
            and reset_udp_permitido_no_modo_atual()
            and agora - ultimo_reconnect_udp >= self._cooldown_reset(emergencia=True)
        ):
            logger.warning(
                "COZMO 01 — reset UDP (RX morto %.0fs dtx=%d rx=STALL)",
                rx_morto,
                dtx,
            )
            if reconnect_udp():
                self.stall_consecutivo = 0
                self.cozmo01_falhas = 0
                self._stall_desde = 0.0
                return ResultadoRecuperacao(reset_udp=True)
            return ResultadoRecuperacao()

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
            reset_udp_permitido_no_modo_atual()
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

        deve_reset = (
            pode_reset
            and rx_morto_suficiente
            and (
                stall_s >= max_stall_s
                or self.cozmo01_falhas >= reset_fails
                or self.stall_consecutivo >= reset_ticks
                or (emergencia and stall_s >= emerg_min_s)
            )
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
