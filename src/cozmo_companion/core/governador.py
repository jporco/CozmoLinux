"""Governador de tráfego UDP + Wi-Fi — ajusta antes de enviar, nunca satura."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from enum import Enum

from cozmo_companion.core.conexao import (
    MedidorUdp,
    MonitorRx,
    cozmo_alcanavel,
    cozmo_rota_ap,
    cozmo_ssid_visivel,
    conexao_ok,
    diagnostico,
    pode_tentar_wifi,
    ratio_udp,
    udp_leve_por_delta,
    udp_saturado_por_delta,
    wlan0_preso_cozmo,
)
from cozmo_companion.core.limites import limites
from cozmo_companion.core.config import network_tuning

logger = logging.getLogger("cozmo.governador")

# Custo abstrato por tipo de comando (unidades do bucket).
_CUSTO: dict[str, int] = {
    "micro": 1,
    "anim": 5,
    "tts": 3,
    "camera": 5,
    "oled": 1,
    "espirito": 5,
    "motor": 7,
    "cancel": 2,
}

_MIN_INTERVALO: dict[str, float] = {
    "micro": 0.8,
    "anim": 0.0,  # preenchido no __init__ a partir de limites
    "tts": 1.5,
    "camera": 8.0,
    "oled": 0.35,
    "espirito": 6.0,
    "motor": 4.0,
}


class FaseLink(Enum):
    VERDE = "verde"
    AMARELO = "amarelo"
    LARANJA = "laranja"
    VERMELHO = "vermelho"


@dataclass(frozen=True)
class TickGovernador:
    fase: FaseLink
    reduzir_trafego: bool
    abortar_flood: bool
    rx_ok: bool
    wifi_ok: bool
    pedir_wifi: bool
    pedir_recuperar: bool
    ratio: float
    ratio_ema: float


class GovernadorCozmo:
    """Orquestra permissões e orçamento UDP antes de cada ação pesada."""

    def __init__(self) -> None:
        lim = limites()
        _MIN_INTERVALO["anim"] = float(os.environ.get("GOV_MIN_ANIM_S", "3"))
        self._fase = FaseLink.VERDE
        self._tokens = float(os.environ.get("GOV_BUDGET_INICIAL", "18"))
        self._burst = float(os.environ.get("GOV_BURST", "22"))
        self._ratio_ema = 0.0
        self._quieto_ate = 0.0
        self._ultimo: dict[str, float] = {}
        self._ultimo_refill = time.monotonic()
        self._ultimo_wifi_probe = 0.0
        self._ultimo_pedido_wifi = 0.0
        self._wifi_ok: bool | None = None
        self._wifi_falhas = 0
        self._ultimo_log = 0.0
        self._ultimo_rx_ok = True
        self._base_anim_livre = False
        self._medidor = MedidorUdp()
        self._wifi_probe_s = float(os.environ.get("GOV_WIFI_PROBE_S", "90"))
        self._wifi_retry_s = float(os.environ.get("COZMO_WIFI_RETRY_S", "25"))
        self._prevencao = float(
            os.environ.get(
                "GOV_RATIO_PREVENCAO",
                str(lim.udp_ratio_leve * 0.88),
            )
        )

    @property
    def fase(self) -> FaseLink:
        return self._fase

    def marcar_quieto(self, segundos: float) -> None:
        """Pausa espírito/câmera — NÃO bloqueia anim de toque/vida."""
        self._quieto_ate = max(
            self._quieto_ate,
            time.monotonic() + max(3.0, segundos),
        )

    def reduzir_trafego(self) -> bool:
        """True = só extras pesados (espírito, explorar, câmera)."""
        return self._fase in (FaseLink.LARANJA, FaseLink.VERMELHO)

    def saturado(self) -> bool:
        return self._fase == FaseLink.VERMELHO

    @property
    def ultimo_rx_ok(self) -> bool:
        return self._ultimo_rx_ok

    def _taxa_refill(self) -> float:
        return {
            FaseLink.VERDE: float(os.environ.get("GOV_REFILL_VERDE", "14")),
            FaseLink.AMARELO: float(os.environ.get("GOV_REFILL_AMARELO", "7")),
            FaseLink.LARANJA: float(os.environ.get("GOV_REFILL_LARANJA", "3")),
            FaseLink.VERMELHO: float(os.environ.get("GOV_REFILL_VERMELHO", "1")),
        }[self._fase]

    def _refill(self, agora: float) -> None:
        dt = max(0.0, agora - self._ultimo_refill)
        self._ultimo_refill = agora
        self._tokens = min(self._burst, self._tokens + dt * self._taxa_refill())

    def pode(self, acao: str, *, prioridade: bool = False) -> bool:
        agora = time.monotonic()
        if self._wifi_ok is False:
            return False
        if agora < self._quieto_ate and acao in ("espirito", "camera") and not prioridade:
            return False

        if self._fase == FaseLink.VERMELHO:
            if prioridade and acao in ("tts", "oled", "anim"):
                return acao != "camera"
            return acao in ("oled",)

        if self._fase == FaseLink.LARANJA:
            if acao in ("espirito", "camera", "motor"):
                return False
            if acao == "anim" and not prioridade and not self._base_anim_livre:
                return False
            if acao == "tts" and not prioridade:
                return False
            # micro = pequeno gesto de cabeça/piscar, custo mínimo e serial.
            if acao == "micro":
                return True

        if self._fase == FaseLink.AMARELO:
            if acao in ("espirito", "camera") and not prioridade:
                return False

        return True

    def reservar(self, acao: str, *, prioridade: bool = False, custo: int | None = None) -> bool:
        """Reserva orçamento antes de enviar — False = adiar (não satura)."""
        if not self.pode(acao, prioridade=prioridade):
            return False
        agora = time.monotonic()
        self._refill(agora)
        min_i = _MIN_INTERVALO.get(acao, 0.0)
        if min_i > 0 and not prioridade and agora - self._ultimo.get(acao, 0.0) < min_i:
            return False
        c = custo if custo is not None else _CUSTO.get(acao, 1)
        if self._tokens < c and not prioridade:
            logger.debug(
                "Governador — sem budget para %s (%.1f < %d, fase=%s)",
                acao,
                self._tokens,
                c,
                self._fase.value,
            )
            return False
        self._tokens -= c
        self._ultimo[acao] = agora
        return True

    def tick(
        self,
        cli,
        *,
        monitor_rx: MonitorRx,
        busy: bool,
        quieto: bool,
    ) -> TickGovernador:
        agora = time.monotonic()
        lim = limites()
        em_quieto = agora < self._quieto_ate

        if agora - self._ultimo_wifi_probe >= self._wifi_probe_s:
            self._ultimo_wifi_probe = agora
            ok = cozmo_alcanavel() and cozmo_rota_ap()
            if ok:
                self._wifi_falhas = 0
            else:
                self._wifi_falhas += 1
            self._wifi_ok = ok
        elif self._wifi_ok is None:
            self._wifi_ok = cozmo_alcanavel() and cozmo_rota_ap()

        rx_monitor_ok = monitor_rx.tick(cli)
        drx, dtx, r_delta = self._medidor.amostra(cli)
        rx_ok = rx_monitor_ok or drx > 0
        r_acum = ratio_udp(cli)
        if r_delta > 0:
            if self._ratio_ema <= 0:
                self._ratio_ema = r_delta
            else:
                alpha = float(os.environ.get("GOV_EMA_ALPHA", "0.35"))
                self._ratio_ema = (1 - alpha) * self._ratio_ema + alpha * r_delta
        r_eff = max(r_delta, self._ratio_ema)
        leve_inst = udp_leve_por_delta(drx, dtx, r_delta)
        sat_inst = udp_saturado_por_delta(drx, dtx) and not rx_ok
        leve_ema = r_eff > float(os.environ.get("COZMO_UDP_DELTA_RATIO_LEVE", "4.5"))
        prev_ema = r_eff > self._prevencao
        idle_saudavel = drx > 0 or dtx < 80
        # Procedural 30fps: janela curta sem RX novo, mas TX ainda baixo (≠ flood COZMO 01)
        from cozmo_companion.core.conexao import _ppclip_sessao_viva, procedural_ativo
        from cozmo_companion.core.motor_cozmo import ppclip_base_ativo

        tx_stall = int(os.environ.get("GOV_TX_DELTA_STALL", "180"))
        ppclip = ppclip_base_ativo(cli)
        ppclip_ping = _ppclip_sessao_viva(cli)
        self._base_anim_livre = ppclip_ping
        tx_ppclip_ok = int(
            os.environ.get("GOV_PPCLIP_DTX_OK", str(network_tuning().base_tx_stall))
        )
        # drx=0 + dtx alto na janela = flood sem ACK — ≠ ppclip saudável.
        procedural_ok = (
            rx_ok
            and (procedural_ativo(cli) or ppclip or ppclip_ping)
            and (drx > 0 or dtx < tx_ppclip_ok)
        )

        wifi_ok = bool(self._wifi_ok) or (rx_ok and cozmo_rota_ap())
        udp_vivo = rx_ok and (wifi_ok or conexao_ok(cli))

        if em_quieto:
            fase = FaseLink.LARANJA if sat_inst else FaseLink.AMARELO
        elif procedural_ok:
            fase = FaseLink.AMARELO if prev_ema else FaseLink.VERDE
        elif not wifi_ok:
            fase = FaseLink.VERMELHO
            self._base_anim_livre = False
        elif not udp_vivo:
            fase = FaseLink.VERMELHO
        elif sat_inst or (not rx_ok and not busy and not quieto):
            fase = FaseLink.VERMELHO
        elif leve_inst or leve_ema or (not rx_ok and busy):
            fase = FaseLink.LARANJA
        elif prev_ema:
            fase = FaseLink.AMARELO
        else:
            fase = FaseLink.VERDE

        self._fase = fase
        if wifi_ok:
            self._refill(agora)
        else:
            self._tokens = 0.0

        reduzir = fase != FaseLink.VERDE or em_quieto
        abortar = (
            sat_inst
            and not busy
            and not quieto
            and not em_quieto
            and not rx_ok
        )

        pedir_wifi = (
            not wifi_ok
            and agora - self._ultimo_pedido_wifi >= self._wifi_retry_s
        )
        if pedir_wifi:
            if (
                not pode_tentar_wifi(forcado=not cozmo_rota_ap())
                and not cozmo_ssid_visivel(rescan=True)
                and not wlan0_preso_cozmo()
            ):
                pedir_wifi = False
            else:
                self._ultimo_pedido_wifi = agora

        stall_rx = (
            not rx_ok
            and drx <= 0
            and dtx >= int(os.environ.get("GOV_TX_DELTA_STALL", "400"))
            and not procedural_ok
        )
        pedir_recuperar = stall_rx and not busy and not quieto and not em_quieto

        if agora - self._ultimo_log >= float(os.environ.get("GOV_LOG_S", "20")):
            self._ultimo_log = agora
            from cozmo_companion.core.debug_trace import dbg

            dbg(
                "H20",
                "governador.py:tick",
                "fase",
                {
                    "fase": fase.value,
                    "drx": drx,
                    "dtx": dtx,
                    "ratio_delta": round(r_delta, 2),
                    "ratio_acum": round(r_acum, 2),
                    "ema": round(self._ratio_ema, 2),
                    "tokens": round(self._tokens, 1),
                    "wifi": wifi_ok,
                    "rx_ok": rx_ok,
                    "reduzir": reduzir,
                },
                run_id="gov",
            )
            logger.info(
                "Governador fase=%s drx=%d dtx=%d rd=%.2f acum=%.2f tokens=%.0f wifi=%s rx=%s",
                fase.value,
                drx,
                dtx,
                r_delta,
                r_acum,
                self._tokens,
                "OK" if wifi_ok else "FAIL",
                "OK" if rx_ok else "STALL",
            )

        self._ultimo_rx_ok = rx_ok
        return TickGovernador(
            fase=fase,
            reduzir_trafego=reduzir,
            abortar_flood=abortar,
            rx_ok=rx_ok,
            wifi_ok=wifi_ok,
            pedir_wifi=pedir_wifi,
            pedir_recuperar=pedir_recuperar,
            ratio=r_delta,
            ratio_ema=self._ratio_ema,
        )
