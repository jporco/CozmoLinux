"""Ciclo de vida — acordado, sonolento, dormindo; câmera e tela em janelas."""

from __future__ import annotations

import logging
import os
import random
import time
from enum import Enum
from typing import TYPE_CHECKING, Callable

from cozmo_companion.core import motor_cozmo as _motor
from cozmo_companion.core.motor_cozmo import parar_rodas_apos_anim_base
from cozmo_companion.core.anims import (
    GRUPOS_ACORDAR_TOQUE,
    GRUPOS_BASE_DESCANSO,
    GRUPOS_BASE_VIVO,
    GRUPOS_SONO,
    GRUPOS_SONO_ENTRADA,
    GRUPOS_SONO_RONCO,
    ContextoAnim,
    detectar_contexto_anim,
    escolher_ctx,
    pool_variacao_oled_base,
)

if TYPE_CHECKING:
    import pycozmo

    from cozmo_companion.core.face_watch import FaceWatch
    from cozmo_companion.display.face import Tela

logger = logging.getLogger("cozmo.vida")

AWAKE_MIN = float(os.environ.get("AWAKE_MIN_S", "1800"))
AWAKE_MAX = float(os.environ.get("AWAKE_MAX_S", "2400"))
AWAKE_APOS_DESPERTAR = float(os.environ.get("AWAKE_APOS_DESPERTAR_S", "900"))
SLEEP_MIN = float(os.environ.get("SLEEP_MIN_S", "1800"))
SLEEP_MAX = float(os.environ.get("SLEEP_MAX_S", "3000"))


def _intervalo_acordado_s() -> tuple[float, float]:
    """Tempo acordado na base até ficar sonolento (COZMO_SLEEP_INTERVAL_MIN)."""
    raw = os.environ.get("COZMO_SLEEP_INTERVAL_MIN", "").strip()
    if raw:
        centro = max(60.0, float(raw) * 60.0)
        jitter = float(os.environ.get("COZMO_SLEEP_INTERVAL_JITTER_S", "90"))
        return max(60.0, centro - jitter), centro + jitter
    return AWAKE_MIN, AWAKE_MAX


def _pausa_pos_despertar_s(segundos: float | None) -> float:
    """Bloqueio mínimo antes de novo sono automático."""
    explicit = max(0.0, float(segundos)) if segundos is not None else 0.0
    if os.environ.get("COZMO_SLEEP_INTERVAL_MIN", "").strip():
        _, imax = _intervalo_acordado_s()
        teto = min(AWAKE_APOS_DESPERTAR, imax)
        if explicit > 0:
            return explicit
        return teto
    return max(explicit, AWAKE_APOS_DESPERTAR)


def _agendar_proximo_sono(agora: float, dur: float) -> float:
    imin, imax = _intervalo_acordado_s()
    if os.environ.get("COZMO_SLEEP_INTERVAL_MIN", "").strip():
        return agora + random.uniform(imin, imax)
    return agora + random.uniform(max(imin, dur), max(imax, dur + 60.0))


def _duracao_sono_s() -> tuple[float, float]:
    """Quanto tempo dorme antes de acordar (COZMO_SLEEP_DURATION_MIN)."""
    raw = os.environ.get("COZMO_SLEEP_DURATION_MIN", "").strip()
    if raw:
        centro = max(120.0, float(raw) * 60.0)
        jitter = float(os.environ.get("COZMO_SLEEP_DURATION_JITTER_S", "120"))
        return max(120.0, centro - jitter), centro + jitter
    return SLEEP_MIN, SLEEP_MAX


def _intervalo_sonolento_s() -> tuple[float, float]:
    """Fase sonolento na base — transição suave antes do sono."""
    return (
        float(os.environ.get("SONOLENTO_MIN_S", "90")),
        float(os.environ.get("SONOLENTO_MAX_S", "240")),
    )


def _intervalo_anim_base_s() -> tuple[float, float]:
    lo = float(os.environ.get("BASE_ANIM_MIN_S", "20"))
    hi = float(os.environ.get("BASE_ANIM_MAX_S", "55"))
    return max(12.0, lo), max(lo + 5.0, hi)


