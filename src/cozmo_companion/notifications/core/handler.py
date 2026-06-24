"""Aplica notificação KDE na fila serial — som nativo Cozmo, OLED, loop base."""

from __future__ import annotations

import logging
import os
import time
from typing import TYPE_CHECKING, Protocol

from cozmo_companion.notifications.core.display import segundos_tela_notif
from cozmo_companion.notifications.core.listener import Notificacao
from cozmo_companion.notifications.core.policy import (
    ContextoNotif,
    deve_processar,
    nome_app_oled,
)

if TYPE_CHECKING:
    import pycozmo

    from cozmo_companion.core.fila_cozmo import FilaCozmo
    from cozmo_companion.core.vida import CicloVida

logger = logging.getLogger("cozmo.notif")


class _HostNotif(Protocol):
    cli: "pycozmo.Client"
    _fila: "FilaCozmo"
    _vida: "CicloVida"
    _ultima_notif: float
    _ultima_notif_app: str
    _ultima_notif_titulo: str
    _falando: bool
    _llm_ocupado: bool
    _modo_udp_leve: bool

    def _na_base_efetivo(self) -> bool: ...


REACOES_NOTIF = (
    "InterestedFace",
    "NeutralFace",
    "LookInPlaceForFacesHeadMovePause",
    "Hiccup",
)


def _pausar_loop_base(cli: "pycozmo.Client", na_base: bool) -> None:
    if not na_base:
        return
    try:
        from cozmo_companion.core.motor_cozmo import (
            _base_oled_anim_loop_ativo,
            _parar_base_oled_anim_loop,
        )

        if _base_oled_anim_loop_ativo():
            _parar_base_oled_anim_loop(timeout=2.0)
    except Exception as exc:
        logger.debug("Pausa loop base (notif): %s", exc)


def _grupo_som_notif() -> str:
    """Marcador lógico — áudio via OutputAudio (som_notif), não anim Hiccup."""
    modo = (os.environ.get("NOTIF_SOM_MODO") or "beep").strip().lower()
    if modo in ("0", "off", "none"):
        return ""
    return modo or "beep"


def _som_notif_habilitado() -> bool:
    if os.environ.get("NOTIF_SOM", "1") != "1":
        return False
    return bool(_grupo_som_notif())


def aplicar_notificacao(
    host: _HostNotif,
    notif: Notificacao,
    *,
    carregando: bool,
    preso_na_base: bool,
) -> bool:
    """Enfileira notif se política permitir. Retorna True se processou."""
    agora = time.monotonic()
    rx_ok = True
    gov = getattr(host, "_gov", None)
    if gov is not None:
        rx_ok = bool(getattr(gov, "ultimo_rx_ok", True))
    ctx = ContextoNotif(
        falando=host._falando,
        llm_ocupado=host._llm_ocupado,
        modo_udp_leve=host._modo_udp_leve,
        na_base=host._na_base_efetivo(),
        carregando=carregando,
        ultima_em=host._ultima_notif,
        agora=agora,
        ultima_app=getattr(host, "_ultima_notif_app", ""),
        ultima_titulo=getattr(host, "_ultima_notif_titulo", ""),
        rx_ok=rx_ok,
    )
    if not deve_processar(notif, ctx):
        return False

    if (
        host._fila.ocupada
        and os.environ.get("NOTIF_BLOCK_FILA_BUSY", "1") == "1"
    ):
        logger.debug("Notificação [%s] adiada — fila ocupada", notif.app or "?")
        return False

    na_base = host._na_base_efetivo()

    rx_pause = float(os.environ.get("NOTIF_RX_PAUSE_S", "18"))
    mon = getattr(host, "_monitor_rx", None)
    if mon is not None:
        mon.pausar(rx_pause)

    detector = getattr(host, "_detector_escuro", None)
    if detector is not None:
        try:
            detector.marcar_despertar(float(os.environ.get("COZMO_ESCURO_DESPERTAR_S", "180")))
        except Exception:
            pass

    dormindo = getattr(host._vida, "dormindo", False) is True
    em_sono = getattr(host._vida, "em_sono", False) is True
    if dormindo or em_sono:
        host._vida.despertar(
            host.cli,
            motivo=f"notif:{(notif.app or '?')[:12]}",
            preso_na_base=preso_na_base,
        )
    else:
        from cozmo_companion.core.vida import AWAKE_APOS_DESPERTAR

        host._vida.registrar_interacao(
            AWAKE_APOS_DESPERTAR,
            cli=host.cli,
            motivo="notif",
            preso_na_base=preso_na_base,
        )

    app_linha = nome_app_oled(notif)
    titulo_linha = None
    duas = False
    seg_app = segundos_tela_notif(duas_linhas=False)[0]
    seg_tit = 0.0
    oled_curto = app_linha
    oled_longo = app_linha

    som_beep = _som_notif_habilitado() and bool(_grupo_som_notif())
    if som_beep:
        logger.info("Notificação → beep + OLED %s", oled_curto)
    else:
        logger.info("Notificação → OLED %s", oled_curto)

    total_oled = seg_app + (seg_tit if duas else 0.0)
    quiet_est = max(
        float(os.environ.get("COZMO_FILA_QUIET_S", "0.8")),
        float(os.environ.get("NOTIF_ANIM_S", "2.2")) * 0.35,
    )
    som_s = float(os.environ.get("NOTIF_SOM_S", "0.65")) if som_beep else 0.0
    margin = float(os.environ.get("NOTIF_HOLD_MARGIN_S", "0.5"))
    pause_loop = float(os.environ.get("NOTIF_PAUSE_LOOP_S", "4"))
    hold_max = min(
        float(os.environ.get("NOTIF_HOLD_MAX_S", "12")),
        float(os.environ.get("COZMO_BASE_OLED_HOLD_MAX_S", "12")),
    )
    hold_s = min(
        max(pause_loop, total_oled + quiet_est + som_s + margin),
        hold_max,
    )

    if na_base:
        from cozmo_companion.core.motor_cozmo import (
            pausar_base_oled_para_texto,
            segurar_base_oled_loop,
        )

        segurar_base_oled_loop(hold_s)
        pausar_base_oled_para_texto(hold_s, host.cli)
    else:
        _pausar_loop_base(host.cli, na_base)

    fila_pause = float(os.environ.get("NOTIF_FILA_PAUSE_S", "0.1"))
    host._fila.pausar(fila_pause)

    ok = host._fila.enviar_notif_resumida(
        oled_curto,
        oled_longo,
        seg_app,
        grupos_anim=REACOES_NOTIF if os.environ.get("NOTIF_ANIM", "0") == "1" else (),
        som_beep=som_beep,
        prioridade=True,
        titulo_oled=titulo_linha if duas else None,
        seg_titulo=seg_tit,
        pausar_loop_ja=True,
    )
    if ok:
        host._ultima_notif = agora
        host._ultima_notif_app = (notif.app or "").strip()
        host._ultima_notif_titulo = (notif.titulo or "").strip()
    if ok and hasattr(host, "_marcar_udp_quieto"):
        host._marcar_udp_quieto(
            float(os.environ.get("NOTIF_UDP_QUIET_S", "10")),
            pausar_fila=False,
        )
    if hasattr(host, "_espirito") and not host._vida.dormindo:
        try:
            host._espirito.registrar_interacao(12.0)
        except Exception:
            pass
    return ok
