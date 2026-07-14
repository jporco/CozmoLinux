"""Política — guardian NÃO reinicia companion se ping OK (evita desconectar)."""

from __future__ import annotations

import time
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path

from cozmo_companion.guardian.core.health import Saude
from cozmo_companion.guardian.core import actions
from cozmo_companion.core.paths import health_file


class AcaoGuardian(Enum):
    NADA = auto()
    REINICIAR = auto()
    REINICIAR_TRAVADO = auto()
    WIFI_APENAS = auto()
    PERFIL_ESTAVEL = auto()
    PERFIL_NORMAL = auto()


@dataclass
class EstadoGuardian:
    iniciado_em: float = field(default_factory=time.monotonic)
    ultimo_restart: float | None = None
    restarts_janela: list[float] = field(default_factory=list)
    perfil_estavel: bool = False
    ciclos_ok: int = 0
    ultimo_wifi: float = 0.0
    ultimo_trim_log: float = 0.0
    servico_off_desde: float | None = None

    def registrar_restart(self) -> None:
        agora = time.monotonic()
        self.ultimo_restart = agora
        self.restarts_janela = [t for t in self.restarts_janela if agora - t < 900]
        self.restarts_janela.append(agora)

    def pode_reiniciar(self, cooldown_s: float) -> bool:
        if self.ultimo_restart is None:
            return True
        return time.monotonic() - self.ultimo_restart >= cooldown_s

    def marcar_servico(self, ativo: bool) -> None:
        if ativo:
            self.servico_off_desde = None
        elif self.servico_off_desde is None:
            self.servico_off_desde = time.monotonic()


def _health_json_estagnado(root: Path, max_s: float) -> bool:
    path = health_file(root)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        ts = datetime.fromisoformat(str(raw["ts"]))
        return max(0.0, time.time() - ts.timestamp()) >= max_s
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return False


def decidir(
    saude: Saude,
    estado: EstadoGuardian,
    *,
    root: Path,
    cooldown_restart_s: float = 600.0,
) -> AcaoGuardian:
    import os

    estado.marcar_servico(saude.servico_ativo)

    # Serviço morto — só sobe de novo se ficou parado tempo suficiente (evita restart storm).
    if not saude.servico_ativo:
        morto_s = (
            time.monotonic() - estado.servico_off_desde
            if estado.servico_off_desde is not None
            else 0.0
        )
        limite = float(os.environ.get("GUARDIAN_RESTART_DEAD_S", "120"))
        if morto_s >= limite and estado.pode_reiniciar(cooldown_restart_s):
            return AcaoGuardian.REINICIAR
        return AcaoGuardian.NADA

    # Processo pode continuar "active" enquanto o loop principal morreu.
    # Nesse caso threads OLED antigas ainda escrevem no log, então o heartbeat
    # textual engana. O JSON é escrito apenas pelo loop principal.
    stale_s = float(os.environ.get("GUARDIAN_HEALTH_STALE_S", "240"))
    boot_grace = float(os.environ.get("GUARDIAN_BOOT_GRACE_S", "180"))
    passou_boot = time.monotonic() - estado.iniciado_em >= boot_grace
    if (
        passou_boot
        and _health_json_estagnado(root, stale_s)
        and estado.pode_reiniciar(cooldown_restart_s)
    ):
        return AcaoGuardian.REINICIAR_TRAVADO

    # Sessão UDP recente — companion vivo. ICMP do Cozmo falha intermitentemente
    # mesmo com RX/UDP OK; não reconectar Wi-Fi só por ping.
    s = saude.sessao
    if (
        s
        and s.idade_s < float(os.environ.get("GUARDIAN_SESSAO_FRESH_S", "300"))
    ):
        if s.estado == "CONNECTED" and s.rx > 0 and s.ratio < 3.5:
            estado.ciclos_ok += 1
            if estado.perfil_estavel and estado.ciclos_ok >= 12:
                return AcaoGuardian.PERFIL_NORMAL
            return AcaoGuardian.NADA

    # Ping falhou — reconecta AP se visível ou wlan0 preso em Cozmo.
    if not saude.ping_ok:
        from cozmo_companion.core.conexao import cozmo_ssid_visivel, wlan0_preso_cozmo

        if not cozmo_ssid_visivel(rescan=True) and not wlan0_preso_cozmo():
            return AcaoGuardian.NADA
        wifi_cd = float(os.environ.get("GUARDIAN_WIFI_COOLDOWN_S", "25"))
        if time.monotonic() - estado.ultimo_wifi >= wifi_cd:
            return AcaoGuardian.WIFI_APENAS
        return AcaoGuardian.NADA

    estado.ciclos_ok += 1
    if estado.perfil_estavel and estado.ciclos_ok >= 12:
        return AcaoGuardian.PERFIL_NORMAL

    # Erros UDP / COZMO 01 — companion resolve in-place; guardian só observa.
    return AcaoGuardian.NADA


def executar(acao: AcaoGuardian, root: Path, estado: EstadoGuardian) -> None:
    if acao == AcaoGuardian.NADA:
        return
    if acao == AcaoGuardian.PERFIL_ESTAVEL:
        actions.perfil_estavel(root)
        estado.perfil_estavel = True
        return
    if acao == AcaoGuardian.PERFIL_NORMAL:
        actions.perfil_normal(root)
        estado.perfil_estavel = False
        return
    if acao == AcaoGuardian.WIFI_APENAS:
        actions.reconectar_wifi(root)
        estado.ultimo_wifi = time.monotonic()
        return
    if acao == AcaoGuardian.REINICIAR:
        actions.reiniciar_companion()
        estado.registrar_restart()
        actions.aguardar_servico()
        return
    if acao == AcaoGuardian.REINICIAR_TRAVADO:
        actions.reiniciar_companion(forcar=True)
        estado.registrar_restart()
        actions.aguardar_servico()
