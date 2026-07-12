"""Rosto OLED em pacotes DisplayImage — keepalive sem flood 30fps."""

from __future__ import annotations

import threading

import numpy as np
from PIL import Image, ImageDraw
from pycozmo import image_encoder, protocol_encoder

_visible_lock = threading.Lock()
_visible_idx = 0
_reaction_expr: str | None = None
_reaction_frames = 0

LARGURA = 128
ALTURA = 32


def solicitar_reacao_visual(tipo: str, *, frames: int = 5) -> None:
    """Pede uma expressao curta para o keeper de olhos grandes da base."""
    global _reaction_expr, _reaction_frames
    expr = (tipo or "").strip().lower()
    if expr not in {"happy", "pet", "wake", "sound", "surprise", "curious"}:
        expr = "curious"
    with _visible_lock:
        _reaction_expr = expr
        _reaction_frames = max(1, int(frames))


def _encode_face(im) -> protocol_encoder.DisplayImage:
    arr = np.array(im)
    if arr.ndim >= 2 and (arr.shape[0] != 32 or arr.shape[1] != 128):
        pil = Image.fromarray(arr).resize((LARGURA, ALTURA))
    else:
        pil = Image.fromarray(arr)
    if pil.size != (LARGURA, ALTURA):
        pil = pil.resize((LARGURA, ALTURA))
    if pil.mode != "1":
        pil = pil.convert("1")
    enc = image_encoder.ImageEncoder(pil)
    return protocol_encoder.DisplayImage(image=bytes(enc.encode()))


def _olho(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], *, pupila: int = 0) -> None:
    draw.rounded_rectangle(box, radius=8, fill=1)
    if pupila:
        x0, y0, x1, y1 = box
        cx = (x0 + x1) // 2 + pupila
        draw.rounded_rectangle((cx - 5, y0 + 7, cx + 5, y1 - 6), radius=3, fill=0)


def _render_olhos_visiveis(expr: str, idx: int) -> Image.Image:
    im = Image.new("1", (LARGURA, ALTURA), color=0)
    draw = ImageDraw.Draw(im)
    fase = idx % 16
    if expr == "blink" or fase == 7:
        draw.rounded_rectangle((5, 14, 58, 18), radius=2, fill=1)
        draw.rounded_rectangle((70, 14, 123, 18), radius=2, fill=1)
        return im
    if expr == "sleep":
        draw.arc((6, 10, 58, 29), start=190, end=350, fill=1, width=3)
        draw.arc((70, 10, 122, 29), start=190, end=350, fill=1, width=3)
        return im
    if expr in {"happy", "pet"}:
        _olho(draw, (5, 7, 58, 29), pupila=-3)
        _olho(draw, (70, 7, 123, 29), pupila=3)
        draw.rectangle((5, 7, 58, 13), fill=0)
        draw.rectangle((70, 7, 123, 13), fill=0)
        return im
    if expr in {"sound", "surprise"}:
        draw.ellipse((6, 2, 58, 31), fill=1)
        draw.ellipse((70, 2, 122, 31), fill=1)
        draw.ellipse((25, 11, 39, 24), fill=0)
        draw.ellipse((89, 11, 103, 24), fill=0)
        return im
    if expr in {"wake", "curious"}:
        _olho(draw, (5, 3, 58, 30), pupila=7 if fase < 8 else -4)
        _olho(draw, (73, 8, 121, 27), pupila=3 if fase < 8 else -6)
        return im
    olhar = (-6, 0, 6, 0)[(fase // 4) % 4]
    _olho(draw, (4, 4, 59, 29), pupila=olhar)
    _olho(draw, (69, 4, 124, 29), pupila=olhar)
    return im


def _proximo_frame_visivel() -> Image.Image:
    global _visible_idx, _reaction_expr, _reaction_frames
    with _visible_lock:
        _visible_idx += 1
        expr = "idle"
        if _reaction_frames > 0 and _reaction_expr:
            expr = _reaction_expr
            _reaction_frames -= 1
            if _reaction_frames <= 0:
                _reaction_expr = None
        elif _visible_idx % 37 in (0, 1):
            expr = "curious"
        elif _visible_idx % 16 == 7:
            expr = "blink"
        return _render_olhos_visiveis(expr, _visible_idx)


def pkt_rosto_neutro() -> protocol_encoder.DisplayImage:
    """Frame estático (fallback)."""
    return _encode_face(_render_olhos_visiveis("idle", 0))


def pkt_rosto_procedural(cli=None) -> protocol_encoder.DisplayImage:
    """Um frame procedural — thread-safe para DisplayKeeper e main loop."""
    del cli
    return _encode_face(_proximo_frame_visivel())