def _intervalo_descanso_s() -> tuple[float, float]:
    return (
        float(os.environ.get("DESCANSO_ANIM_MIN_S", "35")),
        float(os.environ.get("DESCANSO_ANIM_MAX_S", "90")),
    )
SONO_RONCO_MIN = float(os.environ.get("SONO_RONCO_MIN_S", "120"))
SONO_RONCO_MAX = float(os.environ.get("SONO_RONCO_MAX_S", "480"))
SONO_RONCO_CHANCE = float(os.environ.get("SONO_RONCO_CHANCE", "0.45"))
SONO_LOOP_MIN = float(os.environ.get("SONO_LOOP_MIN_S", "90"))
SONO_LOOP_MAX = float(os.environ.get("SONO_LOOP_MAX_S", "300"))
CAM_OFF_MIN = float(os.environ.get("CAM_OFF_MIN_S", "300"))
CAM_OFF_MAX = float(os.environ.get("CAM_OFF_MAX_S", "600"))
CAM_ON_S = float(os.environ.get("CAM_ON_S", "12"))
CAM_ON_MAX = float(os.environ.get("CAM_ON_MAX_S", "20"))
BASE_CAM_OFF_MIN = float(os.environ.get("BASE_CAM_OFF_MIN_S", "35"))
BASE_CAM_OFF_MAX = float(os.environ.get("BASE_CAM_OFF_MAX_S", "70"))
BASE_CAM_ON_S = float(os.environ.get("BASE_CAM_ON_S", "14"))
BASE_CAM_ON_MAX = float(os.environ.get("BASE_CAM_ON_MAX_S", "22"))
SONO_AUTO = os.environ.get("SONO_AUTO", "1") == "1"
SONO_TELA_ESCURA = os.environ.get("SONO_TELA_ESCURA", "0") == "1"


class Fase(Enum):
    ACORDADO = "acordado"
    SONOLENTO = "sonolento"
    DORMINDO = "dormindo"


