"""Na base: edita clips — sem rodas, sem braço/elevador, cabeça neutra."""

from __future__ import annotations

import logging
import math
import os
import random
from collections import defaultdict
from typing import TYPE_CHECKING

from pycozmo import anim as pycozmo_anim
from pycozmo import anim_encoder
from pycozmo import protocol_encoder
from pycozmo import robot

if TYPE_CHECKING:
    import pycozmo

logger = logging.getLogger("cozmo.anim_patch")

_CACHE_ATTR = "_ppclips_sem_rodas_na_base"
_CACHE_VER = 3

_TIPOS_KEYFRAME_SEM_RODAS = (
    anim_encoder.AnimBodyMotion,
    anim_encoder.AnimRecordHeading,
    anim_encoder.AnimTurnToRecordedHeading,
    anim_encoder.AnimLiftHeight,
)

_TIPOS_PACOTE_SEM_RODAS = (
    protocol_encoder.DriveWheels,
    protocol_encoder.TurnInPlaceAtSpeed,
    protocol_encoder.AnimBody,
    protocol_encoder.TurnInPlace,
    protocol_encoder.RecordHeading,
    protocol_encoder.TurnToRecordedHeading,
    protocol_encoder.MoveLift,
    protocol_encoder.AnimLift,
    protocol_encoder.SetLiftHeight,
)

# Cabeça: só micro-movimento (graus) — evita “bater” / sair da base.
_HEAD_MAX_DEG = float(os.environ.get("COZMO_BASE_HEAD_MAX_DEG", "6"))


def _na_base_anim(cli: "pycozmo.Client") -> bool:
    from cozmo_companion.core.charger import na_base_oled

    return na_base_oled(cli)


def _angulo_cabeca_graus() -> int:
    from cozmo_companion.core.motor_cozmo import angulo_cabeca_neutro

    deg = math.degrees(angulo_cabeca_neutro())
    return max(-25, min(25, int(round(deg))))


def _lift_min_mm() -> int:
    return int(robot.MIN_LIFT_HEIGHT.mm)


def clip_imobilizar_na_base(clip: anim_encoder.AnimClip) -> anim_encoder.AnimClip:
    """Remove drive/elevador; cabeça limitada ao neutro ±COZMO_BASE_HEAD_MAX_DEG."""
    neutro = _angulo_cabeca_graus()
    max_d = float(_HEAD_MAX_DEG)
    kf_out: list[anim_encoder.AnimKeyframe] = []
    for k in clip.keyframes:
        if isinstance(k, _TIPOS_KEYFRAME_SEM_RODAS):
            continue
        if isinstance(k, anim_encoder.AnimHeadAngle):
            ang = max(neutro - max_d, min(neutro + max_d, float(k.angle_deg)))
            kf_out.append(
                anim_encoder.AnimHeadAngle(
                    trigger_time_ms=k.trigger_time_ms,
                    duration_ms=k.duration_ms,
                    angle_deg=ang,
                    variability_deg=0.0,
                )
            )
            continue
        kf_out.append(k)
    return anim_encoder.AnimClip(name=clip.name, keyframes=kf_out)


def clip_remover_movimento_rodas(clip: anim_encoder.AnimClip) -> anim_encoder.AnimClip:
    return clip_imobilizar_na_base(clip)


def _ajustar_pacote_base(pkt: object) -> object | None:
    """None = remover pacote da reprodução na base."""
    if isinstance(pkt, _TIPOS_PACOTE_SEM_RODAS):
        return None
    if isinstance(pkt, protocol_encoder.MoveHead):
        return None
    if isinstance(pkt, protocol_encoder.AnimHead):
        neutro = _angulo_cabeca_graus()
        max_d = int(_HEAD_MAX_DEG)
        ang = max(neutro - max_d, min(neutro + max_d, int(pkt.angle_deg)))
        return protocol_encoder.AnimHead(
            duration_ms=pkt.duration_ms,
            variability_deg=0,
            angle_deg=ang,
        )
    return pkt


def ppclip_filtrar_pacotes_rodas(
    pp: pycozmo_anim.PreprocessedClip,
) -> pycozmo_anim.PreprocessedClip:
    """Remove pacotes de corpo na base."""
    out: dict[int, list] = defaultdict(list)
    for t_ms, pacotes in pp.keyframes.items():
        for pkt in pacotes:
            p2 = _ajustar_pacote_base(pkt)
            if p2 is not None:
                out[t_ms].append(p2)
    return pycozmo_anim.PreprocessedClip(out)


def ppclip_tem_frame_oled(pp: pycozmo_anim.PreprocessedClip) -> bool:
    for pacotes in pp.keyframes.values():
        for pkt in pacotes:
            if isinstance(pkt, protocol_encoder.DisplayImage):
                img = getattr(pkt, "image", None)
                if img and img != b"\x3f\x3f":
                    return True
    return False


def ppclip_total_frames_oled(pp: pycozmo_anim.PreprocessedClip) -> int:
    return sum(
        1
        for pacotes in pp.keyframes.values()
        for pkt in pacotes
        if isinstance(pkt, protocol_encoder.DisplayImage)
        and getattr(pkt, "image", None)
        and getattr(pkt, "image", None) != b"\x3f\x3f"
    )


