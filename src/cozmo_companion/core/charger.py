"""Trava na base — carga inteligente mantendo bateria acima do mínimo."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

import pycozmo
from pycozmo import robot

from cozmo_companion.core.alive import filtrar_animacoes_base

logger = logging.getLogger("cozmo.charger")

ANIMACOES_CARGA = frozenset(
    {
        "PlacedOnCharger",
        "IdleOnCharger",
        "IdleOnChargerCharging",
        "GoToSleepSleeping",
        "Sleeping",
        "StartSleeping",
        "gotoSleep_sleeping",
        "sleeploop",
        "NeutralFace",
        "InterestedFace",
        "ReactToPokeReaction",
        "LookInPlaceForFacesHeadMovePause",
    }
)

GRUPOS_CARGA = (
    "PlacedOnCharger",
    "IdleOnChargerCharging",
    "IdleOnCharger",
)

GRUPOS_CARGA_SILENCIOSO = (
    "IdleOnChargerCharging",
    "NeutralFace",
    "InterestedFace",
    "LookInPlaceForFacesHeadMovePause",
)

BATTERY_FULL_V = 4.05
BATTERY_LOW_V = 3.6
BATTERY_V_MIN = 3.5
BATTERY_V_MAX = 4.05
BATTERY_MIN_PCT = int(os.environ.get("BATTERY_MIN_PCT", "60"))
BATTERY_CHARGE_STOP_PCT = int(os.environ.get("BATTERY_CHARGE_STOP_PCT", "90"))
BATTERY_CHARGE_RESUME_PCT = int(os.environ.get("BATTERY_CHARGE_RESUME_PCT", "60"))
# Queda > N V num tick na base = leitura falsa (contato/UDP), não atualiza filtro.
BATTERY_DROP_SPIKE_V = float(os.environ.get("BATTERY_DROP_SPIKE_V", "0.25"))

_carga_prioritaria = False


def modo_botao() -> bool:
    """Base/mesa só pelo botão de cima — sem adivinhar sensores."""
    return os.environ.get("BASE_MODO_BOTAO", "1") == "1"


def na_base(cli: pycozmo.Client) -> bool:
    from cozmo_companion.core.pycozmo_cli import resolver_cliente

    c = resolver_cliente(cli)
    return bool(c.robot_status & robot.RobotStatusFlag.IS_ON_CHARGER)


def em_base(cli: pycozmo.Client) -> bool:
    """Na base ou carregando — mais confiável que só IS_ON_CHARGER."""
    from cozmo_companion.core.pycozmo_cli import resolver_cliente

    c = resolver_cliente(cli)
    st = c.robot_status
    return bool(
        st & (robot.RobotStatusFlag.IS_ON_CHARGER | robot.RobotStatusFlag.IS_CHARGING)
    )


_oled_preso_na_base = False


def _modo_botao_arquivo() -> Path:
    raiz = Path(__file__).resolve().parents[2]
    return raiz / "data" / "cozmo-modo-botao.json"


def carregar_modo_botao() -> dict[str, bool] | None:
    """Último modo BASE/MESA escolhido pelo botão (≠ sensor no boot)."""
    path = _modo_botao_arquivo()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or "preso_na_base" not in raw:
            return None
        return {
            "preso_na_base": bool(raw["preso_na_base"]),
            "mesa_escolhida": bool(raw.get("mesa_escolhida", not raw["preso_na_base"])),
        }
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


def salvar_modo_botao(*, preso_na_base: bool, mesa_escolhida: bool) -> None:
    path = _modo_botao_arquivo()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {"preso_na_base": preso_na_base, "mesa_escolhida": mesa_escolhida},
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        logger.debug("salvar_modo_botao: %s", exc)


def definir_oled_preso_na_base(preso: bool) -> bool:
    """Modo botão: OLED na base segue preso_na_base (≠ IS_ON_CHARGER instável)."""
    global _oled_preso_na_base
    _oled_preso_na_base = preso
    return preso


def na_base_oled(cli: pycozmo.Client) -> bool:
    """Base efetiva para OLED — só modo BASE (botão), não sensor solto."""
    if modo_botao():
        return _oled_preso_na_base
    if _oled_preso_na_base:
        return True
    return em_base(cli) or carregando(cli)


def base_sempre_na_carga() -> bool:
    """Porco: Cozmo fixo na base — comportamento dock/carga mesmo com 100%%."""
    return os.environ.get("COZMO_BASE_SEMPRE_CARGA", "0") == "1"


def base_oled_estavel(cli: "pycozmo.Client") -> bool:
    """Dock fixo: keeper + IdleOnCharger — evita flood UDP (COZMO 01)."""
    if not base_sempre_na_carga():
        return False
    return na_base_oled(cli)


def carregando(cli: pycozmo.Client) -> bool:
    from cozmo_companion.core.pycozmo_cli import resolver_cliente

    c = resolver_cliente(cli)
    return bool(c.robot_status & robot.RobotStatusFlag.IS_CHARGING)


def em_modo_carga_base(cli: pycozmo.Client) -> bool:
    """Na base em modo dock: carga real ou COZMO_BASE_SEMPRE_CARGA=1."""
    if not na_base_oled(cli):
        return False
    return carregando(cli) or base_sempre_na_carga()


def carga_firmware_pausada(cli: pycozmo.Client) -> bool:
    """100%% na base sem carga ativa — firmware Anki para o link procedural."""
    if not na_base_oled(cli):
        return False
    pct = bateria_pct(cli)
    stop = int(os.environ.get("BATTERY_CHARGE_STOP_PCT", "90"))
    return pct >= stop and not carregando(cli)


def contato_base_ruim(cli: pycozmo.Client) -> bool:
    from cozmo_companion.core.pycozmo_cli import resolver_cliente

    c = resolver_cliente(cli)
    return bool(c.robot_status & robot.RobotStatusFlag.IS_CHARGER_OOS)


def bateria_pct(
    cli: pycozmo.Client,
    v_min: float = BATTERY_V_MIN,
    v_max: float = BATTERY_V_MAX,
) -> int:
    v = cli.battery_voltage
    if v <= 0:
        return 0
    return max(0, min(100, int((v - v_min) / (v_max - v_min) * 100)))


def bateria_cheia(cli: pycozmo.Client, limite: float = BATTERY_FULL_V) -> bool:
    return cli.battery_voltage >= limite


def bateria_baixa(cli: pycozmo.Client, limite: float = BATTERY_LOW_V) -> bool:
    return 0 < cli.battery_voltage < limite


def detectar_na_base_boot(cli: pycozmo.Client) -> bool:
    """Espera flags de base e voltagem de carregador antes de liberar mesa."""
    if em_base(cli) or na_base(cli) or carregando(cli):
        return True
    vol_boot = float(os.environ.get("BASE_VOL_BOOT", "3.85"))
    if cli.battery_voltage >= vol_boot:
        return True
    tentativas = int(os.environ.get("BASE_BOOT_TICKS", "8"))
    for _ in range(max(2, tentativas)):
        time.sleep(0.2)
        if em_base(cli) or na_base(cli) or carregando(cli):
            return True
        if cli.battery_voltage >= vol_boot:
            return True
    return False


def carga_prioritaria() -> bool:
    """True quando bateria baixa na base sem IS_CHARGING — corta anim/TTS pesado."""
    return _carga_prioritaria


def abaixo_limite_manutencao(cli: pycozmo.Client) -> bool:
    """Bateria abaixo do piso configurado (padrão 50%)."""
    return bateria_pct(cli) < BATTERY_MIN_PCT


def _rodas_ativas(cli: pycozmo.Client) -> bool:
    from cozmo_companion.core.pycozmo_cli import resolver_cliente

    c = resolver_cliente(cli)
    st = c.robot_status
    if st & (robot.RobotStatusFlag.IS_MOVING | robot.RobotStatusFlag.ARE_WHEELS_MOVING):
        return True
    if cli.robot_moving:
        return True
    try:
        if abs(cli.left_wheel_speed.mmps) > 2 or abs(cli.right_wheel_speed.mmps) > 2:
            return True
    except AttributeError:
        pass
    return False


class BaseGuard:
    """Mantém o robô na base; prioriza carga se bateria cair abaixo do mínimo."""

    TICKS_ENTRAR = 4
    TICKS_SAIR = int(os.environ.get("BASE_TICKS_SAIR", "200"))

    def __init__(self) -> None:
        self._ultimo_stop = 0.0
        self._na_base = False
        # Acordar/boot = BASE; MESA só pelo botão na sessão (não restaurar JSON).
        self._preso_na_base = True
        self._mesa_escolhida = False
        definir_oled_preso_na_base(True)
        self._modo_economia = False
        self._entrou_em = 0.0
        self._avisou_sem_carga = False
        self._avisou_bateria_baixa = False
        self._ultimo_log = 0.0
        self._ticks_na_base = 0
        self._ticks_fora_base = 0
        self._v_filtrada: float | None = None
        self._ultimo_entrada = 0.0
        self._estava_carregando = False
        self._ultimo_anim_carga = 0.0
        self._ultimo_idle_charger = 0.0
        self._pickup_desde = 0.0
        self._fora_contato_desde = 0.0
        self._carga_pausada = False
        self._carga_urgente_ativa = False
        self._ultimo_log_carga = 0.0
        self._ultimo_toggle_botao = 0.0
        self._contato_anterior = False
        self._botao_prioridade_ate = 0.0

    @property
    def botao_prioridade_ativa(self) -> bool:
        return time.monotonic() < self._botao_prioridade_ate

    @property
    def carga_urgente(self) -> bool:
        """Só corta TTS proativo — não respostas ao usuário."""
        return self._carga_urgente_ativa

    @property
    def carga_completa(self) -> bool:
        return self._carga_pausada

    def voltagem_estavel(self, cli: pycozmo.Client) -> float:
        """Filtra picos falsos de bateria (contato instável na base)."""
        v = cli.battery_voltage
        if v <= 0:
            return self._v_filtrada or 0.0
        if self._v_filtrada is None:
            self._v_filtrada = v
        elif abs(v - self._v_filtrada) > 0.22:
            pass  # ignora spike (contato instável na base)
        elif v < self._v_filtrada - BATTERY_DROP_SPIKE_V and (
            self._preso_na_base or em_base(cli)
        ):
            pass  # queda absurda — robô na base não perde 25% em um tick
        else:
            self._v_filtrada = self._v_filtrada * 0.82 + v * 0.18
        return self._v_filtrada

    @property
    def preso_na_base(self) -> bool:
        """Histerese: na base até confirmar saída estável (contato instável)."""
        return self._preso_na_base

    @property
    def mesa_escolhida(self) -> bool:
        """Modo livre foi pedido pelo botão, mesmo se ainda está no carregador."""
        return self._mesa_escolhida

    @property
    def estava_na_base(self) -> bool:
        return self._na_base

    @property
    def base_estavel(self) -> bool:
        return self._preso_na_base

    @property
    def fora_estavel(self) -> bool:
        return self._ticks_fora_base >= self.TICKS_SAIR and not self._preso_na_base

    @property
    def ticks_fora_contato(self) -> int:
        return self._ticks_fora_base

    def filtrar_animacoes(
        self,
        candidatos: tuple[str, ...],
        grupos_disponiveis: set[str] | None = None,
    ) -> tuple[str, ...]:
        if grupos_disponiveis is not None:
            return filtrar_animacoes_base(candidatos, grupos_disponiveis)
        seguros = [c for c in candidatos if c in ANIMACOES_CARGA]
        return tuple(seguros) if seguros else ("IdleOnCharger", "Sleeping")

    def entrou_na_base(
        self,
        cli: pycozmo.Client,
        *,
        silencioso: bool = False,
        ligar_oled: bool = True,
    ) -> None:
        agora = time.monotonic()
        if self._preso_na_base:
            from cozmo_companion.core.debug_trace import dbg

            dbg(
                "H1",
                "charger.py:entrou_na_base",
                "skip_reentry",
                {
                    "silencioso": silencioso,
                    "carregando": carregando(cli),
                    "v": round(cli.battery_voltage, 2),
                },
            )
            from cozmo_companion.core.motor_cozmo import _base_clip_sem_rodas_ativo

            if _rodas_ativas(cli) and not _base_clip_sem_rodas_ativo(cli):
                cli.stop_all_motors()
            return
        self._ultimo_entrada = agora
        carg = carregando(cli)
        from cozmo_companion.core.motor_cozmo import _base_clip_sem_rodas_ativo

        if carg:
            if _rodas_ativas(cli) and not _base_clip_sem_rodas_ativo(cli):
                cli.stop_all_motors()
            if agora - self._ultimo_anim_carga > 30.0:
                tocar_anim_carga(cli)
                self._ultimo_anim_carga = agora
        elif _rodas_ativas(cli) and not _base_clip_sem_rodas_ativo(cli):
            cli.stop_all_motors()
        cli.set_lift_height(robot.MIN_LIFT_HEIGHT.mm)
        self._na_base = True
        v = self.voltagem_estavel(cli)
        pct = max(0, min(100, int((v - 3.5) / (4.05 - 3.5) * 100))) if v > 0 else bateria_pct(cli)
        self._modo_economia = pct < BATTERY_MIN_PCT and v < BATTERY_FULL_V
        self._entrou_em = agora
        self._avisou_sem_carga = False
        self._ticks_na_base = max(self._ticks_na_base, self.TICKS_ENTRAR)
        self._preso_na_base = True
        self._mesa_escolhida = False
        from cozmo_companion.core.charger import definir_oled_preso_na_base
        from cozmo_companion.core.motor_cozmo import ligar_oled_base

        definir_oled_preso_na_base(True)
        salvar_modo_botao(preso_na_base=True, mesa_escolhida=False)

        if ligar_oled:
            ligar_oled_base(cli, forcar=True, preso_na_base=True)
        if not silencioso:
            from cozmo_companion.core.debug_trace import dbg

            dbg(
                "H1",
                "charger.py:entrou_na_base",
                "first_entry",
                {"v": round(v, 2), "pct": pct, "carregando": carg},
            )
            logger.info(
                "Na base: %.2fV (%d%%) carregando=%s",
                v,
                pct,
                carg,
            )

    def saiu_da_base(self, cli: pycozmo.Client | None = None, *, motivo: str = "auto") -> bool:
        """Transição saindo da base — retorna True só na primeira vez."""
        if not self._preso_na_base:
            return False
        if base_sempre_na_carga() and motivo in ("auto", "mesa"):
            return False
        if os.environ.get("BASE_NUNCA_SAIR", "1") == "1" and motivo == "auto":
            return False
        if (
            modo_botao()
            and motivo in ("mesa", "pickup")
            and cli is not None
            and self._no_contato_base(cli)
        ):
            from cozmo_companion.core.debug_trace import dbg

            dbg(
                "H31",
                "charger.py:saiu_da_base",
                "blocked_botao_priority",
                {"motivo": motivo, "preso": True},
                run_id="post-fix",
            )
            return False
        self._na_base = False
        self._preso_na_base = False
        self._ticks_na_base = 0
        self._ticks_fora_base = max(self._ticks_fora_base, self.TICKS_SAIR)
        self._modo_economia = False
        self._carga_pausada = False
        if modo_botao() and motivo == "botao":
            self._mesa_escolhida = True
            definir_oled_preso_na_base(False)
            salvar_modo_botao(preso_na_base=False, mesa_escolhida=True)
        logger.info("Saiu da base (%s)", motivo)
        return True

    def _aplicar_modo_base_boot(self, cli: pycozmo.Client) -> None:
        agora = time.monotonic()
        self._na_base = True
        self._ticks_na_base = max(self._ticks_na_base, self.TICKS_ENTRAR)
        self._entrou_em = agora
        if _rodas_ativas(cli):
            cli.stop_all_motors()
        try:
            cli.set_lift_height(robot.MIN_LIFT_HEIGHT.mm)
        except Exception:
            pass
        definir_oled_preso_na_base(True)

    def inicializar_boot_modo_botao(self, cli: pycozmo.Client) -> bool:
        """Acordar/boot = sempre BASE; MESA só pelo botão na sessão."""
        from cozmo_companion.core.debug_trace import dbg

        on_charger = em_base(cli) or na_base(cli) or carregando(cli)
        self._botao_prioridade_ate = 0.0
        self._preso_na_base = True
        self._mesa_escolhida = False
        self._aplicar_modo_base_boot(cli)
        salvar_modo_botao(preso_na_base=True, mesa_escolhida=False)
        dbg(
            "H32",
            "charger.py:inicializar_boot_modo_botao",
            "boot_base",
            {
                "v": round(cli.battery_voltage, 2),
                "carregando": carregando(cli),
                "on_charger": on_charger,
            },
            run_id="post-fix",
        )
        logger.info("Boot: modo BASE (acordar — MESA só botão)")
        return True

    def alternar_modo_botao(self, cli: pycozmo.Client) -> bool:
        """Botão de cima: alterna BASE (travado) ↔ MESA (rodas)."""
        from cozmo_companion.core.debug_trace import dbg

        agora = time.monotonic()
        debounce = float(os.environ.get("BASE_TOGGLE_DEBOUNCE_S", "3.0"))
        if agora - self._ultimo_toggle_botao < debounce:
            dbg(
                "H24",
                "charger.py:alternar_modo_botao",
                "bounce_blocked",
                {"dt_s": round(agora - self._ultimo_toggle_botao, 3)},
                run_id="post-fix",
            )
            return self._preso_na_base
        self._ultimo_toggle_botao = agora

        if self._preso_na_base:
            if self._no_contato_base(cli):
                self._mesa_escolhida = True
                self._botao_prioridade_ate = agora + float(
                    os.environ.get("BASE_BOTAO_LOCK_S", "8")
                )
                salvar_modo_botao(preso_na_base=True, mesa_escolhida=True)
                cli.stop_all_motors()
                try:
                    cli.cancel_anim()
                except Exception:
                    pass
                logger.info("Botão: modo LIVRE armado — aguardando sair da base")
                return True
            ok = self.saiu_da_base(cli, motivo="botao")
            self._botao_prioridade_ate = agora + float(
                os.environ.get("BASE_BOTAO_LOCK_S", "8")
            )
            dbg(
                "H10",
                "charger.py:alternar_modo_botao",
                "mesa",
                {"ok": ok},
                run_id="post-fix",
            )
            cli.stop_all_motors()
            try:
                cli.cancel_anim()
            except Exception:
                pass
            logger.info("Botão: modo MESA — rodas liberadas")
            return False
        self._mesa_escolhida = False
        self._botao_prioridade_ate = agora + float(
            os.environ.get("BASE_BOTAO_LOCK_S", "8")
        )
        self.entrou_na_base(cli, silencioso=False)
        dbg(
            "H10",
            "charger.py:alternar_modo_botao",
            "base",
            {"v": round(cli.battery_voltage, 2)},
            run_id="post-fix",
        )
        cli.stop_all_motors()
        logger.info("Botão: modo BASE — rodas travadas")
        return True

    def _no_contato_base(self, cli: pycozmo.Client) -> bool:
        return em_base(cli) or na_base(cli) or carregando(cli)

    def _confirmado_fora_da_base(self, cli: pycozmo.Client) -> bool:
        """Levantou de verdade — sem contato elétrico/mecânico por tempo suficiente."""
        if self._no_contato_base(cli):
            return False
        if not cli.robot_picked_up:
            return False
        try:
            v = float(cli.battery_voltage or 0)
        except (TypeError, ValueError):
            v = 0.0
        if v >= float(os.environ.get("BASE_VOL_BOOT", "3.85")):
            return False
        limiar = float(os.environ.get("BASE_PICKUP_OFF_S", "1.2"))
        if self._fora_contato_desde <= 0:
            return False
        return time.monotonic() - self._fora_contato_desde >= limiar

    def liberar_da_base(self, cli: pycozmo.Client, *, motivo: str = "manual") -> bool:
        """Destrava rodas — pickup só fora do modo botão."""
        if not self._preso_na_base:
            return False
        if modo_botao() and motivo not in ("botao", "pickup", "mesa"):
            return False
        if motivo == "pickup":
            try:
                v = float(cli.battery_voltage or 0)
            except (TypeError, ValueError):
                v = 0.0
            vol_base = float(os.environ.get("BASE_VOL_BOOT", "3.85"))
            if v >= vol_base and not self._confirmado_fora_da_base(cli):
                from cozmo_companion.core.debug_trace import dbg

                dbg(
                    "H7",
                    "charger.py:liberar_da_base",
                    "pickup_vol_base",
                    {"v": round(v, 2), "em_base": em_base(cli)},
                    run_id="post-fix",
                )
                return False
            if not self._confirmado_fora_da_base(cli):
                from cozmo_companion.core.debug_trace import dbg

                dbg(
                    "H7",
                    "charger.py:liberar_da_base",
                    "pickup_blocked",
                    {
                        "em_base": em_base(cli),
                        "carregando": carregando(cli),
                        "picked_up": cli.robot_picked_up,
                        "fora_s": round(
                            time.monotonic() - self._fora_contato_desde, 2
                        )
                        if self._fora_contato_desde > 0
                        else 0,
                    },
                    run_id="post-fix",
                )
                return False
            limiar = float(os.environ.get("BASE_PICKUP_S", "0.5"))
            if self._pickup_desde <= 0:
                self._pickup_desde = time.monotonic()
                return False
            if time.monotonic() - self._pickup_desde < limiar:
                return False
        from cozmo_companion.core.debug_trace import dbg

        dbg(
            "H1",
            "charger.py:liberar_da_base",
            "unlock",
            {
                "motivo": motivo,
                "picked_up": cli.robot_picked_up,
                "em_base": em_base(cli),
            },
            run_id="post-fix",
        )
        self._pickup_desde = 0.0
        self._fora_contato_desde = 0.0
        return self.saiu_da_base(cli, motivo=motivo)

    def registrar_pickup(self, cli: pycozmo.Client, pegou: bool) -> None:
        if pegou and cli.robot_picked_up and not self._no_contato_base(cli):
            if self._pickup_desde <= 0:
                self._pickup_desde = time.monotonic()
        else:
            self._pickup_desde = 0.0

    def tentar_liberar_pickup(self, cli: pycozmo.Client) -> bool:
        if not self._preso_na_base or not cli.robot_picked_up:
            return False
        if modo_botao() and self._no_contato_base(cli):
            return False
        return self.liberar_da_base(cli, motivo="pickup")

    def _pode_auto_sair(self, cli: pycozmo.Client, v: float) -> bool:
        """Só libera mesa se claramente fora da base (não contato instável)."""
        if os.environ.get("BASE_NUNCA_SAIR", "1") == "1":
            return False
        limiar = float(os.environ.get("BASE_VOL_MIN_SAIR", "3.55"))
        return v > 0 and v < limiar and not em_base(cli) and not na_base(cli)

    def tick(self, cli: pycozmo.Client) -> None:
        agora = time.monotonic()
        contato = self._no_contato_base(cli)
        if contato and not self._contato_anterior:
            from cozmo_companion.core.debug_trace import dbg

            dbg(
                "H30",
                "charger.py:tick",
                "contato_novo",
                {
                    "v": round(cli.battery_voltage, 2),
                    "mesa_escolhida": self._mesa_escolhida,
                    "modo_botao": modo_botao(),
                },
                run_id="post-fix",
            )
            # Modo botão: BASE/MESA só pelo botão — sem auto-trava aqui.
            if not modo_botao() and not self._mesa_escolhida and not self._preso_na_base:
                self.entrou_na_base(cli, silencioso=False)
        self._contato_anterior = contato

        if contato:
            self._fora_contato_desde = 0.0
        elif self._preso_na_base and self._fora_contato_desde <= 0:
            self._fora_contato_desde = agora

        if contato:
            self._ticks_na_base += 1
            self._ticks_fora_base = 0
            self._na_base = True
            if not modo_botao():
                if self._ticks_na_base >= self.TICKS_ENTRAR and not self._preso_na_base:
                    self.entrou_na_base(cli, silencioso=True)
        else:
            self._ticks_fora_base += 1
            self._ticks_na_base = 0
            self._na_base = False
            if (
                modo_botao()
                and self._mesa_escolhida
                and self._preso_na_base
                and self._ticks_fora_base >= max(4, self.TICKS_SAIR // 8)
            ):
                self.saiu_da_base(cli, motivo="botao")
            elif modo_botao() and self._ticks_fora_base >= self.TICKS_SAIR // 4:
                self._mesa_escolhida = False
            if not modo_botao():
                v = self.voltagem_estavel(cli)
                if self._preso_na_base and not self._pode_auto_sair(cli, v):
                    self._ticks_fora_base = max(0, self._ticks_fora_base - 3)
                elif (
                    self._preso_na_base
                    and self._ticks_fora_base >= self.TICKS_SAIR
                    and self._pode_auto_sair(cli, v)
                ):
                    from cozmo_companion.core.debug_trace import dbg

                    dbg(
                        "H1",
                        "charger.py:tick",
                        "auto_sair",
                        {
                            "v": round(v, 2),
                            "em_base": em_base(cli),
                            "ticks_fora": self._ticks_fora_base,
                        },
                        run_id="post-fix",
                    )
                    self.saiu_da_base(cli, motivo="auto")

        if not self._preso_na_base and not em_base(cli):
            return

        agora = time.monotonic()
        v = self.voltagem_estavel(cli)
        pct = bateria_pct(cli) if v <= 0 else max(
            0, min(100, int((v - 3.5) / (4.05 - 3.5) * 100))
        )
        stop_pct = BATTERY_CHARGE_STOP_PCT
        resume_pct = BATTERY_CHARGE_RESUME_PCT
        carg = carregando(cli)
        if pct >= stop_pct and carg:
            self._carga_pausada = True
        elif pct < resume_pct:
            self._carga_pausada = False
        precisa_carga = pct < resume_pct
        self._modo_economia = precisa_carga and v < BATTERY_FULL_V
        self._carga_urgente_ativa = (
            self._preso_na_base
            and precisa_carga
            and not carregando(cli)
        )
        global _carga_prioritaria
        _carga_prioritaria = self._carga_urgente_ativa

        if agora - self._ultimo_log_carga > 180:
            self._ultimo_log_carga = agora
            if pct >= stop_pct and not carg:
                logger.info(
                    "Carga pausada (%.0f%%) — firmware para em ~%d%%; retoma abaixo de %d%%",
                    pct,
                    stop_pct,
                    resume_pct,
                )
            elif pct < resume_pct and not carg and em_base(cli):
                logger.warning(
                    "Base sem carga elétrica (%.0f%%, %.2fV) — reposicione o Cozmo",
                    pct,
                    v,
                )
        if (
            self._preso_na_base
            and pct >= stop_pct
            and not carg
            and agora - self._ultimo_idle_charger >= float(os.environ.get("COZMO_CHARGE_IDLE_S", "18"))
        ):
            from cozmo_companion.core.motor_cozmo import (
                base_oled_usa_charger,
                ligar_oled_base,
                oled_charger_vivo,
            )

            if base_oled_usa_charger(cli):
                if not oled_charger_vivo(cli):
                    ligar_oled_base(cli, forcar=True, preso_na_base=True)
                self._ultimo_idle_charger = agora
            elif os.environ.get("COZMO_PROC_CHARGE_IDLE", "0") == "1":
                from cozmo_companion.core.motor_cozmo import animar_idle_charger_base

                if animar_idle_charger_base(cli):
                    self._ultimo_idle_charger = agora

        anim_intervalo = float(os.environ.get("COZMO_ANIM_CARGA_S", "180"))
        skip_anim_carga = os.environ.get("COZMO_PROC_FACE_BASE", "1") == "1"
        if (
            not skip_anim_carga
            and carg
            and not self._estava_carregando
            and self._preso_na_base
            and agora - self._ultimo_anim_carga > anim_intervalo
        ):
            if tocar_anim_carga(cli):
                self._ultimo_anim_carga = agora
        elif (
            not skip_anim_carga
            and carg
            and self._preso_na_base
            and agora - self._ultimo_anim_carga > anim_intervalo * 2
        ):
            if tocar_anim_carga(cli):
                self._ultimo_anim_carga = agora
        self._estava_carregando = carg

        if pct < BATTERY_MIN_PCT and not self._avisou_bateria_baixa:
            self._avisou_bateria_baixa = True
            logger.warning(
                "Bateria abaixo de %d%% (%d%%) — priorizando carga na base",
                BATTERY_MIN_PCT,
                pct,
            )
        elif pct >= BATTERY_MIN_PCT:
            self._avisou_bateria_baixa = False

        from cozmo_companion.core.motor_cozmo import _base_clip_sem_rodas_ativo

        if not _base_clip_sem_rodas_ativo(cli):
            intervalo = float(os.environ.get("COZMO_MOTOR_STOP_S", "0.45"))
            if self._preso_na_base:
                intervalo = max(
                    intervalo,
                    float(os.environ.get("COZMO_MOTOR_STOP_BASE_S", "0.45")),
                )
            if carregando(cli) and not _rodas_ativas(cli):
                intervalo = max(
                    intervalo, float(os.environ.get("COZMO_MOTOR_STOP_CHARGE_S", "3.0"))
                )
            if _rodas_ativas(cli) and agora - self._ultimo_stop >= intervalo:
                self._ultimo_stop = agora
                try:
                    cli.stop_all_motors()
                except Exception:
                    pass

        if agora - self._ultimo_log > 120:
            self._ultimo_log = agora
            logger.info(
                "Bateria: %.2fV (%d%%) | na_base | carregando=%s | economia=%s",
                v,
                pct,
                carregando(cli),
                self._modo_economia,
            )

        if (
            not self._avisou_sem_carga
            and agora - self._entrou_em > 90
            and not carregando(cli)
            and pct < BATTERY_MIN_PCT
        ):
            self._avisou_sem_carga = True
            logger.warning(
                "Na base mas sem carga elétrica — reposicione o Cozmo (%.2fV, %d%%)",
                cli.battery_voltage,
                pct,
            )

    def deve_ficar_quieto(self) -> bool:
        """Nunca silencia o robô — só trava rodas na base."""
        if os.environ.get("SEMPRE_VIVO", "1") == "1":
            return False
        return self.base_estavel and self._modo_economia

    def pode_interagir(self) -> bool:
        """Voz e gestos leves sempre permitidos; economia só corta idle pesado."""
        return True

    def texto_tela_carga(self, cli: pycozmo.Client) -> str:
        pct = bateria_pct(cli)
        if carregando(cli):
            return f"Carga {pct}%"
        if pct >= BATTERY_CHARGE_STOP_PCT:
            return f"Ok {pct}%"
        if pct < BATTERY_CHARGE_RESUME_PCT:
            return f"Carga! {pct}%"
        return f"Base {pct}%"


def tocar_anim_carga(cli: pycozmo.Client) -> bool:
    """Animação na base — silenciosa por padrão (sem PlacedOnCharger repetido)."""
    from cozmo_companion.core.motor_cozmo import animar_grupo, base_oled_modo_direto, pulse_rosto_base

    if base_oled_modo_direto():
        if pulse_rosto_base(cli):
            logger.debug("Carga: OLED keepalive direto (sem anim 30fps)")
        return False
    disp = set(cli.animation_groups.keys())
    if os.environ.get("COZMO_SOM_CARGA", "0") == "1":
        pool = GRUPOS_CARGA
    else:
        pool = GRUPOS_CARGA_SILENCIOSO
    for nome in pool:
        if nome in disp:
            if animar_grupo(cli, nome, na_base=True, procedural_antes=False):
                logger.info("Animação de carga: %s", nome)
                return True
    return False


def impedir_saida_da_base(cli: pycozmo.Client) -> None:
    if na_base(cli):
        cli.stop_all_motors()
