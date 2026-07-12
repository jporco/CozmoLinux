"""Pipeline de voz PC — STT, wake, util, conversa, TTS via fila."""

from __future__ import annotations

import logging
import os
import queue
import random
import threading
import time
from pathlib import Path

from cozmo_companion.core import hora
from cozmo_companion.core.animation_director import AnimIntent
from cozmo_companion.core.charger import carregando
from cozmo_companion.core.conexao import conexao_ok
from cozmo_companion.core.limites import limites
from cozmo_companion.core.perf import PERFIS, ModoPerf
from cozmo_companion.core.ritmo import parece_latido
from cozmo_companion.notifications.core.listener import Notificacao, OuvinteNotificacoes
from cozmo_companion.notifications.core.handler import aplicar_notificacao
from cozmo_companion.voice.acoes_llm import (
    AcaoEmocional,
    RespostaCozmo,
    acao_bloqueada_na_carga,
    acao_requer_explorar,
    acao_requer_sono,
    grupos_para_acao,
    inferir_acao_do_usuario,
    resolver_acao,
    tela_para_acao,
)
from cozmo_companion.voice.mic import mic_ocupado_externo, resolver_dispositivo
from cozmo_companion.voice.sinal import (
    audio_na_base,
    comando_util,
    modo_sinal,
    parece_clima,
    parece_hora,
    sinal_para,
    texto_tela_de_fala,
)
from cozmo_companion.voice.espontaneo import FalaEspontanea
from cozmo_companion.voice.stt import Ouvinte
from cozmo_companion.voice.tts import falar, pulso_ping, rx_estavel_pos_tts, rx_frames
from cozmo_companion.voice.wake import WakeWord

logger = logging.getLogger("cozmo.companion.voz")