class CicloVida:
    """Vida própria otimizada — não deixa tudo ligado o tempo todo."""

    def __init__(
        self,
        tela: "Tela",
        face: "FaceWatch",
        tocar: Callable[[tuple[str, ...]], None],
    ):
        self.tela = tela
        self.face = face
        self._tocar = tocar
        self.fase = Fase.ACORDADO
        self._proxima_fase = time.monotonic() + random.uniform(*_intervalo_acordado_s())
        self._proxima_camera = time.monotonic() + random.uniform(CAM_OFF_MIN, CAM_OFF_MAX)
        self._camera_ate = 0.0
        self._interacao_ate = 0.0
        self._proximo_ronco = 0.0
        self._proximo_loop_sono = 0.0
        self._proxima_anim_base = time.monotonic() + random.uniform(
            *_intervalo_anim_base_s()
        )
        self._proxima_anim_descanso = 0.0
        self._tela_sono_ativa = False
        self._falando_ativo = False

    @property
    def dormindo(self) -> bool:
        return self.fase == Fase.DORMINDO

    @property
    def em_sono(self) -> bool:
        return self.fase in (Fase.DORMINDO, Fase.SONOLENTO)

    @property
    def camera_pode(self) -> bool:
        """Câmera só na janela agendada — interação comum não abre câmera."""
        if self.dormindo:
            return False
        return time.monotonic() < self._camera_ate

    def abrir_camera_curta(self, segundos: float = 14.0, *, na_base: bool = True) -> bool:
        """Abre janela curta de câmera (wake word, agenda)."""
        if na_base and os.environ.get("COZMO_FACE_BASE", "0") != "1":
            return False
        agora = time.monotonic()
        dur = max(4.0, min(segundos, float(os.environ.get("BASE_CAM_ON_MAX_S", "12"))))
        if self.face.iniciar_busca(dur, na_base=na_base):
            self._camera_ate = max(self._camera_ate, agora + dur)
            return True
        return False

    def _marcar_acordado(
        self,
        cli: "pycozmo.Client",
        *,
        motivo: str,
        segundos: float | None = None,
        preso_na_base: bool = True,
        animar: bool = True,
    ) -> None:
        """Garante fase acordada e bloqueia novo sono por AWAKE_APOS_DESPERTAR (15 min)."""
        agora = time.monotonic()
        dur = _pausa_pos_despertar_s(segundos)
        estava_sono = self.em_sono
        self.fase = Fase.ACORDADO
        self._tela_sono_ativa = False
        _motor.definir_modo_sono_oled(False)
        _motor.desativar_sono_oled_texto()
        self.tela.clarear()
        if estava_sono:
            self._cancelar_anim_se_seguro(cli)
        try:
            if estava_sono and _motor.base_oled_modo_direto() and preso_na_base:
                _motor.religar_oled_acordado_base(cli, forcar=True)
            elif animar or estava_sono:
                _motor.modo_base_olhos(cli)
        except Exception:
            pass
        self.tela.mostrar(
            "^^",
            segundos=float(os.environ.get("TELA_ACORDOU_S", "8")),
            forcado=True,
            prioridade="sono",
        )
        if animar and estava_sono and not (
            _motor.base_oled_modo_direto() and preso_na_base
        ):
            self._tocar(GRUPOS_ACORDAR_TOQUE)
        self._interacao_ate = agora + dur
        self._proxima_fase = _agendar_proximo_sono(agora, dur)
        self._proxima_anim_base = agora + random.uniform(8.0, 22.0)
        self._proxima_anim_descanso = 0.0
        self._agendar_camera()
        if os.environ.get("COZMO_PROC_FACE_BASE", "1") == "1" and not (
            _motor.base_oled_modo_direto() and preso_na_base
        ):
            try:
                cli.anim_controller.enable_procedural_face(True)
            except Exception:
                pass
        logger.info("Acordou (%s) — sem sono por %.0f min", motivo, dur / 60)

    def acordar_para_voz(self, cli: "pycozmo.Client", *, preso_na_base: bool = True) -> None:
        """Voz acordou o Cozmo — animação se estiver dormindo."""
        if self.em_sono:
            self._marcar_acordado(cli, motivo="voz", preso_na_base=preso_na_base)
        else:
            self._marcar_acordado(
                cli,
                motivo="voz",
                segundos=AWAKE_APOS_DESPERTAR,
                preso_na_base=preso_na_base,
                animar=False,
            )
            if os.environ.get("WAKE_CAMERA_BASE", "0") == "1":
                self.abrir_camera_curta(
                    float(os.environ.get("BASE_CAM_ON_S", "10")),
                    na_base=True,
                )

    def registrar_interacao(
        self,
        segundos: float | None = None,
        *,
        cli: "pycozmo.Client | None" = None,
        motivo: str = "interacao",
        preso_na_base: bool = True,
    ) -> None:
        # Só despertar/notif sem segundos explícitos seguram 15 min; carinho/TTS usam o valor passado.
        dur = AWAKE_APOS_DESPERTAR if segundos is None else max(0.0, float(segundos))
        agora = time.monotonic()
        self._interacao_ate = max(self._interacao_ate, agora + dur)
        self._proxima_fase = max(self._proxima_fase, self._interacao_ate)
        if self.fase == Fase.DORMINDO and cli is None:
            return
        if self.fase != Fase.ACORDADO:
            if cli is not None:
                self._marcar_acordado(
                    cli,
                    motivo=motivo,
                    segundos=dur,
                    preso_na_base=preso_na_base,
                )
            else:
                self.fase = Fase.ACORDADO
                self._tela_sono_ativa = False
                self.tela.clarear()
                logger.info("Acordou (%s)", motivo)
        elif cli is not None and self._tela_sono_ativa:
            self._marcar_acordado(
                cli,
                motivo=motivo,
                segundos=dur,
                preso_na_base=preso_na_base,
                animar=False,
            )

    def _ctx_anim(self, *, na_base: bool, preso_na_base: bool) -> ContextoAnim:
        return detectar_contexto_anim(
            preso_na_base=preso_na_base,
            no_carregador=not na_base,
        )

    def _cancelar_anim_se_seguro(self, cli: "pycozmo.Client") -> None:
        """cancel_anim só fora do loop ppclip — evita matar OLED na base."""
        if _motor._base_oled_anim_loop_ativo() and _motor.base_oled_usa_charger(cli):
            return
        try:
            cli.cancel_anim()
        except Exception:
            pass

    def _executar_anim(
        self,
        cli: "pycozmo.Client",
        nome: str,
        *,
        na_base: bool,
        preso_na_base: bool,
        hold_s: float | None = None,
    ) -> None:
        if not nome:
            return
        if na_base and preso_na_base and _motor.base_oled_usa_charger(cli):
            if _motor.tocar_clip_base_seguro(cli, nome, hold_s=hold_s):
                try:
                    parar_rodas_apos_anim_base(cli)
                except Exception:
                    pass
                return
        self._cancelar_anim_se_seguro(cli)
        try:
            cli.play_anim_group(nome)
        except Exception as exc:
            logger.debug("Anim %s falhou: %s", nome, exc)
            return
        try:
            parar_rodas_apos_anim_base(cli)
        except Exception:
            pass

    def _pool_acordado(
        self,
        cli: "pycozmo.Client",
        *,
        preso_na_base: bool,
    ) -> tuple[str, ...]:
        disp = set(cli.animation_groups.keys())
        if preso_na_base:
            pool = pool_variacao_oled_base(disp, cli)
            if pool:
                return pool
        return GRUPOS_BASE_VIVO

    def _pick(
        self,
        cli: "pycozmo.Client",
        candidatos: tuple[str, ...],
        *,
        na_base: bool,
        preso_na_base: bool,
    ) -> str | None:
        ctx = self._ctx_anim(na_base=na_base, preso_na_base=preso_na_base)
        sem_som = ctx == ContextoAnim.BASE
        return escolher_ctx(
            set(cli.animation_groups.keys()),
            candidatos,
            ctx,
            sem_som_carga=sem_som,
        )

    def _anim_espontanea_acordado(
        self,
        cli: "pycozmo.Client",
        *,
        preso_na_base: bool,
    ) -> None:
        """Anim expressiva ou variação de clip — sem brigar com o loop OLED."""
        chance = float(os.environ.get("BASE_ANIM_CHANCE", "0.85"))
        if random.random() < chance:
            pool = self._pool_acordado(cli, preso_na_base=preso_na_base)
            nome = self._pick(
                cli, pool, na_base=True, preso_na_base=preso_na_base
            )
            if nome:
                self._tocar((nome,))
                return
        try:
            _motor.variar_clip_base_oled(cli)
        except Exception as exc:
            logger.debug("Variar clip acordado: %s", exc)

    def _tick_sonolento(
        self,
        cli: "pycozmo.Client",
        *,
        preso_na_base: bool,
        pode_animar: bool,
        falando: bool,
        agora: float,
    ) -> None:
        """Descanso com olhos pesados — ainda responde a voz/notif."""
        if not pode_animar or falando:
            return
        if self._proxima_anim_descanso <= 0:
            self._proxima_anim_descanso = agora + random.uniform(
                *_intervalo_descanso_s()
            )
            return
        if agora < self._proxima_anim_descanso:
            return
        self._proxima_anim_descanso = agora + random.uniform(
            *_intervalo_descanso_s()
        )
        nome = self._pick(
            cli,
            GRUPOS_BASE_DESCANSO,
            na_base=True,
            preso_na_base=preso_na_base,
        )
        if nome:
            self._executar_anim(
                cli,
                nome,
                na_base=True,
                preso_na_base=preso_na_base,
                hold_s=5.0,
            )
            logger.debug("Descanso (%s)", nome)

    def acordar_por_toque(self, cli: "pycozmo.Client", *, preso_na_base: bool = True) -> bool:
        """Acorda com animação ao tocar/mexer enquanto dorme."""
        if not self.em_sono:
            self._marcar_acordado(
                cli,
                motivo="toque",
                segundos=AWAKE_APOS_DESPERTAR,
                preso_na_base=preso_na_base,
                animar=False,
            )
            return False
        self._marcar_acordado(cli, motivo="toque", preso_na_base=preso_na_base)
        return True

    def despertar(
        self,
        cli: "pycozmo.Client",
        *,
        motivo: str = "evento",
        preso_na_base: bool = True,
    ) -> None:
        """Notificação / evento externo — acorda e segura 15 min acordado."""
        self._marcar_acordado(cli, motivo=motivo, preso_na_base=preso_na_base)

    def _agendar_sono(self) -> None:
        self._proxima_fase = time.monotonic() + random.uniform(*_duracao_sono_s())

    def _agendar_acordado(self) -> None:
        agora = time.monotonic()
        self._proxima_fase = max(
            self._interacao_ate,
            agora + random.uniform(*_intervalo_acordado_s()),
        )

    def _agendar_camera(self) -> None:
        if os.environ.get("SEMPRE_VIVO", "1") == "1":
            self._proxima_camera = time.monotonic() + random.uniform(
                BASE_CAM_OFF_MIN, BASE_CAM_OFF_MAX
            )
        else:
            self._proxima_camera = time.monotonic() + random.uniform(
                CAM_OFF_MIN, CAM_OFF_MAX
            )

    def _iniciar_sono(self, cli: "pycozmo.Client", *, preso_na_base: bool = True) -> None:
        self.fase = Fase.DORMINDO
        self.face.desligar()
        _motor.definir_modo_sono_oled(True)
        rotulo = "ppclip sleep"
        if SONO_TELA_ESCURA:
            self.tela.escurecer()
            self._tela_sono_ativa = False
        elif _motor.sono_oled_usa_texto():
            try:
                _motor.ativar_sono_oled_texto(cli)
            except Exception as exc:
                logger.warning("Sono OLED texto: %s", exc)
            self.tela.mostrar(
                "zZz", segundos=300.0, forcado=True, prioridade="sono"
            )
            self._tela_sono_ativa = True
            rotulo = "zZz legado"
            nome_in = self._pick(
                cli, GRUPOS_SONO_ENTRADA, na_base=True, preso_na_base=preso_na_base
            )
            if nome_in:
                self._executar_anim(
                    cli,
                    nome_in,
                    na_base=True,
                    preso_na_base=preso_na_base,
                    hold_s=8.0,
                )
                rotulo = nome_in
        else:
            try:
                _motor.entrar_sono_base_oled(cli)
            except Exception as exc:
                logger.warning("Sono OLED base: %s", exc)
            self._tela_sono_ativa = False
            try:
                _motor.manter_sono_ppclip(cli)
            except Exception:
                pass
        agora = time.monotonic()
        self._agendar_sono()
        self._proximo_ronco = agora + random.uniform(SONO_RONCO_MIN, SONO_RONCO_MAX)
        self._proximo_loop_sono = agora + random.uniform(SONO_LOOP_MIN, SONO_LOOP_MAX)
        dur = self._proxima_fase - agora
        logger.info("Dormindo (~%.0f min) — entrada %s", dur / 60, rotulo)

    def _tick_ronco(
        self,
        cli: "pycozmo.Client",
        *,
        preso_na_base: bool = True,
    ) -> None:
        if self.fase != Fase.DORMINDO:
            return
        if _motor.sono_oled_texto_ativo():
            return
        if _motor.modo_sono_oled_ativo() and not _motor.sono_oled_usa_texto():
            return
        agora = time.monotonic()
        if agora >= self._proximo_loop_sono:
            self._proximo_loop_sono = agora + random.uniform(SONO_LOOP_MIN, SONO_LOOP_MAX)
            nome = self._pick(
                cli, GRUPOS_SONO, na_base=True, preso_na_base=preso_na_base
            )
            if nome:
                self._executar_anim(
                    cli,
                    nome,
                    na_base=True,
                    preso_na_base=preso_na_base,
                    hold_s=6.0,
                )
                logger.debug("Loop sono (%s)", nome)
        if agora < self._proximo_ronco:
            return
        self._proximo_ronco = agora + random.uniform(SONO_RONCO_MIN, SONO_RONCO_MAX)
        if random.random() >= SONO_RONCO_CHANCE:
            return
        nome = self._pick(
            cli, GRUPOS_SONO_RONCO, na_base=True, preso_na_base=preso_na_base
        )
        if nome:
            try:
                ac = cli.anim_controller
                if os.environ.get("COZMO_PROC_FACE_BASE", "1") == "1":
                    ac.enable_procedural_face(False)
            except Exception:
                pass
            self._executar_anim(
                cli,
                nome,
                na_base=True,
                preso_na_base=preso_na_base,
                hold_s=4.0,
            )
            logger.info("Ronco (%s)", nome)

    def _acordar(
        self,
        cli: "pycozmo.Client",
        *,
        force: bool = False,
        preso_na_base: bool = True,
    ) -> None:
        if self.fase == Fase.ACORDADO and not force:
            return
        self._cancelar_anim_se_seguro(cli)
        self._marcar_acordado(cli, motivo="fim_sono", preso_na_base=preso_na_base)
        logger.info("Acordou (espreguiçou fim do sono)")

    def _sonolento(self, cli: "pycozmo.Client", *, preso_na_base: bool = True) -> None:
        self.fase = Fase.SONOLENTO
        self.face.desligar()
        agora = time.monotonic()
        nome = self._pick(
            cli,
            GRUPOS_BASE_DESCANSO + GRUPOS_SONO_ENTRADA[:1],
            na_base=True,
            preso_na_base=preso_na_base,
        )
        if nome:
            self._executar_anim(
                cli,
                nome,
                na_base=True,
                preso_na_base=preso_na_base,
                hold_s=6.0,
            )
        self._proxima_fase = agora + random.uniform(*_intervalo_sonolento_s())
        self._proxima_anim_descanso = agora + random.uniform(12.0, 28.0)
        logger.info(
            "Descansando (~%.0f min até cochilar)",
            (self._proxima_fase - agora) / 60.0,
        )

    def cochilar(self, cli: "pycozmo.Client", *, preso_na_base: bool = True) -> None:
        """Cochilo sob pedido (voz, LLM ou espírito)."""
        if self.dormindo:
            self._reforcar_sono(cli)
            return
        _motor.definir_modo_sono_oled(True)
        self._iniciar_sono(cli, preso_na_base=preso_na_base)

    def _reforcar_sono(self, cli: "pycozmo.Client") -> None:
        """Já dormindo — reaplica ppclip sleep (ou zZz legado)."""
        if _motor.sono_oled_usa_texto():
            try:
                if not _motor.sono_oled_texto_ativo():
                    _motor.ativar_sono_oled_texto(cli)
                else:
                    _motor.manter_sono_oled_texto(cli)
            except Exception as exc:
                logger.warning("Reforço sono OLED: %s", exc)
            self.tela.mostrar(
                "zZz", segundos=300.0, forcado=True, prioridade="sono"
            )
        else:
            try:
                _motor.entrar_sono_base_oled(cli)
                _motor.manter_sono_ppclip(cli)
            except Exception as exc:
                logger.warning("Reforço sono ppclip: %s", exc)
        logger.info("Sono reforçado (já dormindo)")

    def tick(
        self,
        cli: "pycozmo.Client",
        *,
        na_base: bool,
        preso_na_base: bool = True,
        falando: bool,
        pode_animar: bool,
        pode_camera: bool = True,
    ) -> None:
        agora = time.monotonic()

        if not na_base:
            if self.dormindo:
                self._acordar(cli, force=True, preso_na_base=preso_na_base)
            elif self.fase == Fase.SONOLENTO:
                self.fase = Fase.ACORDADO
            self.tela.clarear()
            return

        if falando:
            if not self._falando_ativo:
                self._falando_ativo = True
                ext = min(25.0, float(os.environ.get("FALANDO_SONO_EXT_S", "25")))
                self._interacao_ate = max(self._interacao_ate, agora + ext)
                self._proxima_fase = max(self._proxima_fase, self._interacao_ate)
        else:
            self._falando_ativo = False

        # Na base: sem ciclo sono — anim de sono mata procedural → COZMO 01 na tela.
        sono_na_base = os.environ.get("COZMO_SONO_NA_BASE", "0") == "1"
        if not sono_na_base:
            if self.dormindo or self.fase == Fase.SONOLENTO:
                self._marcar_acordado(
                    cli, motivo="base_sem_sono", preso_na_base=preso_na_base, animar=False
                )
            self._proxima_fase = agora + random.uniform(*_intervalo_acordado_s())
        elif self.fase == Fase.ACORDADO and agora >= self._proxima_fase:
            if agora < self._interacao_ate:
                self._proxima_fase = self._interacao_ate
            elif SONO_AUTO:
                self._sonolento(cli, preso_na_base=preso_na_base)
            else:
                self._proxima_fase = agora + random.uniform(*_intervalo_acordado_s())
            return
        elif self.fase == Fase.SONOLENTO:
            self._tick_sonolento(
                cli,
                preso_na_base=preso_na_base,
                pode_animar=pode_animar,
                falando=falando,
                agora=agora,
            )
            if agora >= self._proxima_fase:
                if SONO_AUTO:
                    self._iniciar_sono(cli, preso_na_base=preso_na_base)
                else:
                    self.fase = Fase.ACORDADO
                    self._agendar_acordado()
                return
            return
        elif self.fase == Fase.DORMINDO and agora >= self._proxima_fase:
            self._acordar(cli, preso_na_base=preso_na_base)
            return

        # Sono: ppclip oficial (olhos animados) — zZz só com COZMO_SONO_OLED_TEXTO=1
        if self.dormindo:
            if SONO_TELA_ESCURA:
                self.tela.manter_escuro()
            elif _motor.sono_oled_usa_texto():
                self.tela.mostrar(
                    "zZz", segundos=300.0, forcado=False, prioridade="sono"
                )
                if not _motor.sono_oled_texto_ativo():
                    try:
                        _motor.ativar_sono_oled_texto(cli)
                    except Exception:
                        pass
                _motor.manter_sono_oled_texto(cli)
                self._tela_sono_ativa = True
            else:
                self._tela_sono_ativa = False
                _motor.definir_modo_sono_oled(True)
                try:
                    _motor.manter_sono_ppclip(cli)
                except Exception:
                    pass
            self.face.desligar()
            if pode_animar:
                self._tick_ronco(cli, preso_na_base=preso_na_base)
            return

        # Câmera só na janela agendada (30–40 min) — interações não abrem câmera.
        off_min = BASE_CAM_OFF_MIN if os.environ.get("SEMPRE_VIVO", "1") == "1" else CAM_OFF_MIN
        off_max = BASE_CAM_OFF_MAX if os.environ.get("SEMPRE_VIVO", "1") == "1" else CAM_OFF_MAX
        on_s = BASE_CAM_ON_S if os.environ.get("SEMPRE_VIVO", "1") == "1" else CAM_ON_S
        on_max = BASE_CAM_ON_MAX if os.environ.get("SEMPRE_VIVO", "1") == "1" else CAM_ON_MAX

        if self._camera_ate > 0 and not self.face.ativo:
            # Câmera cortada cedo (carga, governador, quieto) — não reabrir em loop.
            self._camera_ate = 0.0
            self._proxima_camera = agora + random.uniform(off_min, off_max)
            logger.info(
                "Câmera base encerrada cedo — próxima em ~%.0f min",
                (off_min + off_max) / 60.0,
            )
        elif (
            pode_camera
            and not self.dormindo
            and agora >= self._proxima_camera
            and not self.face.ativo
            and self._camera_ate <= 0
        ):
            if os.environ.get("COZMO_FACE_BASE", "0") != "1":
                self._proxima_camera = agora + random.uniform(off_min, off_max)
            else:
                dur = random.uniform(on_s, on_max)
                if self.face.iniciar_busca(dur, na_base=True):
                    self._camera_ate = agora + dur
                    self._proxima_camera = agora + dur + random.uniform(off_min, off_max)
                    logger.info("Janela câmera base (~%.0fs)", dur)
                else:
                    self._proxima_camera = agora + random.uniform(off_min, off_max)
        elif self.face.ativo and agora > self._camera_ate > 0:
            self.face.desligar()
            self._camera_ate = 0.0
            self._proxima_camera = agora + random.uniform(off_min, off_max)
            logger.info(
                "Câmera base off — próxima em ~%.0f min",
                (off_min + off_max) / 60.0,
            )

        # Animação espontânea acordado — pool amplo ou varia clip do loop
        if (
            self.fase == Fase.ACORDADO
            and pode_animar
            and not falando
            and not self.face.buscando
            and agora >= self._proxima_anim_base
        ):
            self._anim_espontanea_acordado(
                cli, preso_na_base=preso_na_base
            )
            self._proxima_anim_base = agora + random.uniform(
                *_intervalo_anim_base_s()
            )
