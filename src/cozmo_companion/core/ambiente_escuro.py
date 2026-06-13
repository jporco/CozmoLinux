"""Detecta ambiente escuro pela luminância da câmera — animação de sono na base."""

from __future__ import annotations

import logging
import os
import time
from collections import deque
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from PIL import Image

    import pycozmo

logger = logging.getLogger("cozmo.ambiente")

_AUTO = os.environ.get("COZMO_ESCURO_AUTO", "1") == "1"
_LIM_ESCURO = float(os.environ.get("COZMO_ESCURO_LIM", "32"))
_LIM_CLARO = float(os.environ.get("COZMO_ESCURO_CLARO", "50"))
_AMOSTRAS_MIN = max(2, int(os.environ.get("COZMO_ESCURO_AMOSTRAS", "4")))
_PROBE_S = float(os.environ.get("COZMO_ESCURO_PROBE_S", "5"))
_PROBE_INTERVALO_S = float(os.environ.get("COZMO_ESCURO_PROBE_INTERVALO_S", "90"))
_PROBE_DELAY_S = float(os.environ.get("COZMO_ESCURO_PROBE_DELAY_S", "300"))
_DESPERTAR_S = float(os.environ.get("COZMO_ESCURO_DESPERTAR_S", "180"))


def luminancia_media(imagem: "Image.Image") -> float:
    """Média 0–255 do frame em escala de cinza."""
    import numpy as np

    arr = np.asarray(imagem.convert("L"), dtype=np.float32)
    if arr.size == 0:
        return 255.0
    return float(arr.mean())


class DetectorEscuro:
    """Histerese: várias amostras escuras → sono; claras → volta ao pool acordado."""

    def __init__(self) -> None:
        self._amostras: deque[tuple[float, float]] = deque(maxlen=16)
        self._escuro = False
        self._inicio = time.monotonic()
        self._ultima_probe = 0.0
        self._despertar_ate = 0.0
        self._ultima_transicao = 0.0
        self._on_escuro: Callable[[], None] | None = None
        self._on_claro: Callable[[], None] | None = None

    @property
    def ativo(self) -> bool:
        return _AUTO

    @property
    def escuro(self) -> bool:
        if not _AUTO:
            return False
        if time.monotonic() < self._despertar_ate:
            return False
        return self._escuro

    def registrar_callbacks(
        self,
        *,
        on_escuro: Callable[[], None] | None = None,
        on_claro: Callable[[], None] | None = None,
    ) -> None:
        self._on_escuro = on_escuro
        self._on_claro = on_claro

    def amostrar(self, imagem: "Image.Image") -> None:
        if not _AUTO:
            return
        media = luminancia_media(imagem)
        agora = time.monotonic()
        self._amostras.append((agora, media))
        self._atualizar_estado()

    def marcar_despertar(self, segundos: float | None = None) -> None:
        """Voz / toque / notif — não voltar ao sono por escuro por um tempo."""
        dur = segundos if segundos is not None else _DESPERTAR_S
        self._despertar_ate = time.monotonic() + max(30.0, dur)
        if self._escuro:
            self._escuro = False
            self._ultima_transicao = time.monotonic()
            logger.info("Ambiente: claro (interação) — anim acordada")
            if self._on_claro:
                self._on_claro()

    def _media_recente(self) -> float | None:
        if len(self._amostras) < _AMOSTRAS_MIN:
            return None
        vals = [v for _, v in list(self._amostras)[-_AMOSTRAS_MIN :]]
        return sum(vals) / len(vals)

    def _atualizar_estado(self) -> None:
        media = self._media_recente()
        if media is None:
            return
        if time.monotonic() < self._despertar_ate:
            if self._escuro:
                self._escuro = False
                if self._on_claro:
                    self._on_claro()
            return
        era = self._escuro
        if not self._escuro and media < _LIM_ESCURO:
            self._escuro = True
        elif self._escuro and media > _LIM_CLARO:
            self._escuro = False
        if self._escuro != era:
            self._ultima_transicao = time.monotonic()
            if self._escuro:
                logger.info(
                    "Luz apagada (luminância %.0f < %.0f) — animação de sono",
                    media,
                    _LIM_ESCURO,
                )
                if self._on_escuro:
                    self._on_escuro()
            else:
                logger.info(
                    "Luz acesa (luminância %.0f > %.0f) — animações normais na base",
                    media,
                    _LIM_CLARO,
                )
                if self._on_claro:
                    self._on_claro()

    def tick_probe(
        self,
        face: object,
        *,
        na_base: bool,
        falando: bool,
        camera_ocupada: bool,
    ) -> None:
        """Abre câmera por alguns segundos se não houver outra janela ativa."""
        if not _AUTO or not na_base or falando or camera_ocupada:
            return
        agora = time.monotonic()
        if agora - self._inicio < _PROBE_DELAY_S:
            return
        if agora - self._ultima_probe < _PROBE_INTERVALO_S:
            return
        self._ultima_probe = agora
        try:
            face.iniciar_amostra_luz(_PROBE_S, na_base=True)  # type: ignore[attr-defined]
        except Exception as exc:
            logger.debug("Probe escuro falhou: %s", exc)


_detector: DetectorEscuro | None = None


def detector_escuro() -> DetectorEscuro:
    global _detector
    if _detector is None:
        _detector = DetectorEscuro()
    return _detector


def aplicar_sono_por_escuro(cli: "pycozmo.Client") -> None:
    """Troca clip OLED para grupo de sono (patch sem rodas)."""
    if os.environ.get("COZMO_SONO_NA_BASE", "0") != "1":
        return
    if os.environ.get("COZMO_ESCURO_NA_BASE", "0") == "0":
        from cozmo_companion.core.charger import na_base_oled

        if na_base_oled(cli):
            return
    import random

    from cozmo_companion.core.anims import pool_sono_oled_base
    from cozmo_companion.core.motor_cozmo import (
        _charger_oled_lock,
        base_oled_usa_charger,
        variar_clip_base_oled,
    )

    if not base_oled_usa_charger(cli):
        return
    disp = set(cli.animation_groups.keys())
    pool = pool_sono_oled_base(disp, cli)
    if not pool:
        return
    prefer = ("GoToSleepGetIn", "StartSleeping", "Sleeping", "GoToSleepSleeping")
    nome = next((p for p in prefer if p in pool), random.choice(pool))
    import cozmo_companion.core.motor_cozmo as mc

    with _charger_oled_lock:
        mc._charger_oled_nome = nome
    variar_clip_base_oled(cli, forcado=True)


def aplicar_acordado_por_luz(cli: "pycozmo.Client") -> None:
    from cozmo_companion.core.motor_cozmo import base_oled_usa_charger, variar_clip_base_oled

    if base_oled_usa_charger(cli):
        variar_clip_base_oled(cli, forcado=True)
