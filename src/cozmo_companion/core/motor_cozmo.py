"""Porta PyCozmo — na base: procedural oficial (HW5) ou OLED direto."""

from __future__ import annotations

import logging
import os
import random
import threading
import time
from typing import TYPE_CHECKING

from pycozmo import protocol_encoder, robot

if TYPE_CHECKING:
    import pycozmo

logger = logging.getLogger("cozmo.motor")

FRAME_S = 1.0 / robot.FRAME_RATE
_pulse_lock = threading.Lock()
_idle_charger_lock = threading.Lock()
_ultimo_pulse_base = 0.0
_ultimo_idle_charger_global = 0.0
_ultimo_sync_base = 0.0
_ultimo_keep_oled = 0.0
_ultimo_modo_proc = 0.0
_keep_oled_lock = threading.Lock()
_sync_base_lock = threading.Lock()
_modo_proc_lock = threading.Lock()
_display_lock = threading.Lock()
_display_stop = threading.Event()
_display_thread: threading.Thread | None = None
_oled_keepalive_stop = threading.Event()
_oled_keepalive_thread: threading.Thread | None = None
_ultimo_exibir_clip_grupo = ""
_ultimo_exibir_clip_em = 0.0
_udp_leve_configurado = False
_charger_oled_nome: str | None = None
_ultimo_charger_play = 0.0
_charger_handler_ok = False
_charger_oled_lock = threading.Lock()
_ultimo_charger_handler = 0.0
_ultimo_charger_falha = 0.0
_charger_stream_sessao = False
_charger_loop_stop = threading.Event()
_charger_loop_thread: threading.Thread | None = None
_charger_keeper_ativo = False
_charger_slow_anim = False
_ultimo_charger_sync = 0.0
_charger_clip_ix = 0
_charger_anim_lock = threading.Lock()
_charger_replay_pendente = False
_charger_replay_em_voo = False
_charger_worker_stop = threading.Event()
_charger_worker_thread: threading.Thread | None = None
_charger_worker_start_lock = threading.Lock()
_ultimo_renovar_base = 0.0
_renovar_rx_snap = 0
_renovar_rx_em = 0.0
_base_rx_link_ok = True
_rx_off_desde = 0.0
_ultimo_variar_clip = 0.0
_ultimos_clips_base: list[str] = []
_modo_sono_oled = False
_sono_oled_texto_ativo = False
_sono_getin_feito = False
_sono_zzz_ultimo_envio = 0.0
_manter_sono_ppclip_ultimo = 0.0
_manter_sono_semear_ultimo = 0.0
_clip_loop_stop = threading.Event()
_clip_loop_thread: threading.Thread | None = None
_clip_loop_start_lock = threading.Lock()
_base_oled_loop_hold_ate: float = 0.0
_base_oled_loop_hold_desde: float = 0.0
_ultimo_watchdog_oled: float = 0.0


def definir_modo_sono_oled(dormindo: bool) -> None:
    """Base dormindo: loop ppclip usa pool sono (Sleeping/GoToSleep…), não idle."""
    global _modo_sono_oled, _sono_oled_texto_ativo, _sono_getin_feito
    _modo_sono_oled = dormindo
    if not dormindo:
        _sono_getin_feito = False
    if dormindo and not sono_oled_usa_texto():
        _sono_oled_texto_ativo = False


def _clip_e_sono_oled(cli: "pycozmo.Client", nome: str | None) -> bool:
    """True se o clip pertence ao pool sono (≠ Hiccup/IdleOnCharger acordado)."""
    if not nome:
        return False
    from cozmo_companion.core.anims import GRUPOS_BASE_SONO_SEM_RODAS, pool_sono_oled_base

    if nome in GRUPOS_BASE_SONO_SEM_RODAS:
        return True
    disp = set(cli.animation_groups.keys())
    return nome in pool_sono_oled_base(disp, cli)


def _parar_awake_oled_base(cli: "pycozmo.Client", *, timeout: float = 2.0) -> None:
    """Para keeper 7Hz, worker IdleOnCharger e loop-clips acordado antes do sono."""
    global _charger_stream_sessao, _charger_keeper_ativo
    global _ultimo_exibir_clip_grupo, _ultimos_clips_base
    _parar_display_keeper()
    _parar_oled_keepalive_base()
    _parar_charger_worker(timeout=timeout)
    _parar_loop_clip_base(timeout=timeout)
    _charger_loop_stop.set()
    th_loop = _charger_loop_thread
    if th_loop and th_loop.is_alive() and threading.current_thread() is not th_loop:
        th_loop.join(timeout=min(timeout, 1.5))
    _charger_loop_stop.clear()
    _charger_stream_sessao = False
    _charger_keeper_ativo = False
    try:
        cli._cozmo_cancel_clip_ok = True  # type: ignore[attr-defined]
        cli.cancel_anim()
    except Exception:
        pass
    finally:
        try:
            cli._cozmo_cancel_clip_ok = False  # type: ignore[attr-defined]
        except Exception:
            pass
    try:
        ac = cli.anim_controller
        ac.queue.clear()
    except Exception:
        pass
    _ultimo_exibir_clip_grupo = ""
    _ultimos_clips_base.clear()
    time.sleep(0.35)


def modo_sono_oled_ativo() -> bool:
    return _modo_sono_oled


def sono_oled_usa_texto() -> bool:
    """Legado: zZz estático — padrão é ppclip sleep (olhos animados)."""
    if os.environ.get("SONO_TELA_ESCURA", "0") == "1":
        return False
    return os.environ.get("COZMO_SONO_OLED_TEXTO", "0") == "1"


def sono_oled_texto_ativo() -> bool:
    return _sono_oled_texto_ativo


def ativar_sono_ppclip(cli: "pycozmo.Client") -> bool:
    """Sono na base: loop ppclip oficial (Sleep/GoToSleep…) — olhos animados."""
    global _charger_stream_sessao, _charger_keeper_ativo, _sono_oled_texto_ativo
    definir_modo_sono_oled(True)
    if not sono_oled_usa_texto():
        _sono_oled_texto_ativo = False
    if sono_oled_usa_texto():
        ativar_sono_oled_texto(cli)
        return True
    liberar_base_oled_loop_hold(motivo="sono_ppclip")
    _parar_awake_oled_base(cli, timeout=2.0)
    _marcar_novo_clip_oled(cli)
    _handshake_oled_base(cli)
    pulso_sync_base(cli)
    if detectar_cozmo01_suspeito(cli):
        _sequencia_recuperar_cozmo01(cli)
        _parar_awake_oled_base(cli, timeout=1.0)
    if os.environ.get("COZMO_SONO_FLASH_ZZZ", "1") == "1":
        try:
            enviar_zZZ_sono(cli)
            time.sleep(1.2)
            enviar_zZZ_sono(cli)
            logger.info("Base sono OLED: flash zZz (entrada)")
        except Exception as exc:
            logger.warning("Sono flash zZz: %s", exc)
    try:
        ac = cli.anim_controller
        ac.enable_animations(True)
        ac.enable_procedural_face(False)
    except Exception:
        pass
    parar_flood_anim(cli)
    clip_sono_base_oled(cli)
    with _charger_oled_lock:
        nome = _charger_oled_nome
    if nome and base_oled_usa_charger(cli):
        disp = set(cli.animation_groups.keys())
        entrada = "GoToSleepGetIn"
        if entrada in disp and nome != entrada:
            _exibir_clip_base(cli, entrada, forcar=True)
            time.sleep(min(2.5, _duracao_grupo_s(cli, entrada)))
        clip_sono_base_oled(cli)
        with _charger_oled_lock:
            nome = _charger_oled_nome or nome
        _exibir_clip_base(cli, nome, forcar=True)
        if _base_oled_anim_loop_ativo() and not _clip_loop_vivo():
            _garantir_base_oled_anim_loop(cli)
        logger.info("Base sono OLED: clip %s (ppclip loop)", nome)
        return True
    try:
        import random

        from cozmo_companion.core.anims import pool_sono_oled_base

        disp = set(cli.animation_groups.keys())
        pool = list(pool_sono_oled_base(disp, cli))
        prefer = ("GoToSleepSleeping", "Sleeping", "GoToSleepGetIn", "StartSleeping")
        nome = next((p for p in prefer if p in pool), None)
        if not nome and pool:
            nome = random.choice(pool)
        if nome:
            cli.cancel_anim()
            cli.play_anim_group(nome)
            parar_rodas_apos_anim_base(cli)
            logger.info("Base sono: anim corpo %s (sem charger stream)", nome)
    except Exception as exc:
        logger.warning("Sono anim corpo: %s", exc)
    return False


def manter_sono_ppclip(cli: "pycozmo.Client") -> None:
    """Garante ppclip sleep ativo — sem flood, enable_animations ligado."""
    if not modo_sono_oled_ativo() or _sono_oled_texto_ativo:
        return
    if keeper_base_ativo() or _charger_worker_vivo():
        _parar_awake_oled_base(cli, timeout=1.0)
        with _charger_oled_lock:
            atual = _charger_oled_nome
        if not _clip_e_sono_oled(cli, atual):
            clip_sono_base_oled(cli)
    try:
        ac = cli.anim_controller
        if not ac.animations_enabled:
            ac.enable_animations(True)
        ac.enable_procedural_face(False)
    except Exception:
        pass
    if not _oled_tx_permitido(cli):
        try:
            ping_oob(cli, vezes=1)
        except Exception:
            pass
        return
    if not (base_oled_usa_charger(cli) and _base_oled_anim_loop_ativo()):
        return
    with _charger_oled_lock:
        tem = _charger_oled_nome
    if not tem or not _clip_e_sono_oled(cli, tem):
        clip_sono_base_oled(cli)
    global _manter_sono_ppclip_ultimo, _manter_sono_semear_ultimo
    agora = time.monotonic()
    with _charger_oled_lock:
        clip = _charger_oled_nome
    if clip and _clip_e_sono_oled(cli, clip) and agora - _manter_sono_semear_ultimo >= float(
        os.environ.get("SONO_PPCLIP_SEMEAR_S", os.environ.get("SONO_OLED_REFRESH_S", "18"))
    ):
        if not (_clip_loop_vivo() and _charger_anim_em_play(cli)):
            _manter_sono_semear_ultimo = agora
            _semear_oled_charger(cli, clip)
    if _clip_loop_vivo():
        return
    min_loop = float(os.environ.get("SONO_PPCLIP_LOOP_MIN_S", "45"))
    if agora - _manter_sono_ppclip_ultimo < min_loop:
        return
    _manter_sono_ppclip_ultimo = agora
    _garantir_base_oled_anim_loop(cli)


def ativar_sono_oled_texto(cli: "pycozmo.Client") -> None:
    """Legado: pausa ppclip e mantém zZz estático (COZMO_SONO_OLED_TEXTO=1)."""
    global _sono_oled_texto_ativo, _sono_zzz_ultimo_envio
    global _charger_stream_sessao, _charger_keeper_ativo
    _sono_oled_texto_ativo = True
    definir_modo_sono_oled(True)
    _parar_display_keeper()
    _parar_oled_keepalive_base()
    _parar_charger_worker(timeout=1.5)
    _parar_loop_clip_base(timeout=2.0)
    _charger_stream_sessao = False
    _charger_keeper_ativo = False
    pausar_base_oled_para_texto(3600.0, cli)
    try:
        import random

        from cozmo_companion.core.anims import pool_sono_oled_base

        disp = set(cli.animation_groups.keys())
        pool = list(pool_sono_oled_base(disp, cli))
        prefer = ("GoToSleepSleeping", "Sleeping", "GoToSleepGetIn", "StartSleeping")
        nome = next((p for p in prefer if p in pool), None)
        if not nome and pool:
            nome = random.choice(pool)
        if nome:
            cli.cancel_anim()
            cli.play_anim_group(nome)
            parar_rodas_apos_anim_base(cli)
            logger.info("Base sono: anim corpo %s (sem ppclip loop)", nome)
    except Exception as exc:
        logger.warning("Sono anim corpo: %s", exc)
    try:
        enviar_zZZ_sono(cli)
        _sono_zzz_ultimo_envio = time.monotonic()
    except Exception as exc:
        logger.warning("Sono zZz OLED: %s", exc)
    logger.info("Base sono OLED: texto zZz (ppclip pausado)")


def enviar_zZZ_sono(cli: "pycozmo.Client") -> None:
    """zZz na OLED — via enviar_oled (AnimationController), não conn.send solto."""
    from cozmo_companion.display.face import texto_para_pkt

    pkt = texto_para_pkt("zZz")
    try:
        ac = cli.anim_controller
        ac.enable_procedural_face(False)
        ac.enable_animations(True)
        _handshake_frame_oled(cli, force=True)
        enviar_oled(cli, pkt)
        ac.last_image_pkt = pkt
    except Exception as exc:
        logger.warning("zZz OLED: %s", exc)


def desativar_sono_oled_texto() -> None:
    global _sono_oled_texto_ativo
    if not _sono_oled_texto_ativo:
        return
    _sono_oled_texto_ativo = False
    liberar_base_oled_loop_hold(motivo="acordou")


def manter_sono_oled_texto(cli: "pycozmo.Client") -> None:
    """Impede ppclip/worker de sobrescrever zZz enquanto dorme."""
    if not _sono_oled_texto_ativo:
        return
    global _charger_stream_sessao, _charger_keeper_ativo
    segurar_base_oled_loop(30.0)
    _parar_display_keeper()
    _parar_oled_keepalive_base()
    if _charger_worker_vivo():
        _parar_charger_worker(timeout=0.8)
    if _clip_loop_vivo():
        _parar_loop_clip_base(timeout=0.8)
    if _clip_loop_vivo() or _charger_worker_vivo() or keeper_base_ativo():
        _charger_stream_sessao = False
        _charger_keeper_ativo = False
    # Reforço periódico — worker IdleOnCharger rouba a OLED se religar.
    global _sono_zzz_ultimo_envio
    agora = time.monotonic()
    refresh = float(os.environ.get("SONO_OLED_REFRESH_S", "0.8"))
    if agora - _sono_zzz_ultimo_envio >= refresh:
        _sono_zzz_ultimo_envio = agora
        try:
            enviar_zZZ_sono(cli)
        except Exception:
            pass


def _hold_max_s() -> float:
    return max(1.0, float(os.environ.get("COZMO_BASE_OLED_HOLD_MAX_S", "12")))


def _hold_stack_max_s() -> float:
    """Teto acumulado durante notif/TTS — evita loop religar no meio do áudio."""
    mult = float(os.environ.get("COZMO_BASE_OLED_HOLD_STACK", "2.5"))
    return _hold_max_s() * max(1.0, mult)


def segurar_base_oled_loop(segundos: float) -> None:
    """Bloqueia reinício do ppclip na base (notif/TTS na OLED)."""
    global _base_oled_loop_hold_ate, _base_oled_loop_hold_desde
    agora = time.monotonic()
    max_s = _hold_max_s()
    stack_max = _hold_stack_max_s()
    seg = max(0.0, segundos)
    if agora >= _base_oled_loop_hold_ate:
        _base_oled_loop_hold_desde = agora
        _base_oled_loop_hold_ate = agora + min(seg, max_s)
        return
    fim_stack = _base_oled_loop_hold_desde + stack_max
    candidato = max(_base_oled_loop_hold_ate, agora + seg)
    _base_oled_loop_hold_ate = min(candidato, fim_stack)


def pode_tocar_anim_direto(
    cli: "pycozmo.Client",
    *,
    fila_ocupada: bool = False,
    falando: bool = False,
    face_buscando: bool = False,
) -> bool:
    """Vida/face/LLM: só anima se fila, TTS e loop OLED estiverem livres."""
    if fila_ocupada or falando or face_buscando:
        return False
    if base_oled_loop_segurado():
        return False
    try:
        ac = cli.anim_controller
        if ac.playing_audio:
            return False
    except Exception:
        return False
    return True


def tocar_clip_base_seguro(
    cli: "pycozmo.Client",
    grupo: str,
    *,
    hold_s: float | None = None,
) -> bool:
    """Na base: ppclip oficial sem cancel_anim — não interrompe o loop OLED."""
    if not grupo:
        return False
    from cozmo_companion.core.anims import permitido_sem_rodas_na_base

    if not permitido_sem_rodas_na_base(grupo):
        return False
    if not base_oled_usa_charger(cli):
        return False
    h = (
        hold_s
        if hold_s is not None
        else float(os.environ.get("COZMO_ANIM_BASE_HOLD_S", "2.5")) + 1.5
    )
    segurar_base_oled_loop(h)
    if _exibir_clip_base(cli, grupo, forcar=True):
        return True
    try:
        from cozmo_companion.core.anim_base_patch import play_grupo_sem_rodas_na_base
        from cozmo_companion.core.charger import na_base_oled

        if na_base_oled(cli):
            return play_grupo_sem_rodas_na_base(cli, grupo)
    except Exception as exc:
        logger.debug("tocar_clip_base_seguro %s: %s", grupo, exc)
    return False


def base_oled_loop_segurado() -> bool:
    if _sono_oled_texto_ativo:
        return True
    return time.monotonic() < _base_oled_loop_hold_ate


def liberar_base_oled_loop_hold(*, motivo: str = "") -> bool:
    """Libera hold preso — permite religar ppclip."""
    global _base_oled_loop_hold_ate, _base_oled_loop_hold_desde
    if not base_oled_loop_segurado():
        _base_oled_loop_hold_ate = 0.0
        _base_oled_loop_hold_desde = 0.0
        return False
    if motivo:
        logger.warning("Base OLED: hold liberado (%s)", motivo)
    _base_oled_loop_hold_ate = 0.0
    _base_oled_loop_hold_desde = 0.0
    return True


def expirar_hold_oled_base(cli: "pycozmo.Client | None" = None) -> bool:
    """Watchdog: hold > max ou expirado — libera e restaura ppclip se RX ok."""
    if _sono_oled_texto_ativo:
        return False
    if cli is not None:
        ac = cli.anim_controller
        if ac.playing_audio or ac.playing_animation or not ac.queue.is_empty():
            return False
    global _base_oled_loop_hold_ate, _base_oled_loop_hold_desde
    agora = time.monotonic()
    if _base_oled_loop_hold_desde <= 0 and not base_oled_loop_segurado():
        return False
    max_s = _hold_max_s()
    stack_max = _hold_stack_max_s()
    expirado = agora >= _base_oled_loop_hold_ate
    estourou = (
        _base_oled_loop_hold_desde > 0
        and agora >= _base_oled_loop_hold_desde + stack_max
    )
    if not expirado and not estourou:
        return False
    motivo = f">{stack_max:.0f}s" if estourou else "timeout"
    if base_oled_loop_segurado():
        liberar_base_oled_loop_hold(motivo=motivo)
    else:
        _base_oled_loop_hold_ate = 0.0
        _base_oled_loop_hold_desde = 0.0
    if cli is not None and _oled_sessao_viva(cli) and _base_oled_anim_loop_ativo():
        if modo_sono_oled_ativo() and not sono_oled_usa_texto():
            manter_sono_ppclip(cli)
        else:
            _garantir_base_oled_anim_loop(cli)
    return True


def _oled_max_estatico_s() -> float:
    """Tempo máximo com o mesmo frame OLED — evita burn-in."""
    return max(8.0, float(os.environ.get("COZMO_OLED_MAX_ESTATICO_S", "18")))


def _oled_estatico_demais(
    cli: "pycozmo.Client | None" = None,
    *,
    margem_s: float = 0.0,
) -> bool:
    if base_oled_loop_segurado():
        return False
    if cli is not None:
        ac = cli.anim_controller
        if ac.playing_audio:
            return False
        if _oled_anim_vivo(cli):
            global _ultimo_exibir_clip_em
            _ultimo_exibir_clip_em = time.monotonic()
            return False
    if _ultimo_exibir_clip_em <= 0:
        return False
    return time.monotonic() - _ultimo_exibir_clip_em >= _oled_max_estatico_s() + margem_s


def _oled_anim_vivo(cli: "pycozmo.Client") -> bool:
    """Clip ppclip em execução — olhos se movem mesmo sem trocar grupo."""
    if not rx_link_ok():
        return False
    ac = cli.anim_controller
    if ac.playing_animation or ac.playing_audio:
        return True
    if not ac.queue.is_empty():
        return True
    if _clip_loop_vivo() and (_charger_anim_em_play(cli) or ac.animations_enabled):
        return True
    return False


def reset_oled_watchdog_base() -> None:
    """Pós-reconnect — evita falso 'olhos estáticos' após reset UDP."""
    global _ultimo_exibir_clip_em, _ultimo_watchdog_oled
    _ultimo_exibir_clip_em = time.monotonic()
    _ultimo_watchdog_oled = 0.0


