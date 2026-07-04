"""Mesa segura — sensores de borda, recuo e exploração lenta."""

from __future__ import annotations

import logging
import os
import random
import time
from typing import TYPE_CHECKING, Callable

import pycozmo
from pycozmo import event, protocol_encoder, robot

from cozmo_companion.core.anims import (
    GRUPOS_MESA_CARREGADOR,
    ContextoAnim,
    escolher_ctx,
)
from cozmo_companion.core.charger import (
    abaixo_limite_manutencao,
    carregando,
    em_base,
    modo_botao,
    na_base,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger("cozmo.mesa")

CLIFF_MIN_RAW = int(os.environ.get("CLIFF_MIN_RAW", "380"))
CLIFF_RATIO = float(os.environ.get("CLIFF_RATIO", "0.58"))
MESA_VEL = int(os.environ.get("MESA_VEL_MAX", "32"))
MESA_RECUO_VEL = int(os.environ.get("MESA_RECUO_VEL", "30"))
BUMP_DELTA = float(os.environ.get("MESA_BUMP_DELTA", "2.2"))
MESA_BUMP_MIN_WHEEL = int(os.environ.get("MESA_BUMP_MIN_WHEEL", "10"))
MESA_EMERG_COOLDOWN = float(os.environ.get("MESA_EMERG_COOLDOWN", "3.0"))


def _faixa(nome_min: str, nome_max: str, padrao_min: float, padrao_max: float) -> tuple[float, float]:
    lo = float(os.environ.get(nome_min, str(padrao_min)))
    hi = float(os.environ.get(nome_max, str(padrao_max)))
    return lo, max(lo + 0.1, hi)


def cliff_detectado(cli: pycozmo.Client) -> bool:
    return bool(cli.robot_status & robot.RobotStatusFlag.CLIFF_DETECTED)


def _sensor_ativo(valor: int) -> bool:
    return valor > 0


class SensoresMesa:
    """Lê cliff_data_raw do RobotState (4 sensores IR embaixo)."""

    def __init__(self, cli: pycozmo.Client, segura: "MesaSegura"):
        self.cli = cli
        self._segura = segura
        self.cliff: list[int] = [0, 0, 0, 0]
        self._baseline: list[int] | None = None
        self._amostras_chao = 0
        cli.add_handler(protocol_encoder.RobotState, self._on_state)

    def _on_state(self, _pkt_src, pkt: protocol_encoder.RobotState) -> None:
        cli = self.cli
        self.cliff = list(pkt.cliff_data_raw)
        if self._segura.movimento_travado(cli):
            return
        if cli.robot_picked_up:
            return
        ativos = [v for v in self.cliff if _sensor_ativo(v)]
        if not ativos or max(ativos) < CLIFF_MIN_RAW:
            return
        if self._baseline is None:
            self._baseline = self.cliff.copy()
            self._amostras_chao = 1
            logger.info("Chão calibrado: %s", self._baseline)
            return
        if self._amostras_chao < 40 and not cliff_detectado(cli):
            self._baseline = [
                int((b * 3 + v) / 4) if _sensor_ativo(v) or _sensor_ativo(b) else b
                for b, v in zip(self._baseline, self.cliff)
            ]
            self._amostras_chao += 1

    def perigo_borda(self) -> bool:
        if self._segura.movimento_travado(self.cli):
            return False
        if cliff_detectado(self.cli):
            return True
        ativos = [v for v in self.cliff if _sensor_ativo(v)]
        if not ativos:
            return False
        if self._baseline:
            for atual, base in zip(self.cliff, self._baseline):
                if not _sensor_ativo(atual) and not _sensor_ativo(base):
                    continue
                if _sensor_ativo(base) and _sensor_ativo(atual):
                    if atual < base * CLIFF_RATIO:
                        return True
                elif _sensor_ativo(atual) and atual < CLIFF_MIN_RAW:
                    return True
            return False
        return min(ativos) < CLIFF_MIN_RAW

    def sensor_mais_fraco(self) -> int:
        return min(range(4), key=lambda i: self.cliff[i] if _sensor_ativo(self.cliff[i]) else 99999)


class MesaSegura:
    """Ativa stop-on-cliff do firmware e reage a bordas."""

    def __init__(self, cli: pycozmo.Client):
        self.cli = cli
        self._bloqueado = True
        self.sensores = SensoresMesa(cli, self)
        self._ultimo_susto = 0.0
        cli.add_handler(event.EvtCliffDetectedChange, self._on_cliff)

    def rodas_travadas(self, cli: pycozmo.Client) -> bool:
        """True = sem drive_wheels (carregador em MESA ou base fixa)."""
        if self._bloqueado:
            return True
        if modo_botao() and (em_base(cli) or na_base(cli)):
            return True
        if not modo_botao():
            return em_base(cli) or na_base(cli) or carregando(cli)
        return False

    def movimento_travado(self, cli: pycozmo.Client) -> bool:
        """True = explorador off. Modo botão: só o toggle BASE fixa."""
        if self._bloqueado:
            return True
        if modo_botao():
            return False
        return em_base(cli) or na_base(cli) or carregando(cli)

    def set_bloqueado(self, bloqueado: bool) -> None:
        """True na base — sem cliff, sem exploração."""
        self._bloqueado = bloqueado
        if bloqueado:
            self.sensores._baseline = None
            self.sensores._amostras_chao = 0
            self.cli.conn.send(protocol_encoder.EnableStopOnCliff(enable=False))
        else:
            self.cli.conn.send(protocol_encoder.EnableStopOnCliff(enable=True))

    def ativar(self, *, na_base: bool = False) -> None:
        if na_base:
            self.set_bloqueado(True)
            logger.info("Mesa bloqueada (na base).")
        else:
            self._bloqueado = False
            self.cli.conn.send(protocol_encoder.EnableStopOnCliff(enable=True))
            logger.info("Stop-on-cliff ativado (mesa segura).")

    def _on_cliff(self, _cli, estado: bool) -> None:
        cli = self.cli
        if (
            self._bloqueado
            or self.movimento_travado(cli)
            or cli.robot_picked_up
            or em_base(cli)
            or na_base(cli)
        ):
            return
        if estado:
            logger.warning("Borda detectada (firmware)!")
            self._ultimo_susto = time.monotonic()

    def colisao(self, accel_prev: tuple[float, float, float]) -> bool:
        if self.movimento_travado(self.cli):
            return False
        try:
            l = abs(self.cli.left_wheel_speed.mmps)
            r = abs(self.cli.right_wheel_speed.mmps)
            if l < MESA_BUMP_MIN_WHEEL and r < MESA_BUMP_MIN_WHEEL:
                return False
        except AttributeError:
            if not self.cli.robot_moving:
                return False
        a = self.cli.accel
        delta = (
            abs(a.x - accel_prev[0])
            + abs(a.y - accel_prev[1])
            + abs(a.z - accel_prev[2])
        )
        return delta > BUMP_DELTA


class ExploradorMesa:
    """Explora a mesa devagar — para, olha, anda pouco, recua na borda."""

    def __init__(
        self,
        segura: MesaSegura,
        *,
        obstaculo_frontal: Callable[[], bool] | None = None,
    ):
        self._segura = segura
        self._obstaculo_frontal = obstaculo_frontal
        self._estado = "off"
        self._ate = 0.0
        self._proxima = time.monotonic() + random.uniform(
            *_faixa("MESA_START_MIN_S", "MESA_START_MAX_S", 3.0, 8.0)
        )
        self._accel_prev = (0.0, 0.0, 0.0)
        self._duracao_andar = 0.0
        self._ultima_emergencia = 0.0
        self._desde_drive = 0.0

    @property
    def explorando(self) -> bool:
        return self._estado not in ("off", "pausa")

    @property
    def andando(self) -> bool:
        return self._estado == "andar"

    def antecipar(self, segundos: float = 3.0) -> None:
        """Encurta espera até a próxima exploração."""
        from cozmo_companion.core.debug_trace import dbg

        dbg(
            "H5",
            "mesa.py:antecipar",
            "schedule",
            {"segundos": segundos, "estado": self._estado},
            run_id="post-fix",
        )
        self._proxima = min(self._proxima, time.monotonic() + segundos)

    def parar_tudo(self, cli: pycozmo.Client) -> None:
        self._parar(cli)
        self._estado = "off"
        self._proxima = time.monotonic() + random.uniform(
            *_faixa("MESA_START_MIN_S", "MESA_START_MAX_S", 3.0, 8.0)
        )

    def _parar(self, cli: pycozmo.Client) -> None:
        cli.stop_all_motors()
        cli.cancel_anim()

    def _emergencia(self, cli: pycozmo.Client, motivo: str = "borda") -> None:
        agora = time.monotonic()
        if agora - self._ultima_emergencia < MESA_EMERG_COOLDOWN:
            return
        self._ultima_emergencia = agora
        self._parar(cli)
        grupos = set(cli.animation_groups.keys())
        if "ReactToCliff" in grupos:
            cli.play_anim_group("ReactToCliff")
        elif "ReactToPokeStartled" in grupos:
            cli.play_anim_group("ReactToPokeStartled")
        self._estado = "recuando"
        self._ate = agora + 0.4
        cli.drive_wheels(-MESA_RECUO_VEL, -MESA_RECUO_VEL)
        logger.info("Recuando (%s).", motivo)

    def _drive(self, cli: pycozmo.Client, left: float, right: float) -> None:
        if self._segura.rodas_travadas(cli):
            return
        from cozmo_companion.core.debug_trace import dbg

        dbg(
            "H5",
            "mesa.py:_drive",
            "wheels",
            {"left": left, "right": right, "estado": self._estado},
            run_id="post-fix",
        )
        self._accel_prev = (cli.accel.x, cli.accel.y, cli.accel.z)
        self._desde_drive = time.monotonic()
        cli.drive_wheels(left, right)

    def _iniciar_exploracao(self, cli: pycozmo.Client) -> None:
        if self._segura.movimento_travado(cli):
            return
        if abaixo_limite_manutencao(cli) and not (em_base(cli) or na_base(cli)):
            return
        so_cabeca = self._segura.rodas_travadas(cli)
        if so_cabeca:
            acao = random.choice(("pausa", "olhar", "olhar", "pausa", "olhar"))
        else:
            acao = random.choices(
                ("pausa", "olhar", "andar", "girar"),
                weights=(1.2, 2.2, 2.6, 1.8),
                k=1,
            )[0]
        self._accel_prev = (cli.accel.x, cli.accel.y, cli.accel.z)
        if acao == "pausa":
            self._estado = "pausa"
            self._ate = time.monotonic() + random.uniform(
                *_faixa("MESA_PAUSA_MIN_S", "MESA_PAUSA_MAX_S", 4.0, 12.0)
            )
        elif acao == "olhar":
            self._estado = "olhar"
            self._ate = time.monotonic() + random.uniform(
                *_faixa("MESA_OLHAR_MIN_S", "MESA_OLHAR_MAX_S", 4.0, 10.0)
            )
            ctx = (
                ContextoAnim.CARREGADOR
                if self._segura.rodas_travadas(cli)
                else ContextoAnim.MESA
            )
            candidatos = (
                GRUPOS_MESA_CARREGADOR
                if ctx == ContextoAnim.CARREGADOR
                else (
                    "LookInPlaceForFacesHeadMovePause",
                    "InteractWithFaceTrackingIdle",
                    "NeutralFace",
                )
            )
            nome = escolher_ctx(set(cli.animation_groups.keys()), candidatos, ctx)
            if nome:
                cli.play_anim_group(nome)
        elif acao == "girar":
            self._estado = "girar"
            self._ate = time.monotonic() + random.uniform(
                *_faixa("MESA_GIRO_MIN_S", "MESA_GIRO_MAX_S", 0.25, 0.55)
            )
            sentido = random.choice((-1, 1))
            self._drive(cli, -MESA_VEL * sentido, MESA_VEL * sentido)
        else:
            self._estado = "andar"
            self._duracao_andar = random.uniform(
                *_faixa("MESA_ANDAR_MIN_S", "MESA_ANDAR_MAX_S", 0.45, 1.0)
            )
            self._ate = time.monotonic() + self._duracao_andar
            self._drive(cli, MESA_VEL, MESA_VEL)

    def _checar_perigo(self, cli: pycozmo.Client, sens: SensoresMesa) -> None:
        """Só reage a borda/colisão quando está andando — não parado na mesa."""
        if self._segura.rodas_travadas(cli):
            return
        if self._estado == "andar":
            if sens.perigo_borda():
                self._emergencia(cli, "cliff")
                return
            if self._segura.colisao(self._accel_prev):
                logger.info("Colisão na mesa — recuando.")
                self._emergencia(cli, "colisão")
                return
            if self._obstaculo_frontal is not None and self._obstaculo_frontal():
                logger.info("Obstáculo à frente (câmera) — recuando antes do baque.")
                self._emergencia(cli, "obstáculo")
        elif self._estado == "girar":
            if sens.perigo_borda():
                self._emergencia(cli, "cliff no giro")
        # recuando/girar pós-recuo: não checar colisão (evita loop)

    def tick(self, cli: pycozmo.Client) -> None:
        from cozmo_companion.core.charger import base_sempre_na_carga

        if base_sempre_na_carga():
            if self._estado != "off":
                self.parar_tudo(cli)
            return
        travado = self._segura._bloqueado or cli.robot_picked_up
        if travado:
            if self._estado != "off":
                from cozmo_companion.core.debug_trace import dbg

                dbg(
                    "H22",
                    "mesa.py:tick",
                    "explorador_stop",
                    {
                        "bloqueado": self._segura._bloqueado,
                        "em_base": em_base(cli),
                        "modo_botao": modo_botao(),
                    },
                    run_id="post-fix",
                )
                self.parar_tudo(cli)
            return

        agora = time.monotonic()
        sens = self._segura.sensores

        if self._estado in ("andar", "girar"):
            self._checar_perigo(cli, sens)

        if self._estado == "recuando":
            if agora >= self._ate:
                self._parar(cli)
                self._estado = "girar"
                self._ate = agora + random.uniform(
                    *_faixa("MESA_GIRO_RECUO_MIN_S", "MESA_GIRO_RECUO_MAX_S", 0.35, 0.75)
                )
                g = random.choice((-1, 1))
                self._drive(cli, MESA_VEL * g, -MESA_VEL * g)
            return

        if self._estado in ("andar", "girar"):
            if agora >= self._ate:
                self._parar(cli)
                self._estado = "pausa"
                self._ate = agora + random.uniform(
                    *_faixa("MESA_PAUSA_MIN_S", "MESA_PAUSA_MAX_S", 4.0, 12.0)
                )
            return

        if self._estado == "olhar" and agora >= self._ate:
            self._estado = "pausa"
            self._ate = agora + random.uniform(
                *_faixa("MESA_PAUSA_MIN_S", "MESA_PAUSA_MAX_S", 4.0, 12.0)
            )
            return

        if self._estado == "pausa" and agora >= self._ate:
            self._estado = "off"
            self._proxima = agora + random.uniform(
                *_faixa("MESA_PROX_MIN_S", "MESA_PROX_MAX_S", 6.0, 18.0)
            )

        if self._estado != "off" or agora < self._proxima:
            return

        if abaixo_limite_manutencao(cli) and not (em_base(cli) or na_base(cli)):
            self._proxima = agora + 60
            return

        self._iniciar_exploracao(cli)
