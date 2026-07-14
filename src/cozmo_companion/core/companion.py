"""Orquestrador PC→Cozmo — uma fila, um reconnect, face procedural."""

from __future__ import annotations

import logging
import os
import random
import signal
import sys
import threading
import time
from pathlib import Path

import pycozmo
from pycozmo import event, protocol_encoder

from cozmo_companion.core.alive import VivoNaBase
from cozmo_companion.core.animation_director import AnimationDirector, AnimIntent
from cozmo_companion.core.anims import (
    ContextoAnim,
    detectar_contexto_anim,
    escolher_ctx,
    filtrar_por_contexto,
    pool_por_contexto,
    registrar_inventario,
)
from cozmo_companion.core.charger import (
    BATTERY_FULL_V,
    BaseGuard,
    carregando,
    detectar_na_base_boot,
    em_base,
    modo_botao,
    na_base,
)
from cozmo_companion.core.companion_voz import CompanionVoz
from cozmo_companion.core.config import network_tuning
from cozmo_companion.core.conexao import (
    MonitorRx,
    abrir_cliente,
    aguardar_ping,
    aguardar_robot,
    cozmo_alcanavel,
    cozmo_rota_ap,
    despertar_sessao_leve,
    diagnostico,
    fechar_cliente,
    gravar_saude,
    log_offline_quieto,
    nunca_desconectar_udp,
    permitir_reset_udp_cozmo01,
    reconectar_wifi,
    recuperar_apos_queda,
    recuperar_sessao_inplace,
    sessao_parece_fresca,
)
from cozmo_companion.core.cozmo01_recovery import RecuperadorCozmo01
from cozmo_companion.core.espirito import Espirito
from cozmo_companion.core.face_watch import FaceWatch
from cozmo_companion.core.fila_cozmo import FilaCozmo
from cozmo_companion.core.governador import FaseLink, GovernadorCozmo
from cozmo_companion.core.head_touch import HeadPetDetector
from cozmo_companion.core.mesa import ExploradorMesa, MesaSegura
from cozmo_companion.core.motors import MotorWatchdog
from cozmo_companion.core.perf import PERFIS, ModoPerf, MonitorJogo
from cozmo_companion.core.pet_livre import PetLivre
from cozmo_companion.core.sessao_guard import GuardSessao
from cozmo_companion.core.state import HardwareSnapshot, SafetyState, decide_state
from cozmo_companion.core.vida import CicloVida, Fase
from cozmo_companion.display.face import Tela
from cozmo_companion.perception.events import PerceptionEvent, PerceptionEventKind
from cozmo_companion.voice.chat import Chat
from cozmo_companion.voice.sinal import audio_na_base, sinal_para
from cozmo_companion.weather.bage import BageWeather

logger = logging.getLogger("cozmo.companion")

GRUPOS_CARINHO = ("ReactToPokeReaction",)


def _env_float(nome: str, padrao: float) -> float:
    try:
        return float(os.environ.get(nome, padrao))
    except ValueError:
        return padrao


def _env_int(nome: str, padrao: int) -> int:
    try:
        return int(os.environ.get(nome, padrao))
    except ValueError:
        return padrao


