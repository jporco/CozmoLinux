"""Rosto OLED em pacotes DisplayImage — procedural no estilo Cozmo.

O caminho da base não pode usar o AnimationController 30fps continuamente,
porque no HW5 real isso travou RX e voltou para COZMO 01. Este módulo renderiza
frames proceduralmente usando o mesmo modelo visual do pycozmo e envia só
keyframes pelo keeper leve.
"""

from __future__ import annotations

import math
import random
import threading
from collections import deque
import logging

import numpy as np
from PIL import Image
from pycozmo import image_encoder, protocol_encoder
from pycozmo.procedural_face import ProceduralFace

_visible_lock = threading.Lock()
_visible_idx = 0
_reaction_expr: str | None = None
_reaction_frames = 0
_idle_expr: str = "idle"
_idle_hold_frames = 0
_recent_exprs: deque[str] = deque(maxlen=5)
_rng = random.Random()
logger = logging.getLogger("cozmo.rosto")

LARGURA = 128
ALTURA = 32

_ALIASES = {
    "idle": "idle",
    "curious": "curious",
    "wake": "curious",
    "focused": "focused",
    "sound": "surprise",
    "surprise": "surprise",
    "awe": "awe",
    "happy": "happy",
    "pet": "glee",
    "glee": "glee",
    "sleep": "sleepy",
    "sleepy": "sleepy",
    "dark": "sleepy",
    "escuro": "sleepy",
    "bored": "bored",
    "annoyed": "annoyed",
    "skeptical": "skeptical",
    "worried": "worried",
    "sad": "sad",
    "angry": "angry",
    "scared": "scared",
    "blink": "blink",
}

_IDLE_POOL: tuple[tuple[str, float], ...] = (
    # Na câmera/OLED real, diferenças sutis somem. O "idle" fica leve e o
    # descanso vira uma rotação de micro-estados, sem depender de comandos.
    ("curious", 13),
    ("focused", 11),
    ("skeptical", 9),
    ("happy", 8),
    ("bored", 7),
    ("awe", 6),
    ("worried", 6),
    ("surprise", 5),
    ("glee", 4),
    ("annoyed", 4),
    ("scared", 3),
    ("sad", 3),
    ("idle", 2),
)


def solicitar_reacao_visual(tipo: str, *, frames: int = 5) -> None:
    """Agenda uma expressão curta para o keeper OLED da base."""
    global _reaction_expr, _reaction_frames, _idle_hold_frames
    with _visible_lock:
        _reaction_expr = _normalizar_expr(tipo)
        _reaction_frames = max(1, int(frames))
        _idle_hold_frames = 0


def _normalizar_expr(tipo: str | None) -> str:
    return _ALIASES.get((tipo or "").strip().lower(), "curious")


def _reset_estado_para_teste(seed: int = 1) -> None:
    """Reseta o gerador procedural para testes determinísticos."""
    global _visible_idx, _reaction_expr, _reaction_frames
    global _idle_expr, _idle_hold_frames
    with _visible_lock:
        _visible_idx = 0
        _reaction_expr = None
        _reaction_frames = 0
        _idle_expr = "idle"
        _idle_hold_frames = 0
        _recent_exprs.clear()
        _rng.seed(seed)


def _encode_face(im: Image.Image) -> protocol_encoder.DisplayImage:
    arr = np.array(im)
    if arr.ndim >= 2 and (arr.shape[0] != ALTURA or arr.shape[1] != LARGURA):
        pil = Image.fromarray(arr).resize((LARGURA, ALTURA))
    else:
        pil = Image.fromarray(arr)
    if pil.size != (LARGURA, ALTURA):
        pil = pil.resize((LARGURA, ALTURA))
    if pil.mode != "1":
        pil = pil.convert("1")
    enc = image_encoder.ImageEncoder(pil)
    return protocol_encoder.DisplayImage(image=bytes(enc.encode()))