def ppclips_validos_do_grupo(
    cli: "pycozmo.Client", grupo: str, *, min_frames: int | None = None
) -> tuple[tuple[str, pycozmo_anim.PreprocessedClip], ...]:
    """Membros do grupo com OLED real, sem o sorteio instável do PyCozmo."""
    ag = cli.animation_groups.get(grupo)
    if not ag:
        return ()
    minimo = max(
        2,
        min_frames
        if min_frames is not None
        else int(os.environ.get("COZMO_BASE_OLED_MIN_FRAMES", "8")),
    )
    todos: list[tuple[str, pycozmo_anim.PreprocessedClip]] = []
    fallback: list[tuple[str, pycozmo_anim.PreprocessedClip]] = []
    for membro in ag.members:
        try:
            pp = obter_ppclip_sem_rodas(cli, membro.name)
        except (KeyError, ValueError):
            continue
        total = ppclip_total_frames_oled(pp)
        if total >= 2:
            fallback.append((membro.name, pp))
        if total >= minimo:
            todos.append((membro.name, pp))
    return tuple(todos or fallback)


def obter_ppclip_sem_rodas(cli: "pycozmo.Client", anim_name: str) -> pycozmo_anim.PreprocessedClip:
    """Cache de ppclip editado para a base."""
    cache: dict[str, pycozmo_anim.PreprocessedClip] = getattr(cli, _CACHE_ATTR, None) or {}
    if not hasattr(cli, _CACHE_ATTR):
        setattr(cli, _CACHE_ATTR, cache)
    chave = f"v{_CACHE_VER}:{anim_name}"
    if chave in cache:
        return cache[chave]
    meta = cli._clip_metadata.get(anim_name)
    if not meta:
        raise ValueError(f"clip desconhecido: {anim_name}")
    if anim_name not in cli._clips:
        cli._load_clips(meta.fspec)
    clip = cli._clips[anim_name]
    removidos = sum(1 for k in clip.keyframes if isinstance(k, _TIPOS_KEYFRAME_SEM_RODAS))
    clip_base = clip_imobilizar_na_base(clip)
    pp = pycozmo_anim.PreprocessedClip.from_anim_clip(clip_base)
    pp = ppclip_filtrar_pacotes_rodas(pp)
    cache[chave] = pp
    if removidos:
        logger.debug(
            "Base anim %s: imobilizado (%d kf corpo removidos)",
            anim_name,
            removidos,
        )
    return pp


_FALLBACK_GRUPOS = ("IdleOnCharger", "NeutralFace", "InterestedFace")


def play_clip_sem_rodas_na_base(cli: "pycozmo.Client", anim_name: str) -> bool:
    """Toca clip editado; False se inválido (evita COZMO 01)."""
    try:
        pp = obter_ppclip_sem_rodas(cli, anim_name)
        if not ppclip_tem_frame_oled(pp):
            logger.warning("Base clip %s sem frame OLED — ignorado", anim_name)
            return False
        cli.play_anim_ppclip(pp)
        return True
    except Exception as exc:
        logger.warning("Base clip %s falhou: %s", anim_name, exc)
        return False


def play_grupo_sem_rodas_na_base(cli: "pycozmo.Client", grupo: str) -> bool:
    validos = ppclips_validos_do_grupo(cli, grupo)
    if validos:
        nome, pp = random.choice(validos)
        try:
            cli.play_anim_ppclip(pp)
            logger.debug("Base grupo %s: membro OLED %s", grupo, nome)
            return True
        except Exception as exc:
            logger.warning("Base grupo %s membro %s falhou: %s", grupo, nome, exc)
    for fb in _FALLBACK_GRUPOS:
        opcoes = ppclips_validos_do_grupo(cli, fb, min_frames=2)
        if opcoes and play_clip_sem_rodas_na_base(cli, random.choice(opcoes)[0]):
            logger.info("Base OLED: fallback %s (grupo %s falhou)", fb, grupo)
            return True
    return False


def instalar_play_anim_sem_rodas_na_base(
    cli: "pycozmo.Client",
    *,
    preso_na_base_fn,
) -> None:
    """Na base: play_anim / play_anim_ppclip sem movimento de corpo."""
    from cozmo_companion.core.motor_cozmo import (
        _capturar_ppclip_core,
        instalar_anim_id_seguro,
    )

    _capturar_ppclip_core(cli)
    if getattr(cli, "_cozmo_sem_rodas_patch", False):
        setattr(cli, _CACHE_ATTR, {})
        instalar_anim_id_seguro(cli)
        return

    orig_play = cli.play_anim
    orig_group = cli.play_anim_group
    core_ppclip = cli._cozmo_ppclip_core  # type: ignore[attr-defined]

    def play_anim_patch(name: str) -> None:
        if preso_na_base_fn() or _na_base_anim(cli):
            if not play_clip_sem_rodas_na_base(cli, name):
                play_grupo_sem_rodas_na_base(cli, "IdleOnCharger")
            return
        orig_play(name)

    def play_group_patch(anim_group_name: str) -> None:
        if preso_na_base_fn() or _na_base_anim(cli):
            if not play_grupo_sem_rodas_na_base(cli, anim_group_name):
                play_grupo_sem_rodas_na_base(cli, "IdleOnCharger")
            return
        orig_group(anim_group_name)

    def play_ppclip_patch(pp: pycozmo_anim.PreprocessedClip) -> None:
        if preso_na_base_fn() or _na_base_anim(cli):
            pp2 = ppclip_filtrar_pacotes_rodas(pp)
            if ppclip_tem_frame_oled(pp2):
                core_ppclip(pp2)
            return
        core_ppclip(pp)

    cli.play_anim = play_anim_patch  # type: ignore[method-assign]
    cli.play_anim_group = play_group_patch  # type: ignore[method-assign]
    cli.play_anim_ppclip = play_ppclip_patch  # type: ignore[method-assign]
    cli._cozmo_sem_rodas_patch = True  # type: ignore[attr-defined]
    setattr(cli, _CACHE_ATTR, {})
    instalar_anim_id_seguro(cli)
    logger.info(
        "Base: clips imobilizados (sem roda/elevador/braço; cabeça ±%.0f°)",
        _HEAD_MAX_DEG,
    )