REACOES_WAKE = (
    "ReactToPokeReaction",
    "LookInPlaceForFacesHeadMovePause",
    "InterestedFace",
    "NeutralFace",
)
REACOES_PERGUNTA = (
    "ReactToPokeReaction",
    "LookInPlaceForFacesHeadMovePause",
    "InteractWithFaceTrackingIdle",
    "NeutralFace",
    "InterestedFace",
)
REACOES_BARULHO = (
    "ReactToPokeReaction",
    "CodeLabAmazed",
    "CodeLabExcited",
    "CodeLabWhew",
    "Hiccup",
    "InterestedFace",
)
REACOES_LATIDO = (
    "ReactToPokeReaction",
    "CodeLabAmazed",
    "CodeLabWhew",
    "CodeLabCurious",
    "InterestedFace",
)
REACOES_BARULHO_LIVRE = REACOES_BARULHO + (
    "Surprise",
    "ReactToPokeStartled",
    "HappyBirthdayCozmoReaction",
)
REACOES_LATIDO_LIVRE = REACOES_LATIDO + (
    "CodeLabChicken",
    "CodeLabDuck",
    "CubePounceSuccess",
)
class CompanionVoz:
    """Mixin — métodos de voz; espera atributos do Companion principal."""

    def _iniciar_voz(self) -> None:
        self.fala_q: queue.Queue[str] = queue.Queue()
        self.usuario_q: queue.Queue[str] = queue.Queue()
        self._acao_llm_q: queue.Queue[tuple[RespostaCozmo, str]] = queue.Queue()
        self._stt_fila: queue.Queue[tuple] = queue.Queue()
        self._notif_q: queue.Queue[Notificacao] = queue.Queue()
        self._lock = threading.Lock()
        self._falando = False
        self._tts_cancel = threading.Event()
        self._llm_ocupado = False
        self._llm_lock = threading.Lock()
        self._ultima_pergunta_em = 0.0
        self._ultima_pergunta_txt = ""
        self._ultimo_tts_fim = 0.0
        self._ultimo_util_tela = 0.0
        self._ultima_notif = 0.0
        self._ultima_notif_app = ""
        self._ultima_notif_titulo = ""
        self._cooldown_voz_base_ate = 0.0
        self._stt_base_wake_ate = 0.0
        self._ultimo_barulho = 0.0
        self._ultimo_latido = 0.0
        self._ultima_reacao_fala = 0.0
        self._espontaneo = FalaEspontanea()
        self.ouvinte: Ouvinte | None = None
        self._ouvinte_notif: OuvinteNotificacoes | None = None
        self._voz_cmd = Path(
            os.environ.get(
                "COZMO_VOZ_CMD",
                "/mnt/G/PROJETOS/cozmo-companion/data/voz.cmd",
            )
        )
        self._wake = WakeWord(
            ao_pergunta=lambda t: self._stt_fila.put(("pergunta", t)),
            ao_acordar=lambda: self._stt_fila.put(("wake",)),
        )

    def _pos_tts_ativo(self) -> bool:
        if self._ultimo_tts_fim <= 0:
            return False
        pos_s = max(
            float(os.environ.get("ESPIRITO_POS_TTS_S", "25")),
            float(os.environ.get("COZMO_TTS_POST_QUIET_S", "28")),
            limites().tts_grace_s,
        )
        if self._na_base_efetivo():
            pos_s = max(pos_s, float(os.environ.get("COZMO_POS_TTS_BASE_S", "18")))
        return time.monotonic() - self._ultimo_tts_fim < pos_s

    def _abrir_janela_stt_base(self) -> None:
        self._stt_base_wake_ate = time.monotonic() + float(
            os.environ.get("WAKE_TIMEOUT_S", "12")
        )

    def _ajustar_stt_base(self) -> None:
        if not self.ouvinte:
            return
        if mic_ocupado_externo():
            if getattr(self.ouvinte, "_thread", None) and self.ouvinte._thread.is_alive():
                self.ouvinte.stop()
                logger.info("Microfone liberado para outro serviço (JARVIS)")
            return
        if not (getattr(self.ouvinte, "_thread", None) and self.ouvinte._thread.is_alive()):
            try:
                self.ouvinte.start()
                logger.info("Microfone retomado")
            except Exception as exc:
                logger.warning("Falha ao retomar STT: %s", exc)
            return
        agora = time.monotonic()
        if self._na_base_efetivo():
            if os.environ.get("COZMO_STT_NA_BASE", "0") == "1":
                self.ouvinte.pause()
                return
            if self._wake.aguardando or self._falando or agora < self._stt_base_wake_ate:
                rms = int(os.environ.get("STT_RMS_BASE", "3"))
            elif os.environ.get("COZMO_STT_IDLE_BASE", "1") == "1":
                rms = int(os.environ.get("STT_RMS_IDLE_BASE", "42"))
            else:
                rms = int(os.environ.get("STT_RMS_BASE", "3"))
            self.ouvinte.resume()
        elif self._modo_atual == ModoPerf.JOGO:
            rms = PERFIS[ModoPerf.JOGO].stt_rms
            self.ouvinte.resume()
        else:
            rms = int(os.environ.get("STT_RMS", "5"))
            self.ouvinte.resume()
        self.ouvinte.ajustar_rms(rms)

    def _tela_resposta(self, pergunta: str, fala: str, tela: str | None) -> str | None:
        if tela:
            return tela
        if parece_clima(pergunta) or parece_clima(fala):
            return self.clima.texto_tela()
        if parece_hora(pergunta) or parece_hora(fala):
            return hora.texto_tela()
        return texto_tela_de_fala(fala) or None

    def _resposta_especial(self, usuario: str) -> str | None:
        u = usuario.lower().strip()
        if u in ("hora", "horas") or hora.pergunta_hora(usuario):
            return hora.frase_hora()
        if u == "tempo" or parece_clima(usuario):
            return self.clima.frase()
        return None

    def _pedir_fala(
        self,
        texto: str,
        *,
        pergunta: str = "",
        tela: str | None = None,
        segundos_tela: float | None = None,
        na_base_ok: bool = False,
        prioridade: bool = False,
    ) -> None:
        fala_original = texto
        oled: str | None = None
        if modo_sinal():
            oled = self._tela_resposta(pergunta, fala_original, tela)
            if oled:
                seg = segundos_tela or float(os.environ.get("TELA_RESPOSTA_S", "6"))
                self.tela.mostrar(oled[:16], segundos=seg)
            texto = sinal_para(pergunta, fala_original)
            logger.info("Sinal: %s | tela: %s", texto, (oled or "")[:16])
        if (
            self._na_base_efetivo()
            and not na_base_ok
            and os.environ.get("TTS_NA_BASE", "0") != "1"
        ):
            return
        if not prioridade and not self._gov.pode("tts"):
            return
        if prioridade:
            while True:
                try:
                    self.fala_q.get_nowait()
                except queue.Empty:
                    break
        elif self._falando:
            if self.fala_q.qsize() >= 1:
                return
            self.fala_q.put(texto)
            return
        self._preempt_antes_tts()
        self.fala_q.put(texto)

    def _restaurar_olhos_base_pos_tts(self) -> None:
        from cozmo_companion.core.motor_cozmo import (
            base_oled_loop_segurado,
            base_oled_usa_charger,
            modo_base_olhos,
            modo_charger_oled,
            pulso_sync_base,
        )

        if base_oled_loop_segurado() or (
            getattr(self, "_fila", None) is not None and self._fila.ocupada
        ):
            return
        pulso_sync_base(self.cli)
        if base_oled_usa_charger(self.cli):
            modo_charger_oled(self.cli, forcar=True)
        else:
            modo_base_olhos(self.cli)

    def _preempt_antes_tts(self) -> None:
        lim = limites()
        self._espirito_pausado_ate = max(
            self._espirito_pausado_ate,
            time.monotonic() + lim.tts_pre_quiet_s + lim.tts_post_quiet_s,
        )
        self._face.desligar()
        from cozmo_companion.core.motor_cozmo import base_oled_usa_charger

        if self._na_base_efetivo() and base_oled_usa_charger(self.cli):
            return
        try:
            self.cli.cancel_anim()
            if not self._na_base_efetivo():
                self.cli.stop_all_motors()
        except Exception:
            pass

    def _interromper_fala(self) -> None:
        self._tts_cancel.set()
        self._abortar_trafego_udp()
        with self._llm_lock:
            self._llm_ocupado = False

    def _executar_sinal_fila(self, texto: str) -> bool:
        if not texto or not self._gov.reservar("tts", prioridade=True):
            return False
        from cozmo_companion.core.motor_cozmo import ligar_oled_base, modo_tts_preparar, ping_oob

        lim = limites()
        na_base_proc = self._na_base_efetivo() and self._base_usa_rosto_vivo()
        notif_tts = getattr(self._fila, "_notif_tts_ativo", False)
        if notif_tts:
            manter_face = os.environ.get("NOTIF_TTS_MANTER_FACE", "0") == "1"
        else:
            manter_face = na_base_proc and os.environ.get(
                "TTS_SINAL_MANTEM_FACE_BASE", "1"
            ) == "1"
        if not manter_face:
            modo_tts_preparar(self.cli)
            self._face.desligar()
        else:
            from cozmo_companion.core.motor_cozmo import (
                _clip_loop_vivo,
                base_oled_loop_segurado,
                pausar_base_oled_para_texto,
                segurar_base_oled_loop,
            )

            hold_tts = float(os.environ.get("COZMO_TTS_SINAL_QUIET_S", "8")) + 1.0
            segurar_base_oled_loop(hold_tts)
            pausar_base_oled_para_texto(hold_tts, self.cli)
            if not base_oled_loop_segurado() and not _clip_loop_vivo():
                try:
                    ligar_oled_base(
                        self.cli,
                        forcar=False,
                        preso_na_base=self._na_base_efetivo(),
                    )
                except Exception:
                    pass
        self._monitor_rx.pausar(lim.tts_grace_s)
        pausar_stt = os.environ.get("STT_PAUSE_DURING_TTS", "1") == "1"
        if pausar_stt and self.ouvinte:
            self.ouvinte.pause()
        try:
            if notif_tts:
                max_pkts = int(os.environ.get("NOTIF_TTS_PACOTES", "3"))
            else:
                max_pkts = int(os.environ.get("TTS_SINAL_PACOTES", "1"))
            try:
                self.cli.set_volume(self.volume)
            except Exception:
                pass
            n = falar(
                self.cli,
                texto,
                max_pkts=max_pkts,
                servir=lambda: pulso_ping(self.cli, 1),
                manter_face=manter_face,
                na_base=self._na_base_efetivo(),
            )
            quiet = float(
                os.environ.get(
                    "NOTIF_TTS_QUIET_S",
                    os.environ.get("COZMO_TTS_SINAL_QUIET_S", "6"),
                )
                if notif_tts
                else os.environ.get("COZMO_TTS_SINAL_QUIET_S", "6" if manter_face else "8")
            )
            if self._na_base_efetivo():
                from cozmo_companion.core.motor_cozmo import segurar_base_oled_loop

                segurar_base_oled_loop(quiet + 1.5)
            self._marcar_udp_quieto(quiet, pausar_fila=False)
            self._monitor_rx.pausar(quiet)
            return n > 0
        except Exception as exc:
            msg = str(exc).strip() or type(exc).__name__
            logger.warning("Sinal TTS falhou: %s", msg)
            return False
        finally:
            if pausar_stt and self.ouvinte:
                self.ouvinte.resume()
            if not manter_face:
                ping_oob(self.cli, 1)
            if na_base_proc:
                self._restaurar_olhos_base_pos_tts()
            self._ultimo_tts_fim = time.monotonic()

    def _executar_som_notif_fila(self) -> bool:
        from cozmo_companion.notifications.core.som import tocar_beep_notif

        lim = limites()
        self._monitor_rx.pausar(lim.tts_grace_s)
        manter = self._na_base_efetivo() and os.environ.get(
            "NOTIF_SOM_MANTER_FACE", "1"
        ) == "1"
        ok = tocar_beep_notif(
            self.cli,
            manter_face=manter,
            volume=self.volume,
        )
        quiet = float(os.environ.get("NOTIF_SOM_S", "0.65")) + 0.5
        if self._na_base_efetivo():
            from cozmo_companion.core.motor_cozmo import segurar_base_oled_loop

            segurar_base_oled_loop(quiet + 1.0)
        self._marcar_udp_quieto(quiet, pausar_fila=False)
        return ok

    def _executar_fala(self) -> None:
        if self._carinho_recente():
            return
        try:
            texto = self.fala_q.get_nowait()
        except queue.Empty:
            return
        if not texto or texto.strip() in ("<UNK>", "unk"):
            return
        if not self._gov.reservar("tts"):
            try:
                self.fala_q.put_nowait(texto)
            except queue.Full:
                pass
            return
        from cozmo_companion.core.motor_cozmo import ligar_oled_base, modo_tts_preparar

        lim = limites()
        na_base_proc = self._na_base_efetivo() and self._base_usa_rosto_vivo()
        manter_face = na_base_proc and os.environ.get("TTS_SINAL_MANTEM_FACE_BASE", "1") == "1"
        if not manter_face:
            modo_tts_preparar(self.cli)
        else:
            ligar_oled_base(self.cli, forcar=False, preso_na_base=self._na_base_efetivo())
        with self._lock:
            self._falando = True
        self._tts_cancel.clear()
        if self._na_base_efetivo() and not manter_face:
            self._face.desligar()
        self._monitor_rx.pausar(lim.tts_grace_s)
        if os.environ.get("STT_PAUSE_DURING_TTS", "1") == "1" and self.ouvinte:
            self.ouvinte.pause()
        try:
            max_pkts = lim.tts_max_base if self._na_base_efetivo() else lim.tts_max_mesa
            if modo_sinal():
                max_pkts = int(os.environ.get("TTS_SINAL_PACOTES", "1"))
            rx_antes = rx_frames(self.cli)

            def _servir() -> None:
                pulso_ping(self.cli, 1)
                self._monitor_rx.tick(self.cli)

            falar(
                self.cli,
                texto,
                max_pkts=max_pkts,
                servir=_servir,
                cancelar=self._tts_cancel.is_set,
                manter_face=manter_face,
                na_base=self._na_base_efetivo(),
            )
            sinal_curto = modo_sinal() or max_pkts <= 2
            rx_ok = conexao_ok(self.cli) if sinal_curto else rx_frames(self.cli) > rx_antes
            if rx_ok and self._na_base_efetivo() and not sinal_curto:
                rx_ok = rx_estavel_pos_tts(
                    self.cli, rx_antes, float(os.environ.get("COZMO_TTS_RX_CHECK_S", "6"))
                )
            self._monitor_rx.sincronizar(self.cli)
            quiet = float(os.environ.get("COZMO_TTS_POST_QUIET_OK_S" if rx_ok else "COZMO_TTS_POST_QUIET_S", "14"))
            if sinal_curto:
                quiet = min(quiet, float(os.environ.get("COZMO_TTS_SINAL_QUIET_S", "10")))
            self._marcar_udp_quieto(quiet)
            self._monitor_rx.pausar(quiet)
        finally:
            if self.ouvinte:
                self.ouvinte.resume()
            with self._lock:
                self._falando = False
            if na_base_proc:
                self._restaurar_olhos_base_pos_tts()
            self._ultimo_tts_fim = time.monotonic()

    def _ao_wake_word(self) -> None:
        if hasattr(self, "_detector_escuro"):
            self._detector_escuro.marcar_despertar()
        self._abrir_janela_stt_base()
        self._vida.acordar_para_voz(self.cli)
        logger.info("Wake acordou")
        if (
            self._na_base_efetivo()
            and os.environ.get("WAKE_BASE_VISUAL_ONLY", "1") == "1"
        ):
            from cozmo_companion.display.rosto import solicitar_reacao_visual

            solicitar_reacao_visual("wake", frames=5)
            # Dizer apenas "Cozmo" não deve somar TTS ao stream OLED. Essa
            # sobreposição enche o UDP do firmware e termina em COZMO 01.
            self._fila.enviar_anim(REACOES_WAKE, prioridade=False)
            logger.info("Wake na base — reação somente visual")
            return
        na_carga = self._na_base_efetivo() and carregando(self.cli)
        if na_carga and os.environ.get("WAKE_NA_BASE_RELAX", "1") != "1":
            return
        self._vivo.reagir_ouvir(self.cli)
        if self._na_base_efetivo() and audio_na_base():
            self._vivo.reagir_ouvir(self.cli)
            sinal = sinal_para("", random.choice(("Opa", "Oi", "Beep")))
            logger.info("Sinal: %s", sinal)
            self._fila.enviar_sinal_tts(sinal, prioridade=True)
        else:
            self._fila.enviar_anim(REACOES_WAKE, prioridade=True)
            self._pedir_fala(
                random.choice(("Opa!", "Oi porco!", "Beep!", "Tô ouvindo!")),
                tela="?",
                na_base_ok=True,
                prioridade=True,
            )

    def _responder_util_tela(self, texto: str) -> bool:
        especial = self._resposta_especial(texto)
        if especial is None:
            return False
        self._vida.acordar_para_voz(self.cli)
        oled = self._tela_resposta(texto, especial, None)
        logger.info("Util tela: %s → %s", texto[:30], oled)
        seg = float(os.environ.get("TELA_RESPOSTA_S", "8"))
        if self._na_base_efetivo() and modo_sinal() and audio_na_base() and oled:
            self._fila.enviar_oled(
                oled[:16], segundos=seg, prioridade=True, forcado=True
            )
            sinal = sinal_para(texto, especial)
            logger.info("Sinal: %s | tela: %s", sinal, oled[:16])
            self._fila.enviar_sinal_tts(sinal, prioridade=True)
        else:
            if oled:
                self.tela.mostrar(oled[:16], segundos=seg, prioridade="util")
            if not self._gov.saturado():
                self._fila.enviar_anim(REACOES_PERGUNTA, prioridade=True)
        self._ultimo_util_tela = time.monotonic()
        return True

    def _ao_pergunta_voz(self, texto: str, *, forcar: bool = False) -> None:
        agora = time.monotonic()
        t = texto.strip()
        if forcar and (self._falando or self._llm_ocupado):
            self._interromper_fala()
        elif self._falando or self._llm_ocupado:
            return
        if t == self._ultima_pergunta_txt and agora - self._ultima_pergunta_em < 3.0:
            return
        if self._gov.saturado() and not comando_util(t):
            return
        if self._na_base_efetivo() and not comando_util(t):
            if agora < self._cooldown_voz_base_ate:
                return
            self._cooldown_voz_base_ate = agora + float(
                os.environ.get("COOLDOWN_VOZ_BASE_S", "12")
            )
        self._ultima_pergunta_txt = t
        self._ultima_pergunta_em = agora
        from cozmo_companion.voice.acoes_llm import (
            AcaoEmocional,
            acao_requer_sono,
            inferir_acao_do_usuario,
        )

        if self._na_base_efetivo() and acao_requer_sono(inferir_acao_do_usuario(t)):
            self._vida.cochilar(self.cli, preso_na_base=self._base.preso_na_base)
            if os.environ.get("DORMIR_VOZ_SEM_LLM", "1") == "1":
                logger.info("Dormir imediato (voz): %s", t[:24])
                return
        if comando_util(t) and self._na_base_efetivo():
            util_cooldown = float(os.environ.get("UTIL_VOZ_COOLDOWN_S", "12"))
            if agora - self._ultimo_util_tela < util_cooldown:
                logger.info("Util repetido/eco ignorado: %s", t[:30])
                return
            if self._responder_util_tela(t):
                return
        self.usuario_q.put(texto)

    def _processar_stt(self) -> None:
        while True:
            try:
                item = self._stt_fila.get_nowait()
            except queue.Empty:
                break
            if item[0] == "texto":
                self._tratar_texto_ouvido(item[1])
            elif item[0] == "wake":
                self._ao_wake_word()
            elif item[0] == "pergunta":
                self._ao_pergunta_voz(item[1], forcar=True)
            elif item[0] == "som":
                self._tratar_som_ouvido(item[1], item[2])

    def _stt_receber_som(self, tipo: str, valor: str | float) -> None:
        self._stt_fila.put(("som", tipo, valor))

    def _som_reacao_permitido(self) -> bool:
        if os.environ.get("REACAO_OFICIAL_ENABLED", "1") != "1":
            return False
        if self._falando or self._llm_ocupado:
            return False
        if self._periodo_quieto_ativo():
            return False
        return True

    def _fala_espontanea_permitida(self) -> bool:
        if os.environ.get("ESPONTANEO_ENABLED", "1") != "1":
            return False
        if self._falando or self._llm_ocupado:
            return False
        if self._periodo_quieto_ativo():
            return False
        if getattr(self, "_vida", None) is not None and self._vida.dormindo:
            return False
        gov = getattr(self, "_gov", None)
        if gov is not None and (getattr(gov, "ultimo_rx_ok", True) is False or gov.saturado()):
            return False
        if getattr(self, "_fila", None) is not None and not self._fila.livre:
            return False
        return True

    def _pedir_fala_espontanea(
        self,
        fala: str,
        *,
        tela: str | None = None,
        grupos: tuple[str, ...] | None = None,
        prioridade: bool = False,
    ) -> bool:
        if not fala or not self._fala_espontanea_permitida():
            return False
        logger.info("Fala curta espontanea: %s", fala[:32])
        if grupos is None:
            grupos = ("CodeLabReactHappy", "CodeLabHappy", "InterestedFace", "ReactToPokeReaction")
        self._fila.enviar_anim(grupos, prioridade=prioridade)
        self._pedir_fala(fala, tela=tela, na_base_ok=True, prioridade=prioridade)
        return True

    def _talvez_ecoar_texto(self, texto: str) -> bool:
        self._espontaneo.registrar_ouvido(texto)
        return False

    def _tocar_som_reacao(self, tipo: str) -> bool:
        from cozmo_companion.core.som_reacao import tocar_som_reacao

        self._monitor_rx.pausar(float(os.environ.get("SOM_REACAO_RX_PAUSE_S", "8")))
        ok = tocar_som_reacao(
            self.cli,
            tipo=tipo,
            manter_face=self._na_base_efetivo(),
            volume=self.volume,
        )
        quiet = float(os.environ.get("SOM_REACAO_QUIET_S", "2.5"))
        self._marcar_udp_quieto(quiet, pausar_fila=False)
        return ok

    def _reagir_barulho(self, nivel: float) -> None:
        agora = time.monotonic()
        cooldown = float(os.environ.get("BARULHO_COOLDOWN_S", "6"))
        if agora - self._ultimo_barulho < cooldown or not self._som_reacao_permitido():
            return
        self._ultimo_barulho = agora
        logger.info("Barulho alto detectado (rms=%.0f) — reacao sonora", nivel)
        if hasattr(self, "_detector_escuro"):
            self._detector_escuro.marcar_despertar()
        self._vida.registrar_interacao(
            20.0, cli=self.cli, motivo="barulho", preso_na_base=self._base.preso_na_base
        )
        pool = self._anim_director.pool(
            set(self.cli.animation_groups.keys()), self._ctx_anim(), AnimIntent.SOUND
        )
        if pool:
            self._fila.enviar_anim(pool, prioridade=False)
        # "Repete" o barulho com um bipe curto do próprio alto-falante do Cozmo
        # (sem TTS/fala e sem depender do microfone do PC para o retorno) —
        # mais intenso quanto mais alto veio o som, tipo a florzinha que reage
        # a grito.
        limiar_intenso = float(os.environ.get("BARULHO_INTENSO_RMS", "2600"))
        tipo_som = "susto" if nivel >= limiar_intenso else "curioso"
        if self._na_base_efetivo():
            from cozmo_companion.display.rosto import solicitar_reacao_visual

            solicitar_reacao_visual("sound", frames=5)
        self._tocar_som_reacao(tipo_som)
        logger.info("Barulho na base" if self._na_base_efetivo() else "Barulho livre")

    def _reagir_latido(self, texto: str = "") -> None:
        agora = time.monotonic()
        cooldown = float(os.environ.get("LATIDO_COOLDOWN_S", "4"))
        if agora - self._ultimo_latido < cooldown or not self._som_reacao_permitido():
            return
        self._ultimo_latido = agora
        logger.info("Latido detectado — respondendo: %s", texto[:24])
        self._vida.registrar_interacao(
            18.0, cli=self.cli, motivo="latido", preso_na_base=self._base.preso_na_base
        )
        grupos = REACOES_LATIDO if self._na_base_efetivo() else REACOES_LATIDO_LIVRE
        if self._na_base_efetivo():
            pool = self._anim_director.pool(
                set(self.cli.animation_groups.keys()), self._ctx_anim(), AnimIntent.SOUND
            )
            if pool:
                self._fila.enviar_anim(pool, prioridade=False)
            logger.info("Latido na base — reação leve serializada")
            return
        self._pedir_fala_espontanea("au au", tela=None, grupos=grupos, prioridade=True)

    def _tratar_som_ouvido(self, tipo: str, valor: str | float) -> None:
        if tipo == "barulho":
            try:
                nivel = float(valor)
            except (TypeError, ValueError):
                nivel = 0.0
            self._reagir_barulho(nivel)
        elif tipo == "latido":
            self._reagir_latido(str(valor))

    def _tratar_texto_ouvido(self, texto: str) -> None:
        if (
            self._na_base_efetivo()
            and os.environ.get("BASE_VOICE_REACTIONS_ONLY", "1") == "1"
        ):
            self._wake.encerrar_espera()
            agora = time.monotonic()
            cooldown = float(os.environ.get("BASE_VOICE_REACTION_COOLDOWN_S", "4"))
            if (
                agora - self._ultima_reacao_fala >= cooldown
                and self._fila.livre
                and not self._periodo_quieto_ativo()
                and getattr(getattr(self, "_gov", None), "ultimo_rx_ok", True)
            ):
                pool = self._anim_director.pool(
                    set(self.cli.animation_groups.keys()),
                    self._ctx_anim(),
                    AnimIntent.SOUND,
                )
                if pool and self._fila.enviar_anim(pool, prioridade=False):
                    self._ultima_reacao_fala = agora
                    logger.info("Voz ambiente: reação leve (%s)", texto[:30])
            return
        if parece_latido(texto):
            self._reagir_latido(texto)
            return
        if self._wake.processar(texto):
            logger.info("Wake processado: %s", texto)
            return
        if self._wake.aguardando:
            self._ao_pergunta_voz(texto)
            return
        from cozmo_companion.voice.intent import (
            parece_alias_wake,
            parece_comando_curto,
            parece_fala_dirigida,
            parece_saudacao,
        )
        from cozmo_companion.voice.resposta import resposta_rapida
        from cozmo_companion.voice.wake import contem_wake

        if parece_alias_wake(texto) or contem_wake(texto):
            logger.info("Wake: %s", texto)
            self._ao_wake_word()
            return
        if self._na_base_efetivo():
            if resposta_rapida(texto) or comando_util(texto):
                self._ao_pergunta_voz(texto)
                return
            if os.environ.get("BASE_VOZ_SOMENTE_WAKE", "1") == "1":
                if not (contem_wake(texto) or parece_saudacao(texto)):
                    logger.info("Ignorado (base): %s", texto)
                    self._talvez_ecoar_texto(texto)
                    return
            self._ao_pergunta_voz(texto)
            return
        if os.environ.get("WAKE_RELAX", "1") == "1" and (
            parece_fala_dirigida(texto)
            or parece_saudacao(texto)
            or parece_comando_curto(texto)
        ):
            self._ao_pergunta_voz(texto)
            return
        self._talvez_ecoar_texto(texto)

    def _stt_receber_texto(self, texto: str) -> None:
        self._stt_fila.put(("texto", texto))

    def _aplicar_acao_llm(self, resposta: RespostaCozmo, usuario: str) -> None:
        """Executa animação/tela/motor escolhida pelo LLM (thread principal)."""
        acao = resolver_acao(resposta, usuario)
        if acao == AcaoEmocional.NADA:
            return

        na_base = self._na_base_efetivo()
        carg = carregando(self.cli)
        if na_base and self._na_base_efetivo():
            if acao_requer_explorar(acao):
                tela = tela_para_acao(acao, resposta.tela)
                if tela:
                    self.tela.mostrar(tela, segundos=3.0)
                return
            if carg and acao_bloqueada_na_carga(acao):
                logger.debug("Ação [%s] bloqueada na carga", acao.value)
                acao = AcaoEmocional.CONFORTO
            logger.info("LLM ação na base [%s]", acao.value)
            if acao_requer_sono(acao):
                tela = tela_para_acao(acao, resposta.tela) or "zZz"
                self.tela.mostrar(tela, segundos=300.0, prioridade="sono")
                if not carg:
                    self._vida.cochilar(self.cli, preso_na_base=self._base.preso_na_base)
                else:
                    grupos = grupos_para_acao(acao)
                    if grupos:
                        self._tocar_grupo(grupos)
            else:
                grupos = grupos_para_acao(acao)
                if grupos:
                    self._tocar_grupo(grupos)
                tela = tela_para_acao(acao, resposta.tela)
                if tela:
                    self.tela.mostrar(tela, segundos=4.0)
            self._espirito.registrar_interacao(20.0)
            if not acao_requer_sono(acao):
                self._vida.registrar_interacao(20.0)
            return
        if na_base and carg and acao_bloqueada_na_carga(acao):
            logger.debug("Ação [%s] bloqueada na carga", acao.value)
            acao = AcaoEmocional.CURIOSO if acao == AcaoEmocional.EXPLORAR else AcaoEmocional.NADA
            if acao == AcaoEmocional.NADA:
                tela = tela_para_acao(resolver_acao(resposta, usuario), resposta.tela)
                if tela:
                    self.tela.mostrar(tela, segundos=4.0)
                return

        logger.info("LLM ação [%s]", acao.value)

        if acao_requer_explorar(acao):
            if not self._na_base_efetivo():
                self._explorador.antecipar(2.0)
            grupos = grupos_para_acao(acao)
            if grupos:
                self._tocar_grupo(grupos)
        elif acao_requer_sono(acao):
            tela = tela_para_acao(acao, resposta.tela) or "zZz"
            self.tela.mostrar(tela, segundos=300.0, prioridade="sono")
            if na_base and not carg:
                self._vida.cochilar(self.cli, preso_na_base=self._base.preso_na_base)
            else:
                self._tocar_grupo(grupos_para_acao(acao))
        else:
            grupos = grupos_para_acao(acao)
            if grupos:
                self._tocar_grupo(grupos)

        tela = tela_para_acao(acao, resposta.tela)
        if tela and not acao_requer_sono(acao):
            self.tela.mostrar(tela, segundos=5.0)

        self._espirito.registrar_interacao(20.0)
        if not acao_requer_sono(acao):
            self._vida.registrar_interacao(20.0)

    def _processar_acao_llm(self) -> None:
        try:
            resposta, usuario = self._acao_llm_q.get_nowait()
        except queue.Empty:
            return
        self._aplicar_acao_llm(resposta, usuario)

    def _processar_conversa(self) -> None:
        if self._gov.saturado():
            while True:
                try:
                    self.usuario_q.get_nowait()
                except queue.Empty:
                    break
            return
        try:
            usuario = self.usuario_q.get_nowait()
        except queue.Empty:
            return
        with self._llm_lock:
            if self._llm_ocupado:
                return
            self._llm_ocupado = True
        from cozmo_companion.voice.resposta import resposta_rapida

        rapida = resposta_rapida(usuario)
        if rapida:
            resp = RespostaCozmo(
                fala=rapida,
                acao=inferir_acao_do_usuario(usuario),
            )
            self._pedir_fala(
                rapida,
                pergunta=usuario,
                tela=tela_para_acao(resp.acao) or None,
                na_base_ok=True,
                prioridade=True,
            )
            self._acao_llm_q.put((resp, usuario))
            with self._llm_lock:
                self._llm_ocupado = False
            return
        especial = self._resposta_especial(usuario)
        if especial is not None:
            resp = RespostaCozmo(
                fala=especial,
                acao=inferir_acao_do_usuario(usuario),
            )
            self._pedir_fala(especial, pergunta=usuario, na_base_ok=True)
            self._acao_llm_q.put((resp, usuario))
            with self._llm_lock:
                self._llm_ocupado = False
            return
        perf = PERFIS[self._modo_atual]
        na_base = self._na_base_efetivo()

        def _pensar() -> None:
            try:
                if os.environ.get("LLM_ACOES", "1") == "1":
                    resposta = self.chat.responder_com_acao(
                        usuario, permitir_llm=perf.usar_llm, na_base=na_base
                    )
                    logger.info(
                        "Responde: %s | acao=%s",
                        resposta.fala,
                        resposta.acao.value,
                    )
                    self._acao_llm_q.put((resposta, usuario))
                    tela = tela_para_acao(resposta.acao, resposta.tela) or texto_tela_de_fala(
                        resposta.fala
                    )
                    self._pedir_fala(
                        resposta.fala,
                        pergunta=usuario,
                        tela=tela or None,
                        na_base_ok=True,
                    )
                else:
                    txt = self.chat.responder(usuario, permitir_llm=perf.usar_llm, na_base=na_base)
                    self._pedir_fala(txt, pergunta=usuario, na_base_ok=True)
            except Exception as exc:
                logger.warning("LLM falhou: %s", exc)
                self._pedir_fala("Beep!", tela="Repita?", na_base_ok=True)
            finally:
                with self._llm_lock:
                    self._llm_ocupado = False

        threading.Thread(target=_pensar, daemon=True, name="CozmoLLM").start()

    def _notif_recebida(self, notif: Notificacao) -> None:
        try:
            with self._lock:
                from cozmo_companion.core.charger import carregando

                aplicar_notificacao(
                    self,
                    notif,
                    carregando=carregando(self.cli),
                    preso_na_base=self._base.preso_na_base,
                )
        except Exception as exc:
            logger.warning("Notif imediata: %s", exc)

    def _processar_notificacoes(self) -> None:
        return

    def _loop_voz_arquivo(self) -> None:
        if os.environ.get("COZMO_VOZ_INJECT", "0") != "1":
            return
        if not self._voz_cmd.is_file():
            return
        try:
            txt = self._voz_cmd.read_text(encoding="utf-8").strip()
            self._voz_cmd.unlink(missing_ok=True)
            if txt:
                logger.info("Voz injetada: %s", txt)
                self._tratar_texto_ouvido(txt)
        except OSError as exc:
            logger.warning("voz.cmd: %s", exc)

    def _iniciar_ouvinte(self) -> None:
        if not self.chat_enabled:
            return
        modelo = Path(
            os.environ.get(
                "VOSK_MODEL",
                "/mnt/G/PROJETOS/cozmo-companion/data/vosk-model-small-pt-0.3",
            )
        )
        try:
            from cozmo_companion.voice.mic import ativar_fonte, mic_ocupado_externo

            if not mic_ocupado_externo():
                ativar_fonte()
        except Exception:
            pass
        try:
            self.ouvinte = Ouvinte(
                modelo,
                self._stt_receber_texto,
                on_evento=self._stt_receber_som,
                device=resolver_dispositivo(),
            )
            self.ouvinte.start()
            logger.info("Microfone ativo: %s", self.ouvinte.device_nome)
        except Exception as exc:
            logger.error("STT indisponível: %s", exc)

    def _iniciar_ouvinte_notificacoes(self) -> None:
        if os.environ.get("NOTIF_ENABLED", "0") != "1":
            return
        try:
            self._ouvinte_notif = OuvinteNotificacoes(self._notif_recebida)
            self._ouvinte_notif.start()
        except Exception as exc:
            logger.error("Notificações indisponíveis: %s", exc)

    def parar_voz(self) -> None:
        if self._ouvinte_notif:
            self._ouvinte_notif.stop()
        if self.ouvinte:
            self.ouvinte.stop()