class Companion(CompanionVoz):
    """PC = cérebro; Cozmo = músculo via FilaCozmo serial."""

    def __init__(self, cli: pycozmo.Client):
        self.cli = cli
        self.volume = _env_int("COZMO_VOLUME", 12000)
        self.battery_full_v = _env_float("BATTERY_FULL_V", BATTERY_FULL_V)
        self.chat_enabled = os.environ.get("CHAT_ENABLED", "1") == "1"
        self._iniciar_voz()

        self.clima = BageWeather()
        self.tela = Tela(cli)
        self.chat = Chat(
            url=os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434"),
            model=os.environ.get("OLLAMA_MODEL", "llama3.2:1b"),
            clima=self.clima,
        )
        self._carinho = HeadPetDetector(self._ao_carinho_cabeca)
        self._base = BaseGuard()
        self._vivo = VivoNaBase()
        self._anim_director = AnimationDirector()
        from cozmo_companion.core.sensory_reactions import MotionReactionDetector

        self._motion_reactions = MotionReactionDetector(self._on_motion_reaction)
        self._ultima_reacao_sensor = 0.0
        self._ultimo_evento_percepcao = 0.0
        self._espirito = Espirito()
        self._mesa = MesaSegura(cli)
        self._explorador = ExploradorMesa(
            self._mesa,
            obstaculo_frontal=lambda: self._face.caminho_bloqueado,
            evento_recente=lambda: time.monotonic() - self._ultimo_evento_percepcao
            < float(os.environ.get("MESA_EVENTO_RECENTE_S", "8")),
        )
        self._pet_livre = PetLivre()
        from cozmo_companion.core.leds import LuzesBackpack

        self._luzes = LuzesBackpack()
        self._face = FaceWatch(cli)
        from cozmo_companion.core.ambiente_escuro import detector_escuro

        self._detector_escuro = detector_escuro()
        self._face.vincular_detector_luz(self._detector_escuro)
        self._perf = MonitorJogo()
        self._vida = CicloVida(self.tela, self._face, lambda c: self._tocar_grupo(c))
        self._sono_por_escuro = False
        self._detector_escuro.registrar_callbacks(
            on_escuro=self._on_ambiente_escuro,
            on_claro=self._on_ambiente_claro,
        )
        self._motores = MotorWatchdog()
        self._gov = GovernadorCozmo()
        self._monitor_rx = MonitorRx()
        self._sessao_guard = GuardSessao()
        self._modo_atual = ModoPerf.NORMAL
        self._modo_udp_leve = False

        self._ultimo_keepalive = 0.0
        self._ultimo_wifi_offline = 0.0
        self._ultimo_despertar_base = 0.0
        self._ultimo_saude_json = 0.0
        self._ultimo_reconnect_udp = 0.0

        self._rx_stall_desde = 0.0
        self._ultimo_recuperacao = 0.0
        self._falhas_inplace = 0
        self._ultimo_anim_udp = 0.0
        self._ultimo_tocar = 0.0
        self._ultimo_carinho = 0.0
        self._udp_quieto_ate = 0.0
        self._espirito_pausado_ate = 0.0
        self._transicao_botao_ate = 0.0
        self._proximo_pulse_vivo = time.monotonic() + random.uniform(10, 15)
        self._ultimo_botao = 0.0
        self._botao_liberado = True
        self._preso_anterior = True
        self._face_thread_stop = threading.Event()
        self._face_thread: threading.Thread | None = None
        self._ultimo_pulse_oled = 0.0
        self._ultimo_face_check = 0.0
        self._ultimo_manter_rosto = 0.0
        self._anim_base_ate = 0.0
        self._ultimo_perception_anim = 0.0
        self._perception_pendente: AnimIntent | None = None
        self._anim_hist: list[str] = []
        self._recuperador = RecuperadorCozmo01()
        self._ultimo_inplace_proativo = 0.0
        self._anim_travada_desde = 0.0

        self._fila = FilaCozmo(
            self._gov,
            tocar_grupo=lambda g, **kw: self._tocar_grupo(g, **kw),
            mostrar_oled=self._mostrar_oled_fila,
            executar_sinal=self._executar_sinal_fila,
            executar_som=self._executar_som_notif_fila,
            na_base=self._na_base_efetivo,
            usa_procedural=self._base_usa_rosto_vivo,
        )
        self._instalar_trava_rodas()
        from cozmo_companion.core.paths import data_dir

        self._volume_file = Path(
            os.environ.get(
                "COZMO_VOLUME_FILE",
                str(data_dir() / "volume.txt"),
            )
        )
        self._face.vincular_eventos(self._on_perception_event)

    def _on_ambiente_escuro(self) -> None:
        """Pouca luz entra em sono real; não apenas troca o desenho dos olhos."""
        if not self._na_base_efetivo():
            return
        try:
            from cozmo_companion.display.rosto import solicitar_reacao_visual

            solicitar_reacao_visual("sleepy", frames=4)
        except Exception:
            pass
        if os.environ.get("COZMO_SONO_NA_BASE", "0") != "1":
            return
        self._sono_por_escuro = True
        if not self._vida.dormindo:
            logger.info("Ambiente escuro confirmado — entrando em animação de sono")
            self._vida.cochilar(self.cli, preso_na_base=True)
        else:
            # Nunca apaga o OLED: reforça o ppclip de olhos dormindo.
            self._vida.cochilar(self.cli, preso_na_base=True)

    def _on_ambiente_claro(self) -> None:
        """A luz voltar acorda somente o sono iniciado pelo ambiente."""
        if self._na_base_efetivo():
            try:
                from cozmo_companion.display.rosto import solicitar_reacao_visual

                solicitar_reacao_visual("wake", frames=4)
            except Exception:
                pass
        if not self._sono_por_escuro:
            return
        self._sono_por_escuro = False
        logger.info("Ambiente claro confirmado — acordando")
        self._vida.despertar(self.cli, motivo="luz", preso_na_base=True)

    def _on_motion_reaction(self, evento: object) -> None:
        """Serializa sensores físicos na mesma fila de animações."""
        from cozmo_companion.core.sensory_reactions import SensorReaction

        agora = time.monotonic()
        if agora - self._ultima_reacao_sensor < float(
            os.environ.get("COZMO_SENSOR_REACTION_COOLDOWN_S", "2.5")
        ):
            return
        if self._fila.ocupada or self._falando or self._llm_ocupado:
            return
        intent = {
            SensorReaction.PICKED_UP: AnimIntent.PICKED_UP,
            SensorReaction.SHAKE: AnimIntent.SHAKE,
            SensorReaction.PUT_DOWN: AnimIntent.PUT_DOWN,
        }.get(evento)
        if intent is None:
            return
        pool = self._anim_director.pool(
            set(self.cli.animation_groups.keys()), self._ctx_anim(), intent
        )
        if pool and self._fila.enviar_anim(pool, prioridade=False):
            self._ultima_reacao_sensor = agora
            logger.info("Sensor físico: %s -> reação leve", getattr(evento, "value", evento))

    # ── estado base ──

    def _contato_base_fisico(self) -> bool:
        return em_base(self.cli) or na_base(self.cli) or carregando(self.cli)

    def _safety_state(self) -> SafetyState:
        agora = time.monotonic()
        post_rec = float(os.environ.get("COZMO_POST_RECONNECT_S", "22"))
        quieto_sem_tts = (
            agora < self._udp_quieto_ate
            or (
                self._ultimo_reconnect_udp > 0
                and agora - self._ultimo_reconnect_udp < post_rec
            )
        )
        return decide_state(
            HardwareSnapshot(
                button_base=self._base.preso_na_base,
                free_requested=getattr(self._base, "mesa_escolhida", False),
                on_charger=em_base(self.cli) or na_base(self.cli),
                charging=carregando(self.cli),
                picked_up=bool(getattr(self.cli, "robot_picked_up", False)),
                sleeping=self._vida.dormindo,
                quiet=quieto_sem_tts,
                rx_ok=self._gov.ultimo_rx_ok,
                recovering=self._recuperador.stall_consecutivo > 0,
            )
        )

    def _na_base_efetivo(self) -> bool:
        if modo_botao():
            return self._safety_state().effective_base
        if os.environ.get("COZMO_SEMPRE_NA_BASE", "0") == "1":
            from cozmo_companion.core.conexao import cozmo_alcanavel

            if cozmo_alcanavel():
                return True
        return self._base.preso_na_base or em_base(self.cli) or na_base(self.cli) or carregando(
            self.cli
        )

    def _no_carregador(self) -> bool:
        return not (em_base(self.cli) or na_base(self.cli) or carregando(self.cli))

    def _base_usa_rosto_vivo(self) -> bool:
        if not self._na_base_efetivo():
            return False
        from cozmo_companion.core.motor_cozmo import base_oled_modo_direto, base_oled_modo_proc

        if base_oled_modo_proc() or base_oled_modo_direto():
            return True
        return (
            os.environ.get("COZMO_PROC_FACE_BASE", "1") == "1"
            and os.environ.get("COZMO_PROC_FACE", "1") == "1"
        )

    def _carinho_recente(self) -> bool:
        grace = float(os.environ.get("CARINHO_LINK_GRACE_S", "45"))
        return time.monotonic() - self._ultimo_carinho < grace

    def _on_perception_event(self, evento: PerceptionEvent) -> None:
        """Eventos leves da câmera; decisão passa pelo governador/fila."""
        if evento.kind == PerceptionEventKind.LIGHT_LEVEL:
            return
        self._pet_livre.registrar_evento(evento)
        if self._na_base_efetivo() and evento.kind in (
            PerceptionEventKind.FACE_SEEN,
            PerceptionEventKind.MOTION_HINT,
        ):
            try:
                from cozmo_companion.display.rosto import solicitar_reacao_visual

                solicitar_reacao_visual(
                    "happy" if evento.kind == PerceptionEventKind.FACE_SEEN else "curious",
                    frames=4,
                )
            except Exception:
                pass
        if evento.kind in (
            PerceptionEventKind.FACE_SEEN,
            PerceptionEventKind.MOTION_HINT,
        ):
            self._ultimo_evento_percepcao = time.monotonic()
        if evento.kind == PerceptionEventKind.FACE_LOST:
            return
        if self._vida.dormindo or self._fila.ocupada or self._falando or self._llm_ocupado:
            return
        fala = self._espontaneo.fala_rosto(evento)
        if fala and self._pedir_fala_espontanea(fala, tela="Te vi"):
            return
        safety = self._safety_state()
        if not safety.animation_allowed or not self._gov.pode("anim"):
            return
        agora = time.monotonic()
        cooldown = float(os.environ.get("PERCEPTION_ANIM_COOLDOWN_S", "18"))
        if agora - self._ultimo_perception_anim < cooldown:
            return
        if evento.kind == PerceptionEventKind.FACE_SEEN:
            intent = AnimIntent.FACE_SEEN
        elif evento.kind == PerceptionEventKind.MOTION_HINT:
            intent = AnimIntent.MOTION
        else:
            intent = AnimIntent.LIGHT
        if self._na_base_efetivo() and self._face.ativo:
            self._perception_pendente = intent
            logger.info("Ambiente: %s observado; reação após câmera", evento.kind.value)
            return
        pool = self._anim_director.pool(
            set(self.cli.animation_groups.keys()),
            self._ctx_anim(),
            intent,
        )
        if pool and self._fila.enviar_anim(pool, prioridade=False):
            self._ultimo_perception_anim = agora
            logger.info(
                "Ambiente: %s -> reação visual (pool=%d)",
                evento.kind.value,
                len(pool),
            )

    def _despachar_perception_pendente(self) -> None:
        intent = self._perception_pendente
        if intent is None or self._face.ativo or self._fila.ocupada:
            return
        self._perception_pendente = None
        pool = self._anim_director.pool(
            set(self.cli.animation_groups.keys()), self._ctx_anim(), intent
        )
        if pool and self._fila.enviar_anim(pool, prioridade=False):
            self._ultimo_perception_anim = time.monotonic()
            logger.info("Ambiente: reação %s após observação", intent.value)

    def _quieto_base_anim(self) -> bool:
        if self._pos_tts_ativo():
            return True
        post_rec = float(os.environ.get("COZMO_POST_RECONNECT_S", "22"))
        return (
            self._ultimo_reconnect_udp > 0
            and time.monotonic() - self._ultimo_reconnect_udp < post_rec
        )

    def _periodo_quieto_ativo(self) -> bool:
        agora = time.monotonic()
        if agora < self._udp_quieto_ate:
            return True
        if self._pos_tts_ativo():
            return True
        post_rec = float(os.environ.get("COZMO_POST_RECONNECT_S", "22"))
        return self._ultimo_reconnect_udp > 0 and agora - self._ultimo_reconnect_udp < post_rec

    def _em_transicao(self) -> bool:
        return time.monotonic() < self._transicao_botao_ate

    def _marcar_udp_quieto(
        self, segundos: float | None = None, *, pausar_fila: bool = True
    ) -> None:
        segundos = max(5.0, segundos or float(os.environ.get("COZMO_UDP_QUIET_S", "12")))
        self._udp_quieto_ate = max(self._udp_quieto_ate, time.monotonic() + segundos)
        self._gov.marcar_quieto(segundos)
        if pausar_fila:
            self._fila.pausar(segundos)
        self._modo_udp_leve = True

    def _abortar_trafego_udp(self) -> None:
        self._tts_cancel.set()
        self._face.desligar()
        self._fila.forcar_idle(self.cli)

    # ── anim / fila ──

    def _mostrar_oled_fila(
        self,
        texto: str,
        *,
        segundos: float = 8.0,
        scroll: bool = False,
        passo_s: float = 1.0,
        forcado: bool = False,
    ) -> None:
        from cozmo_companion.core.motor_cozmo import base_suprime_oled_texto

        # Base com anim na dock: texto OLED apaga rosto (COZMO 01 / tela preta).
        if not forcado and base_suprime_oled_texto(self.cli):
            return
        if (
            not forcado
            and self._na_base_efetivo()
            and self._base_usa_rosto_vivo()
            and os.environ.get("COZMO_OLED_NA_BASE", "0") != "1"
        ):
            return
        if scroll:
            self.tela.mostrar_scroll(
                texto,
                segundos=segundos,
                passo_s=passo_s,
                prioridade="notif",
                forcado=forcado,
            )
        else:
            self.tela.mostrar(
                texto,
                segundos=segundos,
                prioridade="notif",
                forcado=forcado,
            )

    def _ctx_anim(self) -> ContextoAnim:
        return detectar_contexto_anim(
            preso_na_base=self._base.preso_na_base,
            no_carregador=self._no_carregador(),
        )

    def _escolher_anim_sem_repetir(
        self,
        pool: tuple[str, ...],
        *,
        prioridade: bool,
    ) -> str | None:
        if not pool:
            return None
        if prioridade:
            return random.choice(pool)
        janela = max(2, _env_int("COZMO_ANIM_ANTI_REPEAT", 5))
        recentes = set(self._anim_hist[-janela:])
        candidatos = [nome for nome in pool if nome not in recentes]
        if not candidatos:
            candidatos = list(pool)
        nome = random.choice(candidatos)
        self._anim_hist.append(nome)
        if len(self._anim_hist) > janela * 2:
            del self._anim_hist[: -janela * 2]
        return nome

    def _tocar_grupo(self, candidatos: tuple[str, ...], *, prioridade: bool = False) -> bool:
        if self._falando or self._llm_ocupado:
            return False
        safety = self._safety_state()
        if not prioridade and not safety.animation_allowed:
            return False
        if not prioridade and not self._gov.reservar("anim", prioridade=prioridade):
            return False
        from cozmo_companion.core.motor_cozmo import base_oled_loop_segurado

        if (
            not prioridade
            and self._na_base_efetivo()
            and (self._fila.ocupada or base_oled_loop_segurado() or self.tela.ocupada())
        ):
            return False
        disp = set(self.cli.animation_groups.keys())
        ctx = self._ctx_anim()
        # prioridade (carinho, wake): só o pool pedido — não expandir GRUPOS_BASE_VIVO
        if prioridade:
            pool = filtrar_por_contexto(
                candidatos,
                disp,
                ctx,
                sem_som_carga=ctx == ContextoAnim.BASE,
            )
            if ctx == ContextoAnim.BASE:
                pool = tuple(c for c in pool if c != "NeutralFace") or pool
            nome = self._escolher_anim_sem_repetir(pool, prioridade=prioridade)
        else:
            candidatos = pool_por_contexto(candidatos, ctx)
            if ctx == ContextoAnim.BASE:
                candidatos = tuple(c for c in candidatos if c != "NeutralFace") or candidatos
            pool = filtrar_por_contexto(
                candidatos,
                disp,
                ctx,
                sem_som_carga=ctx == ContextoAnim.BASE,
            )
            nome = self._escolher_anim_sem_repetir(pool, prioridade=prioridade)
        if not nome:
            return False
        from cozmo_companion.core.motor_cozmo import animar_grupo, modo_base_olhos

        na_base = ctx != ContextoAnim.MESA
        proc = na_base and self._base_usa_rosto_vivo()
        if not animar_grupo(self.cli, nome, na_base=na_base, procedural_antes=proc):
            return False
        agora = time.monotonic()
        hold = float(os.environ.get("COZMO_ANIM_BASE_HOLD_S", "2.5"))
        self._ultimo_anim_udp = agora
        self._ultimo_tocar = agora
        self._monitor_rx.pausar(hold + 2.0)
        if na_base and proc:
            modo_base_olhos(self.cli)
        return True

    # ── carinho / botão ──

    def _carinho_cabeca_externa(self) -> bool:
        """Cabeça movida por anim ppclip, fila ou TTS — não é toque humano."""
        if self._falando or self._pos_tts_ativo() or not self._fila.livre:
            return True
        if not self._na_base_efetivo():
            ac = self.cli.anim_controller
            if (
                ac.playing_animation
                or ac.playing_audio
                or not ac.queue.is_empty()
                or self._explorador.explorando
                or self._pet_livre.movimento_interno
                or self._face.buscando
                or self._face.rastreando
            ):
                return True
            return False
        # O ppclip contínuo da base tem movimento limitado a ±6°. Não o usamos
        # como bloqueio porque isso tornava impossível detectar o dedo enquanto
        # os olhos estavam vivos. Os limiares do HeadPetDetector filtram esse
        # micro-movimento; fila/TTS/câmera continuam sendo bloqueios reais.
        ac = self.cli.anim_controller
        if ac.playing_animation or ac.playing_audio or not ac.queue.is_empty():
            return True
        if self._face.buscando or self._face.rastreando:
            return True
        return False

    def _ao_carinho_cabeca(self) -> None:
        agora = time.monotonic()
        if self._vida.dormindo:
            self._detector_escuro.marcar_despertar()
            acordou = self._vida.acordar_por_toque(
                self.cli, preso_na_base=self._na_base_efetivo()
            )
            logger.info("Toque — acordando (%s)", "dormindo" if acordou else "já acordado")
            return
        from cozmo_companion.core.charger import carga_prioritaria

        if self._na_base_efetivo() and carga_prioritaria():
            logger.debug("Carinho ignorado — bateria baixa na base")
            return
        if self._periodo_quieto_ativo() or self._falando or self._pos_tts_ativo():
            logger.debug("Carinho ignorado (quieto/TTS)")
            return
        cooldown = float(os.environ.get("CARINHO_COOLDOWN_S", "10"))
        if agora - self._ultimo_carinho < cooldown:
            return
        burst_gap = float(os.environ.get("CARINHO_BURST_GAP_S", "20"))
        if self._ultimo_carinho > 0 and agora - self._ultimo_carinho < burst_gap:
            self._vida.registrar_interacao(12.0)
            return
        self._ultimo_carinho = agora
        self._detector_escuro.marcar_despertar()
        logger.info("Carinho")
        self._vida.registrar_interacao(25.0)
        na_base = self._na_base_efetivo()
        if na_base:
            from cozmo_companion.display.rosto import solicitar_reacao_visual

            solicitar_reacao_visual("pet", frames=6)
            pool = self._anim_director.pool(
                set(self.cli.animation_groups.keys()), self._ctx_anim(), AnimIntent.PET
            )
            if pool:
                self._fila.enviar_anim(pool, prioridade=False)
            self._carinho.sincronizar_baseline(self.cli)
        else:
            self._fila.enviar_anim(GRUPOS_CARINHO, prioridade=False)

    def _ao_toggle_botao(self) -> None:
        oled_s = float(os.environ.get("BOTAO_OLED_S", "2.5"))
        quiet_udp = float(os.environ.get("BOTAO_QUIET_S", "4"))
        ouv = self.ouvinte
        if ouv:
            ouv.pause()
        try:
            agora = time.monotonic()
            self._transicao_botao_ate = agora + float(os.environ.get("BOTAO_TRANSICAO_S", "8"))
            self._face.desligar()
            self._explorador.parar_tudo(self.cli)
            try:
                self.cli.cancel_anim()
            except Exception as exc:
                logger.debug("Falha ao cancelar animação durante troca de modo: %s", exc)
            self.cli.stop_all_motors()
            self._base.alternar_modo_botao(self.cli)
            from cozmo_companion.core.charger import definir_oled_preso_na_base

            safety = self._safety_state()
            definir_oled_preso_na_base(safety.effective_base)
            label = "Livre" if getattr(self._base, "mesa_escolhida", False) else "Base"
            if safety.effective_base:
                self._mesa.set_bloqueado(True)
                from pycozmo import robot as _robot

                try:
                    self.cli.set_lift_height(_robot.MIN_LIFT_HEIGHT.mm)
                except Exception as exc:
                    logger.debug("Falha ao baixar braço na troca p/ Base: %s", exc)
                from cozmo_companion.core.motor_cozmo import ligar_oled_base

                ligar_oled_base(self.cli, forcar=True, preso_na_base=safety.effective_base)
            else:
                self._mesa.set_bloqueado(False)
                from cozmo_companion.core.motor_cozmo import modo_mesa_vivo

                modo_mesa_vivo(self.cli)
                self._pet_livre.entrar_modo_livre()
                self._face.ligar(na_base=False, forcar=True)
                self._face.iniciar_busca(
                    float(os.environ.get("PET_LIVRE_CAMERA_START_S", "10")),
                    na_base=False,
                )
                self._explorador.antecipar(float(os.environ.get("PET_LIVRE_START_S", "1.2")))
            self._fila.enviar_oled(label, segundos=oled_s, prioridade=True)
            self._marcar_udp_quieto(quiet_udp, pausar_fila=False)
            self._fila.drenar(self.cli, timeout_s=float(os.environ.get("BOTAO_FILA_DRAIN_S", "10")))
            self._monitor_rx.sincronizar(self.cli)
            self._ultimo_carinho = agora
            logger.info("Botão: %s (movimento=%s)", label, safety.movement_allowed)
        finally:
            if ouv:
                ouv.resume()

    def _eventos(self) -> None:
        def ao_botao(_cli: pycozmo.Client, pkt: protocol_encoder.ButtonPressed) -> None:
            if not pkt.pressed:
                self._botao_liberado = True
                return
            if not self._botao_liberado:
                return
            agora = time.monotonic()
            if agora - self._ultimo_botao < float(os.environ.get("BASE_TOGGLE_DEBOUNCE_S", "3")):
                return
            self._botao_liberado = False
            self._ultimo_botao = agora
            self._ao_toggle_botao()

        def ao_pegar(pkt_src: object, pegou: bool) -> None:
            from cozmo_companion.core.pycozmo_cli import resolver_cliente

            c = resolver_cliente(pkt_src)
            self._base.registrar_pickup(c, pegou)
            if pegou and self._base.preso_na_base:
                c.stop_all_motors()

        def ao_buffer_anim_cheio(_cli: pycozmo.Client, cheio: bool) -> None:
            """Sinal direto do firmware (RobotState.status) — chega ANTES do RX
            morrer e da tela travar em COZMO 01. Parar de mandar frame na hora
            é o único jeito de evitar o estouro; esperar o stall é tarde demais."""
            from cozmo_companion.core.motor_cozmo import (
                _parar_display_keeper,
                _parar_loop_clip_base,
                segurar_base_oled_loop,
            )

            if cheio:
                logger.warning(
                    "Buffer de anim do robô cheio — parando envio (evita COZMO 01)"
                )
                try:
                    _parar_loop_clip_base(timeout=0.3)
                except Exception as exc:
                    logger.debug("Falha ao parar loop clip (buffer cheio): %s", exc)
                try:
                    _parar_display_keeper()
                except Exception as exc:
                    logger.debug("Falha ao parar keeper (buffer cheio): %s", exc)
                segurar_base_oled_loop(
                    float(os.environ.get("COZMO_BUFFER_CHEIO_HOLD_S", "3"))
                )
            else:
                logger.info("Buffer de anim do robô liberado — retomando")

        self.cli.add_handler(event.EvtRobotPickedUpChange, ao_pegar)
        self.cli.add_handler(protocol_encoder.ButtonPressed, ao_botao)
        self.cli.add_handler(event.EvtRobotAnimBufferFullChange, ao_buffer_anim_cheio)

    def _instalar_trava_rodas(self) -> None:
        from pycozmo import robot

        cli = self.cli
        orig_drive = cli.drive_wheels
        orig_lift = cli.set_lift_height
        orig_move_lift = cli.move_lift
        orig_move_head = cli.move_head
        lift_min = robot.MIN_LIFT_HEIGHT.mm

        def _na_base() -> bool:
            return self._base.preso_na_base or self._na_base_efetivo()

        def _guard_drive(left: float, right: float, *args, **kwargs):
            if _na_base():
                return
            return orig_drive(left, right, *args, **kwargs)

        def _guard_lift(height: float, *args, **kwargs):
            if _na_base():
                return orig_lift(lift_min, *args, **kwargs)
            return orig_lift(height, *args, **kwargs)

        def _guard_move_lift(speed: float, *args, **kwargs):
            if _na_base():
                return
            return orig_move_lift(speed, *args, **kwargs)

        def _guard_move_head(speed: float, *args, **kwargs):
            if _na_base():
                return
            return orig_move_head(0.0, *args, **kwargs)

        cli.drive_wheels = _guard_drive  # type: ignore[method-assign]
        cli.set_lift_height = _guard_lift  # type: ignore[method-assign]
        cli.move_lift = _guard_move_lift  # type: ignore[method-assign]
        cli.move_head = _guard_move_head  # type: ignore[method-assign]

    def _sincronizar_local(self) -> None:
        from cozmo_companion.core.charger import base_sempre_na_carga, definir_oled_preso_na_base

        preso = self._base.preso_na_base
        if base_sempre_na_carga() and not preso and self._base._no_contato_base(self.cli):
            self._base.entrou_na_base(self.cli, silencioso=True)
            preso = True
        safety = self._safety_state()
        definir_oled_preso_na_base(safety.effective_base)
        self._mesa.set_bloqueado(not safety.movement_allowed)
        if safety.effective_base:
            self._explorador.parar_tudo(self.cli)
        self._preso_anterior = preso

    # ── face procedural: AnimationController 30fps — sem thread extra ──

    def _garantir_display_vivo(self) -> None:
        """Anti COZMO 01: stream 30fps na base; anim presa = cancela."""
        if not self._na_base_efetivo() or not self._base_usa_rosto_vivo():
            return
        from cozmo_companion.core.motor_cozmo import (
            modo_sono_oled_ativo,
            religar_oled_acordado_base,
        )

        if (
            not self._vida.dormindo
            and self._vida.fase == Fase.ACORDADO
            and modo_sono_oled_ativo()
        ):
            religar_oled_acordado_base(self.cli, forcar=True)
            return
        if self._vida.dormindo:
            from cozmo_companion.core.motor_cozmo import (
                entrar_sono_base_oled,
                manter_sono_oled_texto,
                manter_sono_ppclip,
                modo_sono_oled_ativo,
                sono_oled_texto_ativo,
                sono_oled_usa_texto,
            )

            if sono_oled_usa_texto():
                if not sono_oled_texto_ativo():
                    from cozmo_companion.core.motor_cozmo import ativar_sono_oled_texto

                    ativar_sono_oled_texto(self.cli)
                else:
                    manter_sono_oled_texto(self.cli)
            elif modo_sono_oled_ativo():
                manter_sono_ppclip(self.cli)
            else:
                try:
                    entrar_sono_base_oled(self.cli)
                except Exception as exc:
                    logger.warning("Sono OLED (display): %s", exc)
            return
        from cozmo_companion.core.motor_cozmo import (
            _charger_play_stream,
            _charger_stream_sessao,
            base_oled_loop_segurado,
            base_oled_modo_direto,
            base_oled_usa_charger,
            expirar_hold_oled_base,
            ligar_oled_base,
            modo_base_olhos,
            pulse_rosto_base,
            rx_link_ok,
            segurar_base_oled_loop,
        )

        if self._fila.ocupada or self.tela.ocupada():
            if self.tela.ocupada():
                restante = max(0.5, self.tela._ate - time.monotonic() + 1.5)
                segurar_base_oled_loop(restante)
        else:
            expirar_hold_oled_base(self.cli)
        if base_oled_loop_segurado() or self._fila.ocupada:
            return

        from cozmo_companion.core.motor_cozmo import (
            _base_anim_loop_vivo,
            _base_oled_anim_loop_ativo,
            keeper_base_ativo,
        )

        if keeper_base_ativo() and not (
            _base_oled_anim_loop_ativo() and _base_anim_loop_vivo()
        ):
            return
        from cozmo_companion.core.conexao import sessao_pycozmo_ativa

        if not sessao_pycozmo_ativa(self.cli):
            return
        if (
            base_oled_usa_charger(self.cli)
            and _base_oled_anim_loop_ativo()
            and rx_link_ok()
            and not _base_anim_loop_vivo()
        ):
            from cozmo_companion.core.motor_cozmo import (
                _garantir_base_oled_anim_loop,
                oled_charger_vivo,
            )

            if not oled_charger_vivo(self.cli):
                ligar_oled_base(self.cli, forcar=True, preso_na_base=True)
            else:
                _garantir_base_oled_anim_loop(self.cli)
            return
        if base_oled_usa_charger(self.cli) and _charger_play_stream(self.cli):
            from cozmo_companion.core.motor_cozmo import vigiar_anim_presa

            self._anim_travada_desde, cancelou = vigiar_anim_presa(
                self.cli, self._anim_travada_desde
            )
            if cancelou:
                ligar_oled_base(self.cli, forcar=True, preso_na_base=True)
            elif self._anim_travada_desde <= 0:
                if not _charger_stream_sessao and rx_link_ok():
                    ligar_oled_base(self.cli, forcar=False, preso_na_base=True)
            return

        if base_oled_modo_direto():
            pulse_rosto_base(self.cli)
            return

        from cozmo_companion.core.motor_cozmo import _clip_loop_vivo

        if _base_oled_anim_loop_ativo() and _clip_loop_vivo():
            return

        from cozmo_companion.core.motor_cozmo import vigiar_anim_presa

        self._anim_travada_desde, cancelou = vigiar_anim_presa(
            self.cli, self._anim_travada_desde
        )
        if cancelou:
            modo_base_olhos(self.cli)

    def _modo_sono_zZz_oled(self) -> bool:
        if not self._vida.dormindo or not self._na_base_efetivo():
            return False
        from cozmo_companion.core.motor_cozmo import sono_oled_usa_texto

        return sono_oled_usa_texto()

    def _manter_sono_zZz_oled(self) -> None:
        from cozmo_companion.core.motor_cozmo import (
            ativar_sono_oled_texto,
            manter_sono_oled_texto,
            sono_oled_texto_ativo,
        )

        if not sono_oled_texto_ativo():
            try:
                ativar_sono_oled_texto(self.cli)
            except Exception as exc:
                logger.warning("Sono zZz OLED: %s", exc)
        manter_sono_oled_texto(self.cli)
        self.tela.mostrar(
            "zZz", segundos=300.0, forcado=False, prioridade="sono"
        )

    def _garantir_rosto_base(self) -> None:
        from cozmo_companion.core.charger import em_base
        from cozmo_companion.core.motor_cozmo import (
            _charger_play_stream,
            base_oled_modo_proc,
            ligar_oled_base,
            oled_charger_vivo,
        )

        from cozmo_companion.core.motor_cozmo import rx_link_ok

        if self._vida.dormindo and self._na_base_efetivo():
            from cozmo_companion.core.motor_cozmo import (
                definir_modo_sono_oled,
                manter_sono_oled_texto,
                manter_sono_ppclip,
                modo_sono_oled_ativo,
                sono_oled_texto_ativo,
                sono_oled_usa_texto,
            )

            definir_modo_sono_oled(True)
            if sono_oled_usa_texto():
                self._manter_sono_zZz_oled()
            # ppclip sono: vigiar_tela_congelada_base() — evita flood duplicado
            return

        if (
            em_base(self.cli)
            and _charger_play_stream(self.cli)
            and base_oled_modo_proc()
            and rx_link_ok()
        ):
            from cozmo_companion.core.motor_cozmo import (
                base_oled_carga_cheia_ativo,
            )

            if base_oled_carga_cheia_ativo(self.cli):
                if not oled_charger_vivo(self.cli):
                    ligar_oled_base(self.cli, forcar=True, preso_na_base=True)
            elif not oled_charger_vivo(self.cli):
                ligar_oled_base(self.cli, forcar=True, preso_na_base=True)
        if not self._na_base_efetivo() or not self._base_usa_rosto_vivo():
            return
        from cozmo_companion.core.motor_cozmo import base_oled_loop_segurado

        if base_oled_loop_segurado() or self._fila.ocupada:
            return
        agora = time.monotonic()
        if agora - self._ultimo_manter_rosto < float(os.environ.get("COZMO_FACE_KEEP_S", "8")):
            return
        self._ultimo_manter_rosto = agora
        from cozmo_companion.core.motor_cozmo import (
            base_oled_carga_cheia_ativo,
            base_oled_minimo_ativo,
            base_oled_usa_charger,
            base_oled_usa_proc_vivo,
            keeper_base_ativo,
            manter_proc_vivo_base,
            modo_base_olhos,
            vigiar_flood_base,
        )

        from cozmo_companion.core.motor_cozmo import (
            _base_anim_loop_vivo,
            _base_oled_anim_loop_ativo,
        )

        if base_oled_carga_cheia_ativo(self.cli) and keeper_base_ativo():
            if self._vida.dormindo:
                return
            if _base_oled_anim_loop_ativo():
                if not _base_anim_loop_vivo():
                    from cozmo_companion.core.motor_cozmo import (
                        _garantir_base_oled_anim_loop,
                        _parar_display_keeper,
                    )

                    _parar_display_keeper()
                    _garantir_base_oled_anim_loop(self.cli)
                return
            return
        if base_oled_usa_proc_vivo(self.cli):
            manter_proc_vivo_base(self.cli)
        elif base_oled_minimo_ativo(self.cli):
            from cozmo_companion.core.motor_cozmo import keeper_base_ativo

            if not keeper_base_ativo():
                modo_base_olhos(self.cli)
        elif base_oled_usa_charger(self.cli):
            from cozmo_companion.core.motor_cozmo import (
                _charger_anim_base_ativa,
                _charger_stream_sessao,
                _garantir_base_oled_anim_loop,
                _garantir_charger_worker,
                _tick_charger_oled,
                keeper_base_ativo,
                oled_charger_vivo,
                processar_replay_charger_pendente,
            )

            if rx_link_ok():
                processar_replay_charger_pendente(self.cli)
            if (
                _base_oled_anim_loop_ativo()
                and rx_link_ok()
                and not _base_anim_loop_vivo()
            ):
                if not oled_charger_vivo(self.cli):
                    ligar_oled_base(self.cli, forcar=True, preso_na_base=True)
                else:
                    _garantir_base_oled_anim_loop(self.cli)
            elif rx_link_ok() and keeper_base_ativo():
                _tick_charger_oled(self.cli)
            elif rx_link_ok() and (
                _charger_stream_sessao or _charger_anim_base_ativa(self.cli)
            ):
                _tick_charger_oled(self.cli)
                if _charger_stream_sessao:
                    _garantir_charger_worker(self.cli)
            elif rx_link_ok() and _base_oled_anim_loop_ativo():
                ligar_oled_base(self.cli, forcar=True, preso_na_base=True)
            else:
                modo_base_olhos(self.cli)
        else:
            vigiar_flood_base(self.cli)

    def _iniciar_thread_face(self) -> None:
        """Keepalive OLED no main loop — sem thread (race no gerador de rosto)."""
        from cozmo_companion.core.motor_cozmo import (
            _charger_anim_base_ativa,
            modo_base_olhos,
        )

        self._ultimo_pulse_oled = 0.0
        if _charger_anim_base_ativa(self.cli):
            return
        modo_base_olhos(self.cli)

    # ── conexão — UM caminho ──

    def _atualizar_cliente(self, cli: pycozmo.Client) -> None:
        self.cli = cli
        self.tela.cli = cli
        self._face.cli = cli
        self._mesa.cli = cli
        self._instalar_trava_rodas()
        self._eventos()

    def _recuperar_udp(self, *, forcado: bool = False) -> bool:
        """Sem COZMO_NEVER_DISCONNECT: in-place; senão só despertar leve (sem disconnect)."""
        if nunca_desconectar_udp():
            from cozmo_companion.core.motor_cozmo import (
                _stream_oled_estavel,
                base_oled_carga_cheia_ativo,
                ligar_oled_base,
                renovar_sessao_base_oled,
            )

            if self._na_base_efetivo() and _stream_oled_estavel(self.cli):
                logger.debug("Sessão — stream OLED vivo, sem renovar")
            elif self._na_base_efetivo() and base_oled_carga_cheia_ativo(self.cli):
                if not _stream_oled_estavel(self.cli):
                    renovar_sessao_base_oled(self.cli, self._gov._medidor)
                    self._monitor_rx.sincronizar(self.cli)
                    logger.info("Sessão — renovar base (sem disconnect)")
            else:
                despertar_sessao_leve(self.cli, self._monitor_rx, self._gov._medidor)
                self._garantir_rosto_base()
                logger.info("Sessão — despertar leve (sem disconnect)")
            return True
        lim = int(os.environ.get("COZMO_INPLACE_FAIL_MAX", "2"))
        if self._falhas_inplace < lim and recuperar_sessao_inplace(self.cli):
            self._falhas_inplace = 0
            self._monitor_rx.sincronizar(self.cli)
            self._gov._medidor.reset()
            self._garantir_rosto_base()
            logger.info("UDP recuperado in-place (sem COZMO 01)")
            return True
        self._falhas_inplace += 1
        return self._reconectar_sessao_udp(silencioso=True, forcado=forcado)

    def _reconectar_sessao_udp(
        self,
        *,
        silencioso: bool = True,
        forcado: bool = False,
        cozmo01: bool = False,
        apos_wifi: bool = False,
    ) -> bool:
        reset_cozmo01 = cozmo01 and permitir_reset_udp_cozmo01()
        na_base_agora = self._na_base_efetivo()
        if reset_cozmo01:
            from cozmo_companion.core.cozmo01_recovery import (
                reset_udp_permitido_no_modo_atual,
            )
            from cozmo_companion.core.motor_cozmo import (
                base_oled_stable_only,
                ligar_oled_base,
                rx_link_ok,
                rx_morto_s,
            )

            if (
                na_base_agora
                and base_oled_stable_only()
                and not reset_udp_permitido_no_modo_atual()
            ):
                logger.warning(
                    "COZMO 01 — reset UDP bloqueado na base estável; mantendo sessão"
                )
                despertar_sessao_leve(self.cli, self._monitor_rx, self._gov._medidor)
                try:
                    ligar_oled_base(self.cli, forcar=True)
                except Exception as exc:
                    logger.debug("religar OLED procedural: %s", exc)
                self._garantir_rosto_base()
                return False

            if (
                na_base_agora
                and not apos_wifi
                and base_oled_stable_only()
                and (rx_link_ok() or rx_morto_s() <= float(
                os.environ.get("COZMO01_RESET_RX_DEAD_MIN_S", "30")
                ))
            ):
                logger.warning(
                    "COZMO 01 — reset UDP bloqueado (RX ainda recuperável)"
                )
                despertar_sessao_leve(self.cli, self._monitor_rx, self._gov._medidor)
                try:
                    ligar_oled_base(self.cli, forcar=True)
                except Exception as exc:
                    logger.debug("religar OLED procedural: %s", exc)
                self._garantir_rosto_base()
                return False

            if na_base_agora and not apos_wifi and not reset_udp_permitido_no_modo_atual():
                logger.warning(
                    "COZMO 01 — reset UDP bloqueado pelo OLED estável"
                )
                despertar_sessao_leve(self.cli, self._monitor_rx, self._gov._medidor)
                try:
                    from cozmo_companion.core.motor_cozmo import (
                        ligar_oled_base,
                    )

                    ligar_oled_base(self.cli, forcar=True)
                except Exception as exc:
                    logger.debug("religar OLED procedural: %s", exc)
                self._garantir_rosto_base()
                return False
        # COZMO 01 é uma tela do firmware. RX vivo e frame enviado pelo PC não
        # provam que a OLED o exibiu (confirmado pela webcam no HW5). Quando o
        # chamador marcou cozmo01, não masque o reset com esses falsos ACKs.
        if nunca_desconectar_udp() and not reset_cozmo01:
            despertar_sessao_leve(self.cli, self._monitor_rx, self._gov._medidor)
            self._garantir_rosto_base()
            return False
        agora = time.monotonic()
        if reset_cozmo01 and self._ultimo_reconnect_udp > 0:
            pos_reset = float(os.environ.get("COZMO01_POST_RESET_MIN_S", "60"))
            idade_reset = agora - self._ultimo_reconnect_udp
            if idade_reset < pos_reset:
                logger.info(
                    "COZMO 01 — reset duplicado ignorado (sessão nova há %.0fs)",
                    idade_reset,
                )
                return True
        cooldown = float(os.environ.get("COZMO_RATIO_PREVENT_COOLDOWN_S", "25"))
        if not forcado and agora - self._ultimo_reconnect_udp < cooldown:
            return False
        if not self._sessao_guard.tentar_reconectar(forcar=forcado):
            return False
        if not silencioso:
            logger.warning("COZMO 01 — reconexão UDP")
        elif forcado and cozmo_alcanavel():
            logger.info("COZMO 01 — reset UDP (ping OK, rx parado)")
        if reset_cozmo01:
            try:
                from cozmo_companion.core.motor_cozmo import (
                    _parar_awake_oled_base,
                    parar_flood_anim,
                )

                _parar_awake_oled_base(self.cli, timeout=1.0)
                parar_flood_anim(self.cli)
            except Exception as exc:
                logger.debug("Falha ao parar OLED antes do reset: %s", exc)
        self._abortar_trafego_udp()
        quiet_pre = float(os.environ.get("COZMO_POST_RECONNECT_S", "22"))
        self._fila.pausar(quiet_pre)
        if not reset_cozmo01 and not aguardar_ping(
            float(os.environ.get("COZMO_RECONNECT_WAIT_PING_S", "25"))
        ):
            self._sessao_guard.liberar(sucesso=False)
            return False
        self._ultimo_reconnect_udp = agora
        if self.ouvinte:
            self.ouvinte.pause()
        ok = False
        try:
            fechar_cliente(
                self.cli,
                pausa=float(
                    os.environ.get(
                        "COZMO01_DISCONNECT_PAUSE_S",
                        os.environ.get("COZMO_DISCONNECT_PAUSE_S", "5"),
                    )
                    if reset_cozmo01
                    else os.environ.get("COZMO_DISCONNECT_PAUSE_S", "12")
                ),
                forcado=reset_cozmo01,
            )
            self.cli = abrir_cliente(
                log_level="INFO",
                protocol_log_level="WARNING",
                robot_log_level="WARNING",
            )
            self._atualizar_cliente(self.cli)
            self.cli.load_anims()
            from cozmo_companion.core.anim_base_patch import instalar_play_anim_sem_rodas_na_base

            instalar_play_anim_sem_rodas_na_base(
                self.cli,
                preso_na_base_fn=self._na_base_efetivo,
            )
            self.cli.set_volume(self.volume)
            self._monitor_rx.reset()
            self._gov._medidor.reset()
            if self._na_base_efetivo():
                from cozmo_companion.core.motor_cozmo import (
                    modo_base_olhos,
                    resetar_sessao_oled_base,
                    reset_oled_watchdog_base,
                    segurar_base_oled_loop,
                    _iniciar_display_keeper,
                )

                reset_oled_watchdog_base()
                if reset_cozmo01:
                    # Voltar direto pro stream de 30fps é o que estourou o
                    # buffer há segundos. Aquece devagar: keeper a 1Hz por um
                    # tempo, fase começa em "laranja" (só sobe a verde depois
                    # de ficar estável) em vez de já religar em velocidade máxima.
                    resetar_sessao_oled_base(fase_inicial="laranja")
                    aquecimento_s = float(
                        os.environ.get("COZMO01_AQUECIMENTO_S", "20")
                    )
                    segurar_base_oled_loop(aquecimento_s)
                    try:
                        _iniciar_display_keeper(self.cli, 1.0, grupo="IdleOnCharger")
                    except Exception as exc:
                        logger.debug("Falha ao iniciar keeper de aquecimento: %s", exc)
                else:
                    resetar_sessao_oled_base()
                    modo_base_olhos(self.cli)
            else:
                # Fora da base não existe regra de preservar OLED estável: se o
                # socket velho morreu, a sessão nova precisa voltar com câmera,
                # sensores e animações livres.
                try:
                    self._face.cli = self.cli
                    if self._base.mesa_escolhida:
                        self._face.ligar(na_base=False, forcar=True)
                except Exception as exc:
                    logger.debug("Pós-reconnect livre: face/câmera: %s", exc)
            self._marcar_udp_quieto(quiet_pre)
            logger.info("Reconexão UDP OK — quieto %.0fs", quiet_pre)
            ok = True
            return True
        except Exception as exc:
            logger.error("Reconexão UDP falhou: %s", exc)
            return False
        finally:
            self._sessao_guard.liberar(sucesso=ok)
            if self.ouvinte:
                self.ouvinte.resume()

    def _reabrir_udp_apos_wifi(self) -> bool:
        """Wi-Fi voltou: o socket PyCozmo antigo costuma ficar sem RX."""
        estava_na_base = self._base.preso_na_base
        mesa_escolhida = self._base.mesa_escolhida
        ok = self._reconectar_sessao_udp(
            silencioso=False,
            forcado=True,
            cozmo01=True,
            apos_wifi=True,
        )
        if ok:
            from cozmo_companion.core.charger import definir_oled_preso_na_base, em_base

            fisicamente_na_base = em_base(self.cli)
            self._base._preso_na_base = bool(fisicamente_na_base or estava_na_base)
            self._base._mesa_escolhida = bool(mesa_escolhida and not self._base._preso_na_base)
            definir_oled_preso_na_base(self._base._preso_na_base)
            self._recuperador.stall_consecutivo = 0
        return ok

    def _sessao_fresca_no_boot(self) -> bool:
        """Boot: stream OLED na base — só reset UDP se sessão herdada stale (rx alto)."""
        wait_s = (
            float(os.environ.get("COZMO_BOOT_FRESH_WAIT_S", "6"))
            if os.environ.get("COZMO_BOOT_FRESH_SESSION", "0") == "1"
            else 0.0
        )
        deadline = time.monotonic() + wait_s
        while not cozmo_alcanavel():
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.35)
        from cozmo_companion.core.motor_cozmo import ligar_oled_base

        self._monitor_rx.sincronizar(self.cli)
        self._gov._medidor.reset()
        d = diagnostico(self.cli)

        from cozmo_companion.core.cozmo01_recovery import (
            reset_udp_permitido_no_modo_atual,
        )

        if (
            os.environ.get("COZMO_BOOT_FRESH_SESSION", "0") == "1"
            and reset_udp_permitido_no_modo_atual()
        ):
            logger.warning("Boot — reset UDP explícito para limpar COZMO 01")
            self._reconectar_sessao_udp(
                silencioso=False, forcado=True, cozmo01=True
            )
            return True
        if os.environ.get("COZMO_BOOT_FRESH_SESSION", "0") == "1":
            logger.info("Boot — reset UDP bloqueado pela política atual")

        if sessao_parece_fresca(self.cli):
            logger.info("Boot — sessão OK (rx=%d), sem reset", d["recv_frames"])
            if self._na_base_efetivo():
                ligar_oled_base(self.cli, forcar=True, preso_na_base=True)
            return False

        if os.environ.get("COZMO_BOOT_FRESH_SESSION", "0") != "1":
            logger.info(
                "Boot — rx=%d acumulado, reset desligado (COZMO_BOOT_FRESH_SESSION=0)",
                d["recv_frames"],
            )
            if self._na_base_efetivo():
                ligar_oled_base(self.cli, forcar=True, preso_na_base=True)
            return False

        logger.info("Boot — sessão stale rx=%d, reset UDP", d["recv_frames"])
        if not nunca_desconectar_udp():
            self._reconectar_sessao_udp(silencioso=True, forcado=True)
        else:
            despertar_sessao_leve(self.cli, self._monitor_rx, self._gov._medidor)

    def _tick_conexao(self) -> None:
        from cozmo_companion.core.motor_cozmo import base_oled_modo, base_oled_modo_direto

        agora = time.monotonic()
        from cozmo_companion.core.motor_cozmo import base_oled_loop_segurado

        busy = (
            self._falando
            or self._llm_ocupado
            or self._carinho_recente()
            or self._pos_tts_ativo()
            or self._em_transicao()
            or self._fila.ocupada
            or base_oled_loop_segurado()
        )
        quieto = self._periodo_quieto_ativo()
        intervalo = float(os.environ.get("COZMO_KEEPALIVE_S", "10"))
        if agora - self._ultimo_keepalive < intervalo:
            return
        self._ultimo_keepalive = agora

        g = self._gov.tick(
            self.cli,
            monitor_rx=self._monitor_rx,
            busy=busy,
            quieto=quieto,
        )
        self._modo_udp_leve = g.reduzir_trafego
        from cozmo_companion.core.motor_cozmo import (
            ajustar_oled_fase_link,
            cortar_flood_udp_base,
            definir_rx_link_ok,
        )

        definir_rx_link_ok(g.rx_ok)
        if self._na_base_efetivo():
            ajustar_oled_fase_link(self.cli, g.fase.value)

        # Watchdog COZMO 01 (alto nível, à prova dos gates finos): rx_ok=False
        # contínuo por muito tempo enquanto o AP segue conectado = sessão de
        # aplicação travada (tela COZMO 01). A recuperação fina às vezes não
        # dispara (early-returns silenciosos por alcance/estado/flood). Aqui
        # reconectamos o UDP usando rota do AP (barato), sem depender de ICMP.
        if not g.rx_ok:
            if self._rx_stall_desde <= 0:
                self._rx_stall_desde = agora
            stall_cont = agora - self._rx_stall_desde
            teto = float(os.environ.get("COZMO01_WATCHDOG_S", "30"))
            if cozmo_rota_ap():
                teto = max(
                    teto,
                    float(os.environ.get("COZMO01_RX_DEAD_ROUTE_S", "20")),
                )
            cooldown = float(os.environ.get("COZMO01_WATCHDOG_COOLDOWN_S", "20"))
            if (
                stall_cont >= teto
                and cozmo_rota_ap()
                and agora - self._ultimo_reconnect_udp >= cooldown
            ):
                from cozmo_companion.core.motor_cozmo import (
                    detectar_cozmo01_suspeito,
                    oled_resgate_recente,
                )

                # Só reconecta (apaga a tela) se ela estiver REALMENTE travada em
                # COZMO 01. Durante animação, drx=0 é benigno (clip é one-way, o
                # firmware não manda telemetria) — reconectar apagaria a tela à toa.
                if oled_resgate_recente():
                    logger.warning(
                        "COZMO 01 watchdog adiado — OLED resgate ativo %.0fs",
                        stall_cont,
                    )
                    return
                if detectar_cozmo01_suspeito(self.cli):
                    from cozmo_companion.core.cozmo01_recovery import (
                        reset_udp_permitido_no_modo_atual,
                    )

                    if not reset_udp_permitido_no_modo_atual():
                        logger.warning(
                            "COZMO 01 watchdog — reset UDP bloqueado pelo OLED estável"
                        )
                        return
                    logger.warning(
                        "COZMO 01 watchdog — tela travada %.0fs, reconectando UDP",
                        stall_cont,
                    )
                    self._reconectar_sessao_udp(
                        silencioso=False, forcado=True, cozmo01=True
                    )
                    self._rx_stall_desde = 0.0
                    return
        else:
            self._rx_stall_desde = 0.0

        if not cozmo_alcanavel():
            if g.rx_ok and cozmo_rota_ap():
                log_offline_quieto(
                    "Ping falhou, mas UDP/RX vivo — mantendo sessão Cozmo."
                )
            else:
                wifi_ok = False
                definir_rx_link_ok(False)
                cortar_flood_udp_base(self.cli)
                self._gov.marcar_quieto(
                    float(os.environ.get("COZMO_OFFLINE_QUIET_S", "45"))
                )
                if g.pedir_wifi and not busy:
                    wifi_ok = reconectar_wifi()
                elif (
                    not busy
                    and not quieto
                    and not g.rx_ok
                    and agora - self._ultimo_despertar_base
                    >= float(os.environ.get("COZMO_WIFI_STALL_S", "25"))
                ):
                    from cozmo_companion.core.conexao import pode_tentar_wifi

                    if pode_tentar_wifi():
                        wifi_ok = reconectar_wifi()
                if wifi_ok:
                    self._reabrir_udp_apos_wifi()
                if not cozmo_alcanavel():
                    if not g.rx_ok:
                        cortar_flood_udp_base(self.cli)
                    if agora - self._ultimo_saude_json >= 60.0:
                        self._ultimo_saude_json = agora
                        log_offline_quieto()
                    return

        if self._na_base_efetivo() and not g.rx_ok:
            from cozmo_companion.core.conexao import avisar_modo_wifi_setup

            avisar_modo_wifi_setup(self.cli)

        if g.abortar_flood and g.rx_ok and not busy and not quieto:
            from cozmo_companion.core.conexao import _ppclip_sessao_viva
            from cozmo_companion.core.motor_cozmo import ppclip_base_ativo

            ppclip_vivo = (
                self._na_base_efetivo()
                and ppclip_base_ativo(self.cli)
                and _ppclip_sessao_viva(self.cli)
            )
            if not ppclip_vivo:
                if self._na_base_efetivo():
                    cortar_flood_udp_base(self.cli)
                else:
                    self._abortar_trafego_udp()
                logger.warning(
                    "UDP saturado na base (fase=%s) — pausa anim charger",
                    g.fase.value,
                )
                return

        if g.pedir_wifi and not busy:
            if reconectar_wifi():
                self._reabrir_udp_apos_wifi()

        drx, dtx, _ = self._gov._medidor.amostra(self.cli)
        from cozmo_companion.core.config import network_tuning

        tx_stall_base = network_tuning().base_tx_stall
        janela_sem_drx = drx <= 0 and dtx >= tx_stall_base
        if (
            self._na_base_efetivo()
            and not busy
            and not quieto
            and janela_sem_drx
            and agora - self._ultimo_despertar_base
            >= float(os.environ.get("COZMO_BASE_DESPERTAR_S", "35"))
        ):
            if g.rx_ok:
                cortar_flood_udp_base(self.cli)
                self._ultimo_despertar_base = agora
            else:
                from cozmo_companion.core.motor_cozmo import (
                    cortar_flood_udp_base,
                    ping_sessao_base,
                    pulso_sync_base,
                )

                self._ultimo_despertar_base = agora
                cortar_flood_udp_base(self.cli)
                pulso_sync_base(self.cli, forcado=True)
                ping_sessao_base(self.cli)
                _dg = diagnostico(self.cli)
                logger.warning(
                    "Base: stall RX (dtx=%d) — ping (recuperador trata) "
                    "[rf=%d rp=%d desc=%d rb=%d]",
                    dtx,
                    _dg.get("recv_frames", 0),
                    _dg.get("recv_packets", 0),
                    _dg.get("discarded", 0),
                    _dg.get("recv_bytes", 0),
                )

        if agora - self._ultimo_saude_json >= 12.0:
            self._ultimo_saude_json = agora
            drx, dtx, _ = self._gov._medidor.amostra(self.cli)
            gravar_saude(
                self.cli,
                extra={
                    "fase": g.fase.value,
                    "rx_ok": g.rx_ok,
                    "preso_base": self._base.preso_na_base,
                    "ratio_janela": round(g.ratio, 3),
                    "drx": drx,
                    "dtx": dtx,
                },
            )

        drx_st, dtx_st, _ = self._gov._medidor.amostra(self.cli)
        self._recuperador.atualizar_stall(
            self.cli,
            g,
            self._gov._medidor,
            busy=busy,
            quieto=quieto,
        )

        if self._na_base_efetivo() and not g.rx_ok:
            cortar_flood_udp_base(self.cli)
            self._recuperador.tick_base(
                self.cli,
                g,
                self._monitor_rx,
                self._gov._medidor,
                busy=busy,
                quieto=quieto,
                na_base=True,
                ultimo_reconnect_udp=self._ultimo_reconnect_udp,
                reconnect_udp=lambda: self._reconectar_sessao_udp(
                    silencioso=False, forcado=True, cozmo01=True
                ),
                recuperar_inplace=lambda: self._recuperar_udp(forcado=True),
            )
            return

        if not self._na_base_efetivo() and not g.rx_ok and not busy:
            if cozmo_rota_ap() or cozmo_alcanavel():
                logger.warning("Sessão livre sem RX — reabrindo UDP")
                self._reconectar_sessao_udp(
                    silencioso=False,
                    forcado=True,
                    cozmo01=True,
                )
            return

        if (busy or quieto) and g.rx_ok:
            return

        if self._na_base_efetivo():
            from cozmo_companion.core.motor_cozmo import (
                base_oled_carga_cheia_ativo,
                base_oled_usa_pulse,
                manter_oled_base_ativo,
                manter_oled_pulse,
                processar_replay_charger_pendente,
                pulso_oled_carga_cheia,
                pulso_sync_base,
                vigiar_flood_base,
                _oled_sessao_viva,
            )

            pulso_sync_base(self.cli)
            if g.rx_ok and not self._vida.dormindo:
                processar_replay_charger_pendente(self.cli)
            if g.rx_ok or _oled_sessao_viva(self.cli):
                manter_oled_base_ativo(self.cli)
            if not base_oled_carga_cheia_ativo(self.cli):
                pulso_oled_carga_cheia(self.cli)
            if base_oled_usa_pulse(self.cli):
                manter_oled_pulse(self.cli)
            if not self._vida.dormindo:
                vigiar_flood_base(self.cli)

            self._recuperador.tick_base(
                self.cli,
                g,
                self._monitor_rx,
                self._gov._medidor,
                busy=busy,
                quieto=quieto,
                na_base=True,
                ultimo_reconnect_udp=self._ultimo_reconnect_udp,
                reconnect_udp=lambda: self._reconectar_sessao_udp(
                    silencioso=False, forcado=True, cozmo01=True
                ),
                recuperar_inplace=lambda: self._recuperar_udp(forcado=True),
            )

    # ── vivo leve ──

    def _pulse_vivo(self) -> None:
        agora = time.monotonic()
        if self._vida.dormindo:
            return
        from cozmo_companion.core.charger import carga_prioritaria

        if self._na_base_efetivo() and carga_prioritaria():
            return
        if self._carinho_recente() or not self._fila.livre:
            return
        if self._gov.fase == FaseLink.VERMELHO:
            return
        if not self._gov.ultimo_rx_ok or self._modo_udp_leve:
            return
        if self._falando or self._llm_ocupado or self._quieto_base_anim():
            return
        pulse_s = float(os.environ.get("SEMPRE_PULSE_S", "15"))
        if agora < self._proximo_pulse_vivo:
            return
        self._proximo_pulse_vivo = agora + random.uniform(pulse_s * 0.85, pulse_s * 1.15)
        if self.cli.robot_picked_up:
            return
        if not self._gov.reservar("micro"):
            return
        # Em link degradado, somente o gesto barato; animação completa fica
        # reservada para VERDE.
        if self._gov.fase != FaseLink.VERDE:
            self._vivo.reagir_ouvir(self.cli)
            return
        if (
            self._na_base_efetivo()
            and self._vida.fase == Fase.ACORDADO
            and random.random()
            < float(os.environ.get("PULSE_ANIM_CHANCE", "0.35"))
        ):
            from cozmo_companion.core.motor_cozmo import (
                pode_tocar_anim_direto,
                variar_clip_base_oled,
            )

            if pode_tocar_anim_direto(
                self.cli,
                fila_ocupada=self._fila.ocupada,
                falando=self._falando,
                face_buscando=self._face.buscando,
            ):
                if variar_clip_base_oled(self.cli):
                    return
        self._vivo.reagir_ouvir(self.cli)

    def _tick_escuro(self) -> None:
        if not self._na_base_efetivo():
            return
        from cozmo_companion.core.charger import carga_prioritaria

        if carga_prioritaria():
            return
        from cozmo_companion.core.motor_cozmo import tick_espiar_escuro

        tick_espiar_escuro(self.cli)
        # As janelas normais do FaceWatch já alimentam o detector de luz.
        # Abrir uma segunda sonda aqui disputa o stream de câmera com o OLED
        # e pode deixar o rádio preso na tela de recuperação "COZMO 01".
        if os.environ.get("COZMO_FACE_BASE", "0") == "1":
            return
        self._detector_escuro.tick_probe(
            self._face,
            na_base=True,
            falando=self._falando or self._llm_ocupado,
            camera_ocupada=self._face.buscando,
        )

    def _tick_face(self) -> None:
        """Câmera só em rajadas — tick só enquanto face_watch.ativo."""
        if not self._face.ativo:
            return
        safety = self._safety_state()
        permitido = (
            safety.camera_allowed
            and
            self._gov.pode("camera")
            and not self._falando
            and not self._pos_tts_ativo()
            and not self._carinho_recente()
        )
        self._face.tick(permitido=permitido)

    def _loop_vida(self) -> None:
        safety = self._safety_state()
        pode_cam = (
            safety.camera_allowed
            and self._gov.pode("camera")
            and not self._falando
            and not self._pos_tts_ativo()
            and not self._carinho_recente()
        )
        from cozmo_companion.core.motor_cozmo import pode_tocar_anim_direto

        self._vida.tick(
            self.cli,
            na_base=self._na_base_efetivo(),
            preso_na_base=self._base.preso_na_base,
            falando=self._falando,
            pode_animar=(
                safety.animation_allowed
                and self._gov.pode("anim")
                and self._gov.ultimo_rx_ok
                and pode_tocar_anim_direto(
                    self.cli,
                    fila_ocupada=self._fila.ocupada,
                    falando=self._falando,
                    face_buscando=self._face.buscando,
                )
            ),
            pode_camera=pode_cam,
        )
        self._despachar_perception_pendente()

    def _loop_pet_autonomo(self) -> None:
        safety = self._safety_state()
        if not self._fila.ocupada and not self._falando:
            luzes = getattr(self, "_luzes", None)
            if luzes is not None:
                luzes.tick(self.cli, na_base=safety.effective_base)
        if self._vida.dormindo or self._falando or self._llm_ocupado:
            return
        livre = safety.movement_allowed
        free_ready = safety.free_armed and not safety.effective_base
        no_carregador_livre = safety.free_armed and safety.effective_base

        ocupado = self._fila.ocupada or self._periodo_quieto_ativo()
        if livre and (self._explorador.explorando or not ocupado):
            if (
                self._explorador.explorando
                and self._gov.pode("camera")
                and not self._face.ativo
            ):
                self._face.ligar(na_base=False, forcar=True)
            self._face.ativar_vigilancia_obstaculo(
                self._explorador.explorando and self._face.ativo
            )
            self._explorador.tick(self.cli)
        elif not safety.free_armed:
            self._face.ativar_vigilancia_obstaculo(False)
            return
        else:
            self._face.ativar_vigilancia_obstaculo(False)

        if self._periodo_quieto_ativo() or not self._gov.ultimo_rx_ok:
            return
        if self._fila.ocupada or not safety.animation_allowed:
            return

        if livre and self._gov.pode("camera") and not self._face.ativo:
            self._face.ligar(na_base=False, forcar=True)

        plano = self._pet_livre.escolher(
            livre=livre or free_ready,
            no_carregador=no_carregador_livre,
            face_ativa=self._face.buscando or self._face.rastreando,
        )
        if plano is None:
            return

        logger.info("Pet %s — modo=%s", plano.acao, safety.mode.value)
        if plano.acao == "explorar":
            if livre:
                self._explorador.antecipar(0.1)
            return
        if plano.acao == "camera":
            if safety.camera_allowed and self._gov.pode("camera"):
                self._face.iniciar_busca(plano.camera_s or 8.0, na_base=safety.effective_base)
            if plano.anims:
                self._fila.enviar_anim(plano.anims, prioridade=False)
            return
        if plano.acao == "gesto":
            if livre:
                self._pet_livre.gesto_curto(self.cli)
            if plano.anims:
                self._fila.enviar_anim(plano.anims, prioridade=False)
            return
        if plano.acao == "scan":
            if livre:
                self._pet_livre.scan_curto(self.cli)
            if safety.camera_allowed and self._gov.pode("camera"):
                self._face.iniciar_busca(6.0, na_base=safety.effective_base)
            return
        if plano.anims:
            self._fila.enviar_anim(plano.anims, prioridade=False)

    def _loop_volume_arquivo(self) -> None:
        if not self._volume_file.is_file():
            return
        try:
            novo = max(0, min(65535, int(self._volume_file.read_text(encoding="utf-8").strip())))
            if novo != self.volume:
                self.volume = novo
                self.cli.set_volume(novo)
        except (OSError, ValueError):
            pass
        finally:
            self._volume_file.unlink(missing_ok=True)

    def _aplicar_modo(self, modo: ModoPerf) -> None:
        if modo == self._modo_atual:
            return
        self._modo_atual = modo
        perf = PERFIS[modo]
        self.chat.set_llm(perf.usar_llm)
        self._ajustar_stt_base()

    # ── main loop ──

    def run(self) -> None:
        from cozmo_companion.core.motor_cozmo import (
            base_oled_modo,
            base_oled_modo_direto,
            base_oled_stable_only,
            modo_base_olhos,
            parar_flood_anim,
            pulso_sync_base,
        )

        oled_base_desc = "keeper-estavel" if base_oled_stable_only() else base_oled_modo()
        logger.info(
            "Companheiro v2 — PC cérebro / Cozmo músculo (OLED base=%s)",
            oled_base_desc,
        )

        from cozmo_companion.core.motor_cozmo import (
            base_oled_usa_charger,
            base_oled_usa_pulse,
            instalar_guard_bodyinfo,
        )

        instalar_guard_bodyinfo(self.cli)
        pulso_sync_base(self.cli)
        self._iniciar_ouvinte()
        self._iniciar_ouvinte_notificacoes()
        self.cli.load_anims()
        from cozmo_companion.core.anim_base_patch import instalar_play_anim_sem_rodas_na_base

        instalar_play_anim_sem_rodas_na_base(
            self.cli,
            preso_na_base_fn=self._na_base_efetivo,
        )
        registrar_inventario(set(self.cli.animation_groups.keys()))

        boot_acordado_env = os.environ.get("COZMO_BOOT_ACORDADO", "1") == "1"
        if modo_botao():
            na_base_boot = self._base.inicializar_boot_modo_botao(self.cli)
        else:
            na_base_boot = detectar_na_base_boot(self.cli)
            if na_base_boot:
                self._base.entrou_na_base(
                    self.cli,
                    silencioso=True,
                    ligar_oled=not boot_acordado_env,
                )

        from cozmo_companion.core.charger import definir_oled_preso_na_base
        from cozmo_companion.core.motor_cozmo import (
            base_oled_usa_charger,
            base_oled_usa_pulse,
            ligar_oled_base,
            manter_oled_pulse,
            parar_flood_anim,
            pulse_rosto_base,
        )

        definir_oled_preso_na_base(self._base.preso_na_base)

        from cozmo_companion.core.motor_cozmo import (
            definir_modo_sono_oled,
            religar_oled_acordado_base,
        )

        boot_reset_feito = False
        if os.environ.get("COZMO_BOOT_FRESH_SESSION", "0") == "1":
            boot_reset_feito = self._sessao_fresca_no_boot()

        boot_acordado = (
            os.environ.get("COZMO_BOOT_ACORDADO", "1") == "1"
            and self._na_base_efetivo()
        )
        if boot_acordado:
            if not base_oled_usa_charger(self.cli):
                parar_flood_anim(self.cli)
            definir_modo_sono_oled(False)
            self._vida._marcar_acordado(
                self.cli,
                motivo="boot",
                preso_na_base=self._base.preso_na_base,
                animar=False,
            )
            religar_oled_acordado_base(self.cli, forcar=True)
            logger.info("Boot — OLED acordado (keeper estável)")
        else:
            if not base_oled_usa_charger(self.cli):
                parar_flood_anim(self.cli)
            ligar_oled_base(
                self.cli,
                forcar=self._base.preso_na_base,
                preso_na_base=self._base.preso_na_base,
            )
        from cozmo_companion.core.charger import em_base
        from cozmo_companion.core.motor_cozmo import (
            _charger_play_stream,
            oled_charger_vivo,
        )

        if (
            not boot_acordado
            and em_base(self.cli)
            and _charger_play_stream(self.cli)
            and not oled_charger_vivo(self.cli)
        ):
            ligar_oled_base(self.cli, forcar=True, preso_na_base=True)
        if base_oled_usa_pulse(self.cli):
            parar_flood_anim(self.cli)
            pulse_rosto_base(self.cli, forcar=True)
            manter_oled_pulse(self.cli, forcar=True)
        elif self._na_base_efetivo() and not boot_acordado:
            from cozmo_companion.core.motor_cozmo import acordar_idle_charger_boot

            acordar_idle_charger_boot(self.cli)
        self.cli.set_volume(self.volume)

        if modo_botao():
            self._mesa.ativar(na_base=na_base_boot)
            self._mesa.set_bloqueado(self._base.preso_na_base)
            if self._base.preso_na_base:
                self._explorador.parar_tudo(self.cli)
        else:
            self._mesa.ativar(na_base=True)
            self._mesa.set_bloqueado(True)

        self._eventos()
        self._iniciar_thread_face()
        self._aplicar_modo(ModoPerf.NORMAL)
        if not boot_reset_feito:
            self._sessao_fresca_no_boot()
        boot_quiet = float(os.environ.get("COZMO_BOOT_QUIET_S", "4"))
        self._marcar_udp_quieto(boot_quiet)
        self._ultimo_reconnect_udp = time.monotonic()
        logger.info("Vivo preso_na_base=%s", self._base.preso_na_base)

        from cozmo_companion.core.radio_keepalive import iniciar_keepalive_radio

        iniciar_keepalive_radio()

        loop_sleep = float(os.environ.get("LOOP_SLEEP", "0.25"))
        from cozmo_companion.core.motor_cozmo import definir_rx_link_ok

        while True:
            try:
                definir_rx_link_ok(self._monitor_rx.tick(self.cli))
                self._tick_conexao()
                self._aplicar_modo(self._perf.tick())
                self._loop_volume_arquivo()
                self._loop_voz_arquivo()
                from cozmo_companion.core.conexao import (
                    cozmo_rota_ap,
                    cozmo_ssid_visivel,
                    reconectar_wifi,
                    wlan0_preso_cozmo,
                )

                agora = time.monotonic()
                online = cozmo_alcanavel() and cozmo_rota_ap()
                precisa_wifi = (
                    not online
                    and (
                        cozmo_ssid_visivel(rescan=True)
                        or not cozmo_rota_ap()
                        or wlan0_preso_cozmo()
                    )
                )
                if precisa_wifi:
                    if not cozmo_rota_ap() or agora - self._ultimo_wifi_offline >= float(
                        str(network_tuning().wifi_offline_retry_s)
                    ):
                        self._ultimo_wifi_offline = agora
                        if reconectar_wifi(forcado=not cozmo_rota_ap()):
                            online = self._reabrir_udp_apos_wifi()
                elif online:
                    self._ultimo_wifi_offline = 0.0
                if online:
                    self._base.tick(self.cli)
                    self._sincronizar_local()
                    self._ajustar_stt_base()
                    self._carinho.update(
                        self.cli,
                        preso_na_base=self._na_base_efetivo(),
                        em_sono=self._vida.em_sono,
                        face_ativo=self._face.buscando,
                        cabeca_externa=self._carinho_cabeca_externa(),
                    )
                    self._motion_reactions.update(self.cli)
                self._processar_stt()
                if not online:
                    self.tela.tick(direct=False)
                    time.sleep(loop_sleep)
                    continue
                self._fila.tick(self.cli)
                sono_zZz = self._modo_sono_zZz_oled()
                if sono_zZz:
                    self._manter_sono_zZz_oled()
                    self.tela.tick(direct=True)
                else:
                    self.tela.tick(direct=False)
                    self._garantir_rosto_base()
                    if self._na_base_efetivo():
                        from cozmo_companion.core.motor_cozmo import (
                            sono_oled_usa_texto,
                            vigiar_tela_congelada_base,
                        )

                        vigiar_tela_congelada_base(self.cli)
                    if not self._vida.dormindo:
                        self._garantir_display_vivo()
                    from cozmo_companion.core.motor_cozmo import travar_oled_minimo

                    if self._na_base_efetivo():
                        travar_oled_minimo(self.cli)
                self._processar_notificacoes()
                self._processar_conversa()
                self._processar_acao_llm()
                self._executar_fala()
                self._pulse_vivo()
                self._loop_pet_autonomo()
                from cozmo_companion.core.motor_cozmo import base_oled_modo_direto

                if (
                    self._na_base_efetivo()
                    and not self._falando
                    and self._fila.livre
                    and not self._vida.dormindo
                    and not base_oled_modo_direto()
                ):
                    self._vivo.tick_cabeca_base(self.cli)
                    self._carinho.sincronizar_baseline(self.cli)
                self._loop_vida()
                self._tick_escuro()
                self._tick_face()
                safety = self._safety_state()
                self._motores.tick(
                    self.cli,
                    na_base=safety.effective_base,
                    movimento_permitido=safety.movement_allowed,
                    rosto_procedural=self._base_usa_rosto_vivo() and not self._vida.dormindo,
                )
            except Exception as exc:
                logger.error("Tick falhou: %s", exc, exc_info=True)
                agora = time.monotonic()
                if agora - self._ultimo_recuperacao >= 30.0:
                    self._ultimo_recuperacao = agora
                    despertar_sessao_leve(self.cli, self._monitor_rx, self._gov._medidor)
                    self._garantir_rosto_base()
            time.sleep(loop_sleep)

    def parar(self) -> None:
        self._face_thread_stop.set()
        self.parar_voz()


