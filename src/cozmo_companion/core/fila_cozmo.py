"""Fila serial de ações leves no Cozmo — uma por vez, sem flood UDP.

Conflitos documentados:
- Rosto procedural vs anim: procedural desliga antes da anim; restaura quando a fila esvazia.
- TTS na base: só via fila (sinal 1 palavra) + OLED; não enviar frases longas.
"""

from __future__ import annotations

import logging
import os
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Callable

from cozmo_companion.core.motor_cozmo import (
    FRAME_S,
    modo_base_olhos,
    restaurar_apos_anim_base,
)

if TYPE_CHECKING:
    import pycozmo

    from cozmo_companion.core.governador import GovernadorCozmo

logger = logging.getLogger("cozmo.fila")


class EstadoFila(Enum):
    IDLE = "idle"
    ANIM = "anim"
    TTS = "tts"
    OLED = "oled"
    WAIT_OLED = "wait_oled"
    WAIT_QUIET = "wait_quiet"


class TipoItem(str, Enum):
    ANIM = "anim"
    SOM = "som"
    OLED = "oled"
    TTS = "tts"
    QUIET = "quiet"


@dataclass
class ItemFila:
    tipo: TipoItem
    prioridade: bool = False
    reservado: bool = False
    grupos: tuple[str, ...] = ()
    oled_curto: str = ""
    oled_longo: str = ""
    oled_seg: float = 8.0
    tts: str = ""
    quiet_s: float = 0.0
    scroll: bool = False
    scroll_passo: float = 1.0
    oled_forcado: bool = False
    notif: bool = False