def _forcar_movimento_oled_base(cli: "pycozmo.Client") -> bool:
    """Olhos parados demais na base — troca clip ou religa loop ppclip."""
    global _charger_oled_nome
    if base_oled_loop_segurado():
        return False
    ac = cli.anim_controller
    if ac.playing_audio or ac.playing_animation or not ac.queue.is_empty():
        reset_oled_watchdog_base()
        return False
    if _oled_anim_vivo(cli):
        reset_oled_watchdog_base()
        return False
    if not base_oled_usa_charger(cli) or not _oled_tx_permitido(cli):
        return False
    logger.warning(
        "Base OLED: olhos estáticos >%.0fs — variar clip",
        _oled_max_estatico_s(),
    )
    liberar_base_oled_loop_hold(motivo="oled_estatico")
    try:
        cli.cancel_anim()
    except Exception:
        pass
    if modo_sono_oled_ativo() and not _sono_oled_texto_ativo:
        if ativar_sono_ppclip(cli):
            return True
        manter_sono_ppclip(cli)
        return _clip_loop_vivo()
    nome = _escolher_proximo_clip_base(cli)
    with _charger_oled_lock:
        _charger_oled_nome = nome
    if _base_oled_anim_loop_ativo():
        return _garantir_base_oled_anim_loop(cli) or _exibir_clip_base(cli, nome, forcar=True)
    return (
        variar_clip_base_oled(cli, forcado=True)
        or _exibir_clip_base(cli, nome, forcar=True)
    )


def vigiar_tela_congelada_base(cli: "pycozmo.Client") -> bool:
    """Na base: hold infinito ou ppclip parado com sessão viva — restaura anim."""
    if _sono_oled_texto_ativo:
        return False
    if modo_sono_oled_ativo() and not sono_oled_usa_texto():
        manter_sono_ppclip(cli)
        if not _clip_loop_vivo():
            ativar_sono_ppclip(cli)
        return _clip_loop_vivo()
    global _ultimo_watchdog_oled
    agora = time.monotonic()
    intervalo = float(os.environ.get("COZMO_OLED_WATCHDOG_S", "4"))
    if agora - _ultimo_watchdog_oled < intervalo:
        return False
    _ultimo_watchdog_oled = agora
    if expirar_hold_oled_base(cli):
        return True
    if not base_oled_usa_charger(cli) or not _oled_sessao_viva(cli):
        return False
    if _oled_estatico_demais(cli) and _oled_tx_permitido(cli):
        return _forcar_movimento_oled_base(cli)
    if _base_oled_anim_loop_ativo() and not base_oled_loop_segurado():
        ac = cli.anim_controller
        if not _clip_loop_vivo():
            logger.warning("Base OLED: loop ppclip parado — religando")
            return _garantir_base_oled_anim_loop(cli)
        if not ac.animations_enabled:
            logger.warning("Base OLED: enable_animations OFF — restaurando")
            ac.enable_animations(True)
            return _garantir_base_oled_anim_loop(cli)
        if _charger_anim_em_play(cli) or ac.playing_audio is True:
            return False
    if detectar_cozmo01_suspeito(cli):
        if _clip_loop_vivo() or _garantir_base_oled_anim_loop(cli):
            return True
        logger.warning("COZMO 01 suspeito — timeout sem frame OLED")
        return _sequencia_recuperar_cozmo01(cli)
    if not _base_oled_anim_loop_ativo() or base_oled_loop_segurado():
        return False
    stale_s = _oled_max_estatico_s()
    loop_morto = not _clip_loop_vivo()
    clip_parado = (
        _ultimo_exibir_clip_em > 0
        and agora - _ultimo_exibir_clip_em >= stale_s
        and not _charger_anim_em_play(cli)
    )
    if loop_morto or clip_parado:
        from cozmo_companion.core.conexao import cozmo_alcanavel

        logger.warning(
            "Base OLED congelado (loop=%s stale=%.0fs) — religando ppclip",
            "off" if loop_morto else "stale",
            agora - _ultimo_exibir_clip_em if _ultimo_exibir_clip_em else 0.0,
        )
        if not rx_link_ok():
            return _sequencia_recuperar_cozmo01(cli)
        if cozmo_alcanavel() and _garantir_base_oled_anim_loop(cli):
            return True
        return _sequencia_recuperar_cozmo01(cli)
    return False


def pausar_base_oled_para_texto(
    segundos: float,
    cli: "pycozmo.Client | None" = None,
) -> None:
    """Para ppclip na base e impede reinício enquanto notif/TTS usa OLED."""
    segurar_base_oled_loop(segundos)
    _parar_loop_clip_base(timeout=2.5)
    if cli is not None:
        try:
            cli.cancel_anim()
        except Exception:
            pass


def definir_rx_link_ok(ok: bool) -> None:
    """Atualizado a cada tick do companion — worker charger obedece."""
    global _base_rx_link_ok, _rx_off_desde
    if ok:
        _rx_off_desde = 0.0
    elif _rx_off_desde <= 0:
        _rx_off_desde = time.monotonic()
    _base_rx_link_ok = ok


def rx_link_ok() -> bool:
    return _base_rx_link_ok


def _oled_tx_permitido(cli: "pycozmo.Client") -> bool:
    """TX ppclip na base — só com RX vivo (ppclip saudável tolera drx=0 via MonitorRx)."""
    return rx_link_ok()


def _oled_sessao_viva(cli: "pycozmo.Client") -> bool:
    """Base: sessão viva para ppclip — sono permite ping sem drx."""
    return _oled_tx_permitido(cli)


def religar_base_oled_pos_notif(cli: "pycozmo.Client") -> None:
    """Após notif/TTS: religa ppclip — seq COZMO 01 só se tela travada."""
    if _sono_oled_texto_ativo:
        manter_sono_oled_texto(cli)
        return
    if modo_sono_oled_ativo() and not sono_oled_usa_texto():
        ativar_sono_ppclip(cli)
        return
    if base_oled_loop_segurado():
        return
    from cozmo_companion.core.conexao import cozmo_alcanavel

    if not cozmo_alcanavel() and not rx_link_ok():
        segurar_base_oled_loop(4.0)
        try:
            ping_oob(cli, vezes=2)
        except Exception:
            pass
        return
    if not base_oled_usa_charger(cli):
        ligar_oled_base(cli, forcar=True)
        return
    if _clip_loop_vivo():
        return
    if _base_oled_anim_loop_ativo() and _garantir_base_oled_anim_loop(cli):
        return
    if detectar_cozmo01_suspeito(cli):
        _sequencia_recuperar_cozmo01(cli)
    elif cozmo_alcanavel():
        _garantir_base_oled_anim_loop(cli)


def _base_clip_sem_rodas_ativo(cli: "pycozmo.Client") -> bool:
    """Na base com patch de anim — não usar stop_all_motors (porco: só editar clip)."""
    if os.environ.get("COZMO_BASE_STOP_RODAS_CMD", "0") == "1":
        return False
    if not getattr(cli, "_cozmo_sem_rodas_patch", False):
        return False
    from cozmo_companion.core.charger import na_base_oled

    return na_base_oled(cli)


def parar_rodas_apos_anim_base(cli: "pycozmo.Client") -> None:
    """Fora da base ou COZMO_BASE_STOP_RODAS_CMD=1. Na base: rodas só no clip editado."""
    if _base_clip_sem_rodas_ativo(cli):
        return
    try:
        cli.stop_all_motors()
    except Exception:
        pass


def vigiar_rodas_na_base(cli: "pycozmo.Client", *, preso: bool) -> None:
    """Desativado na base — movimento de roda é editado no clip, não por comando."""
    del cli, preso


def cortar_flood_udp_base(cli: "pycozmo.Client") -> None:
    """RX parado: corta replay/worker — mantém ppclip em modo ping se ativo."""
    global _charger_replay_pendente
    _charger_replay_pendente = False
    ping_sessao_base(cli)
    if modo_sono_oled_ativo() and not _sono_oled_texto_ativo:
        if rx_link_ok() and _base_oled_anim_loop_ativo() and not _clip_loop_vivo():
            _garantir_base_oled_anim_loop(cli)
        return
    if not rx_link_ok():
        _parar_charger_worker(timeout=1.0)
        if _base_oled_anim_loop_ativo() and _clip_loop_vivo():
            pulso_sync_base(cli, forcado=True)
            return
        _parar_base_oled_anim_loop(timeout=1.0)
        pulso_sync_base(cli, forcado=True)
        return
    if _oled_sessao_viva(cli):
        if _base_oled_anim_loop_ativo() and not _clip_loop_vivo():
            _garantir_base_oled_anim_loop(cli)
        return
    _parar_base_oled_anim_loop(timeout=1.0)
    _parar_charger_worker(timeout=1.0)
    pulso_sync_base(cli, forcado=True)


def _reset_anim_id(cli: "pycozmo.Client") -> None:
    cli._next_anim_id = 1


def _normalizar_anim_id(cli: "pycozmo.Client") -> int:
    """PyCozmo aceita anim_id 1–255; sem wrap vira 256 e todos os clips falham."""
    aid = int(getattr(cli, "_next_anim_id", 1))
    if aid < 1 or aid > 255:
        aid = 1
        cli._next_anim_id = 1  # type: ignore[attr-defined]
    return aid


def _capturar_ppclip_core(cli: "pycozmo.Client") -> None:
    """Referência estável ao play_anim_ppclip original do PyCozmo (sem patches)."""
    if getattr(cli, "_cozmo_ppclip_core", None) is not None:
        return
    from pycozmo.client import Client

    cli._cozmo_ppclip_core = Client.play_anim_ppclip.__get__(cli, Client)  # type: ignore[attr-defined]


def _pos_ppclip_incrementar(cli: "pycozmo.Client") -> None:
    nxt = int(getattr(cli, "_next_anim_id", 1))
    if nxt > 255 or nxt < 1:
        cli._next_anim_id = 1  # type: ignore[attr-defined]


def _executar_ppclip_core(cli: "pycozmo.Client", pp: object) -> None:
    """PyCozmo oficial + wrap anim_id — único caminho que envia StartAnimation."""
    _capturar_ppclip_core(cli)
    _normalizar_anim_id(cli)
    cli._cozmo_ppclip_core(pp)  # type: ignore[attr-defined]
    _pos_ppclip_incrementar(cli)


def instalar_anim_id_seguro(cli: "pycozmo.Client") -> None:
    """Envolve o play_anim_ppclip atual (patch sem-rodas) — sempre por fora."""
    _capturar_ppclip_core(cli)
    inner = cli.play_anim_ppclip
    if getattr(cli, "_cozmo_anim_id_wrapper", None) is inner:
        return

    def play_ppclip_seguro(pp: object) -> None:
        _normalizar_anim_id(cli)
        inner(pp)
        _pos_ppclip_incrementar(cli)

    cli.play_anim_ppclip = play_ppclip_seguro  # type: ignore[method-assign]
    cli._cozmo_anim_id_seguro = True  # type: ignore[attr-defined]
    cli._cozmo_anim_id_wrapper = play_ppclip_seguro  # type: ignore[attr-defined]


_espiar_escuro_ate = 0.0
_ultimo_espiar_escuro = 0.0


def _pool_oled_base_seguro(cli: "pycozmo.Client") -> tuple[str, ...]:
    """Base: luz acesa → anim normais (sem roda/toque); escuro → sono."""
    from cozmo_companion.core.ambiente_escuro import detector_escuro
    from cozmo_companion.core.anims import pool_sono_oled_base, pool_variacao_oled_base

    disp = set(cli.animation_groups.keys())
    if detector_escuro().escuro:
        return pool_sono_oled_base(disp, cli)
    pool = pool_variacao_oled_base(disp, cli)
    return pool if pool else ("IdleOnCharger", "NeutralFace")


def _candidatos_charger_oled(
    cli: "pycozmo.Client",
    *,
    carga_pausada: bool,
    carregando_agora: bool,
) -> tuple[str, ...]:
    """Base: dock sempre → idle; luz apagada → sono; senão rotação leve."""
    awake = os.environ.get("COZMO_CHARGER_AWAKE_IDLE", "IdleOnCharger")
    if awake in ("0", "off", "none"):
        awake = ""
    from cozmo_companion.core.ambiente_escuro import detector_escuro
    from cozmo_companion.core.charger import bateria_pct, em_modo_carga_base, na_base_oled

    rotacao = _pool_oled_base_seguro(cli)
    stop = int(os.environ.get("BATTERY_CHARGE_STOP_PCT", "90"))
    cheia = na_base_oled(cli) and bateria_pct(cli) >= stop
    rotacao = _pool_oled_base_seguro(cli)
    if carga_pausada or cheia:
        from cozmo_companion.core.anims import GRUPOS_BASE_OLED_SEGUROS

        if "IdleOnCharger" in cli.animation_groups:
            return ("IdleOnCharger",) + tuple(n for n in rotacao if n != "IdleOnCharger")
        if awake and awake in rotacao and awake in GRUPOS_BASE_OLED_SEGUROS:
            return (awake,) + tuple(n for n in rotacao if n != awake)
        if rotacao:
            return rotacao
        return ("IdleOnCharger", "NeutralFace")
    if em_modo_carga_base(cli):
        pref = (awake,) if awake and awake in cli.animation_groups else ()
        base = ("IdleOnCharger", "IdleOnChargerCharging")
        return pref + rotacao + tuple(b for b in base if b not in rotacao)
    if detector_escuro().escuro:
        return _pool_oled_base_seguro(cli)
    if carregando_agora:
        return ("IdleOnChargerCharging", "IdleOnCharger")
    if awake:
        pref = (awake,) if awake in set(cli.animation_groups.keys()) else ()
        return pref + rotacao + ("IdleOnChargerCharging", "IdleOnCharger")
    return ("IdleOnCharger", "IdleOnChargerCharging") + rotacao


def _escolher_clip_variar(
    pool: list[str],
    *,
    atual: str | None,
    recentes: list[str],
) -> str | None:
    """Sorteia clip diferente do atual e dos últimos N (peso menor em IdleOnCharger)."""
    if not pool:
        return None
    anti = max(1, int(os.environ.get("COZMO_BASE_VARIAR_ANTI_REPEAT", "3")))
    recentes_set = set(recentes[-anti:])
    candidatos = [n for n in pool if n != atual and n not in recentes_set]
    if not candidatos:
        candidatos = [n for n in pool if n != atual]
    if not candidatos:
        candidatos = list(pool)
    peso_idle = float(os.environ.get("COZMO_BASE_IDLE_PESO", "0.35"))
    pesos = [peso_idle if n == "IdleOnCharger" else 1.0 for n in candidatos]
    return random.choices(candidatos, weights=pesos, k=1)[0]


_CLIP_SONO_LOOP_PREF = (
    "GoToSleepSleeping",
    "Sleeping",
    "GuardDogSleepLoop",
    "GoToSleepGetIn",
)


def clip_sono_base_oled(cli: "pycozmo.Client") -> bool:
    """Sono na base: clip de dormir no ppclip — OLED continua vivo."""
    global _sono_getin_feito
    if _sono_oled_texto_ativo or sono_oled_usa_texto():
        return False
    import random

    from cozmo_companion.core.anims import pool_sono_oled_base

    definir_modo_sono_oled(True)
    disp = set(cli.animation_groups.keys())
    pool = tuple(pool_sono_oled_base(disp, cli))
    if not pool:
        return False
    min_n = max(2, int(os.environ.get("COZMO_BASE_OLED_MIN_FRAMES", "8")))
    pool_ok = tuple(p for p in pool if len(_frames_clip_oled(cli, p)) >= min_n)
    candidatos = pool_ok or pool
    if not _sono_getin_feito and "GoToSleepGetIn" in candidatos:
        nome = "GoToSleepGetIn"
        _sono_getin_feito = True
    else:
        nome = next((p for p in _CLIP_SONO_LOOP_PREF if p in candidatos), None)
        if not nome:
            nome = random.choice(candidatos)
    with _charger_oled_lock:
        global _charger_oled_nome
        if _charger_oled_nome == nome:
            return True
        _charger_oled_nome = nome
    ac = cli.anim_controller
    ac.enable_animations(True)
    logger.info("Base sono OLED: clip %s", nome)
    return True


def entrar_sono_base_oled(cli: "pycozmo.Client") -> bool:
    """Ativa modo sono: ppclip sleep (olhos) ou legado zZz se COZMO_SONO_OLED_TEXTO=1."""
    if sono_oled_usa_texto():
        ativar_sono_oled_texto(cli)
        return True
    return ativar_sono_ppclip(cli)


def variar_clip_base_oled(cli: "pycozmo.Client", *, forcado: bool = False) -> bool:
    """Troca o clip na base — pool amplo, anti-repetição, sem mexer nas rodas."""
    global _charger_oled_nome, _ultimo_variar_clip, _ultimos_clips_base
    if modo_sono_oled_ativo() or _sono_oled_texto_ativo:
        return False
    if base_oled_loop_segurado():
        return False
    if _base_anim_loop_vivo():
        return False
    from cozmo_companion.core.charger import carga_prioritaria

    from cozmo_companion.core.ambiente_escuro import detector_escuro

    from cozmo_companion.core.charger import base_oled_estavel

    escuro = detector_escuro().escuro
    agora = time.monotonic()
    global _espiar_escuro_ate
    anim_loop = _base_oled_anim_loop_ativo()
    if (
        base_oled_estavel(cli)
        and not escuro
        and not forcado
        and not anim_loop
        and not modo_sono_oled_ativo()
    ):
        if os.environ.get("COZMO_BASE_VARIAR_LUZ", "0") != "1":
            idle = os.environ.get("COZMO_CHARGER_AWAKE_IDLE", "IdleOnCharger")
            if idle and idle not in ("0", "off", "none"):
                with _charger_oled_lock:
                    if _charger_oled_nome != idle:
                        _charger_oled_nome = idle
            return False
    if escuro and _espiar_escuro_ate > 0 and agora >= _espiar_escuro_ate:
        _espiar_escuro_ate = 0.0
        from cozmo_companion.core.ambiente_escuro import aplicar_sono_por_escuro

        aplicar_sono_por_escuro(cli)
        return True
    if escuro and _espiar_escuro_ate > agora:
        return False
    if (
        carga_prioritaria()
        and not forcado
        and not escuro
        and not anim_loop
        and not modo_sono_oled_ativo()
    ):
        idle = os.environ.get("COZMO_CHARGER_AWAKE_IDLE", "IdleOnCharger")
        if idle and idle not in ("0", "off", "none"):
            with _charger_oled_lock:
                if _charger_oled_nome != idle:
                    _charger_oled_nome = idle
                    logger.info("Base: carga prioritária — clip %s", idle)
        return False
    if not rx_link_ok() or not base_oled_usa_charger(cli):
        return False
    if not _charger_stream_sessao:
        return False
    from cozmo_companion.core.anims import pool_sono_oled_base, pool_variacao_oled_base

    escuro = detector_escuro().escuro
    intervalo = float(
        os.environ.get("COZMO_ESCURO_VARIAR_S", "75")
        if escuro
        else os.environ.get("COZMO_BASE_VARIAR_S", "38")
    )
    if agora - _ultimo_variar_clip < intervalo:
        return False
    if not forcado and not escuro and random.random() > float(
        os.environ.get("COZMO_BASE_VARIAR_CHANCE", "0.38")
    ):
        return False
    disp = set(cli.animation_groups.keys())
    if escuro or modo_sono_oled_ativo():
        ok_pool = list(pool_sono_oled_base(disp, cli))
    else:
        ok_pool = list(
            _pool_oled_com_frames(cli, pool_variacao_oled_base(disp, cli))
        )
    if not ok_pool:
        return False
    with _charger_oled_lock:
        atual = _charger_oled_nome
    nome = _escolher_clip_variar(ok_pool, atual=atual, recentes=_ultimos_clips_base)
    if not nome or (nome == atual and not forcado):
        return False
    if modo_sono_oled_ativo() or _sono_oled_texto_ativo:
        return False
    _ultimo_variar_clip = agora
    _ultimos_clips_base.append(nome)
    anti = max(2, int(os.environ.get("COZMO_BASE_VARIAR_ANTI_REPEAT", "3")))
    if len(_ultimos_clips_base) > anti + 2:
        del _ultimos_clips_base[: -(anti + 2)]
    with _charger_oled_lock:
        _charger_oled_nome = nome
    logger.info(
        "Base OLED: variar clip → %s (pool=%d)",
        nome,
        len(ok_pool),
    )
    if _charger_play_stream(cli) and not _charger_keeper_ativo:
        with _charger_oled_lock:
            _charger_oled_nome = nome
        return _replay_anim_charger(cli, nome)
    if (
        keeper_base_ativo()
        or _charger_keeper_ativo
        or (
            base_oled_carga_cheia_ativo(cli)
            and os.environ.get("COZMO_BASE_KEEPER_VIVO", "0") == "1"
        )
    ):
        if _base_oled_anim_loop_ativo():
            _garantir_base_oled_anim_loop(cli)
            return True
        return (
            _iniciar_keeper_clip_oled_base(cli, nome)
            or _exibir_clip_base(cli, nome)
            or _semear_oled_charger(cli, nome)
        )
    if _charger_worker_vivo():
        return True
    if _charger_play_stream(cli) and not _charger_keeper_ativo:
        return _replay_anim_charger(cli, nome)
    return True


