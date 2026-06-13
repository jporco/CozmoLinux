"""Rosto procedural em pacotes DisplayImage — keepalive OLED sem flood 30fps."""

from __future__ import annotations

import threading

import numpy as np
from PIL import Image
from pycozmo import image_encoder, procedural_face, protocol_encoder

_keeper_lock = threading.Lock()
_keeper_gen: iter | None = None


def _proximo_frame_keeper() -> object:
    """Gerador próprio — NUNCA usar anim_controller.face_generator (race entre threads)."""
    global _keeper_gen
    with _keeper_lock:
        if _keeper_gen is None:
            _keeper_gen = iter(procedural_face.ProceduralFaceGenerator())
        try:
            return next(_keeper_gen)
        except StopIteration:
            _keeper_gen = iter(procedural_face.ProceduralFaceGenerator())
            return next(_keeper_gen)


def _encode_face(im) -> protocol_encoder.DisplayImage:
    arr = np.array(im)
    if arr.ndim >= 2 and (arr.shape[0] != 32 or arr.shape[1] != 128):
        pil = Image.fromarray(arr).resize((128, 32))
    else:
        pil = Image.fromarray(arr)
    if pil.size != (128, 32):
        pil = pil.resize((128, 32))
    enc = image_encoder.ImageEncoder(pil)
    return protocol_encoder.DisplayImage(image=bytes(enc.encode()))


def pkt_rosto_neutro() -> protocol_encoder.DisplayImage:
    """Frame estático (fallback)."""
    return _encode_face(procedural_face.ProceduralFace().render())


def pkt_rosto_procedural(cli=None) -> protocol_encoder.DisplayImage:
    """Um frame procedural — thread-safe para DisplayKeeper e main loop."""
    del cli
    im = _proximo_frame_keeper()
    if not im:
        return pkt_rosto_neutro()
    try:
        return _encode_face(im)
    except (ValueError, OSError):
        return pkt_rosto_neutro()