@dataclass
class FilaCozmo:
    """Orquestra envios UDP leves ao robô em série."""

    gov: GovernadorCozmo
    tocar_grupo: Callable[..., object]
    mostrar_oled: Callable[..., None]
    executar_sinal: Callable[[str], bool]
    executar_som: Callable[[], bool]
    na_base: Callable[[], bool]
    usa_procedural: Callable[[], bool]

    _fila: deque[ItemFila] = field(default_factory=deque, init=False)
    _estado: EstadoFila = field(default=EstadoFila.IDLE, init=False)
    _pausado_ate: float = field(default=0.0, init=False)
    _quiet_fim: float = field(default=0.0, init=False)
    _oled_fim: float = field(default=0.0, init=False)
    _anim_aguardando: bool = field(default=False, init=False)
    _anim_deadline: float = field(default=0.0, init=False)
    _notif_tts_ativo: bool = field(default=False, init=False)
    _estado_desde: float = field(default=0.0, init=False)
    _procedural_desligado: bool = field(default=False, init=False)

    @property
    def estado(self) -> EstadoFila:
        return self._estado

    @property
    def livre(self) -> bool:
        agora = time.monotonic()
        if agora < self._pausado_ate or agora < self._quiet_fim or agora < self._oled_fim:
            return False
        if self._estado != EstadoFila.IDLE:
            return False
        return len(self._fila) == 0

    @property
    def ocupada(self) -> bool:
        return not self.livre

    @property
    def vazia(self) -> bool:
        agora = time.monotonic()
        return (
            len(self._fila) == 0
            and self._estado == EstadoFila.IDLE
            and not self._anim_aguardando
            and agora >= self._oled_fim
        )

    def pausar(self, segundos: float) -> None:
        agora = time.monotonic()
        hold_max = float(os.environ.get("COZMO_BASE_OLED_HOLD_MAX_S", "15"))
        seg = min(max(0.0, segundos), hold_max)
        candidato = max(self._pausado_ate, agora + seg)
        self._pausado_ate = min(candidato, agora + hold_max)

    def forcar_idle(self, cli: "pycozmo.Client") -> None:
        """Limpa fila presa após abort/reconnect UDP."""
        self._fila.clear()
        self._anim_aguardando = False
        self._anim_deadline = 0.0
        self._estado = EstadoFila.IDLE
        self._estado_desde = 0.0
        self._quiet_fim = 0.0
        self._oled_fim = 0.0
        self._pausado_ate = 0.0
        try:
            from cozmo_companion.core.motor_cozmo import liberar_base_oled_loop_hold

            liberar_base_oled_loop_hold(motivo="fila_forcar_idle")
        except Exception:
            pass
        try:
            cli.cancel_anim()
        except Exception:
            pass
        self._restaurar_rosto_pos_item(cli)
        self._procedural_desligado = False

    def _max_oled(self) -> int:
        return int(os.environ.get("COZMO_MAX_OLED_CHARS", "16"))

    def _max_palavras_tts(self) -> int:
        return int(os.environ.get("COZMO_MAX_TTS_SINAL_WORDS", "1"))

    def _timeout_anim(self) -> float:
        return float(os.environ.get("COZMO_FILA_TIMEOUT_S", "6"))

    def _quiet_padrao(self) -> float:
        return float(os.environ.get("COZMO_FILA_QUIET_S", "0.8"))

    def _tts_pesado(self, texto: str) -> bool:
        t = texto.strip()
        if not t:
            return False
        n = len(t.split())
        if n > self._max_palavras_tts():
            logger.info(
                "Fila — TTS rejeitado (%d palavras, máx %d): %s",
                n,
                self._max_palavras_tts(),
                t[:24],
            )
            return True
        lim = int(os.environ.get("TTS_SINAL_MAX_CHARS", "10"))
        if len(t) > lim:
            logger.info("Fila — TTS rejeitado (longo demais): %s", t[:24])
            return True
        return False

    def _oled_pesado(self, texto: str) -> bool:
        if len(texto) > self._max_oled():
            logger.info("Fila — OLED rejeitado (%d > %d chars)", len(texto), self._max_oled())
            return True
        return False

    def _reservar_gov(self, item: ItemFila) -> bool:
        prio = item.prioridade
        if item.tipo == TipoItem.ANIM:
            return self.gov.reservar("anim", prioridade=prio)
        if item.tipo == TipoItem.SOM:
            return self.gov.reservar("anim", prioridade=prio)
        if item.tipo == TipoItem.TTS:
            return self.gov.reservar("tts", prioridade=prio)
        if item.tipo == TipoItem.OLED:
            return self.gov.reservar("oled", prioridade=prio)
        return True

    def _enqueue_batch(self, batch: list[ItemFila]) -> bool:
        """Reserva todos os itens antes de enfileirar — evita ordem quebrada (TTS→OLED)."""
        items: list[ItemFila] = []
        for item in batch:
            if item.tipo == TipoItem.TTS and self._tts_pesado(item.tts):
                continue
            items.append(item)
        if not items:
            return False
        for item in items:
            if not self._reservar_gov(item):
                logger.debug("Fila batch — adiado (governador): %s", item.tipo.value)
                return False
            item.reservado = True
        for item in reversed(items):
            self._fila.appendleft(item)
        return True

    def enqueue(self, item: ItemFila, *, prioridade: bool = False) -> bool:
        if os.environ.get("COZMO_FILA_ATIVA", "1") != "1":
            return False
        item.prioridade = prioridade
        if item.tipo == TipoItem.TTS and self._tts_pesado(item.tts):
            return False
        if item.tipo == TipoItem.OLED and not item.scroll and self._oled_pesado(item.oled_curto):
            return False
        if not self._reservar_gov(item):
            logger.debug("Fila — adiado (governador): %s", item.tipo.value)
            return False
        item.reservado = True
        if prioridade:
            self._fila.appendleft(item)
        else:
            self._fila.append(item)
        return True

    def enviar_anim(
        self,
        grupos: tuple[str, ...],
        *,
        prioridade: bool = False,
    ) -> bool:
        if not grupos:
            return False
        return self.enqueue(
            ItemFila(tipo=TipoItem.ANIM, grupos=grupos),
            prioridade=prioridade,
        )

    def enviar_oled(
        self,
        texto: str,
        *,
        segundos: float = 8.0,
        scroll: bool = False,
        texto_longo: str = "",
        passo_s: float = 1.0,
        prioridade: bool = False,
        forcado: bool = False,
    ) -> bool:
        curto = texto[: self._max_oled()]
        return self.enqueue(
            ItemFila(
                tipo=TipoItem.OLED,
                oled_curto=curto,
                oled_longo=texto_longo or texto,
                oled_seg=segundos,
                scroll=scroll,
                scroll_passo=passo_s,
                oled_forcado=forcado,
            ),
            prioridade=prioridade,
        )

    def enviar_sinal_tts(self, texto: str, *, prioridade: bool = False) -> bool:
        return self.enqueue(
            ItemFila(tipo=TipoItem.TTS, tts=texto.strip()),
            prioridade=prioridade,
        )

    def enviar_carinho_base(
        self,
        oled: str,
        sinal_tts: str | None,
        *,
        oled_seg: float | None = None,
    ) -> bool:
        """OLED → pausa → sinal TTS — ordem correta (appendleft invertido)."""
        seg = oled_seg if oled_seg is not None else float(
            os.environ.get("CARINHO_OLED_S", "3.5")
        )
        hold = float(os.environ.get("CARINHO_OLED_HOLD_S", "1.2"))
        batch: list[ItemFila] = [
            ItemFila(
                tipo=TipoItem.OLED,
                oled_curto=oled[: self._max_oled()],
                oled_seg=seg,
                oled_forcado=True,
                prioridade=True,
            ),
            ItemFila(tipo=TipoItem.QUIET, quiet_s=hold, prioridade=True),
        ]
        if sinal_tts:
            batch.append(ItemFila(tipo=TipoItem.TTS, tts=sinal_tts.strip(), prioridade=True))
        return self._enqueue_batch(batch)

    def enviar_notif_resumida(
        self,
        oled_curto: str,
        oled_longo: str,
        seg_tela: float,
        *,
        grupos_anim: tuple[str, ...],
        som_beep: bool = False,
        som_grupo: str | None = None,
        sinal_tts: str | None = None,
        prioridade: bool = False,
        titulo_oled: str | None = None,
        seg_titulo: float = 0.0,
        pausar_loop_ja: bool = False,
    ) -> bool:
        """Pipeline notif: OLED app → beep curto → quiet (NOTIF_OLED_PRIMEIRO=1).

        NOTIF_OLED_PRIMEIRO=1: nome do app na tela antes do beep.
        NOTIF_SOM_PRIMEIRO=1: beep antes do OLED (legado, mais lento).
        """
        if sinal_tts:
            logger.debug("Notif — sinal_tts ignorado (sem TTS): %s", sinal_tts[:12])
        oled_primeiro = os.environ.get("NOTIF_OLED_PRIMEIRO", "1") == "1"
        som_primeiro = (
            not oled_primeiro
            and os.environ.get("NOTIF_SOM_PRIMEIRO", os.environ.get("NOTIF_SINAL_PRIMEIRO", "0"))
            == "1"
        )
        if not pausar_loop_ja and self.na_base():
            try:
                from cozmo_companion.core.motor_cozmo import (
                    _base_oled_anim_loop_ativo,
                    _parar_base_oled_anim_loop,
                )

                if _base_oled_anim_loop_ativo():
                    _parar_base_oled_anim_loop(
                        timeout=float(os.environ.get("NOTIF_LOOP_STOP_S", "0.25"))
                    )
            except Exception:
                pass
        anim_first = os.environ.get("COZMO_NOTIF_ANIM_FIRST", "1") == "1"
        anim_na_base = os.environ.get("COZMO_NOTIF_ANIM_NA_BASE", "0") == "1"
        pular_oled = (
            self.na_base()
            and os.environ.get("NOTIF_OLED_NA_BASE", "1") != "1"
            and os.environ.get("COZMO_OLED_NA_BASE", "0") != "1"
            and os.environ.get("COZMO_BASE_OLED_CHARGER", "1") == "1"
        )
        scroll = (
            os.environ.get("NOTIF_SCROLL", "0") == "1"
            and oled_longo != oled_curto
            and len(oled_longo) > self._max_oled()
        )
        quiet = max(
            self._quiet_padrao(),
            float(os.environ.get("NOTIF_QUIET_S", "1.0")),
        )
        batch: list[ItemFila] = []
        oled_items: list[ItemFila] = []
        if not pular_oled:
            oled_items.append(
                ItemFila(
                    tipo=TipoItem.OLED,
                    oled_curto=oled_curto[: self._max_oled()],
                    oled_longo=oled_longo,
                    oled_seg=seg_tela,
                    scroll=scroll,
                    scroll_passo=float(os.environ.get("NOTIF_SCROLL_PASSO_S", "1.0")),
                    oled_forcado=True,
                    prioridade=prioridade,
                    notif=True,
                )
            )
            if titulo_oled and seg_titulo > 0:
                oled_items.append(
                    ItemFila(
                        tipo=TipoItem.OLED,
                        oled_curto=titulo_oled[: self._max_oled()],
                        oled_seg=seg_titulo,
                        oled_forcado=True,
                        prioridade=prioridade,
                        notif=True,
                    )
                )
        som_item: ItemFila | None = None
        if som_beep:
            modo_som = (os.environ.get("NOTIF_SOM_MODO") or "beep").strip().lower()
            if modo_som in ("sinal", "tts"):
                logger.debug(
                    "Notif — NOTIF_SOM_MODO=%s → beep UDP (sem TTS local/PC)",
                    modo_som,
                )
            if modo_som not in ("0", "off", "none"):
                som_item = ItemFila(
                    tipo=TipoItem.SOM,
                    prioridade=prioridade,
                    notif=True,
                )
        if som_primeiro and som_item is not None:
            batch.append(som_item)
        if anim_first and grupos_anim and (anim_na_base or not self.na_base()):
            batch.append(
                ItemFila(tipo=TipoItem.ANIM, grupos=grupos_anim, prioridade=prioridade)
            )
        batch.extend(oled_items)
        if not som_primeiro and som_item is not None:
            batch.append(som_item)
        batch.append(
            ItemFila(tipo=TipoItem.QUIET, quiet_s=quiet, prioridade=prioridade, notif=True)
        )
        return self._enqueue_batch(batch)

    def _desligar_procedural(self, cli: pycozmo.Client) -> None:
        if self._procedural_desligado:
            return
        if self.na_base() and self.usa_procedural():
            return
        ac = cli.anim_controller
        if ac.procedural_face_enabled:
            ac.enable_procedural_face(False)
            self._procedural_desligado = True

    def _restaurar_procedural(self, cli: pycozmo.Client) -> None:
        if not self._procedural_desligado:
            return
        self._restaurar_rosto_pos_item(cli)
        self._procedural_desligado = False

    def _restaurar_rosto_pos_item(self, cli: pycozmo.Client) -> None:
        """Sempre após anim/TTS na fila — evita rosto preso olhando para baixo."""
        if not self.na_base():
            return
        if self.usa_procedural():
            from cozmo_companion.core.motor_cozmo import (
                base_oled_usa_charger,
                ligar_oled_base,
                modo_charger_oled,
            )

            if base_oled_usa_charger(cli):
                from cozmo_companion.core.motor_cozmo import (
                    _base_oled_anim_loop_ativo,
                    _garantir_base_oled_anim_loop,
                )

                from cozmo_companion.core.motor_cozmo import base_oled_loop_segurado

                if base_oled_loop_segurado():
                    return
                from cozmo_companion.core.motor_cozmo import _oled_tx_permitido

                if not _oled_tx_permitido(cli):
                    return
                if _base_oled_anim_loop_ativo():
                    from cozmo_companion.core.motor_cozmo import (
                        modo_sono_oled_ativo,
                        sono_oled_texto_ativo,
                        sono_oled_usa_texto,
                    )

                    if modo_sono_oled_ativo():
                        if sono_oled_texto_ativo() or sono_oled_usa_texto():
                            from cozmo_companion.core.motor_cozmo import (
                                manter_sono_oled_texto,
                            )

                            manter_sono_oled_texto(cli)
                            return
                        from cozmo_companion.core.motor_cozmo import manter_sono_ppclip

                        manter_sono_ppclip(cli)
                        return
                    _garantir_base_oled_anim_loop(cli)
                else:
                    modo_charger_oled(cli, forcar=True)
            else:
                ligar_oled_base(cli, forcar=True)
        else:
            restaurar_apos_anim_base(cli)

    @staticmethod
    def _anim_liberada(cli: pycozmo.Client) -> bool:
        ac = cli.anim_controller
        return not ac.playing_animation and not ac.playing_audio

    def _aguardar_anim_tick(self, cli: pycozmo.Client) -> bool:
        if self._anim_liberada(cli):
            hold = float(os.environ.get("COZMO_FILA_ANIM_HOLD_S", "0.25"))
            if hold > 0:
                time.sleep(min(hold, 0.2))
            self._anim_aguardando = False
            self._estado = EstadoFila.IDLE
            self._restaurar_rosto_pos_item(cli)
            self._procedural_desligado = False
            if not self._fila:
                self._restaurar_procedural(cli)
            return True
        if time.monotonic() >= self._anim_deadline:
            logger.warning("Fila — timeout aguardando anim (%.1fs)", self._timeout_anim())
            try:
                cli.cancel_anim()
            except Exception:
                pass
            self._anim_aguardando = False
            self._estado = EstadoFila.IDLE
            self._restaurar_rosto_pos_item(cli)
            self._procedural_desligado = False
            if not self._fila:
                self._restaurar_procedural(cli)
            return True
        return False

    def _iniciar_item(self, cli: pycozmo.Client, item: ItemFila) -> None:
        self._estado_desde = time.monotonic()
        if item.tipo == TipoItem.ANIM:
            self._desligar_procedural(cli)
            ok = self.tocar_grupo(item.grupos, prioridade=item.prioridade)
            if ok is False:
                self._estado = EstadoFila.IDLE
                self._anim_aguardando = False
                self._anim_deadline = 0.0
                self._restaurar_rosto_pos_item(cli)
                self._procedural_desligado = False
                logger.debug("Fila — anim pulada (robô ocupado)")
                return
            self._estado = EstadoFila.ANIM
            self._anim_aguardando = True
            self._anim_deadline = time.monotonic() + self._timeout_anim()
            logger.info("Fila — anim enfileirada (%d grupos)", len(item.grupos))
            return
        if item.tipo == TipoItem.SOM:
            if self.na_base():
                from cozmo_companion.core.motor_cozmo import (
                    pausar_base_oled_para_texto,
                    segurar_base_oled_loop,
                )

                hold = float(os.environ.get("NOTIF_SOM_S", "0.65")) + 1.0
                segurar_base_oled_loop(hold)
                pausar_base_oled_para_texto(hold, cli)
            ok = self.executar_som()
            self._estado = EstadoFila.IDLE
            logger.info(
                "Fila — play_audio beep notif: %s",
                "ok" if ok else "falhou",
            )
            return
        if item.tipo == TipoItem.OLED:
            if self.na_base() and item.oled_forcado:
                from cozmo_companion.core.motor_cozmo import (
                    pausar_base_oled_para_texto,
                    segurar_base_oled_loop,
                )

                hold = item.oled_seg + 1.5
                segurar_base_oled_loop(hold)
                pausar_base_oled_para_texto(hold, cli)
            self._estado = EstadoFila.OLED
            if item.scroll:
                self.mostrar_oled(
                    item.oled_longo,
                    segundos=item.oled_seg,
                    scroll=True,
                    passo_s=item.scroll_passo,
                    forcado=item.oled_forcado,
                )
            else:
                self.mostrar_oled(
                    item.oled_curto[: self._max_oled()],
                    segundos=item.oled_seg,
                    scroll=False,
                    forcado=item.oled_forcado,
                )
            self._oled_fim = time.monotonic() + max(0.1, item.oled_seg)
            self._estado = EstadoFila.WAIT_OLED
            logger.info("Fila — OLED: %s (%.1fs)", item.oled_curto[:16], item.oled_seg)
            return
        if item.tipo == TipoItem.TTS:
            self._estado = EstadoFila.TTS
            manter = (
                self.na_base()
                and self.usa_procedural()
                and os.environ.get("TTS_SINAL_MANTEM_FACE_BASE", "1") == "1"
            )
            if not manter:
                self._desligar_procedural(cli)
            if self.na_base():
                manter_face = os.environ.get("TTS_SINAL_MANTEM_FACE_BASE", "1") == "1"
                if item.notif or not manter_face:
                    from cozmo_companion.core.motor_cozmo import (
                        pausar_base_oled_para_texto,
                        segurar_base_oled_loop,
                    )

                    tts_hold = float(
                        os.environ.get(
                            "NOTIF_TTS_QUIET_S",
                            os.environ.get("COZMO_TTS_SINAL_QUIET_S", "6"),
                        )
                        if item.notif
                        else os.environ.get("COZMO_TTS_SINAL_QUIET_S", "6")
                    ) + 1.0
                    segurar_base_oled_loop(tts_hold)
                    pausar_base_oled_para_texto(tts_hold, cli)
            self._notif_tts_ativo = item.notif
            ok = self.executar_sinal(item.tts)
            self._notif_tts_ativo = False
            self._estado = EstadoFila.IDLE
            if not self.na_base():
                self._restaurar_rosto_pos_item(cli)
            else:
                from cozmo_companion.core.motor_cozmo import base_oled_loop_segurado

                if not base_oled_loop_segurado():
                    self._restaurar_rosto_pos_item(cli)
            self._procedural_desligado = False
            logger.info("Fila — sinal TTS: %s (%s)", item.tts[:12], "ok" if ok else "falhou")
            return
        if item.tipo == TipoItem.QUIET:
            self._estado = EstadoFila.WAIT_QUIET
            self._quiet_fim = time.monotonic() + max(0.1, item.quiet_s)
            if self.na_base():
                from cozmo_companion.core.motor_cozmo import segurar_base_oled_loop

                post = float(
                    os.environ.get(
                        "NOTIF_POST_QUIET_S",
                        os.environ.get("NOTIF_UDP_QUIET_S", "8"),
                    )
                )
                segurar_base_oled_loop(item.quiet_s + post + 2.0)
            return

    def _drenar_rx_pos_quiet(self, cli: "pycozmo.Client") -> None:
        """Pós-notif/TTS: ping + estabilizar antes de religar loop na base."""
        if not self.na_base():
            return
        from cozmo_companion.core.motor_cozmo import (
            ping_oob,
            religar_base_oled_pos_notif,
            segurar_base_oled_loop,
            sono_oled_texto_ativo,
            manter_sono_oled_texto,
        )
        from cozmo_companion.voice.tts import estabilizar_pos_audio, rx_frames

        post = float(os.environ.get("NOTIF_POST_QUIET_S", "6"))
        segurar_base_oled_loop(post + 3.0)
        rx0 = rx_frames(cli)
        try:
            ping_oob(cli, vezes=3)
        except Exception:
            pass
        estabilizar_pos_audio(cli, rx0)
        from cozmo_companion.core.motor_cozmo import (
            modo_sono_oled_ativo,
            manter_sono_ppclip,
            sono_oled_usa_texto,
        )

        if sono_oled_texto_ativo() or sono_oled_usa_texto():
            manter_sono_oled_texto(cli)
        elif modo_sono_oled_ativo():
            manter_sono_ppclip(cli)
        else:
            religar_base_oled_pos_notif(cli)

    def tick(self, cli: pycozmo.Client) -> None:
        """Avança um passo da fila (chamar na thread principal)."""
        if os.environ.get("COZMO_FILA_ATIVA", "1") != "1":
            return
        agora = time.monotonic()
        max_estado = float(os.environ.get("COZMO_FILA_ESTADO_MAX_S", "15"))
        if (
            self._estado != EstadoFila.IDLE
            and self._estado_desde > 0
            and agora - self._estado_desde >= max_estado
        ):
            logger.warning(
                "Fila — estado %s preso >%.0fs — liberando hold/loop",
                self._estado.value,
                max_estado,
            )
            self.forcar_idle(cli)
            return
        if agora < self._pausado_ate:
            return

        if self._estado == EstadoFila.ANIM or self._anim_aguardando:
            self._aguardar_anim_tick(cli)
            if self._anim_aguardando:
                return

        if agora < self._quiet_fim:
            return

        if self._estado == EstadoFila.WAIT_QUIET:
            self._estado = EstadoFila.IDLE
            self._quiet_fim = 0.0
            if self.na_base() and not self._fila:
                self._drenar_rx_pos_quiet(cli)

        if self._estado == EstadoFila.WAIT_OLED:
            if agora < self._oled_fim:
                if self.na_base():
                    try:
                        from cozmo_companion.core.motor_cozmo import segurar_base_oled_loop

                        segurar_base_oled_loop(max(0.5, self._oled_fim - agora + 1.0))
                    except Exception:
                        pass
                return
            self._estado = EstadoFila.IDLE
            self._oled_fim = 0.0
            if self.na_base() and not self._fila:
                try:
                    from cozmo_companion.core.motor_cozmo import liberar_base_oled_loop_hold

                    liberar_base_oled_loop_hold(motivo="fim_oled_fila")
                except Exception:
                    pass
                self._restaurar_rosto_pos_item(cli)
                self._procedural_desligado = False

        if self._estado != EstadoFila.IDLE:
            return

        if not self._fila:
            from cozmo_companion.core.motor_cozmo import base_oled_loop_segurado

            if agora >= self._quiet_fim and not base_oled_loop_segurado():
                self._restaurar_procedural(cli)
            return

        item = self._fila.popleft()
        if not item.reservado and not self._reservar_gov(item):
            self._fila.appendleft(item)
            return
        self._iniciar_item(cli, item)
        if self._estado == EstadoFila.ANIM:
            time.sleep(min(FRAME_S * 2, 0.06))

    def drenar(self, cli: "pycozmo.Client", *, timeout_s: float = 8.0) -> bool:
        """Processa a fila até esvaziar (transição botão / pós-reconnect)."""
        fim = time.monotonic() + max(0.5, timeout_s)
        while time.monotonic() < fim:
            if self.vazia and time.monotonic() >= self._pausado_ate:
                return True
            self.tick(cli)
            if self._estado == EstadoFila.ANIM or self._anim_aguardando:
                time.sleep(min(FRAME_S * 2, 0.08))
            else:
                time.sleep(min(FRAME_S, 0.04))
        logger.warning("Fila — drenagem incompleta (%.1fs)", timeout_s)
        return self.vazia