def _base_face(idx: int) -> ProceduralFace:
    face = ProceduralFace(width=128, height=64)
    # Olhos um pouco mais próximos, como no app original.
    face.eyes[0].center_x += 9
    face.eyes[1].center_x -= 9
    # Saccades discretos e irregulares. O keeper roda lento, então cada frame
    # precisa parecer vivo sem depender de 30fps.
    fase_x = (-8, -4, 0, 5, 8, 2, -5, 0)[(idx // 3) % 8]
    fase_y = (0, -7, -2, 4, 0, -4, 5, 0)[(idx // 5) % 8]
    face.center_x = fase_x
    face.center_y = fase_y + math.sin(idx * 0.45) * 2.0
    return face


def _set_top(face: ProceduralFace, y: float, *, bend: float = 0.25, angle_l: float = 0.0, angle_r: float = 0.0) -> None:
    face.eyes[0].lids[0].y = y
    face.eyes[1].lids[0].y = y
    face.eyes[0].lids[0].bend = bend
    face.eyes[1].lids[0].bend = bend
    face.eyes[0].lids[0].angle = angle_l
    face.eyes[1].lids[0].angle = angle_r


def _set_bottom(face: ProceduralFace, y: float, *, bend: float = 0.25, angle_l: float = 0.0, angle_r: float = 0.0) -> None:
    face.eyes[0].lids[1].y = y
    face.eyes[1].lids[1].y = y
    face.eyes[0].lids[1].bend = bend
    face.eyes[1].lids[1].bend = bend
    face.eyes[0].lids[1].angle = angle_l
    face.eyes[1].lids[1].angle = angle_r


def _aplicar_expr(face: ProceduralFace, expr: str, idx: int) -> None:
    expr = _normalizar_expr(expr)
    pulse = math.sin(idx * 0.7) * 0.04

    if expr == "idle":
        face.eyes[0].scale_y = 0.92 + pulse
        face.eyes[1].scale_y = 0.92 - pulse
        return

    if expr == "curious":
        face.eyes[0].scale_x = 1.12
        face.eyes[0].scale_y = 1.06
        face.eyes[1].scale_x = 0.92
        face.eyes[1].scale_y = 0.82
        face.eyes[0].angle = -2
        face.eyes[1].angle = 2
        face.center_x += 5
        return

    if expr == "focused":
        face.eyes[0].scale_y = 0.72
        face.eyes[1].scale_y = 0.72
        face.eyes[0].scale_x = 1.12
        face.eyes[1].scale_x = 1.12
        _set_top(face, 0.18, bend=0.15)
        _set_bottom(face, 0.12, bend=0.1)
        return

    if expr == "skeptical":
        face.eyes[0].scale_y = 0.72
        face.eyes[1].scale_y = 0.95
        _set_top(face, 0.22, bend=0.2, angle_l=-7, angle_r=4)
        face.center_x -= 4
        return

    if expr == "happy":
        face.eyes[0].scale_x = 1.12
        face.eyes[1].scale_x = 1.12
        face.eyes[0].scale_y = 0.74
        face.eyes[1].scale_y = 0.74
        _set_top(face, 0.24, bend=0.45)
        face.center_y -= 5
        return

    if expr == "glee":
        face.eyes[0].scale_x = 1.35
        face.eyes[1].scale_x = 1.35
        face.eyes[0].scale_y = 0.62
        face.eyes[1].scale_y = 0.62
        _set_top(face, 0.34, bend=0.65)
        face.center_y -= 6
        return

    if expr == "surprise":
        face.eyes[0].scale_x = 1.05
        face.eyes[1].scale_x = 1.05
        face.eyes[0].scale_y = 1.18
        face.eyes[1].scale_y = 1.18
        face.center_y -= 5
        return

    if expr == "awe":
        face.eyes[0].scale_x = 1.25
        face.eyes[1].scale_x = 1.25
        face.eyes[0].scale_y = 1.22
        face.eyes[1].scale_y = 1.22
        face.center_y -= 4
        return

    if expr == "worried":
        face.eyes[0].scale_y = 0.88
        face.eyes[1].scale_y = 0.88
        _set_top(face, 0.15, bend=0.25, angle_l=7, angle_r=-7)
        _set_bottom(face, 0.10, bend=0.1)
        face.center_y += 4
        return

    if expr == "sad":
        face.eyes[0].scale_y = 0.72
        face.eyes[1].scale_y = 0.72
        _set_top(face, 0.28, bend=0.25, angle_l=8, angle_r=-8)
        _set_bottom(face, 0.18, bend=0.2)
        face.center_y += 10
        return

    if expr == "bored":
        face.eyes[0].scale_x = 1.25
        face.eyes[1].scale_x = 1.25
        face.eyes[0].scale_y = 0.40
        face.eyes[1].scale_y = 0.40
        _set_top(face, 0.30, bend=0.15)
        face.center_y += 5
        return

    if expr == "annoyed":
        face.eyes[0].scale_y = 0.55
        face.eyes[1].scale_y = 0.55
        _set_top(face, 0.33, bend=0.2, angle_l=-6, angle_r=6)
        face.eyes[0].angle = -2
        face.eyes[1].angle = 2
        return

    if expr == "angry":
        face.eyes[0].scale_y = 0.62
        face.eyes[1].scale_y = 0.62
        face.eyes[0].scale_x = 1.12
        face.eyes[1].scale_x = 1.12
        _set_top(face, 0.35, bend=0.15, angle_l=-12, angle_r=12)
        _set_bottom(face, 0.10, bend=0.1, angle_l=4, angle_r=-4)
        return

    if expr == "scared":
        face.eyes[0].scale_y = 1.12
        face.eyes[1].scale_y = 1.12
        _set_bottom(face, 0.18, bend=0.3)
        face.center_y -= 3
        return

    if expr == "sleepy":
        face.eyes[0].scale_x = 1.35
        face.eyes[1].scale_x = 1.35
        face.eyes[0].scale_y = 0.22
        face.eyes[1].scale_y = 0.22
        _set_top(face, 0.40, bend=0.6)
        face.center_y += 7
        return

    if expr == "blink":
        # Nunca y=0: a OLED não pode parecer apagada.
        face.eyes[0].scale_x = 1.65
        face.eyes[1].scale_x = 1.65
        face.eyes[0].scale_y = 0.18
        face.eyes[1].scale_y = 0.18
        face.center_y += 2


def _render_olhos_visiveis(expr: str, idx: int) -> Image.Image:
    face = _base_face(idx)
    _aplicar_expr(face, expr, idx)
    for eye in face.eyes:
        # A câmera/webcam e o OLED real deixam diferenças sutis parecidas.
        # Aumenta a assinatura visual sem voltar ao desenho genérico antigo.
        eye.scale_x *= 1.18
        eye.scale_y *= 1.08
    im64 = face.render()
    im32 = Image.fromarray(np.array(im64)[::2]).convert("1")
    return im32.resize((LARGURA, ALTURA)) if im32.size != (LARGURA, ALTURA) else im32


def _expressao_idle(idx: int) -> str:
    global _idle_expr, _idle_hold_frames
    # Piscadas são raras e curtas; não entram como "estado" para não virar
    # repetição visível em 0.5 Hz.
    if idx % 29 == 7 or idx % 47 == 19:
        return "blink"

    if _idle_hold_frames > 0:
        _idle_hold_frames -= 1
        return _idle_expr

    candidatos = [
        (expr, peso)
        for expr, peso in _IDLE_POOL
        if expr not in _recent_exprs
    ]
    if not candidatos:
        candidatos = list(_IDLE_POOL)
    exprs, pesos = zip(*candidatos)
    _idle_expr = _rng.choices(exprs, weights=pesos, k=1)[0]
    _recent_exprs.append(_idle_expr)
    # Não segura por padrão. A taxa real pode cair para 0.5 Hz em link ruim; se
    # segurarmos frames aqui, a webcam enxerga sempre as mesmas 2-3 expressões.
    _idle_hold_frames = 0
    return _idle_expr


def _proximo_frame_visivel() -> Image.Image:
    global _visible_idx, _reaction_expr, _reaction_frames
    with _visible_lock:
        _visible_idx += 1
        if _reaction_frames > 0 and _reaction_expr:
            expr = _reaction_expr
            _reaction_frames -= 1
            if _reaction_frames <= 0:
                _reaction_expr = None
        else:
            expr = _expressao_idle(_visible_idx)
        if _visible_idx % 12 == 0:
            logger.info("OLED procedural expressão=%s frame=%d", expr, _visible_idx)
        return _render_olhos_visiveis(expr, _visible_idx)


def pkt_rosto_neutro() -> protocol_encoder.DisplayImage:
    """Frame estático (fallback)."""
    return _encode_face(_render_olhos_visiveis("idle", 0))


def pkt_rosto_procedural(cli=None) -> protocol_encoder.DisplayImage:
    """Um frame procedural — thread-safe para DisplayKeeper e main loop."""
    del cli
    return _encode_face(_proximo_frame_visivel())