def tick_espiar_escuro(cli: "pycozmo.Client") -> None:
    """No escuro: de vez em quando rosto normal, depois volta ao sono."""
    global _espiar_escuro_ate, _ultimo_espiar_escuro, _charger_oled_nome
    from cozmo_companion.core.ambiente_escuro import detector_escuro
    from cozmo_companion.core.anims import pool_espiar_escuro_base

    if not detector_escuro().escuro:
        _espiar_escuro_ate = 0.0
        return
    agora = time.monotonic()
    if agora < _espiar_escuro_ate:
        return
    intervalo = float(os.environ.get("COZMO_ESCURO_ESPIAR_INTERVALO_S", "360"))
    if agora - _ultimo_espiar_escuro < intervalo:
        return
    chance = float(os.environ.get("COZMO_ESCURO_ESPIAR_CHANCE", "0.38"))
    if random.random() > chance:
        return
    disp = set(cli.animation_groups.keys())
    pool = list(pool_espiar_escuro_base(disp, cli))
    if not pool:
        return
    dur = float(os.environ.get("COZMO_ESCURO_ESPIAR_S", "14"))
    nome = random.choice(pool)
    _ultimo_espiar_escuro = agora
    _espiar_escuro_ate = agora + dur
    with _charger_oled_lock:
        _charger_oled_nome = nome
    logger.info("Escuro: espiar %s (%.0fs) → volta ao sono", nome, dur)
    variar_clip_base_oled(cli, forcado=True)


def base_oled_carga_cheia_ativo(cli: "pycozmo.Client") -> bool:
    """100%% na base: IdleOnCharger contínuo (firmware pausado ou bateria cheia)."""
    if os.environ.get("COZMO_BASE_OLED_CHARGER_FULL", "0") != "1":
        return False
    if not base_oled_modo_proc():
        return False
    from cozmo_companion.core.charger import bateria_pct, carga_firmware_pausada, na_base_oled

    if not na_base_oled(cli):
        return False
    stop = int(os.environ.get("BATTERY_CHARGE_STOP_PCT", "90"))
    return carga_firmware_pausada(cli) or bateria_pct(cli) >= stop


def base_oled_usa_charger(cli: "pycozmo.Client") -> bool:
    """HW5 na base: IdleOnCharger contínuo — única tela que substitui COZMO 01."""
    if base_oled_carga_cheia_ativo(cli):
        return True
    if os.environ.get("COZMO_BASE_OLED_CHARGER", "1") != "1":
        return False
    if not base_oled_modo_proc():
        return False
    from cozmo_companion.core.charger import na_base_oled

    return na_base_oled(cli)


def instalar_guard_cancel_anim_base(cli: "pycozmo.Client") -> None:
    """Na base com stream IdleOnCharger: cancel externo não mata o clip."""
    if getattr(cli, "_cozmo_cancel_guard", False):
        return
    orig = cli.cancel_anim

    def cancel_seguro() -> None:
        cur = threading.current_thread()
        # Worker precisa cancelar no início de play_anim_ppclip (PyCozmo oficial).
        if cur is _charger_worker_thread:
            orig()
            return
        if cur is _clip_loop_thread:
            orig()
            return
        if base_oled_usa_proc_vivo(cli):
            ac = cli.anim_controller
            if ac.animations_enabled and ac.procedural_face_enabled:
                return
        if getattr(cli, "_cozmo_cancel_clip_ok", False):
            orig()
            return
        if base_oled_usa_charger(cli) and (
            (
                _charger_play_stream(cli)
                and not _charger_keeper_ativo
                and not keeper_base_ativo()
                and (_charger_worker_vivo() or _charger_anim_em_play(cli))
            )
            or (
                _base_oled_anim_loop_ativo()
                and (_clip_loop_vivo() or cur is _clip_loop_thread)
            )
        ):
            return
        orig()

    cli.cancel_anim = cancel_seguro  # type: ignore[method-assign]
    cli._cozmo_cancel_guard = True  # type: ignore[attr-defined]


def instalar_guard_anim_base(cli: "pycozmo.Client") -> None:
    """Base: não zera OLED no AnimationEnded (PyCozmo → COZMO 01)."""
    ac = cli.anim_controller
    if getattr(ac, "_cozmo_anim_base_guard", False):
        return
    orig_clear = ac._clear_last_image_pkt
    orig_ended = ac._on_animation_ended

    def _clear_safe() -> None:
        if base_oled_usa_charger(cli):
            return
        orig_clear()

    def _on_animation_ended_safe(conn: object, pkt: object) -> None:
        from cozmo_companion.core.pycozmo_cli import resolver_cliente

        c = resolver_cliente(conn)
        ac2 = c.anim_controller
        ac2.playing_animation = False
        if base_oled_usa_charger(c):
            return
        orig_ended(conn, pkt)

    ac._clear_last_image_pkt = _clear_safe  # type: ignore[method-assign]
    ac._on_animation_ended = _on_animation_ended_safe  # type: ignore[method-assign]
    ac._cozmo_anim_base_guard = True  # type: ignore[attr-defined]


def instalar_charger_display_guard(cli: "pycozmo.Client") -> None:
    """Compat — guard completo na base."""
    instalar_guard_anim_base(cli)


def _charger_clip_min_s() -> float:
    try:
        return max(8.0, float(os.environ.get("COZMO_CHARGER_CLIP_S", "14")))
    except ValueError:
        return 14.0


def _base_clip_max_s() -> float:
    try:
        return max(4.0, float(os.environ.get("COZMO_BASE_CLIP_MAX_S", "12")))
    except ValueError:
        return 6.0


def _duracao_clip_base_s() -> float:
    return min(_charger_clip_min_s(), _base_clip_max_s())


def _base_oled_anim_loop_ativo() -> bool:
    modo = os.environ.get("COZMO_BASE_OLED_ANIM_LOOP", "auto").strip().lower()
    if modo in ("0", "off", "false", "no"):
        return False
    if modo in ("1", "on", "true", "yes"):
        return True
    if os.environ.get("COZMO_CHARGER_PLAY_STREAM", "1") == "0":
        if os.environ.get("COZMO_BASE_OLED_KEEPALIVE", "1") == "0":
            return True
        return os.environ.get("COZMO_BASE_OLED_MODE", "proc") == "proc"
    return False


def ppclip_base_ativo(cli: "pycozmo.Client") -> bool:
    """Base 100%%: loop ppclip — TX alto sem drx na janela é normal (≠ COZMO 01)."""
    return _base_oled_anim_loop_ativo() and base_oled_usa_charger(cli)


def _duracao_grupo_s(cli: "pycozmo.Client", grupo: str) -> float:
    return len(_frames_clip_oled(cli, grupo)) * 0.033 + 0.3


def _escolher_proximo_clip_base(cli: "pycozmo.Client") -> str:
    global _ultimos_clips_base
    from cozmo_companion.core.anims import pool_sono_oled_base, pool_variacao_oled_base

    disp = set(cli.animation_groups.keys())
    if modo_sono_oled_ativo():
        pool = list(pool_sono_oled_base(disp, cli))
        prefer = ("GoToSleepSleeping", "Sleeping", "GuardDogSleepLoop")
        fixo = next((p for p in prefer if p in pool), None)
        if fixo:
            return fixo
    else:
        pool = _pool_oled_com_frames(cli, pool_variacao_oled_base(disp, cli))
    with _charger_oled_lock:
        atual = _charger_oled_nome
    nome = _escolher_clip_variar(list(pool), atual=atual, recentes=_ultimos_clips_base)
    if not nome and pool:
        nome = pool[0]
    if not nome:
        if modo_sono_oled_ativo():
            prefer = ("GoToSleepSleeping", "Sleeping", "GoToSleepGetIn")
            nome = next((p for p in prefer if p in disp), "Sleeping")
        else:
            nome = os.environ.get("COZMO_CHARGER_AWAKE_IDLE", "IdleOnCharger")
    _ultimos_clips_base.append(nome)
    anti = max(2, int(os.environ.get("COZMO_BASE_VARIAR_ANTI_REPEAT", "3")))
    if len(_ultimos_clips_base) > anti + 2:
        del _ultimos_clips_base[: -(anti + 2)]
    return nome


def _clip_loop_vivo() -> bool:
    th = _clip_loop_thread
    return th is not None and th.is_alive()


def _base_anim_loop_vivo() -> bool:
    return _clip_loop_vivo()


def _parar_loop_clip_base(timeout: float = 2.0) -> None:
    global _clip_loop_thread
    _clip_loop_stop.set()
    th = _clip_loop_thread
    _clip_loop_thread = None
    if th and th.is_alive() and threading.current_thread() is not th:
        th.join(timeout=timeout)
    _clip_loop_stop.clear()


def _parar_base_oled_anim_loop(timeout: float = 2.0) -> None:
    _parar_loop_clip_base(timeout)


def _keeper_clip_hz(cli: "pycozmo.Client") -> float:
    if base_oled_carga_cheia_ativo(cli):
        hz = float(os.environ.get("COZMO_BASE_FULL_KEEPER_HZ", "7"))
    else:
        hz = float(os.environ.get("COZMO_CHARGER_OLED_HZ", "2.5"))
    return max(2.0, min(12.0, hz))


def _iniciar_keeper_clip_oled_base(cli: "pycozmo.Client", grupo: str, *, hz: float | None = None) -> bool:
    """Percorre frames do clip na base — sem rodas, sem play_anim 30fps."""
    if modo_sono_oled_ativo() or _sono_oled_texto_ativo:
        if modo_sono_oled_ativo() and not _sono_oled_texto_ativo:
            manter_sono_ppclip(cli)
        return True
    if _base_oled_anim_loop_ativo():
        return _garantir_base_oled_anim_loop(cli)
    if not grupo:
        return False
    rate = hz if hz is not None else _keeper_clip_hz(cli)
    frames = _frames_clip_oled(cli, grupo)
    if len(frames) < 2:
        return _exibir_clip_base(cli, grupo, forcar=True) or _semear_oled_charger(cli, grupo)
    _parar_oled_keepalive_base()
    _iniciar_display_keeper(cli, rate, grupo=grupo)
    return True


def _intervalo_variar_base_s() -> float:
    """Janela troca clip — acordado ~18±4s; sono mais longo."""
    if modo_sono_oled_ativo():
        centro = float(os.environ.get("COZMO_SLEEP_CLIP_HOLD_S", "22"))
        jitter = float(os.environ.get("COZMO_SLEEP_CLIP_JITTER_S", "8"))
        return max(18.0, centro + random.uniform(-jitter, jitter))
    centro = float(os.environ.get("COZMO_BASE_VARIAR_S", "22"))
    jitter = float(os.environ.get("COZMO_BASE_VARIAR_JITTER_S", "6"))
    intervalo = max(12.0, min(28.0, random.uniform(centro - jitter, centro + jitter)))
    return min(intervalo, _oled_max_estatico_s())


def _aguardar_fim_clip_loop(
    cli: "pycozmo.Client",
    grupo: str,
    *,
    max_s: float | None = None,
) -> None:
    """Espera duração do clip (ou max_s) + drenagem da fila (máx 20s)."""
    ac = cli.anim_controller
    limite = _duracao_grupo_s(cli, grupo)
    if max_s is not None:
        # Clip curto: espera pelo menos COZMO_BASE_VARIAR_S — evita flood "variar clip".
        limite = max(limite, max(4.0, max_s))
    fim = time.monotonic() + limite
    while time.monotonic() < fim:
        if _clip_loop_stop.is_set():
            return
        if _clip_loop_stop.wait(0.2):
            return
    drain_fim = time.monotonic() + min(8.0, float(os.environ.get("COZMO_BASE_CLIP_DRAIN_S", "4")))
    while time.monotonic() < drain_fim:
        if _clip_loop_stop.is_set():
            return
        if ac.queue.is_empty():
            return
        if _clip_loop_stop.wait(0.2):
            return


def _loop_clip_base_continuo(cli: "pycozmo.Client") -> None:
    """Base na carga: ppclip oficial em sequência — sem keepalive estático."""
    global _charger_oled_nome
    while not _clip_loop_stop.is_set():
        if _sono_oled_texto_ativo or (modo_sono_oled_ativo() and sono_oled_usa_texto()):
            if _clip_loop_stop.wait(0.5):
                return
            continue
        while base_oled_loop_segurado() and not _clip_loop_stop.is_set():
            if _clip_loop_stop.wait(0.25):
                return
        g = ""
        try:
            if not base_oled_usa_charger(cli) or not _oled_sessao_viva(cli):
                if _clip_loop_stop.wait(1.0):
                    break
                continue
            with _charger_oled_lock:
                g = _charger_oled_nome or ""
            if modo_sono_oled_ativo():
                from cozmo_companion.core.anims import (
                    GRUPOS_BASE_SONO_SEM_RODAS,
                    pool_sono_oled_base,
                )

                sono_ok = set(pool_sono_oled_base(set(cli.animation_groups.keys()), cli))
                if g and g not in sono_ok and g not in GRUPOS_BASE_SONO_SEM_RODAS:
                    g = _escolher_proximo_clip_base(cli)
                    with _charger_oled_lock:
                        _charger_oled_nome = g
            if not g:
                g = _escolher_proximo_clip_base(cli)
                with _charger_oled_lock:
                    _charger_oled_nome = g
            if not g:
                if _clip_loop_stop.wait(1.0):
                    break
                continue
            if base_oled_loop_segurado():
                if _clip_loop_stop.wait(0.25):
                    break
                continue
            if not _oled_tx_permitido(cli):
                try:
                    ping_sessao_base(cli)
                    pulso_sync_base(cli, forcado=True)
                except Exception:
                    pass
                if _clip_loop_stop.wait(1.0):
                    break
                continue
            _parar_display_keeper()
            if modo_sono_oled_ativo():
                clip_sono_base_oled(cli)
                with _charger_oled_lock:
                    g = _charger_oled_nome or g
                if not _clip_e_sono_oled(cli, g):
                    if _clip_loop_stop.wait(0.25):
                        break
                    continue
            agora_clip = time.monotonic()
            hold_sono = float(os.environ.get("COZMO_SLEEP_CLIP_HOLD_S", "22"))
            if (
                modo_sono_oled_ativo()
                and g == _ultimo_exibir_clip_grupo
                and _charger_anim_em_play(cli)
                and agora_clip - _ultimo_exibir_clip_em < hold_sono
            ):
                _aguardar_fim_clip_loop(
                cli,
                g,
                max_s=min(_intervalo_variar_base_s(), _oled_max_estatico_s()),
            )
                continue
            _exibir_clip_base(cli, g, forcar=modo_sono_oled_ativo())
            if not _oled_tx_permitido(cli):
                if _clip_loop_stop.wait(2.0):
                    break
                continue
            _aguardar_fim_clip_loop(
                cli,
                g,
                max_s=min(_intervalo_variar_base_s(), _oled_max_estatico_s()),
            )
            if modo_sono_oled_ativo():
                from cozmo_companion.core.anims import pool_sono_oled_base

                disp_s = set(cli.animation_groups.keys())
                pool_n = len(pool_sono_oled_base(disp_s, cli))
                if g == "GoToSleepGetIn" and "GoToSleepSleeping" in disp_s:
                    g2 = "GoToSleepSleeping"
                else:
                    g2 = next(
                        (p for p in ("GoToSleepSleeping", "Sleeping") if p in disp_s),
                        _escolher_proximo_clip_base(cli),
                    )
                with _charger_oled_lock:
                    _charger_oled_nome = g2
                global _ultimo_variar_clip
                _ultimo_variar_clip = time.monotonic()
                logger.info(
                    "Base sono OLED: loop clip → %s (pool=%d)",
                    g2,
                    pool_n,
                )
            else:
                from cozmo_companion.core.anims import pool_variacao_oled_base

                disp = set(cli.animation_groups.keys())
                pool_n = len(_pool_oled_com_frames(cli, pool_variacao_oled_base(disp, cli)))
                g2 = _escolher_proximo_clip_base(cli)
                with _charger_oled_lock:
                    _charger_oled_nome = g2
                _ultimo_variar_clip = time.monotonic()
                logger.info(
                    "Base OLED: variar clip → %s (pool=%d)",
                    g2,
                    pool_n,
                )
        except Exception as exc:
            logger.warning("loop_clip_base_continuo %s: %s", g or "?", exc)
            if _clip_loop_stop.wait(1.0):
                break


def iniciar_loop_clip_base(cli: "pycozmo.Client") -> bool:
    global _charger_stream_sessao, _charger_keeper_ativo
    if not rx_link_ok():
        return False
    if _sono_oled_texto_ativo:
        return False
    if modo_sono_oled_ativo() and sono_oled_usa_texto():
        return False
    if base_oled_loop_segurado():
        return False
    if not _base_oled_anim_loop_ativo():
        return False
    if modo_sono_oled_ativo():
        clip_sono_base_oled(cli)
    _charger_stream_sessao = True
    _charger_keeper_ativo = True
    with _clip_loop_start_lock:
        if _clip_loop_vivo():
            return True
        _parar_display_keeper()
        _parar_oled_keepalive_base()
        _parar_charger_worker(timeout=0.5)
        _clip_loop_stop.clear()
        global _clip_loop_thread
        _clip_loop_thread = threading.Thread(
            target=_loop_clip_base_continuo,
            args=(cli,),
            daemon=True,
            name="BaseOledClipLoop",
        )
        _clip_loop_thread.start()
        logger.info("Base OLED: loop clips contínuo (ppclip, sem rodas)")
    return True


_garantir_loop_em_voo = False


def _garantir_base_oled_anim_loop(cli: "pycozmo.Client") -> bool:
    global _garantir_loop_em_voo
    if not rx_link_ok():
        return False
    if _garantir_loop_em_voo:
        return _clip_loop_vivo()
    _garantir_loop_em_voo = True
    try:
        return iniciar_loop_clip_base(cli)
    finally:
        _garantir_loop_em_voo = False


def _iniciar_clip_base_continuo(cli: "pycozmo.Client") -> bool:
    return iniciar_loop_clip_base(cli)


def _anim_thread_viva(cli: "pycozmo.Client") -> bool:
    ac = cli.anim_controller
    return bool(ac.thread and ac.thread.is_alive() and ac.animations_enabled)


def _charger_worker_vivo() -> bool:
    th = _charger_worker_thread
    return th is not None and th.is_alive()


def _charger_anim_em_play(cli: "pycozmo.Client") -> bool:
    """Fila/clip ativo — evita cancel_anim em loop."""
    if _base_oled_anim_loop_ativo() and (
        _clip_loop_vivo() or threading.current_thread() is _clip_loop_thread
    ):
        ac = cli.anim_controller
        if ac.playing_animation or ac.playing_audio or not ac.queue.is_empty():
            return True
    if _charger_replay_em_voo or _charger_worker_vivo():
        return True
    ac = cli.anim_controller
    if ac.playing_audio or ac.playing_animation:
        return True
    if not ac.queue.is_empty():
        return True
    if _base_oled_anim_loop_ativo():
        return False
    return time.monotonic() - _ultimo_charger_play < _duracao_clip_base_s()


def _pedir_replay_charger() -> None:
    """Só agenda replay com RX vivo — evita dtx≈600 sem drx (COZMO 01)."""
    global _charger_replay_pendente
    if not rx_link_ok():
        return
    if _base_oled_anim_loop_ativo():
        return
    _charger_replay_pendente = True


def _parar_charger_worker(timeout: float = 2.0) -> None:
    global _charger_worker_thread
    _charger_worker_stop.set()
    th = _charger_worker_thread
    _charger_worker_thread = None
    if th and th.is_alive() and threading.current_thread() is not th:
        th.join(timeout=timeout)
    _charger_worker_stop.clear()


