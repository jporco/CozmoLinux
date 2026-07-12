"""Frames OLED visiveis para keeper da base."""

from __future__ import annotations

from cozmo_companion.display import rosto


def test_olhos_visiveis_ocupam_oled() -> None:
    im = rosto._render_olhos_visiveis("idle", 1)

    assert im.mode == "1"
    assert im.size == (128, 32)
    assert im.getbbox() == (4, 4, 125, 30)


def test_reacao_visual_muda_frame_seguinte() -> None:
    base = rosto._render_olhos_visiveis("idle", 1).tobytes()

    rosto.solicitar_reacao_visual("sound", frames=1)
    reacao = rosto._proximo_frame_visivel().tobytes()

    assert reacao != base


def test_pkt_rosto_procedural_binario_valido() -> None:
    pkt = rosto.pkt_rosto_procedural()

    assert len(pkt.image) > 64