def executar(log_level: str = "INFO") -> int:
    try:
        os.nice(int(os.environ.get("COZMO_NICE", "10")))
    except (OSError, ValueError):
        pass

    from cozmo_companion.core.conexao import aguardar_cozmo_online, log_offline_quieto

    nunca_desconectar = os.environ.get("COZMO_NEVER_DISCONNECT", "1") == "1"
    tentativas = 0
    tentativas_offline = 0
    backoff_base = float(os.environ.get("COZMO_OFFLINE_BACKOFF_S", "120"))
    backoff_max = float(os.environ.get("COZMO_OFFLINE_BACKOFF_MAX_S", "600"))
    cli = None
    while cli is None:
        if not cozmo_alcanavel():
            tentativas_offline += 1
            pausa = min(
                backoff_base * (1.4 ** min(tentativas_offline - 1, 6)),
                backoff_max,
            )
            log_offline_quieto(
                f"Cozmo offline — aguardando {pausa:.0f}s (sem flood Wi-Fi)."
            )
            aguardar_cozmo_online(pausa)
            continue
        try:
            cli = abrir_cliente(
                log_level=log_level,
                protocol_log_level="WARNING",
                robot_log_level="WARNING",
            )
            tentativas = 0
            tentativas_offline = 0
        except Exception as exc:
            tentativas += 1
            logger.error("Falha ao conectar (%d): %s", tentativas, exc)
            recuperar_apos_queda(tentativas)

    app = Companion(cli)
    app._monitor_rx.reset()

    def _sig(signum, _frame):
        logger.info("Parando (sinal %s)", signum)
        app.parar()
        if not nunca_desconectar:
            fechar_cliente(cli)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _sig)
    signal.signal(signal.SIGINT, _sig)
    try:
        app.run()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        app.parar()
    return 0