def _loop_charger_anim_worker(cli: "pycozmo.Client") -> None:
    """Loop contínuo IdleOnCharger — igual app Anki (play → espera fim → repete)."""
    global _ultimo_charger_play, _charger_replay_em_voo
    clip_pause = float(os.environ.get("COZMO_CHARGER_LOOP_PAUSE_S", "0.12"))
    clip_max = _duracao_clip_base_s()
    while not _charger_worker_stop.is_set():
        if not rx_link_ok():
            if _charger_worker_stop.wait(2.0):
                break
            continue
        if modo_sono_oled_ativo() or _sono_oled_texto_ativo:
            if _charger_worker_stop.wait(0.5):
                break
            continue
        if not base_oled_usa_charger(cli) or not _charger_stream_sessao or _charger_keeper_ativo:
            if _charger_worker_stop.wait(0.4):
                break
            continue
        with _charger_oled_lock:
            nome = _charger_oled_nome
        if not nome:
            if _charger_worker_stop.wait(0.4):
                break
            continue
        if not _charger_anim_lock.acquire(blocking=False):
            if _charger_worker_stop.wait(0.15):
                break
            continue
        try:
            instalar_guard_anim_base(cli)
            instalar_guard_cancel_anim_base(cli)
            ac = cli.anim_controller
            _garantir_thread_anim(cli)
            ac.enable_procedural_face(False)
            ac.enable_animations(True)
            instalar_anim_id_seguro(cli)
            _reset_anim_id(cli)
            _charger_replay_em_voo = True
            _ultimo_charger_play = time.monotonic()
            logger.info("Base OLED: Playing animation group %s", nome)
            # API oficial PyCozmo: load_anims (boot) + play_anim_group → play_anim_ppclip
            cli.play_anim_group(nome)
        except Exception as exc:
            logger.warning("charger anim worker %s: %s", nome, exc)
            _charger_worker_stop.wait(1.0)
            continue
        finally:
            _charger_replay_em_voo = False
            _charger_anim_lock.release()
        fim = time.monotonic() + clip_max + 0.2
        while not _charger_worker_stop.is_set() and time.monotonic() < fim:
            if _charger_worker_stop.wait(FRAME_S):
                break
        _charger_worker_stop.wait(clip_pause)


def _garantir_charger_worker(cli: "pycozmo.Client") -> bool:
    """Thread dedicada — stream 30fps sem cancel/replay fragmentado."""
    global _charger_worker_thread
    if not _charger_play_stream(cli) or _charger_keeper_ativo:
        return False
    with _charger_worker_start_lock:
        if _charger_worker_vivo():
            return True
        _parar_charger_worker(timeout=0.5)
        _charger_worker_stop.clear()
        _charger_worker_thread = threading.Thread(
            target=_loop_charger_anim_worker,
            args=(cli,),
            daemon=True,
            name="cozmo-charger-anim-worker",
        )
        _charger_worker_thread.start()
    return True


def _replay_anim_charger(cli: "pycozmo.Client", nome: str | None) -> bool:
    """IdleOnCharger — worker contínuo (stream) ou keeper clip (100%%)."""
    if not nome or not base_oled_usa_charger(cli) or not rx_link_ok():
        return False
    if _base_oled_anim_loop_ativo() and not _charger_play_stream(cli):
        return _garantir_base_oled_anim_loop(cli)
    if keeper_base_ativo() or (
        not _charger_play_stream(cli) and base_oled_carga_cheia_ativo(cli)
    ):
        return _exibir_clip_base(cli, nome) or _semear_oled_charger(cli, nome)
    if _charger_play_stream(cli) and not _charger_keeper_ativo:
        with _charger_oled_lock:
            global _charger_oled_nome
            _charger_oled_nome = nome
        return _garantir_charger_worker(cli)
    if _charger_anim_em_play(cli):
        return True
    if not _charger_anim_lock.acquire(blocking=False):
        return True
    try:
        instalar_guard_anim_base(cli)
        ac = cli.anim_controller
        ac.enable_procedural_face(False)
        _garantir_thread_anim(cli)
        ac.enable_animations(True)
        instalar_anim_id_seguro(cli)
        _reset_anim_id(cli)
        logger.info("Base OLED: Playing animation group %s", nome)
        cli.play_anim_group(nome)
        _ultimo_charger_play = time.monotonic()
        return True
    except Exception as exc:
        logger.debug("replay_anim_charger %s: %s", nome, exc)
        return False
    finally:
        _charger_anim_lock.release()


def instalar_oled_charger_handler(cli: "pycozmo.Client") -> None:
    """Religa IdleOnCharger em loop quando o clip termina (comportamento original)."""
    global _charger_handler_ok
    if _charger_handler_ok:
        return

    def ao_anim_terminou(pkt_src: object, _pkt=None) -> None:
        from cozmo_companion.core.pycozmo_cli import resolver_cliente

        global _ultimo_charger_handler, _charger_replay_pendente
        c = resolver_cliente(pkt_src)
        if not base_oled_usa_charger(c):
            return
        agora = time.monotonic()
        if agora - _ultimo_charger_handler < 0.35:
            return
        _ultimo_charger_handler = agora
        if _base_oled_anim_loop_ativo():
            return
        if not rx_link_ok():
            return
        if (
            _charger_keeper_ativo
            and _charger_stream_sessao
            and _charger_oled_nome
            and _charger_play_stream(cli)
        ):
            _pedir_replay_charger()

    try:
        cli.add_handler(protocol_encoder.AnimationEnded, ao_anim_terminou)
        _charger_handler_ok = True
    except Exception as exc:
        logger.debug("instalar_oled_charger_handler: %s", exc)


def _charger_anim_base_ativa(cli: "pycozmo.Client") -> bool:
    with _charger_oled_lock:
        nome = _charger_oled_nome
    return bool(nome and _charger_stream_sessao and base_oled_usa_charger(cli))


def _charger_stream_ativo(cli: "pycozmo.Client") -> bool:
    if not _charger_stream_sessao:
        return False
    ac = cli.anim_controller
    return bool(ac.animations_enabled)


def charger_oled_ativo(cli: "pycozmo.Client") -> bool:
    with _charger_oled_lock:
        nome = _charger_oled_nome
    if not nome:
        return False
    if _charger_keeper_ativo:
        return _charger_stream_sessao
    ac = cli.anim_controller
    return bool(_charger_stream_sessao and ac.animations_enabled)


def _charger_usa_keeper(cli: "pycozmo.Client") -> bool:
    """100%% na base: sem thread 30fps (dtx≈300 → COZMO 01)."""
    if os.environ.get("COZMO_CHARGER_OLED_KEEPER", "1") != "1":
        return False
    return base_oled_carga_cheia_ativo(cli)


def manter_proc_vivo_base(cli: "pycozmo.Client") -> bool:
    """Garante AnimationController 30fps + rosto procedural na base (app Anki)."""
    if not base_oled_usa_proc_vivo(cli):
        return False
    instalar_guard_anim_base(cli)
    instalar_guard_cancel_anim_base(cli)
    ac = cli.anim_controller
    proc_on = os.environ.get("COZMO_PROC_FACE_BASE", "1") == "1"
    _garantir_thread_anim(cli)
    if ac.queue.is_empty() and ac.playing_animation:
        ac.playing_animation = False
    if not ac.animations_enabled or ac.procedural_face_enabled != proc_on:
        ac.enable_animations(True)
        ac.enable_procedural_face(proc_on)
    if _imagem_vazia(ac.last_image_pkt):
        from cozmo_companion.display.rosto import pkt_rosto_procedural

        try:
            ac.display_image(pkt_rosto_procedural(cli))
        except Exception:
            pass
    return True


def _charger_play_stream(cli: "pycozmo.Client") -> bool:
    """30fps play_anim na base — desligado em 100%% (ratio>1 → tela preta / COZMO 01)."""
    if os.environ.get("COZMO_CHARGER_PLAY_STREAM", "1") != "1":
        return False
    if base_oled_carga_cheia_ativo(cli) and os.environ.get(
        "COZMO_CHARGER_STREAM_NA_CHEIA", "0"
    ) != "1":
        return False
    return True


def base_oled_usa_proc_vivo(cli: "pycozmo.Client") -> bool:
    """Base: rosto procedural 30fps — só enquanto carrega; 100%% usa clip IdleOnCharger."""
    if not base_oled_modo_proc():
        return False
    # Keeper/clip na base (stream=0) — procedural aqui gerava recursão ligar↔charger↔proc.
    if os.environ.get("COZMO_CHARGER_PLAY_STREAM", "1") == "0":
        return False
    if _charger_play_stream(cli):
        return False
    from cozmo_companion.core.charger import na_base_oled

    if not na_base_oled(cli):
        return False
    # HW5 100%%: firmware pausa RX — procedural só TX, OLED parada (≠ app Anki).
    if base_oled_carga_cheia_ativo(cli):
        return False
    return os.environ.get("COZMO_BASE_OLED_CHARGER", "1") == "1"


def _imagem_vazia(pkt: object) -> bool:
    img = getattr(pkt, "image", None)
    return not img or img == b"\x3f\x3f"


def _ppclip_grupo(cli: "pycozmo.Client", grupo: str):
    """PreprocessedClip do grupo — na base usa clip sem keyframes de roda."""
    from cozmo_companion.core.anim_base_patch import (
        obter_ppclip_sem_rodas,
        _na_base_anim,
    )
    from cozmo_companion.core.charger import na_base_oled

    ag = cli.animation_groups.get(grupo)
    if not ag:
        return None
    anim_name = ag.choose_member().name
    meta = cli._clip_metadata.get(anim_name)
    if not meta:
        return None
    if na_base_oled(cli) or _na_base_anim(cli):
        try:
            return obter_ppclip_sem_rodas(cli, anim_name)
        except ValueError:
            return None
    from pycozmo import anim as pycozmo_anim

    if anim_name not in cli._ppclips:
        if anim_name not in cli._clips:
            cli._load_clips(meta.fspec)
        cli._ppclips[anim_name] = pycozmo_anim.PreprocessedClip.from_anim_clip(
            cli._clips[anim_name]
        )
    return cli._ppclips.get(anim_name)


def _frame_grupo_charger(cli: "pycozmo.Client", grupo: str) -> protocol_encoder.DisplayImage | None:
    """Primeiro frame OLED do clip — sem play_anim (sem flood UDP)."""
    pp = _ppclip_grupo(cli, grupo)
    if not pp:
        return None
    for t in sorted(pp.keyframes.keys())[:8]:
        for action in pp.keyframes[t]:
            if isinstance(action, protocol_encoder.DisplayImage):
                return action
    return None


def _marcar_novo_clip_oled(cli: "pycozmo.Client") -> None:
    """Próximo frame OLED exige StartAnimation (firmware HW5 ignora só DisplayImage)."""
    setattr(cli, "_cozmo_oled_clip_sessao", None)


def _handshake_frame_oled(cli: "pycozmo.Client", *, force: bool = False) -> None:
    if not force and getattr(cli, "_cozmo_oled_clip_sessao", None) is not None:
        return
    try:
        cli.conn.send(protocol_encoder.EnableAnimationState())
        aid = _normalizar_anim_id(cli)
        cli.conn.send(protocol_encoder.StartAnimation(anim_id=aid))
        cli._next_anim_id = aid + 1 if aid < 255 else 1  # type: ignore[attr-defined]
        cli._cozmo_oled_clip_sessao = aid  # type: ignore[attr-defined]
    except Exception as exc:
        logger.debug("handshake_frame_oled: %s", exc)


def _pool_oled_com_frames(
    cli: "pycozmo.Client", candidatos: tuple[str, ...] | list[str]
) -> tuple[str, ...]:
    """Só grupos com N frames OLED reais após patch sem rodas."""
    min_n = max(2, int(os.environ.get("COZMO_BASE_OLED_MIN_FRAMES", "8")))
    ok: list[str] = []
    for g in candidatos:
        n = len(_frames_clip_oled(cli, g))
        if n >= min_n:
            ok.append(g)
    if ok:
        return tuple(ok)
    for fb in ("CodeLabBlink", "Hiccup", "CodeLabSquint1", "InterestedFace", "IdleOnCharger"):
        if fb in candidatos and len(_frames_clip_oled(cli, fb)) >= 2:
            logger.warning(
                "pool OLED: nenhum clip com >=%d frames — fallback %s",
                min_n,
                fb,
            )
            return (fb,)
    return tuple(candidatos[:1]) if candidatos else ()


def _exibir_clip_base(
    cli: "pycozmo.Client", grupo: str, *, forcar: bool = False, recuperacao: bool = False
) -> bool:
    """Caminho Anki oficial: StartAnimation + play_anim_ppclip (sem rodas)."""
    global _ultimo_exibir_clip_grupo, _ultimo_exibir_clip_em, _ultimo_charger_play
    global _charger_oled_nome
    if modo_sono_oled_ativo() and not _sono_oled_texto_ativo:
        if not _clip_e_sono_oled(cli, grupo):
            clip_sono_base_oled(cli)
            with _charger_oled_lock:
                grupo = _charger_oled_nome or grupo
            if not _clip_e_sono_oled(cli, grupo):
                logger.warning(
                    "Base sono: bloqueado clip acordado %s",
                    grupo or "?",
                )
                return False
    if base_oled_loop_segurado() and not forcar:
        return False
    if not grupo or not base_oled_usa_charger(cli):
        return False
    if not _oled_tx_permitido(cli):
        if recuperacao:
            from cozmo_companion.core.conexao import cozmo_alcanavel

            if not cozmo_alcanavel():
                return False
            ping_sessao_base(cli)
            pulso_sync_base(cli, forcado=True)
            if not _oled_tx_permitido(cli):
                logger.warning(
                    "Base OLED: clip %s adiado — RX parado após ping",
                    grupo,
                )
                return False
        else:
            try:
                ping_oob(cli, vezes=max(2, int(os.environ.get("COZMO_PING_PRE_CLIP", "2"))))
            except Exception:
                pass
            if not forcar:
                logger.debug("Base OLED: clip %s adiado (RX parado)", grupo)
                return False
            logger.warning(
                "Base OLED: clip %s bloqueado sem RX (evita flood COZMO 01)",
                grupo,
            )
            return False
    if base_oled_loop_segurado() and not forcar:
        return False
    if (
        _base_oled_anim_loop_ativo()
        and threading.current_thread() is not _clip_loop_thread
        and not forcar
    ):
        if _clip_loop_vivo() or _garantir_loop_em_voo:
            return True
        with _charger_oled_lock:
            _charger_oled_nome = grupo
        return iniciar_loop_clip_base(cli)
    n = len(_frames_clip_oled(cli, grupo))
    min_n = max(2, int(os.environ.get("COZMO_BASE_OLED_MIN_FRAMES", "8")))
    if n < min_n:
        logger.warning("Base clip %s só %d frame(s) OLED — troca", grupo, n)
        return False
    agora = time.monotonic()
    gap = (
        0.0
        if _base_oled_anim_loop_ativo()
        else float(os.environ.get("COZMO_BASE_CLIP_REPLAY_MIN_S", "14"))
    )
    ac = cli.anim_controller
    if (
        not forcar
        and grupo == _ultimo_exibir_clip_grupo
        and agora - _ultimo_exibir_clip_em < gap
        and (_charger_anim_em_play(cli) or not ac.queue.is_empty())
    ):
        if _base_oled_anim_loop_ativo():
            _garantir_base_oled_anim_loop(cli)
        return True
    if (
        not forcar
        and _base_oled_anim_loop_ativo()
        and (_clip_loop_vivo() or threading.current_thread() is _clip_loop_thread)
        and grupo == _ultimo_exibir_clip_grupo
        and (_charger_anim_em_play(cli) or not ac.queue.is_empty())
    ):
        _garantir_base_oled_anim_loop(cli)
        return True
    if (
        _base_oled_anim_loop_ativo()
        and threading.current_thread() is not _clip_loop_thread
        and not forcar
    ):
        with _charger_oled_lock:
            _charger_oled_nome = grupo
        _ultimo_exibir_clip_grupo = grupo
        _ultimo_exibir_clip_em = agora
        _parar_oled_keepalive_base()
        _garantir_base_oled_anim_loop(cli)
        return True
    from cozmo_companion.core.conexao import cozmo_alcanavel

    from cozmo_companion.core.anim_base_patch import play_grupo_sem_rodas_na_base

    instalar_guard_anim_base(cli)
    instalar_guard_cancel_anim_base(cli)
    instalar_anim_id_seguro(cli)
    _parar_display_keeper()
    _handshake_oled_base(cli)
    ac.enable_procedural_face(False)
    ac.enable_animations(True)
    _garantir_thread_anim(cli)
    _reset_anim_id(cli)
    _marcar_novo_clip_oled(cli)
    cli._cozmo_cancel_clip_ok = True  # type: ignore[attr-defined]
    try:
        if threading.current_thread() is not ac.thread:
            try:
                cli.cancel_anim()
            except Exception:
                pass
            ac.queue.clear()
        ok = play_grupo_sem_rodas_na_base(cli, grupo)
    finally:
        cli._cozmo_cancel_clip_ok = False  # type: ignore[attr-defined]
    if not ok:
        return _semear_oled_charger(cli, grupo)
    _ultimo_charger_play = agora
    _ultimo_exibir_clip_grupo = grupo
    _ultimo_exibir_clip_em = agora
    if _base_oled_anim_loop_ativo():
        if threading.current_thread() is not _clip_loop_thread and not forcar:
            _garantir_base_oled_anim_loop(cli)
    else:
        iniciar_oled_keepalive_base(cli)
    from cozmo_companion.core.conexao import cozmo_alcanavel

    if not rx_link_ok() and not cozmo_alcanavel():
        logger.debug("Base OLED: clip %s adiado (offline)", grupo)
        return False
    if rx_link_ok():
        logger.info("Base OLED: clip oficial %s (%d frames, anim ON)", grupo, n)
    else:
        logger.warning(
            "Base OLED: clip %s enfileirado sem RX (tela pode estar COZMO 01)",
            grupo,
        )
    return True


def _parar_oled_keepalive_base() -> None:
    global _oled_keepalive_thread
    _oled_keepalive_stop.set()
    th = _oled_keepalive_thread
    _oled_keepalive_thread = None
    if th and th.is_alive() and threading.current_thread() is not th:
        th.join(timeout=2.0)
    _oled_keepalive_stop.clear()


def _loop_oled_keepalive_base(cli: "pycozmo.Client") -> None:
    """HW5 100%%: reenvia último frame — firmware apaga OLED sem refresh (~30s)."""
    if _base_oled_anim_loop_ativo():
        return
    hz = float(os.environ.get("COZMO_BASE_OLED_KEEPALIVE_HZ", "5"))
    interval = 1.0 / max(2.0, min(8.0, hz))
    ac = cli.anim_controller
    n_log = 0
    while not _oled_keepalive_stop.is_set():
        if modo_sono_oled_ativo() or _sono_oled_texto_ativo:
            if _oled_keepalive_stop.wait(interval):
                break
            continue
        if not base_oled_usa_charger(cli) or not rx_link_ok():
            if _oled_keepalive_stop.wait(interval):
                break
            continue
        if ac.playing_audio and not _keeper_envia_durante_audio():
            if _oled_keepalive_stop.wait(0.1):
                break
            continue
        try:
            if not ac.animations_enabled:
                ac.enable_animations(True)
                _garantir_thread_anim(cli)
            pkt = ac.last_image_pkt
            if _imagem_vazia(pkt):
                with _charger_oled_lock:
                    grupo = _charger_oled_nome
                _handshake_frame_oled(cli, force=True)
                _semear_oled_charger(cli, grupo)
            else:
                _handshake_frame_oled(cli)
                cli.conn.send(protocol_encoder.EnableAnimationState())
                cli.conn.send(pkt)
            n_log += 1
            if n_log == 1 or n_log % max(1, int(hz * 25)) == 0:
                pkt_log = ac.last_image_pkt
                logger.info(
                    "Base OLED keepalive: %s (%d B, %.1f Hz)",
                    _ultimo_exibir_clip_grupo or "?",
                    len(getattr(pkt_log, "image", b"") or b""),
                    hz,
                )
        except Exception as exc:
            logger.warning("oled_keepalive: %s", exc)
        if _oled_keepalive_stop.wait(interval):
            break


def iniciar_oled_keepalive_base(cli: "pycozmo.Client") -> None:
    global _oled_keepalive_thread
    if _base_oled_anim_loop_ativo():
        return
    if os.environ.get("COZMO_BASE_OLED_KEEPALIVE", "1") != "1":
        return
    with _display_lock:
        th = _oled_keepalive_thread
    if th and th.is_alive():
        return
    _oled_keepalive_stop.clear()
    with _display_lock:
        _oled_keepalive_thread = threading.Thread(
            target=_loop_oled_keepalive_base,
            args=(cli,),
            daemon=True,
            name="BaseOledKeepalive",
        )
        _oled_keepalive_thread.start()


