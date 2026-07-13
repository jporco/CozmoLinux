"""Frames OLED visiveis para keeper da base."""

from __future__ import annotations

from cozmo_companion.display import rosto


def test_olhos_visiveis_ocupam_oled() -> None:
    im = rosto._render_olhos_visiveis("idle", 1)

    assert im.mode == "1"
    assert im.size == (128, 32)
    bbox = im.getbbox()
    assert bbox is not None
    x0, y0, x1, y1 = bbox
    assert x0 < 35
    assert x1 > 90
    assert y0 < 10
    assert y1 > 22


def test_reacao_visual_muda_frame_seguinte() -> None:
    base = rosto._render_olhos_visiveis("idle", 1).tobytes()

    rosto.solicitar_reacao_visual("sound", frames=1)
    reacao = rosto._proximo_frame_visivel().tobytes()

    assert reacao != base


def test_pkt_rosto_procedural_binario_valido() -> None:
    pkt = rosto.pkt_rosto_procedural()

    assert len(pkt.image) > 8


def test_blink_nunca_apaga_oled() -> None:
    im = rosto._render_olhos_visiveis("blink", 1)

    assert im.getbbox() is not None