def _frames_clip_oled(
    cli: "pycozmo.Client", grupo: str
) -> tuple[protocol_encoder.DisplayImage, ...]:
    """Keyframes OLED do clip — mesma ordem que pycozmo.client.play_anim_ppclip."""
    pp = _ppclip_grupo(cli, grupo)
    if not pp:
        return ()
    frames: list[protocol_encoder.DisplayImage] = []
    for t in sorted(pp.keyframes.keys()):
        for action in pp.keyframes[t]:
            if isinstance(action, protocol_encoder.DisplayImage) and not _imagem_vazia(action):
                frames.append(action)
    return tuple(frames)


def _semear_oled_charger(cli: "pycozmo.Client", grupo: str | None) -> bool:
    from cozmo_companion.display.rosto import pkt_rosto_procedural

    ac = cli.anim_controller
    pkt = None
    if grupo:
        clip_pkt = _frame_grupo_charger(cli, grupo)
        if clip_pkt is not None and not _imagem_vazia(clip_pkt):
            pkt = clip_pkt
    if pkt is None:
        if modo_sono_oled_ativo() or _sono_oled_texto_ativo:
            return False
        pkt = pkt_rosto_procedural(cli)
    try:
        _handshake_frame_oled(cli, force=True)
        enviar_oled(cli, pkt)
        ac.last_image_pkt = pkt
        ac.enable_animations(True)
        _garantir_thread_anim(cli)
        if _base_oled_anim_loop_ativo():
            _garantir_base_oled_anim_loop(cli)
        else:
            iniciar_oled_keepalive_base(cli)
        return True
    except Exception as exc:
        logger.debug("semear_oled_charger: %s", exc)
        return False


def _rx_parou_na_janela(cli: "pycozmo.Client", janela_s: float = 12.0) -> bool:
    """True só ao fechar a janela sem crescimento de recv_frames (≠ spam a cada tick)."""
    global _renovar_rx_snap, _renovar_rx_em
    from cozmo_companion.core.conexao import diagnostico

    d = diagnostico(cli)
    rx = int(d.get("recv_frames", 0))
    agora = time.monotonic()
    if agora - _renovar_rx_em < janela_s:
        if rx > _renovar_rx_snap:
            _renovar_rx_snap = rx
        return False
    parou = rx <= _renovar_rx_snap
    _renovar_rx_snap = rx
    _renovar_rx_em = agora
    return parou


def _stream_oled_estavel(cli: "pycozmo.Client") -> bool:
    """HW5 100%%: rx parado é normal — não renovar/despertar se OLED vivo."""
    if not base_oled_usa_charger(cli):
        return False
    if keeper_base_ativo() and _charger_stream_sessao:
        return True
    if _base_oled_anim_loop_ativo() and _base_anim_loop_vivo():
        return rx_link_ok()
    if not _charger_play_stream(cli):
        return oled_charger_vivo(cli)
    if _charger_keeper_ativo or _charger_usa_keeper(cli):
        return oled_charger_vivo(cli)
    return bool(
        _charger_stream_sessao
        and _charger_worker_vivo()
        and (_charger_anim_em_play(cli) or _anim_thread_viva(cli))
    )


def renovar_sessao_base_oled(
    cli: "pycozmo.Client",
    medidor: "MedidorUdp | None" = None,
    *,
    forcar: bool = False,
) -> bool:
    """Re-handshake sem Disconnect/EndAnimation — HW5 base 100%% (≠ COZMO 01)."""
    global _ultimo_renovar_base, _ultimo_sync_base, _charger_replay_pendente
    global _renovar_rx_snap, _renovar_rx_em
    from cozmo_companion.core.conexao import cozmo_alcanavel, diagnostico

    if modo_sono_oled_ativo() or _sono_oled_texto_ativo:
        if not cozmo_alcanavel():
            return False
        if _pulso_recuperar_rx(cli):
            if modo_sono_oled_ativo() and not _sono_oled_texto_ativo:
                manter_sono_ppclip(cli)
            return True
        return False
    if not cozmo_alcanavel():
        return False
    if not base_oled_carga_cheia_ativo(cli) and not base_oled_usa_charger(cli):
        return False
    if _stream_oled_estavel(cli):
        if not _charger_worker_vivo():
            _garantir_charger_worker(cli)
        return False
    intervalo = float(os.environ.get("COZMO_RENOVAR_BASE_S", "20"))
    agora = time.monotonic()
    min_s = intervalo if not forcar else float(
        os.environ.get("COZMO_RENOVAR_FORCAR_MIN_S", "8")
    )
    if agora - _ultimo_renovar_base < min_s:
        return False

    rx_antes = int(diagnostico(cli).get("recv_frames", 0))
    # Keeper clip vivo: só ping — renovar agressivo mata animação (rx parado é normal HW5).
    if keeper_base_ativo() and base_oled_carga_cheia_ativo(cli):
        _ultimo_renovar_base = agora
        try:
            _refresh_sessao_oled_leve(cli)
        except Exception as exc:
            logger.debug("renovar keeper: %s", exc)
        return True
    proc_vivo = base_oled_usa_proc_vivo(cli)
    stream_vivo = (
        base_oled_usa_charger(cli)
        and _charger_play_stream(cli)
        and not _charger_keeper_ativo
        and not _charger_usa_keeper(cli)
    )
    if stream_vivo and not proc_vivo:
        if rx_antes <= _renovar_rx_snap:
            if not _charger_worker_vivo():
                _garantir_charger_worker(cli)
            return False
    _ultimo_renovar_base = agora
    instalar_charger_display_guard(cli)
    if proc_vivo or stream_vivo:
        try:
            _handshake_oled_base(cli)
            _refresh_sessao_oled_leve(cli)
            _ultimo_sync_base = agora
        except Exception as exc:
            logger.warning("renovar_sessao_base_oled (vivo): %s", exc)
            return False
        if proc_vivo:
            manter_proc_vivo_base(cli)
        else:
            if not _charger_stream_sessao:
                modo_charger_oled(cli, forcar=True)
            ac = cli.anim_controller
            if not _anim_thread_viva(cli):
                _ligar_anim_charger(cli)
            if not _charger_worker_vivo():
                _garantir_charger_worker(cli)
            elif not _charger_anim_em_play(cli):
                with _charger_oled_lock:
                    nome = _charger_oled_nome
                if nome:
                    _replay_anim_charger(cli, nome)
    else:
        _parar_thread_anim(cli)
        ac = cli.anim_controller
        ac.enable_procedural_face(False)
        ac.enable_animations(False)
        ac.queue.clear()
        try:
            _handshake_oled_base(cli)
            _ultimo_sync_base = agora
        except Exception as exc:
            logger.warning("renovar_sessao_base_oled: %s", exc)
            return False
        with _charger_oled_lock:
            grupo = _charger_oled_nome
        if _charger_keeper_ativo or _charger_usa_keeper(cli):
            _semear_oled_charger(cli, grupo)
            if not _charger_loop_thread or not _charger_loop_thread.is_alive():
                iniciar_loop_charger(cli)
        elif threading.current_thread() is _charger_loop_thread:
            _pedir_replay_charger()
        else:
            modo_charger_oled(cli, forcar=True)
    time.sleep(0.15 if (proc_vivo or stream_vivo) else 0.35)
    rx_depois = int(diagnostico(cli).get("recv_frames", 0))
    if rx_depois <= rx_antes and stream_vivo and not proc_vivo:
        logger.debug(
            "Base: renovar ignorado rx parado (%d) — stream vivo",
            rx_antes,
        )
        return False
    if rx_depois <= rx_antes:
        logger.debug(
            "Base: renovar sem drx (%d→%d) — stream/OLED intacto",
            rx_antes,
            rx_depois,
        )
        return False
    if medidor is not None:
        medidor.reset()
    _renovar_rx_snap = rx_depois
    _renovar_rx_em = time.monotonic()
    logger.info(
        "Base: sessão renovada rx %d→%d (≠ COZMO 01)",
        rx_antes,
        rx_depois,
    )
    return True


def _refresh_sessao_oled_leve(cli: "pycozmo.Client") -> None:
    global _ultimo_charger_sync
    intervalo = float(os.environ.get("COZMO_SYNC_BASE_S", "5"))
    agora = time.monotonic()
    if agora - _ultimo_charger_sync < intervalo:
        return
    _ultimo_charger_sync = agora
    try:
        cli.conn.send(protocol_encoder.EnableAnimationState())
        cli.conn.send(protocol_encoder.SyncTime())
        cli.conn.send(protocol_encoder.Ping())
    except Exception as exc:
        logger.debug("refresh_sessao_oled: %s", exc)


def _ligar_anim_charger(cli: "pycozmo.Client") -> None:
    ac = cli.anim_controller
    _garantir_thread_anim(cli)
    ac.enable_procedural_face(False)
    ac.enable_animations(True)
    instalar_charger_display_guard(cli)


def _manter_charger_handshake(cli: "pycozmo.Client") -> bool:
    _handshake_oled_base(cli)
    return True


def _tick_charger_oled(cli: "pycozmo.Client") -> bool:
    """Sync na base — stream clip, keeper ou handshake leve."""
    if modo_sono_oled_ativo() or _sono_oled_texto_ativo:
        return False
    if not base_oled_usa_charger(cli):
        return False
    if keeper_base_ativo() and base_oled_carga_cheia_ativo(cli):
        _refresh_sessao_oled_leve(cli)
        return True
    if base_oled_usa_proc_vivo(cli):
        _refresh_sessao_oled_leve(cli)
        manter_proc_vivo_base(cli)
        return True
    if _charger_stream_ativo(cli):
        _refresh_sessao_oled_leve(cli)
        if not _anim_thread_viva(cli):
            _ligar_anim_charger(cli)
        if not _charger_worker_vivo():
            _garantir_charger_worker(cli)
        return True
    if _charger_keeper_ativo:
        if _base_oled_anim_loop_ativo():
            _garantir_base_oled_anim_loop(cli)
            _refresh_sessao_oled_leve(cli)
            return True
        with _charger_oled_lock:
            grupo = _charger_oled_nome
        _refresh_sessao_oled_leve(cli)
        ac = cli.anim_controller
        pkt = ac.last_image_pkt
        if _imagem_vazia(pkt):
            return _semear_oled_charger(cli, grupo)
        try:
            cli.conn.send(pkt)
            return True
        except Exception:
            return _semear_oled_charger(cli, grupo)
    ac = cli.anim_controller
    if ac.playing_animation or ac.playing_audio:
        return _manter_charger_handshake(cli)
    if _charger_stream_sessao and _charger_play_stream(cli):
        return _garantir_charger_worker(cli) or _manter_charger_handshake(cli)
    return _manter_charger_handshake(cli)


def processar_replay_charger_pendente(cli: "pycozmo.Client") -> bool:
    """Religa worker IdleOnCharger na thread principal (≠ UDP/charger loop)."""
    global _charger_replay_pendente
    if modo_sono_oled_ativo() or _sono_oled_texto_ativo:
        _charger_replay_pendente = False
        return False
    if not _charger_replay_pendente or not rx_link_ok():
        _charger_replay_pendente = False
        return False
    if not base_oled_usa_charger(cli) or not _charger_stream_sessao:
        _charger_replay_pendente = False
        return False
    _charger_replay_pendente = False
    if _charger_worker_vivo():
        return True
    with _charger_oled_lock:
        grupo = _charger_oled_nome
    if not grupo:
        return False
    return _garantir_charger_worker(cli)


def _loop_charger_oled(cli: "pycozmo.Client") -> None:
    hz = float(os.environ.get("COZMO_CHARGER_OLED_HZ", "1.5"))
    intervalo = 1.0 / max(0.5, min(4.0, hz))
    replay_s = float(os.environ.get("COZMO_CHARGER_REPLAY_S", "18"))
    ultimo_replay = 0.0
    while not _charger_loop_stop.wait(intervalo):
        try:
            if modo_sono_oled_ativo() or _sono_oled_texto_ativo:
                continue
            if not base_oled_usa_charger(cli):
                continue
            if base_oled_usa_proc_vivo(cli):
                _refresh_sessao_oled_leve(cli)
                continue
            agora = time.monotonic()
            with _charger_oled_lock:
                grupo = _charger_oled_nome
            if base_oled_carga_cheia_ativo(cli) and _charger_stream_sessao and (
                keeper_base_ativo() or _charger_keeper_ativo
            ):
                if rx_link_ok():
                    _refresh_sessao_oled_leve(cli)
                tick_espiar_escuro(cli)
                if rx_link_ok() and not _charger_replay_em_voo and not _base_anim_loop_vivo():
                    variar_clip_base_oled(cli)
                elif _base_anim_loop_vivo():
                    _iniciar_clip_base_continuo(cli)
            elif (
                base_oled_carga_cheia_ativo(cli)
                and _charger_play_stream(cli)
                and not _charger_keeper_ativo
            ):
                _tick_charger_oled(cli)
                tick_espiar_escuro(cli)
                if rx_link_ok() and not _charger_replay_em_voo and not _base_anim_loop_vivo():
                    variar_clip_base_oled(cli)
                elif _base_anim_loop_vivo():
                    _iniciar_clip_base_continuo(cli)
                if (
                    rx_link_ok()
                    and _rx_parou_na_janela(cli, 14.0)
                    and grupo
                    and not _charger_anim_em_play(cli)
                ):
                    if _base_oled_anim_loop_ativo():
                        _garantir_base_oled_anim_loop(cli)
                    else:
                        _replay_anim_charger(cli, grupo)
            elif agora - _ultimo_renovar_base >= float(
                os.environ.get("COZMO_RENOVAR_BASE_S", "20")
            ):
                if keeper_base_ativo() and base_oled_carga_cheia_ativo(cli) and rx_link_ok():
                    _refresh_sessao_oled_leve(cli)
                elif (
                    _charger_play_stream(cli)
                    and _charger_stream_sessao
                    and not _charger_keeper_ativo
                ):
                    if not _charger_worker_vivo():
                        _garantir_charger_worker(cli)
                elif _rx_parou_na_janela(cli, 14.0):
                    from cozmo_companion.core.conexao import cozmo_alcanavel

                    if cozmo_alcanavel() and not _stream_oled_estavel(cli):
                        renovar_sessao_base_oled(cli, forcar=True)
            elif _charger_keeper_ativo and grupo and agora - ultimo_replay >= replay_s:
                if _base_oled_anim_loop_ativo():
                    _garantir_base_oled_anim_loop(cli)
                elif not keeper_base_ativo():
                    if not _iniciar_keeper_clip_oled_base(cli, grupo):
                        if not _exibir_clip_base(cli, grupo):
                            _semear_oled_charger(cli, grupo)
                ultimo_replay = agora
            else:
                _tick_charger_oled(cli)
        except Exception as exc:
            logger.debug("loop_charger_oled: %s", exc)


def iniciar_loop_charger(cli: "pycozmo.Client") -> None:
    global _charger_loop_thread
    cur = threading.current_thread()
    with _charger_oled_lock:
        th = _charger_loop_thread
    if th and th.is_alive():
        if cur is th:
            return
        _charger_loop_stop.set()
        th.join(timeout=2.0)
    _charger_loop_stop.clear()
    _charger_loop_thread = threading.Thread(
        target=_loop_charger_oled,
        args=(cli,),
        daemon=True,
        name="cozmo-charger-oled",
    )
    _charger_loop_thread.start()


def religar_charger_suave(cli: "pycozmo.Client") -> bool:
    if not base_oled_usa_charger(cli):
        return False
    if keeper_base_ativo() and base_oled_carga_cheia_ativo(cli):
        with _charger_oled_lock:
            grupo = _charger_oled_nome
        _refresh_sessao_oled_leve(cli)
        _semear_oled_charger(cli, grupo)
        return True
    if base_oled_usa_proc_vivo(cli):
        modo_proc_base(cli)
        return True
    if _charger_stream_ativo(cli):
        if _charger_worker_vivo() or _charger_anim_em_play(cli):
            return _tick_charger_oled(cli)
        return _garantir_charger_worker(cli) or _tick_charger_oled(cli)
    with _charger_oled_lock:
        nome = _charger_oled_nome
    if not nome:
        return modo_charger_oled(cli, forcar=False)
    if _charger_keeper_ativo:
        ok = _semear_oled_charger(cli, nome)
        if ok:
            _ultimo_charger_play = time.monotonic()
        return ok
    if not _charger_play_stream(cli):
        if _base_oled_anim_loop_ativo():
            return (
                _garantir_base_oled_anim_loop(cli)
                or modo_charger_oled(cli, forcar=False)
                or True
            )
        modo_base_olhos(cli)
        return True
    return _garantir_charger_worker(cli)


def _ativar_oled_keeper_vivo(cli: "pycozmo.Client", agora: float) -> bool:
    """100%% na base: clip InteractWithFace ~6-8Hz (Anki, baixo UDP, olhos vivos)."""
    if _sono_oled_texto_ativo or modo_sono_oled_ativo():
        return True
    global _charger_oled_nome, _ultimo_charger_play, _charger_stream_sessao, _charger_keeper_ativo
    _parar_display_keeper()
    _parar_charger_worker()
    _charger_stream_sessao = True
    _charger_keeper_ativo = True
    from cozmo_companion.core.charger import carregando, carga_firmware_pausada
    from cozmo_companion.core.anims import pool_variacao_oled_base

    pausada = carga_firmware_pausada(cli)
    candidatos = _candidatos_charger_oled(
        cli, carga_pausada=pausada, carregando_agora=carregando(cli)
    )
    disp = set(cli.animation_groups.keys())
    idle_fixo = os.environ.get("COZMO_CHARGER_AWAKE_IDLE", "IdleOnCharger")
    pool = list(
        _pool_oled_com_frames(cli, tuple(n for n in pool_variacao_oled_base(disp, cli) if n in disp))
    )
    if pool:
        grupo = _escolher_clip_variar(pool, atual=None, recentes=_ultimos_clips_base)
    else:
        grupo = next((n for n in candidatos if n in disp), None)
    if not grupo and idle_fixo in disp:
        grupo = idle_fixo
    with _charger_oled_lock:
        _charger_oled_nome = grupo or idle_fixo
    instalar_oled_charger_handler(cli)
    clip = grupo or idle_fixo
    _parar_oled_keepalive_base()
    if _base_oled_anim_loop_ativo():
        iniciar_loop_clip_base(cli)
        ok = _exibir_clip_base(cli, clip, forcar=True)
        if not ok:
            _semear_oled_charger(cli, clip)
    else:
        iniciar_loop_charger(cli)
        ok = _exibir_clip_base(cli, clip)
        if not ok:
            _semear_oled_charger(cli, clip)
    logger.info(
        "Base OLED: vivo %s (pool=%d, clip oficial)",
        grupo or idle_fixo,
        len(pool),
    )
    return True


def _ativar_charger_stream(cli: "pycozmo.Client", nome: str, agora: float) -> bool:
    """IdleOnCharger contínuo 30fps — igual app Anki."""
    if modo_sono_oled_ativo() or _sono_oled_texto_ativo:
        return False
    global _charger_oled_nome, _ultimo_charger_play, _charger_stream_sessao
    global _charger_keeper_ativo, _charger_slow_anim
    instalar_guard_anim_base(cli)
    _parar_display_keeper()
    _charger_keeper_ativo = False
    _charger_slow_anim = False
    _charger_stream_sessao = True
    with _charger_oled_lock:
        _charger_oled_nome = nome
        _ultimo_charger_play = agora
    _handshake_oled_base(cli)
    _ligar_anim_charger(cli)
    _garantir_charger_worker(cli)
    instalar_oled_charger_handler(cli)
    iniciar_loop_charger(cli)
    return True


def _ativar_charger_keeper(cli: "pycozmo.Client", nome: str, agora: float) -> bool:
    """Fallback: keeper OLED sem clip (COZMO_CHARGER_OLED_KEEPER=1)."""
    global _charger_oled_nome, _ultimo_charger_play, _charger_stream_sessao
    global _charger_keeper_ativo, _charger_slow_anim
    _parar_charger_worker()
    instalar_guard_anim_base(cli)
    _parar_display_keeper()
    _parar_thread_anim(cli)
    _charger_keeper_ativo = True
    _charger_slow_anim = False
    _charger_stream_sessao = True
    with _charger_oled_lock:
        _charger_oled_nome = nome
        _ultimo_charger_play = agora
    _handshake_oled_base(cli)
    if not _iniciar_keeper_clip_oled_base(cli, nome):
        _semear_oled_charger(cli, nome)
    instalar_oled_charger_handler(cli)
    iniciar_loop_charger(cli)
    if _base_oled_anim_loop_ativo():
        _garantir_base_oled_anim_loop(cli)
    return True


def modo_charger_oled(cli: "pycozmo.Client", *, forcar: bool = False) -> bool:
    """IdleOnCharger na OLED — keeper na carga cheia, stream se carregando."""
    if _sono_oled_texto_ativo:
        return True
    if modo_sono_oled_ativo():
        if sono_oled_usa_texto():
            ativar_sono_oled_texto(cli)
        else:
            manter_sono_ppclip(cli)
        return True
    global _charger_oled_nome, _ultimo_charger_play, _ultimo_charger_falha, _charger_stream_sessao, _charger_keeper_ativo
    if not base_oled_usa_charger(cli):
        with _charger_oled_lock:
            _charger_oled_nome = None
        _charger_keeper_ativo = False
        _parar_base_oled_anim_loop()
        _parar_charger_worker()
        return False
    if (
        base_oled_carga_cheia_ativo(cli)
        and _charger_play_stream(cli)
        and (_charger_worker_vivo() or _charger_stream_sessao)
        and not forcar
    ):
        return _tick_charger_oled(cli)
    if (
        base_oled_carga_cheia_ativo(cli)
        and keeper_base_ativo()
        and os.environ.get("COZMO_BASE_KEEPER_VIVO", "0") == "1"
        and not _charger_play_stream(cli)
        and not forcar
    ):
        if _base_oled_anim_loop_ativo() and not _base_anim_loop_vivo():
            _parar_display_keeper()
            _garantir_base_oled_anim_loop(cli)
        return True
    if _charger_anim_base_ativa(cli):
        with _charger_oled_lock:
            atual = _charger_oled_nome
        if (
            keeper_base_ativo()
            and base_oled_carga_cheia_ativo(cli)
            and not _base_anim_loop_vivo()
        ):
            _refresh_sessao_oled_leve(cli)
            return True
        if not forcar:
            return _tick_charger_oled(cli)
        if atual and not _charger_anim_em_play(cli):
            return _replay_anim_charger(cli, atual) or True
        return _tick_charger_oled(cli)
    if _charger_stream_ativo(cli):
        if not forcar:
            return _tick_charger_oled(cli)
        with _charger_oled_lock:
            grupo = _charger_oled_nome
        if grupo and not _charger_anim_em_play(cli):
            return _replay_anim_charger(cli, grupo)
        return _tick_charger_oled(cli)
    if _charger_keeper_ativo and not forcar:
        return _tick_charger_oled(cli)
    _parar_display_keeper()
    ac = cli.anim_controller
    agora = time.monotonic()
    with _charger_oled_lock:
        atual = _charger_oled_nome
    if not _charger_keeper_ativo and _charger_anim_em_play(cli):
        return _tick_charger_oled(cli)
    if not forcar and agora - _ultimo_charger_falha < 8.0:
        return False
    from cozmo_companion.core.anims import pool_variacao_oled_base
    from cozmo_companion.core.charger import (
        base_oled_estavel,
        carregando,
        carga_firmware_pausada,
    )

    pausada = carga_firmware_pausada(cli)
    cheia = base_oled_carga_cheia_ativo(cli)
    disp = set(cli.animation_groups.keys())
    candidatos = _candidatos_charger_oled(
        cli, carga_pausada=pausada or cheia, carregando_agora=carregando(cli)
    )
    nome_awake = next((n for n in candidatos if n in disp), None)

    # 100%% na base: stream 30fps — só se não estiver em modo keeper estável.
    if (
        cheia
        and _charger_play_stream(cli)
        and nome_awake
        and not base_oled_estavel(cli)
    ):
        with _charger_oled_lock:
            atual_awake = _charger_oled_nome
        if forcar or not _charger_worker_vivo():
            _parar_display_keeper()
            if forcar or atual_awake != nome_awake:
                try:
                    if threading.current_thread() is not ac.thread:
                        cli.cancel_anim()
                except Exception:
                    pass
                ac.queue.clear()
            _ativar_charger_stream(cli, nome_awake, agora)
            if not getattr(modo_charger_oled, "_log_stream_awake", False):
                modo_charger_oled._log_stream_awake = True  # type: ignore[attr-defined]
                logger.info(
                    "Base OLED: %s stream 30fps (Anki, olhos realistas, ≠ COZMO 01)",
                    nome_awake,
                )
        return True

    if cheia and (
        base_oled_estavel(cli)
        or os.environ.get("COZMO_BASE_KEEPER_VIVO", "0") == "1"
    ):
        if modo_sono_oled_ativo():
            manter_sono_ppclip(cli)
            return True
        pool_nome = _escolher_clip_variar(
            list(
                _pool_oled_com_frames(
                    cli, tuple(n for n in pool_variacao_oled_base(disp, cli) if n in disp)
                )
            ),
            atual=None,
            recentes=_ultimos_clips_base,
        )
        nome_cheia = pool_nome or nome_awake or os.environ.get(
            "COZMO_CHARGER_AWAKE_IDLE", "IdleOnCharger"
        )
        if nome_cheia not in disp:
            nome_cheia = nome_awake or "IdleOnCharger"
        with _charger_oled_lock:
            atual_cheia = _charger_oled_nome
        if _charger_play_stream(cli):
            if forcar or not _charger_worker_vivo() or atual_cheia != nome_cheia:
                _ativar_charger_stream(cli, nome_cheia, agora)
            elif not _charger_worker_vivo():
                _garantir_charger_worker(cli)
        else:
            _ativar_oled_keeper_vivo(cli, agora)
        if not getattr(modo_charger_oled, "_log_keeper_vivo", False):
            modo_charger_oled._log_keeper_vivo = True  # type: ignore[attr-defined]
            hz = float(os.environ.get("COZMO_BASE_FULL_KEEPER_HZ", "7"))
            with _charger_oled_lock:
                clip = _charger_oled_nome or nome_cheia
            if _base_oled_anim_loop_ativo():
                modo = "loop-clips"
            else:
                modo = "stream" if _charger_play_stream(cli) else "keeper"
            logger.info(
                "Base OLED: %s %s %.1f Hz (100%%, ≠ COZMO 01)",
                modo,
                clip,
                hz,
            )
        return True

    candidatos = _candidatos_charger_oled(
        cli, carga_pausada=pausada, carregando_agora=carregando(cli)
    )
    nome = next((n for n in candidatos if n in disp), None)
    if not nome:
        return False
    if not forcar and _charger_keeper_ativo and atual == nome:
        return _tick_charger_oled(cli)
    if forcar or atual != nome:
        if _charger_stream_ativo(cli) and atual == nome and forcar:
            with _charger_oled_lock:
                grupo = _charger_oled_nome
            if grupo and not _charger_anim_em_play(cli):
                return _replay_anim_charger(cli, grupo)
            return _tick_charger_oled(cli)
        elif not (_charger_stream_ativo(cli) and atual == nome):
            try:
                if threading.current_thread() is not ac.thread:
                    cli.cancel_anim()
            except Exception:
                pass
            ac.queue.clear()
    try:
        if _charger_play_stream(cli):
            if _charger_anim_base_ativa(cli):
                return _tick_charger_oled(cli) or True
            _ativar_charger_stream(cli, nome, agora)
            modo = "contínuo"
        elif _charger_usa_keeper(cli):
            _ativar_charger_keeper(cli, nome, agora)
            modo = "keeper"
        else:
            _charger_keeper_ativo = False
            parar_flood_anim(cli)
            _handshake_oled_base(cli)
            pulso_oled_carga_cheia(cli)
            modo = "handshake"
            _charger_stream_sessao = True
            with _charger_oled_lock:
                _charger_oled_nome = nome
                _ultimo_charger_play = agora
            instalar_oled_charger_handler(cli)
            iniciar_loop_charger(cli)
        if not getattr(modo_charger_oled, "_log_ok", False):
            modo_charger_oled._log_ok = True  # type: ignore[attr-defined]
            if modo == "contínuo":
                logger.info(
                    "Base OLED: %s stream 30fps (app Anki, ≠ COZMO 01)",
                    nome,
                )
            elif modo == "keeper":
                hz = os.environ.get("COZMO_CHARGER_OLED_HZ", "2.5")
                logger.info(
                    "Base OLED: %s keeper %.1fHz (HW5 ≠ COZMO 01)",
                    nome,
                    float(hz),
                )
            else:
                logger.info("Base OLED: %s %s (HW5 ≠ COZMO 01)", nome, modo)
        return True
    except Exception as exc:
        _ultimo_charger_falha = agora
        logger.warning("modo_charger_oled %s: %s", nome, exc, exc_info=True)
        with _charger_oled_lock:
            _charger_oled_nome = None
        return False


def base_proc_hz() -> float:
    """Hz do keeper na base (0 = AnimationController 30fps)."""
    try:
        hz = float(os.environ.get("COZMO_BASE_PROC_HZ", "2"))
    except ValueError:
        hz = 2.0
    if hz <= 0:
        return 0.0
    return max(1.0, min(8.0, hz))


def keeper_base_ativo() -> bool:
    with _display_lock:
        th = _display_thread
    return th is not None and th.is_alive()


def oled_charger_vivo(cli: "pycozmo.Client") -> bool:
    """Keeper ou worker stream — OLED na base está ativo (≠ só _charger_worker_vivo)."""
    if _base_anim_loop_vivo():
        return True
    if keeper_base_ativo():
        return True
    if _charger_worker_vivo():
        return True
    if _charger_stream_sessao and (
        _charger_anim_em_play(cli) or _anim_thread_viva(cli)
    ):
        return True
    return charger_oled_ativo(cli)


def _keeper_envia_durante_audio() -> bool:
    """Na base: TTS não pode apagar OLED (keeper pausava em playing_audio)."""
    return os.environ.get("COZMO_KEEPER_DURING_TTS", "1") == "1"


def _keeper_pausa_anim_audio(ac) -> bool:
    if _keeper_envia_durante_audio():
        return bool(ac.playing_animation)
    return bool(ac.playing_animation or ac.playing_audio)


def _parar_display_keeper() -> None:
    global _display_thread
    _display_stop.set()
    cur = threading.current_thread()
    with _display_lock:
        th = _display_thread
        _display_thread = None
    if th and th.is_alive() and cur is not th:
        th.join(timeout=2.0)
    _display_stop.clear()


def _loop_display_keeper(cli: "pycozmo.Client", hz: float) -> None:
    from cozmo_companion.display.rosto import pkt_rosto_procedural

    interval = 1.0 / hz
    ac = cli.anim_controller
    frame_n = 0
    while not _display_stop.is_set():
        if modo_sono_oled_ativo() or _sono_oled_texto_ativo:
            if _display_stop.wait(interval):
                break
            continue
        if _keeper_pausa_anim_audio(ac):
            if _display_stop.wait(0.08):
                break
            continue
        try:
            frame_n += 1
            if frame_n == 1 or frame_n % max(2, int(hz * 2)) == 0:
                cli.conn.send(protocol_encoder.EnableAnimationState())
            pkt = pkt_rosto_procedural(cli)
            enviar_oled(cli, pkt)
            global _ultimo_exibir_clip_em
            _ultimo_exibir_clip_em = time.monotonic()
        except Exception as exc:
            logger.debug("display_keeper: %s", exc)
        if _display_stop.wait(interval):
            break


def _loop_display_clip_keeper(
    cli: "pycozmo.Client", grupo: str, hz: float
) -> None:
    """Reproduz frames OLED do clip oficial — rosto Anki na base 100%%."""
    from cozmo_companion.display.rosto import pkt_rosto_procedural

    frames = _frames_clip_oled(cli, grupo)
    interval = 1.0 / hz
    ac = cli.anim_controller
    idx = 0
    frame_n = 0
    ultimo_log = time.monotonic()
    while not _display_stop.is_set():
        if modo_sono_oled_ativo() or _sono_oled_texto_ativo:
            if _display_stop.wait(interval):
                break
            continue
        if _keeper_pausa_anim_audio(ac):
            if _display_stop.wait(0.08):
                break
            continue
        try:
            frame_n += 1
            if frame_n == 1:
                _handshake_frame_oled(cli, force=True)
            elif frame_n % max(2, int(hz * 2)) == 0:
                cli.conn.send(protocol_encoder.EnableAnimationState())
            if frames:
                pkt = frames[idx % len(frames)]
                idx += 1
            else:
                pkt = pkt_rosto_procedural(cli)
            enviar_oled(cli, pkt)
            global _ultimo_exibir_clip_em, _ultimo_exibir_clip_grupo
            _ultimo_exibir_clip_em = time.monotonic()
            _ultimo_exibir_clip_grupo = grupo
            agora = time.monotonic()
            if agora - ultimo_log >= 25.0:
                ultimo_log = agora
                logger.info(
                    "Base OLED keeper TX: %s frame %d/%d (%.1f Hz)",
                    grupo,
                    idx % max(len(frames), 1),
                    len(frames),
                    hz,
                )
        except Exception as exc:
            logger.warning("display_clip_keeper %s: %s", grupo, exc)
        if _display_stop.wait(interval):
            break


def _iniciar_display_keeper(
    cli: "pycozmo.Client", hz: float, *, grupo: str | None = None
) -> None:
    global _display_thread
    if modo_sono_oled_ativo() or _sono_oled_texto_ativo:
        return
    if _base_oled_anim_loop_ativo():
        _garantir_base_oled_anim_loop(cli)
        return
    _parar_display_keeper()
    instalar_guard_anim_base(cli)
    _handshake_oled_base(cli)
    ac = cli.anim_controller
    ac.enable_procedural_face(False)
    ac.enable_animations(False)
    if ac.thread and ac.thread.is_alive():
        _parar_thread_anim(cli)
    _display_stop.clear()
    frames = _frames_clip_oled(cli, grupo) if grupo else ()
    if grupo and frames:
        target = _loop_display_clip_keeper
        args: tuple = (cli, grupo, hz)
        modo_log = f"clip {grupo} ({len(frames)} frames)"
    else:
        target = _loop_display_keeper
        args = (cli, hz)
        modo_log = "procedural"
    with _display_lock:
        _display_thread = threading.Thread(
            target=target,
            args=args,
            daemon=True,
            name="BaseOledKeeper",
        )
        _display_thread.start()
    if not getattr(_iniciar_display_keeper, "_log_ok", False):
        _iniciar_display_keeper._log_ok = True  # type: ignore[attr-defined]
        logger.info("Base OLED: keeper %s %.1f Hz", modo_log, hz)


def usa_keeper_base(cli: "pycozmo.Client") -> bool:
    if base_oled_usa_pulse(cli) or not base_oled_modo_proc():
        return False
    if base_oled_usa_charger(cli):
        return False
    from cozmo_companion.core.charger import em_base

    if base_oled_minimo_ativo(cli):
        return True
    return em_base(cli) and base_proc_hz() > 0


def _handshake_oled_base(cli: "pycozmo.Client") -> None:
    """Refresh leve — sem Enable duplicado (re-dispara BodyInfo e flood 30fps)."""
    try:
        cli.conn.send(protocol_encoder.SetOrigin())
        cli.conn.send(protocol_encoder.EnableAnimationState())
        cli.conn.send(protocol_encoder.SyncTime())
        cli.conn.send(protocol_encoder.Ping())
    except Exception as exc:
        logger.debug("handshake_oled_base: %s", exc)


def modo_oled_minimo_base(cli: "pycozmo.Client", *, forcar: bool = False) -> None:
    """TX baixo: keeper 3fps + handshake — robô continua respondendo RX."""
    global _charger_oled_nome
    with _charger_oled_lock:
        _charger_oled_nome = None
    parar_flood_anim(cli)
    ac = cli.anim_controller
    ac.enable_procedural_face(False)
    ac.enable_animations(False)
    if keeper_base_ativo():
        if forcar:
            _handshake_oled_base(cli)
        return
    _handshake_oled_base(cli)
    hz = base_proc_hz()
    if hz <= 0:
        hz = float(os.environ.get("COZMO_BASE_PROC_HZ", "3"))
    if hz <= 0:
        hz = 3.0
    _iniciar_display_keeper(cli, max(2.0, min(8.0, hz)))
    travar_oled_minimo(cli)
    if not getattr(modo_oled_minimo_base, "_log_ok", False):
        modo_oled_minimo_base._log_ok = True  # type: ignore[attr-defined]
        logger.info("Base OLED: mínimo %.1f Hz (sem anim flood, ≠ COZMO 01)", hz)


def travar_oled_minimo(cli: "pycozmo.Client") -> None:
    """Garante que nada religou procedural/anim na base (causa COZMO 01)."""
    if base_oled_usa_proc_vivo(cli):
        return
    if _base_oled_anim_loop_ativo() and (
        _clip_loop_vivo() or _charger_anim_em_play(cli) or oled_charger_vivo(cli)
    ):
        return
    if base_oled_carga_cheia_ativo(cli):
        if keeper_base_ativo() and (
            base_oled_usa_charger(cli) or os.environ.get("COZMO_BASE_KEEPER_VIVO", "0") == "1"
        ):
            return
        if keeper_base_ativo():
            _parar_display_keeper()
        return
    if not base_oled_minimo_ativo(cli):
        return
    ac = cli.anim_controller
    if ac.procedural_face_enabled or ac.animations_enabled:
        ac.enable_procedural_face(False)
        ac.enable_animations(False)
    if ac.thread and ac.thread.is_alive():
        parar_flood_anim(cli)


_ultimo_wake_carga_cheia = 0.0


def pulso_oled_carga_cheia(cli: "pycozmo.Client") -> bool:
    """100%% na base: firmware pausa RX — rajada leve sem reset do medidor."""
    global _ultimo_wake_carga_cheia
    if os.environ.get("COZMO_FULL_CHARGE_WAKE", "1") != "1":
        return False
    from cozmo_companion.core.charger import carga_firmware_pausada

    if not carga_firmware_pausada(cli):
        return False
    intervalo = float(os.environ.get("COZMO_FULL_CHARGE_WAKE_S", "12"))
    agora = time.monotonic()
    if agora - _ultimo_wake_carga_cheia < intervalo:
        return False
    _ultimo_wake_carga_cheia = agora
    if base_oled_usa_proc_vivo(cli):
        _refresh_sessao_oled_leve(cli)
        return True
    if base_oled_usa_charger(cli):
        return _tick_charger_oled(cli) or manter_oled_base_ativo(cli)
    parar_flood_anim(cli)
    ac = cli.anim_controller
    ac.enable_procedural_face(False)
    ac.enable_animations(False)
    try:
        from cozmo_companion.display.rosto import pkt_rosto_procedural

        cli.conn.send(protocol_encoder.EnableAnimationState())
        pkt = pkt_rosto_procedural(cli)
        cli.conn.send(pkt)
        ac.last_image_pkt = pkt
        cli.conn.send(protocol_encoder.SyncTime())
        cli.conn.send(protocol_encoder.Ping())
    except Exception as exc:
        logger.debug("pulso_oled_carga_cheia: %s", exc)
        return False
    if not getattr(pulso_oled_carga_cheia, "_log_ok", False):
        pulso_oled_carga_cheia._log_ok = True  # type: ignore[attr-defined]
        logger.info("Base 100%%: pulso OLED (firmware pausado, ≠ COZMO 01)")
    return True


def instalar_guard_bodyinfo(cli: "pycozmo.Client") -> None:
    """Evita 2× thread 30fps se BodyInfo repetir _initialize_robot."""
    if getattr(cli, "_cozmo_guard_bodyinfo", False):
        return
    orig = cli._initialize_robot

    def _init_once() -> None:
        ac = cli.anim_controller
        if ac.thread and ac.thread.is_alive():
            parar_flood_anim(cli)
            return
        orig()
        if base_oled_usa_charger(cli) or base_oled_minimo_ativo(cli) or (
            base_oled_modo_proc() and os.environ.get("COZMO_BASE_OLED_MIN", "1") == "1"
        ):
            parar_flood_anim(cli)

    cli._initialize_robot = _init_once  # type: ignore[method-assign]
    cli._cozmo_guard_bodyinfo = True  # type: ignore[attr-defined]
    instalar_guard_anim_base(cli)
    instalar_guard_cancel_anim_base(cli)
    instalar_oled_charger_handler(cli)


def acordar_oled_minimo(
    cli: "pycozmo.Client",
    monitor: "MonitorRx | None" = None,
    medidor: "MedidorUdp | None" = None,
    *,
    reset_medidor: bool = True,
) -> None:
    if monitor is not None:
        monitor.sincronizar(cli)
    if medidor is not None and reset_medidor:
        medidor.reset()
    configurar_udp_leve_base(cli)
    from cozmo_companion.core.charger import em_base

    if em_base(cli) or base_oled_usa_charger(cli) or base_oled_carga_cheia_ativo(cli):
        if _stream_oled_estavel(cli):
            return
        if base_oled_carga_cheia_ativo(cli):
            if not keeper_base_ativo():
                ligar_oled_base(cli, forcar=True)
            elif not _stream_oled_estavel(cli):
                renovar_sessao_base_oled(cli, medidor, forcar=True)
        else:
            ligar_oled_base(cli, forcar=True)
        return
    if base_oled_usa_proc_vivo(cli):
        manter_proc_vivo_base(cli)
        return
    modo_oled_minimo_base(cli, forcar=True)


def base_oled_modo() -> str:
    return os.environ.get("COZMO_BASE_OLED_MODE", "proc").strip().lower()


def base_oled_modo_direto() -> bool:
    return base_oled_modo() == "direct"


def base_oled_modo_proc() -> bool:
    """Caminho PyCozmo: AnimationController 30fps + procedural (o que o firmware espera)."""
    return base_oled_modo() in ("proc", "procedural", "anim")


def base_oled_modo_minimo() -> bool:
    """Base HW5: handshake + frames leves — sem play_anim (flood → COZMO 01)."""
    return (
        os.environ.get("COZMO_BASE_OLED_MIN", "1") == "1"
        and base_oled_modo_proc()
    )


def base_oled_minimo_ativo(cli: "pycozmo.Client") -> bool:
    from cozmo_companion.core.charger import em_base

    if base_oled_carga_cheia_ativo(cli):
        return False
    return base_oled_modo_minimo() and em_base(cli)


def base_oled_usa_pulse(cli: "pycozmo.Client") -> bool:
    """Na base HW5: 1 frame ~3s só quando procedural 30fps está off (≠ COZMO 01)."""
    if base_oled_usa_proc_vivo(cli):
        return False
    if base_oled_usa_charger(cli):
        return False
    if base_oled_modo_direto():
        return True
    if os.environ.get("COZMO_BASE_PULSE_PROC", "1") != "1":
        return False
    if not base_oled_modo_proc():
        return False
    from cozmo_companion.core.charger import em_base

    return em_base(cli)


def angulo_cabeca_neutro() -> float:
    min_a = robot.MIN_HEAD_ANGLE.radians
    max_a = robot.MAX_HEAD_ANGLE.radians
    faixa = max_a - min_a
    frac = float(os.environ.get("BASE_HEAD_FRAC", "0.62"))
    frac = max(0.35, min(0.85, frac))
    return min_a + faixa * frac


def cabeca_precisa_reset(cli: "pycozmo.Client", *, tol: float | None = None) -> bool:
    if tol is None:
        tol = float(os.environ.get("BASE_HEAD_TOL_RAD", "0.09"))
    try:
        return abs(cli.head_angle.radians - angulo_cabeca_neutro()) > tol
    except (AttributeError, TypeError):
        return True


def cabeca_base_neutra(cli: "pycozmo.Client", *, forcar: bool = False) -> None:
    if base_oled_modo_proc():
        return
    if not forcar and os.environ.get("BASE_HEAD_RESET", "1") != "1":
        return
    if not forcar and not cabeca_precisa_reset(cli):
        return
    try:
        cli.set_head_angle(
            angulo_cabeca_neutro(),
            max_speed=float(os.environ.get("BASE_HEAD_SPEED", "8.0")),
        )
    except Exception:
        pass


def configurar_udp_leve_base(cli: "pycozmo.Client") -> None:
    """Ping PyCozmo padrão 0,5s — robô desconecta (COZMO 01) após 5s sem ping."""
    global _udp_leve_configurado
    try:
        ping_s = float(os.environ.get("COZMO_PING_INTERVAL_S", "0.5"))
        cli.conn.PING_INTERVAL = max(0.4, min(2.0, ping_s))
        if not _udp_leve_configurado:
            _udp_leve_configurado = True
            logger.info("Base UDP leve: ping a cada %.1fs", ping_s)
    except Exception:
        pass


def _parar_thread_anim(cli: "pycozmo.Client") -> None:
    ac = cli.anim_controller
    try:
        if threading.current_thread() is not ac.thread:
            cli.cancel_anim()
    except Exception:
        pass
    ac.queue.clear()
    ac.enable_procedural_face(False)
    ac.enable_animations(False)
    if ac.thread and ac.thread.is_alive():
        if threading.current_thread() is ac.thread:
            ac.stop_flag = True
            return
        ac.stop_flag = True
        ac.thread.join(timeout=2.0)
        ac.thread = None
        ac.stop_flag = False


def _garantir_thread_anim(cli: "pycozmo.Client") -> None:
    ac = cli.anim_controller
    if not ac.thread or not ac.thread.is_alive():
        ac.stop_flag = False
        ac.start()


def parar_flood_anim(cli: "pycozmo.Client") -> None:
    """Para loop 30fps — pulse, direct, keeper ou OLED mínimo na base."""
    if keeper_base_ativo() and base_oled_carga_cheia_ativo(cli):
        return
    if base_oled_usa_proc_vivo(cli):
        ac = cli.anim_controller
        proc_on = os.environ.get("COZMO_PROC_FACE_BASE", "1") == "1"
        if not ac.animations_enabled or ac.procedural_face_enabled != proc_on:
            ac.enable_procedural_face(proc_on)
            ac.enable_animations(True)
            _garantir_thread_anim(cli)
        return
    if base_oled_usa_charger(cli):
        if (
            keeper_base_ativo()
            or _charger_keeper_ativo
            or _charger_stream_sessao
            or os.environ.get("COZMO_BASE_KEEPER_VIVO", "0") == "1"
            or (_base_oled_anim_loop_ativo() and _base_anim_loop_vivo())
        ):
            return
        _parar_display_keeper()
        ac = cli.anim_controller
        if _charger_stream_ativo(cli):
            ac.enable_procedural_face(False)
            return
        if _charger_keeper_ativo:
            if ac.thread and ac.thread.is_alive():
                _parar_thread_anim(cli)
            return
        with _charger_oled_lock:
            em_charger = bool(_charger_oled_nome)
        if em_charger or charger_oled_ativo(cli):
            return
    if base_oled_modo_proc() and not base_oled_usa_pulse(cli):
        if usa_keeper_base(cli) or base_oled_minimo_ativo(cli):
            ac = cli.anim_controller
            if ac.thread and ac.thread.is_alive():
                logger.info("Base OLED: thread anim OFF (keeper/min)")
                _parar_thread_anim(cli)
            else:
                ac.enable_procedural_face(False)
                ac.enable_animations(False)
            return
        return
    ac = cli.anim_controller
    if ac.thread and ac.thread.is_alive():
        logger.info("Base OLED: thread anim OFF (pulse na base)")
        _parar_thread_anim(cli)
    elif not ac.animations_enabled and not ac.procedural_face_enabled:
        return
    else:
        ac.enable_procedural_face(False)
        ac.enable_animations(False)


def _intervalo_pulse_base() -> float:
    hz = float(os.environ.get("COZMO_BASE_FACE_HZ", "0.25"))
    if hz > 0:
        return max(0.8, min(18.0, 1.0 / hz))
    return float(os.environ.get("COZMO_OLED_REFRESH_S", "12"))


def manter_oled_pulse(cli: "pycozmo.Client", *, forcar: bool = False) -> bool:
    """Reenvia último rosto — sem isso a OLED cai em COZMO 01 entre pulses."""
    if not base_oled_usa_pulse(cli):
        return False
    global _ultimo_keep_oled
    intervalo = float(os.environ.get("COZMO_OLED_KEEPALIVE_S", "0.45"))
    with _keep_oled_lock:
        agora = time.monotonic()
        if not forcar and agora - _ultimo_keep_oled < intervalo:
            return False
        _ultimo_keep_oled = agora
    ac = cli.anim_controller
    pkt = getattr(ac, "last_image_pkt", None)
    if pkt is None or not getattr(pkt, "image", None):
        return pulse_rosto_base(cli, forcar=True)
    try:
        cli.conn.send(pkt)
        return True
    except Exception as exc:
        logger.debug("manter_oled_pulse: %s", exc)
        return False


def pulse_rosto_base(cli: "pycozmo.Client", *, forcar: bool = False) -> bool:
    global _ultimo_pulse_base
    ac = cli.anim_controller
    if ac.playing_animation or ac.playing_audio:
        return False
    from cozmo_companion.display.rosto import pkt_rosto_procedural

    with _pulse_lock:
        agora = time.monotonic()
        if not forcar and agora - _ultimo_pulse_base < _intervalo_pulse_base():
            return False
        parar_flood_anim(cli)
        try:
            pkt = pkt_rosto_procedural(cli)
            cli.conn.send(pkt)
            ac.last_image_pkt = pkt
            _ultimo_pulse_base = agora
            return True
        except Exception as exc:
            logger.warning("OLED keepalive falhou: %s", exc)
            return False


def modo_proc_base(cli: "pycozmo.Client") -> None:
    """Olhos procedural 30fps — mesa/off-base; na base usar clip keeper/stream."""
    global _ultimo_modo_proc
    from cozmo_companion.core.charger import na_base_oled

    if na_base_oled(cli) or base_oled_carga_cheia_ativo(cli) or base_oled_usa_charger(cli):
        modo_charger_oled(cli, forcar=False)
        return
    configurar_udp_leve_base(cli)
    _parar_charger_worker()
    ac = cli.anim_controller
    proc_on = os.environ.get("COZMO_PROC_FACE_BASE", "1") == "1"
    with _modo_proc_lock:
        agora = time.monotonic()
        if (
            ac.animations_enabled
            and ac.procedural_face_enabled == proc_on
            and ac.thread
            and ac.thread.is_alive()
            and agora - _ultimo_modo_proc < 2.0
        ):
            return
        _ultimo_modo_proc = agora
    _garantir_thread_anim(cli)
    try:
        cli.cancel_anim()
    except Exception:
        pass
    ac.queue.clear()
    ac.enable_animations(True)
    ac.enable_procedural_face(proc_on)
    if not getattr(modo_proc_base, "_log_ok", False):
        modo_proc_base._log_ok = True  # type: ignore[attr-defined]
        logger.info("Base OLED: procedural oficial (AnimationController 30fps)")


def garantir_display_vivo(cli: "pycozmo.Client", *, na_base: bool = True, forcar: bool = False) -> None:
    if na_base and base_oled_modo_proc():
        from cozmo_companion.core.charger import em_base

        if em_base(cli) or base_oled_usa_charger(cli):
            ligar_oled_base(cli, forcar=forcar)
            return
        modo_proc_base(cli)
        return
    if na_base and base_oled_modo_direto():
        pulse_rosto_base(cli, forcar=forcar)
        return
    ac = cli.anim_controller
    ac.enable_animations(True)
    if na_base and os.environ.get("COZMO_PROC_FACE_BASE", "0") == "1":
        ac.enable_procedural_face(True)
    elif os.environ.get("COZMO_PROC_FACE", "1") == "1":
        ac.enable_procedural_face(True)


def _limpar_fila_anim(cli: "pycozmo.Client") -> None:
    ac = cli.anim_controller
    try:
        cli.cancel_anim()
    except Exception:
        pass
    ac.queue.clear()


def pulso_sync_base(cli: "pycozmo.Client", *, forcado: bool = False) -> None:
    """SyncTime periódico na base — firmware HW5 exige sessão viva (≠ COZMO 01)."""
    global _ultimo_sync_base
    intervalo = float(os.environ.get("COZMO_SYNC_BASE_S", "8"))
    if not rx_link_ok():
        intervalo = min(intervalo, float(os.environ.get("COZMO_SYNC_BASE_RX_OFF_S", "3")))
    with _sync_base_lock:
        agora = time.monotonic()
        if not forcado and agora - _ultimo_sync_base < intervalo:
            return
        _ultimo_sync_base = agora
    try:
        cli.conn.send(protocol_encoder.SyncTime())
        cli.conn.send(protocol_encoder.Ping())
    except Exception as exc:
        logger.debug("pulso_sync_base: %s", exc)


def ping_sessao_base(cli: "pycozmo.Client", *, sync: bool = True) -> None:
    """Ping/Sync sempre — mesmo com ppclip ativo (≠ ping_oob que ignora anim)."""
    try:
        if sync:
            cli.conn.send(protocol_encoder.SyncTime())
        cli.conn.send(protocol_encoder.Ping())
    except Exception as exc:
        logger.debug("ping_sessao_base: %s", exc)


def acordar_idle_charger_boot(cli: "pycozmo.Client") -> None:
    """Boot na base: IdleOnCharger contínuo."""
    if os.environ.get("COZMO_BASE_WAKE_ANIM", "0") != "1":
        return
    if _charger_stream_ativo(cli) or _charger_keeper_ativo:
        return
    modo_charger_oled(cli, forcar=True)


def acordar_cozmo01(cli: "pycozmo.Client") -> None:
    """Recoloca olhos sem Disconnect."""
    if base_oled_minimo_ativo(cli):
        modo_oled_minimo_base(cli, forcar=True)
        return
    configurar_udp_leve_base(cli)
    parar_flood_anim(cli)
    _handshake_oled_base(cli)
    modo_base_olhos(cli)


_CLIP_NEUTRO_COZMO01 = ("CodeLabBlink", "Hiccup", "CodeLabSquint1", "IdleOnCharger")
_ultimo_recuperar_cozmo01 = 0.0


def _clip_neutro_cozmo01(cli: "pycozmo.Client") -> str:
    disp = set(cli.animation_groups.keys())
    for g in _CLIP_NEUTRO_COZMO01:
        if g in disp and len(_frames_clip_oled(cli, g)) >= 2:
            return g
    for g in disp:
        if len(_frames_clip_oled(cli, g)) >= 8:
            return g
    return "CodeLabBlink"


def _drenar_fila_anim(cli: "pycozmo.Client") -> None:
    """Espera fila anim esvaziar após cancel — evita COZMO 01 pós-notif."""
    ac = cli.anim_controller
    try:
        ac.queue.clear()
    except Exception:
        pass
    fim = time.monotonic() + float(os.environ.get("COZMO01_DRAIN_S", "4"))
    while time.monotonic() < fim:
        if ac.queue.is_empty():
            return
        time.sleep(0.08)


def detectar_cozmo01_suspeito(cli: "pycozmo.Client") -> bool:
    """Ping OK na base: sem frame OLED recente — firmware pode estar em COZMO 01."""
    from cozmo_companion.core.conexao import cozmo_alcanavel

    if not cozmo_alcanavel():
        return False
    if not rx_link_ok():
        dead_s = float(os.environ.get("COZMO01_RX_DEAD_S", "8"))
        if _rx_off_desde > 0 and time.monotonic() - _rx_off_desde >= dead_s:
            return True
        return False
    if base_oled_loop_segurado():
        return False
    if not base_oled_usa_charger(cli) and not base_oled_carga_cheia_ativo(cli):
        return False
    if _ultimo_exibir_clip_em <= 0:
        return False
    ac = cli.anim_controller
    if ac.playing_audio is True or ac.playing_animation is True:
        return False
    if _clip_loop_vivo() and _charger_anim_em_play(cli):
        return False
    if modo_sono_oled_ativo() and _clip_loop_vivo():
        return False
    timeout = float(os.environ.get("COZMO01_OLED_TIMEOUT_S", "18"))
    if _base_oled_anim_loop_ativo() and _clip_loop_vivo():
        clip_max = float(os.environ.get("COZMO_BASE_CLIP_MAX_S", "16"))
        timeout = min(_oled_max_estatico_s(), max(timeout, clip_max + 2.0))
    if modo_sono_oled_ativo():
        timeout = max(timeout, float(os.environ.get("COZMO01_SLEEP_TIMEOUT_S", "50")))
    return time.monotonic() - _ultimo_exibir_clip_em >= timeout


def _pulso_recuperar_rx(cli: "pycozmo.Client", *, tentativas: int = 5) -> bool:
    """Ping + sync — True se RX voltou (sem enqueue de clip)."""
    gap = float(os.environ.get("COZMO01_PING_GAP_S", "0.12"))
    for _ in range(max(1, tentativas)):
        ping_sessao_base(cli)
        pulso_sync_base(cli, forcado=True)
        time.sleep(gap)
        if rx_link_ok():
            return True
    return rx_link_ok()


def _sequencia_recuperar_cozmo01(cli: "pycozmo.Client") -> bool:
    """Pausa flood → drenagem → enable_animations → clip neutro → ppclip loop."""
    from cozmo_companion.core.conexao import cozmo_alcanavel

    if not cozmo_alcanavel():
        return False
    liberar_base_oled_loop_hold(motivo="cozmo01_seq")
    _normalizar_anim_id(cli)
    parar_flood_anim(cli)
    _parar_loop_clip_base(timeout=2.0)
    try:
        cli.cancel_anim()
    except Exception:
        pass
    _drenar_fila_anim(cli)
    _handshake_oled_base(cli)
    pulso_sync_base(cli, forcado=True)
    if not _pulso_recuperar_rx(cli):
        logger.warning("Recuperação OLED — RX parado após ping (sem clip)")
        return False
    ac = cli.anim_controller
    ac.enable_procedural_face(False)
    ac.enable_animations(True)
    _garantir_thread_anim(cli)
    _reset_anim_id(cli)
    if modo_sono_oled_ativo() and not sono_oled_usa_texto():
        clip_sono_base_oled(cli)
        with _charger_oled_lock:
            sono_clip = _charger_oled_nome or "GoToSleepSleeping"
        ok_clip = _exibir_clip_base(
            cli, sono_clip, forcar=True, recuperacao=False
        )
        ok_loop = _garantir_base_oled_anim_loop(cli) if rx_link_ok() else False
        logger.info(
            "Recuperação OLED — sono: clip=%s loop=%s (sem disconnect)",
            sono_clip,
            ok_loop,
        )
        return bool(ok_clip or ok_loop)
    neutro = _clip_neutro_cozmo01(cli)
    sem_rx = not rx_link_ok()
    ok_clip = _exibir_clip_base(cli, neutro, forcar=True, recuperacao=sem_rx)
    if sem_rx and ok_clip:
        time.sleep(float(os.environ.get("COZMO01_CLIP_ACK_S", "0.45")))
    ok_loop = False
    if rx_link_ok():
        if base_oled_carga_cheia_ativo(cli) or ppclip_base_ativo(cli):
            ok_loop = _garantir_base_oled_anim_loop(cli)
        else:
            acordar_cozmo01(cli)
            ok_loop = _stream_oled_estavel(cli) or _clip_loop_vivo()
    elif ok_clip:
        logger.warning(
            "Recuperação OLED — clip %s sem ACK (precisa reset UDP)",
            neutro,
        )
        return False
    if not ok_clip and sem_rx:
        logger.warning("Recuperação OLED — sem ACK após clip mínimo")
        return False
    logger.info(
        "Recuperação OLED — neutro=%s clip=%s loop=%s (sem disconnect)",
        neutro,
        ok_clip,
        ok_loop,
    )
    return bool(ok_clip or ok_loop)


def recuperar_cozmo01_auto(
    cli: "pycozmo.Client",
    monitor: object,
    medidor: object | None = None,
    *,
    forcar: bool = False,
) -> bool:
    """Tela COZMO 01: sequência agressiva — sem reconnect UDP."""
    global _ultimo_recuperar_cozmo01
    from cozmo_companion.core.conexao import cozmo_alcanavel

    if not cozmo_alcanavel():
        return False
    agora = time.monotonic()
    cooldown = float(os.environ.get("COZMO01_AUTO_COOLDOWN_S", "18"))
    if not forcar and agora - _ultimo_recuperar_cozmo01 < cooldown:
        return False
    _ultimo_recuperar_cozmo01 = agora
    _sequencia_recuperar_cozmo01(cli)
    try:
        monitor.sincronizar(cli)  # type: ignore[union-attr]
    except Exception:
        pass
    if medidor is not None:
        try:
            medidor.reset()  # type: ignore[union-attr]
        except Exception:
            pass
    return rx_link_ok()


def religar_oled_acordado_base(cli: "pycozmo.Client", *, forcar: bool = False) -> bool:
    """Sai do modo sono OLED e religa ppclip acordado (IdleOnCharger / pool vivo)."""
    global _charger_oled_nome
    definir_modo_sono_oled(False)
    desativar_sono_oled_texto()
    liberar_base_oled_loop_hold(motivo="acordar_oled")
    _parar_loop_clip_base(timeout=2.0)
    idle = (os.environ.get("COZMO_CHARGER_AWAKE_IDLE") or "IdleOnCharger").strip()
    with _charger_oled_lock:
        if idle and idle not in ("0", "off", "none") and idle in cli.animation_groups:
            _charger_oled_nome = idle
        else:
            _charger_oled_nome = _escolher_proximo_clip_base(cli) or "IdleOnCharger"
    try:
        _handshake_oled_base(cli)
        pulso_sync_base(cli)
    except Exception as exc:
        logger.warning("religar_oled_acordado: handshake %s", exc)
    if _base_oled_anim_loop_ativo():
        ok = _garantir_base_oled_anim_loop(cli)
        if ok:
            logger.info("Base OLED acordado — loop ppclip (%s)", _charger_oled_nome)
        return ok
    return bool(modo_charger_oled(cli, forcar=forcar))


def ligar_oled_base(cli: "pycozmo.Client", *, forcar: bool = False, preso_na_base: bool = False) -> None:
    """Um caminho OLED na base — clip keeper (100%%) ou stream InteractWithFace."""
    if _sono_oled_texto_ativo:
        manter_sono_oled_texto(cli)
        return
    if modo_sono_oled_ativo() and sono_oled_usa_texto():
        ativar_sono_oled_texto(cli)
        return
    if modo_sono_oled_ativo():
        manter_sono_ppclip(cli)
        return
    from cozmo_companion.core.charger import em_base

    na_base_fisico = preso_na_base or em_base(cli)
    if na_base_fisico or base_oled_usa_charger(cli):
        modo_charger_oled(cli, forcar=forcar or na_base_fisico)
        if base_oled_usa_charger(cli) and _base_oled_anim_loop_ativo():
            _iniciar_clip_base_continuo(cli)
        return
    modo_base_olhos(cli)


def modo_base_olhos(cli: "pycozmo.Client") -> None:
    global _charger_oled_nome, _charger_stream_sessao
    if modo_sono_oled_ativo() or _sono_oled_texto_ativo:
        if sono_oled_usa_texto() or _sono_oled_texto_ativo:
            manter_sono_oled_texto(cli)
        else:
            manter_sono_ppclip(cli)
        return
    from cozmo_companion.core.charger import na_base_oled

    configurar_udp_leve_base(cli)
    if na_base_oled(cli) and _charger_play_stream(cli) and base_oled_modo_proc():
        ligar_oled_base(cli, forcar=False, preso_na_base=True)
        return
    if base_oled_modo_proc() and base_oled_usa_proc_vivo(cli):
        _parar_display_keeper()
        _parar_charger_worker()
        with _charger_oled_lock:
            _charger_oled_nome = None
        _charger_stream_sessao = False
        manter_proc_vivo_base(cli)
        return
    if base_oled_usa_pulse(cli):
        _parar_display_keeper()
        parar_flood_anim(cli)
        ac = cli.anim_controller
        ac.enable_procedural_face(False)
        ac.enable_animations(False)
        pulse_rosto_base(cli, forcar=True)
        return
    if base_oled_modo_proc():
        if base_oled_carga_cheia_ativo(cli):
            if modo_charger_oled(cli):
                return
        if base_oled_minimo_ativo(cli):
            modo_oled_minimo_base(cli)
            return
        if base_oled_usa_charger(cli):
            if modo_charger_oled(cli):
                return
        if usa_keeper_base(cli):
            _iniciar_display_keeper(cli, base_proc_hz())
            return
        _parar_display_keeper()
        with _charger_oled_lock:
            _charger_oled_nome = None
        if _charger_play_stream(cli):
            from cozmo_companion.core.charger import em_base

            if em_base(cli) or base_oled_carga_cheia_ativo(cli):
                modo_charger_oled(cli, forcar=True)
                return
        from cozmo_companion.core.charger import em_base

        if em_base(cli) or base_oled_carga_cheia_ativo(cli):
            ligar_oled_base(cli, forcar=False)
            return
        modo_proc_base(cli)
    else:
        _parar_display_keeper()
        garantir_display_vivo(cli, na_base=True, forcar=True)
        cabeca_base_neutra(cli)


def modo_mesa_vivo(cli: "pycozmo.Client") -> None:
    from cozmo_companion.core.charger import base_sempre_na_carga

    if base_sempre_na_carga():
        ligar_oled_base(cli, forcar=True, preso_na_base=True)
        return
    _garantir_thread_anim(cli)
    ac = cli.anim_controller
    ac.enable_procedural_face(os.environ.get("COZMO_PROC_FACE", "1") == "1")
    ac.enable_animations(True)


def modo_tts_preparar(cli: "pycozmo.Client") -> tuple[bool, bool]:
    ac = cli.anim_controller
    face_was = ac.procedural_face_enabled
    anim_was = ac.animations_enabled
    if base_oled_usa_pulse(cli) or base_oled_modo_direto():
        parar_flood_anim(cli)
        return face_was, anim_was
    if base_oled_modo_proc():
        from cozmo_companion.core.charger import em_base

        if em_base(cli) and (
            base_oled_carga_cheia_ativo(cli) or base_oled_usa_charger(cli)
        ):
            return face_was, anim_was
        if em_base(cli) and base_oled_minimo_ativo(cli):
            parar_flood_anim(cli)
            ac.enable_procedural_face(False)
            ac.enable_animations(False)
            return face_was, anim_was
        if em_base(cli):
            _garantir_thread_anim(cli)
            ac.enable_procedural_face(False)
            ac.enable_animations(True)
            return face_was, anim_was
    _garantir_thread_anim(cli)
    ac.enable_procedural_face(False)
    ac.enable_animations(True)
    try:
        ac.cancel_anim()
    except Exception:
        pass
    return face_was, anim_was


def manter_oled_base_ativo(cli: "pycozmo.Client") -> bool:
    """Refresh leve entre clips — não reinicia anim."""
    if _sono_oled_texto_ativo:
        manter_sono_oled_texto(cli)
        return True
    if modo_sono_oled_ativo():
        if not rx_link_ok():
            return False
        manter_sono_ppclip(cli)
        return True
    if not base_oled_usa_charger(cli) or not _oled_sessao_viva(cli):
        return False
    if _base_oled_anim_loop_ativo() and not _clip_loop_vivo():
        return _garantir_base_oled_anim_loop(cli)
    ac = cli.anim_controller
    pkt = ac.last_image_pkt
    if _imagem_vazia(pkt):
        with _charger_oled_lock:
            grupo = _charger_oled_nome
        return _semear_oled_charger(cli, grupo)
    try:
        cli.conn.send(pkt)
        return True
    except Exception:
        return False


def modo_tts_restaurar(cli: "pycozmo.Client", face_was: bool, anim_was: bool, *, na_base: bool) -> None:
    if na_base:
        if _sono_oled_texto_ativo:
            manter_sono_oled_texto(cli)
            return
        if modo_sono_oled_ativo():
            manter_sono_ppclip(cli)
            return
        if base_oled_usa_proc_vivo(cli):
            manter_proc_vivo_base(cli)
        elif base_oled_usa_charger(cli):
            if (
                _base_oled_anim_loop_ativo()
                and rx_link_ok()
                and not base_oled_loop_segurado()
            ):
                _garantir_base_oled_anim_loop(cli)
            else:
                with _charger_oled_lock:
                    grupo = _charger_oled_nome
                if grupo:
                    _exibir_clip_base(cli, grupo, forcar=False) or manter_oled_base_ativo(cli)
                else:
                    modo_charger_oled(cli, forcar=True)
        else:
            modo_base_olhos(cli)
        return
    ac = cli.anim_controller
    ac.enable_procedural_face(face_was or os.environ.get("COZMO_PROC_FACE", "1") == "1")
    ac.enable_animations(anim_was)


def base_suprime_oled_texto(cli: "pycozmo.Client") -> bool:
    """Na base com anim OLED: notificações não podem trocar por texto estático."""
    if modo_sono_oled_ativo():
        return False
    if os.environ.get("COZMO_OLED_NA_BASE", "0") == "1":
        return False
    from cozmo_companion.core.charger import na_base_oled

    return na_base_oled(cli) and base_oled_usa_charger(cli)


def _oled_tx_direto(cli: "pycozmo.Client") -> bool:
    """HW5 100%%: fila do AnimationController sem animations_enabled = tela preta."""
    if base_oled_modo_direto() or os.environ.get("COZMO_OLED_DIRECT", "0") == "1":
        return True
    if keeper_base_ativo() or _charger_keeper_ativo:
        return True
    if base_oled_usa_charger(cli) and (
        base_oled_carga_cheia_ativo(cli)
        or os.environ.get("COZMO_BASE_KEEPER_VIVO", "0") == "1"
    ):
        return True
    return False


def enviar_oled(cli: "pycozmo.Client", pkt: protocol_encoder.DisplayImage) -> None:
    if _oled_tx_direto(cli):
        _handshake_frame_oled(cli)
        cli.conn.send(pkt)
        ac = cli.anim_controller
        ac.last_image_pkt = pkt
        if _imagem_vazia(ac.last_image_pkt):
            ac.last_image_pkt = pkt
    else:
        cli.anim_controller.display_image(pkt)


def ping_oob(cli: "pycozmo.Client", vezes: int = 1) -> None:
    ac = cli.anim_controller
    if ac.animations_enabled and (
        ac.procedural_face_enabled or ac.playing_animation or ac.playing_audio
    ):
        return
    for _ in range(max(1, vezes)):
        try:
            cli.conn.send(protocol_encoder.Ping())
        except Exception:
            pass
        time.sleep(0.08)


def enviar_audio_fila(
    cli: "pycozmo.Client",
    pkt: protocol_encoder.OutputAudio,
    *,
    manter_face: bool = False,
) -> None:
    # Sinal curto na base com ppclip: conn.send direto (play_audio → EOFError).
    if manter_face and (base_oled_usa_charger(cli) or base_oled_carga_cheia_ativo(cli)):
        try:
            cli.conn.send(pkt)
            time.sleep(max(FRAME_S * 2, 0.05))
            return
        except Exception:
            pass
    if base_oled_usa_pulse(cli) or base_oled_modo_direto():
        parar_flood_anim(cli)
        cli.conn.send(pkt)
        time.sleep(max(FRAME_S * 2, 0.05))
        pulse_rosto_base(cli, forcar=True)
        manter_oled_pulse(cli, forcar=True)
        return
    ac = cli.anim_controller
    if manter_face and base_oled_modo_proc():
        from cozmo_companion.core.charger import em_base

        if em_base(cli):
            if base_oled_minimo_ativo(cli):
                cli.conn.send(pkt)
                time.sleep(max(FRAME_S * 2, 0.05))
                return
            if base_oled_usa_charger(cli):
                ac.enable_animations(True)
                _garantir_thread_anim(cli)
                try:
                    ac.play_audio([pkt])
                except Exception:
                    try:
                        cli.conn.send(pkt)
                    except Exception:
                        pass
                time.sleep(max(FRAME_S * 2, 0.05))
                with _charger_oled_lock:
                    grupo = _charger_oled_nome
                if grupo:
                    if _charger_play_stream(cli):
                        _replay_anim_charger(cli, grupo)
                    else:
                        _semear_oled_charger(cli, grupo)
                _refresh_sessao_oled_leve(cli)
                return
            if usa_keeper_base(cli):
                cli.conn.send(pkt)
                time.sleep(max(FRAME_S * 2, 0.05))
                return
            modo_proc_base(cli)
            ac.play_audio([pkt])
            time.sleep(max(FRAME_S * 2, 0.05))
            return
    ac.enable_procedural_face(False)
    ac.enable_animations(True)
    _garantir_thread_anim(cli)
    ac.play_audio([pkt])
    time.sleep(max(FRAME_S * 2, 0.05))


_ANIM_IDLE_BASE = frozenset(
    {
        "IdleOnCharger",
        "IdleOnChargerCharging",
        "LookInPlaceForFacesHeadMovePause",
        "NeutralFace",
        "InterestedFace",
        "Hiccup",
        "HiccupGetIn",
        "CodeLabHiccup",
    }
)


def animar_idle_charger_base(cli: "pycozmo.Client") -> bool:
    """HW5 na base: religa IdleOnCharger sem cancelar (≠ COZMO 01)."""
    if modo_sono_oled_ativo() or _sono_oled_texto_ativo:
        manter_sono_ppclip(cli)
        return True
    global _ultimo_idle_charger_global
    if not base_oled_usa_charger(cli):
        return False
    min_s = float(os.environ.get("COZMO_CHARGE_IDLE_S", "18"))
    with _idle_charger_lock:
        agora = time.monotonic()
        if agora - _ultimo_idle_charger_global < min_s:
            return False
        _ultimo_idle_charger_global = agora
    return modo_charger_oled(cli, forcar=True)


def animar_grupo(
    cli: "pycozmo.Client",
    nome: str,
    *,
    na_base: bool,
    procedural_antes: bool,
) -> bool:
    del procedural_antes
    if not nome:
        return False
    if na_base:
        from cozmo_companion.core.anims import permitido_sem_rodas_na_base

        if not permitido_sem_rodas_na_base(nome):
            logger.debug("Anim %s bloqueada na base", nome)
            modo_base_olhos(cli)
            return False
        if base_oled_usa_charger(cli):
            if nome in ("IdleOnCharger", "IdleOnChargerCharging"):
                return modo_charger_oled(cli, forcar=True)
            if tocar_clip_base_seguro(cli, nome):
                logger.info("Anim base ppclip: %s", nome)
                return True
            if base_oled_loop_segurado() or (
                _base_oled_anim_loop_ativo() and _clip_loop_vivo()
            ):
                logger.debug("Anim %s adiada — loop OLED ocupado", nome)
                return False
            return modo_charger_oled(cli, forcar=False)
        _limpar_fila_anim(cli)
        parar_flood_anim(cli)
        ac = cli.anim_controller
        ac.enable_procedural_face(False)
        ac.enable_animations(False)
        try:
            _reset_anim_id(cli)
            cli.play_anim_group(nome)
            logger.info("Anim base permitida: %s", nome)
            return True
        except Exception as exc:
            logger.warning("anim base %s falhou: %s", nome, exc)
            modo_base_olhos(cli)
            return False
    _garantir_thread_anim(cli)
    ac = cli.anim_controller
    try:
        cli.cancel_anim()
    except Exception:
        pass
    cli.stop_all_motors()
    ac.enable_animations(True)
    ac.enable_procedural_face(False)
    try:
        cli.play_anim_group(nome)
        logger.info("Anim: %s (base=%s)", nome, na_base)
        return True
    except Exception as exc:
        logger.warning("anim %s falhou: %s", nome, exc)
        return False


def restaurar_apos_anim_base(cli: "pycozmo.Client") -> None:
    modo_base_olhos(cli)


def olhos_procedural(cli: "pycozmo.Client", *, ativo: bool, na_base: bool = True) -> None:
    if na_base and base_oled_modo_direto():
        if ativo:
            pulse_rosto_base(cli)
        return
    if na_base and ativo:
        modo_base_olhos(cli)
        return
    ac = cli.anim_controller
    ac.enable_procedural_face(ativo)
    if ativo:
        ac.enable_animations(True)


def vigiar_flood_base(cli: "pycozmo.Client") -> bool:
    if _sono_oled_texto_ativo or modo_sono_oled_ativo():
        if modo_sono_oled_ativo() and not _sono_oled_texto_ativo:
            manter_sono_ppclip(cli)
        return False
    if not _oled_sessao_viva(cli):
        return False
    if base_oled_carga_cheia_ativo(cli) and keeper_base_ativo():
        _refresh_sessao_oled_leve(cli)
        return False
    if base_oled_carga_cheia_ativo(cli) and os.environ.get("COZMO_BASE_KEEPER_VIVO", "0") == "1":
        if _base_oled_anim_loop_ativo():
            if not _base_anim_loop_vivo():
                _ativar_oled_keeper_vivo(cli, time.monotonic())
        elif not keeper_base_ativo():
            _ativar_oled_keeper_vivo(cli, time.monotonic())
        _refresh_sessao_oled_leve(cli)
        return False
    if base_oled_carga_cheia_ativo(cli) and _charger_play_stream(cli):
        if not _charger_worker_vivo():
            modo_charger_oled(cli, forcar=False)
        _refresh_sessao_oled_leve(cli)
        return False
    if base_oled_usa_proc_vivo(cli):
        manter_proc_vivo_base(cli)
        _refresh_sessao_oled_leve(cli)
        return False
    if base_oled_usa_charger(cli) or _charger_stream_sessao:
        ac = cli.anim_controller
        ac.enable_procedural_face(False)
        if _charger_keeper_ativo and _base_oled_anim_loop_ativo():
            if not _clip_loop_vivo() and not base_oled_loop_segurado():
                _garantir_base_oled_anim_loop(cli)
            elif _clip_loop_vivo():
                _refresh_sessao_oled_leve(cli)
            _refresh_sessao_oled_leve(cli)
            return False
        if _charger_stream_sessao and not _charger_keeper_ativo:
            if not _anim_thread_viva(cli):
                _ligar_anim_charger(cli)
            if not _charger_worker_vivo():
                _garantir_charger_worker(cli)
            return False
        if _charger_stream_ativo(cli):
            if not _anim_thread_viva(cli):
                _ligar_anim_charger(cli)
            if not _charger_worker_vivo():
                _garantir_charger_worker(cli)
            return False
        if _charger_keeper_ativo and not _base_oled_anim_loop_ativo():
            with _charger_oled_lock:
                grupo = _charger_oled_nome
            if grupo and not keeper_base_ativo():
                _iniciar_keeper_clip_oled_base(cli, grupo)
            elif ac.thread and ac.thread.is_alive():
                _parar_thread_anim(cli)
            if not keeper_base_ativo():
                ac.enable_animations(False)
            _refresh_sessao_oled_leve(cli)
            return False
        if keeper_base_ativo():
            _refresh_sessao_oled_leve(cli)
            return False
        _parar_display_keeper()
        if ac.thread and ac.thread.is_alive():
            _parar_thread_anim(cli)
        elif ac.animations_enabled or ac.procedural_face_enabled:
            ac.enable_animations(False)
        if not charger_oled_ativo(cli):
            return modo_charger_oled(cli, forcar=False)
        return False
    if base_oled_usa_pulse(cli):
        parar_flood_anim(cli)
        ac = cli.anim_controller
        if ac.thread and ac.thread.is_alive():
            logger.warning("Base pulse: thread 30fps ainda ativa — parando")
            _parar_thread_anim(cli)
        manter_oled_pulse(cli)
        return pulse_rosto_base(cli) or True
    if usa_keeper_base(cli):
        if not keeper_base_ativo():
            logger.warning("Base keeper OLED parado — religando")
            _iniciar_display_keeper(cli, base_proc_hz())
            return True
        if cli.anim_controller.thread and cli.anim_controller.thread.is_alive():
            parar_flood_anim(cli)
        return False
    if base_oled_modo_proc():
        if _charger_stream_sessao or _charger_keeper_ativo:
            return False
        from cozmo_companion.core.charger import em_base

        if em_base(cli) and (
            base_oled_carga_cheia_ativo(cli) or charger_oled_ativo(cli)
        ):
            return False
        ac = cli.anim_controller
        if not ac.animations_enabled or not ac.procedural_face_enabled:
            if em_base(cli) or base_oled_carga_cheia_ativo(cli) or base_oled_usa_charger(cli):
                if not oled_charger_vivo(cli):
                    logger.warning("Base OLED parado — religando clip/stream")
                    ligar_oled_base(cli, forcar=True)
                return True
            if _charger_play_stream(cli) and (
                _charger_stream_sessao or em_base(cli) or base_oled_carga_cheia_ativo(cli)
            ):
                if not oled_charger_vivo(cli):
                    modo_charger_oled(cli, forcar=False)
                return False
            logger.warning("Base: procedural caiu — religando (mesa)")
            modo_proc_base(cli)
            return True
        return False
    if not base_oled_modo_direto():
        return False
    ac = cli.anim_controller
    if ac.thread and ac.thread.is_alive():
        logger.warning("Base: thread anim ativa no modo direct — parando")
        parar_flood_anim(cli)
        return pulse_rosto_base(cli, forcar=True)
    return False


def anim_flood_ativo(cli: "pycozmo.Client") -> bool:
    if base_oled_modo_proc():
        return False
    ac = cli.anim_controller
    if base_oled_modo_direto() and ac.thread and ac.thread.is_alive():
        return True
    return bool(ac.animations_enabled or ac.procedural_face_enabled)
