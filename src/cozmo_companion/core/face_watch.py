"""Rastreamento de rosto — cabeça + giro no corpo, estilo Cozmo original."""

from __future__ import annotations

import logging
import os
import queue
import random
import time
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image

from pycozmo import event, robot

from cozmo_companion.core.charger import em_base
from cozmo_companion.core.motor_cozmo import angulo_cabeca_neutro
from cozmo_companion.perception.events import (
    EventSink,
    PerceptionEvent,
    PerceptionEventKind,
)

if TYPE_CHECKING:
    import pycozmo

logger = logging.getLogger("cozmo.face")

try:
    import cv2

    _CV2 = True
except ImportError:
    _CV2 = False

FACE_FRAME_S = float(os.environ.get("FACE_FRAME_S", "0.18"))
FACE_FRAME_BASE_S = float(os.environ.get("FACE_FRAME_BASE_S", "0.55"))
FACE_TRACK_MIN_S = float(os.environ.get("FACE_TRACK_MIN_S", "0.10"))
FACE_SMOOTH = float(os.environ.get("FACE_SMOOTH", "0.42"))
DEADBAND_X = float(os.environ.get("FACE_DEADBAND_X", "0.07"))
DEADBAND_Y = float(os.environ.get("FACE_DEADBAND_Y", "0.06"))
FACE_BODY_START = float(os.environ.get("FACE_BODY_START", "0.14"))
FACE_BODY_VEL = int(os.environ.get("FACE_BODY_VEL", "18"))
FACE_EXTEND_S = float(os.environ.get("FACE_EXTEND_S", "2.0"))
FACE_PERDIDO_S = float(os.environ.get("FACE_PERDIDO_S", "2.5"))
FACE_SCAN_CHANCE = float(os.environ.get("FACE_SCAN_CHANCE", "0.35"))
FACE_CORPO_MESA = os.environ.get("FACE_CORPO_MESA", "0") == "1"
FACE_BODY_MAX_S = float(os.environ.get("FACE_BODY_MAX_S", "1.0"))


class FaceWatch:
    """Segue rosto na câmera — olhar contínuo enquanto a pessoa se mexe."""

    def __init__(self, cli: "pycozmo.Client"):
        self.cli = cli
        self.ativo = False
        self._busca_ativa = False
        self._busca_ate = 0.0
        self._na_base = True
        self._scan_dir = 1
        self._ultimo_scan = 0.0
        self._ultimo_rosto = 0.0
        self._ultimo_frame = 0.0
        self._ultimo_head = 0.0
        self._ultimo_body = 0.0
        self._intervalo_frame = FACE_FRAME_S
        self._chance_scan = FACE_SCAN_CHANCE
        self._offset_x = 0.0
        self._offset_y = 0.0
        self._smooth_x = 0.0
        self._smooth_y = 0.0
        self._lock_rosto = False
        self._corpo_desde = 0.0
        self._cascade = None
        q_max = 1 if os.environ.get("COZMO_FACE_BASE", "0") == "1" else 2
        self._img_q: queue.Queue = queue.Queue(maxsize=q_max)
        self._amostra_luz_ate = 0.0
        self._detector_luz: object | None = None
        self._event_sink: EventSink | None = None
        self._prev_motion_frame: np.ndarray | None = None
        self._ultimo_face_lost_emit = 0.0

        if _CV2:
            path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            self._cascade = cv2.CascadeClassifier(path)

        cli.add_handler(event.EvtNewRawCameraImage, self._on_imagem)

    @property
    def corpo_ativo(self) -> bool:
        """Corpo girando para seguir rosto (fora da base, se habilitado)."""
        if not FACE_CORPO_MESA or self._na_base or em_base(self.cli):
            return False
        return (time.monotonic() - self._ultimo_body) < 0.8

    def aplicar_perfil(self, intervalo_frame: float, chance_scan: float) -> None:
        self._intervalo_frame = max(0.22, intervalo_frame)
        self._chance_scan = max(0.05, min(0.55, chance_scan))

    @property
    def buscando(self) -> bool:
        return self._busca_ativa and time.monotonic() < self._busca_ate

    @property
    def rastreando(self) -> bool:
        return self._lock_rosto and (time.monotonic() - self._ultimo_rosto) < FACE_PERDIDO_S

    @property
    def _intervalo_efetivo(self) -> float:
        base = self._intervalo_frame
        if self._na_base:
            base = max(base, FACE_FRAME_BASE_S)
        if self.rastreando:
            return base
        return max(base, 0.55 if self._na_base else 0.35)

    def ligar(self, na_base: bool = False, *, forcar: bool = False) -> None:
        if (
            na_base
            and not forcar
            and os.environ.get("COZMO_FACE_BASE", "0") != "1"
            and os.environ.get("COZMO_ESCURO_AUTO", "1") != "1"
        ):
            return
        if self.ativo:
            self._na_base = na_base
            return
        self.cli.enable_camera(True, color=False)
        self.ativo = True
        self._na_base = na_base
        logger.info("Câmera ligada (%s).", "base" if na_base else "mesa")

    def vincular_detector_luz(self, detector: object | None) -> None:
        self._detector_luz = detector

    def vincular_eventos(self, sink: EventSink | None) -> None:
        self._event_sink = sink

    def _emitir_evento(self, evento: PerceptionEvent) -> None:
        if self._event_sink is None:
            return
        try:
            self._event_sink(evento)
        except Exception as exc:
            logger.debug("Evento percepção ignorado: %s", exc)

    def iniciar_amostra_luz(self, duracao_s: float, *, na_base: bool = True) -> bool:
        """Câmera só para luminância (sem busca de rosto)."""
        self.ligar(na_base=na_base, forcar=True)
        agora = time.monotonic()
        self._amostra_luz_ate = agora + max(2.0, duracao_s)
        self._busca_ativa = False
        self._busca_ate = 0.0
        return self.ativo

    def desligar(self) -> None:
        if not self.ativo:
            return
        self._parar_corpo()
        self.cli.enable_camera(False)
        self.ativo = False
        self._busca_ativa = False
        self._busca_ate = 0.0
        self._amostra_luz_ate = 0.0
        self._lock_rosto = False
        self._corpo_desde = 0.0
        self._smooth_x = 0.0
        self._smooth_y = 0.0

    def iniciar_busca(self, duracao_s: float, na_base: bool = True) -> bool:
        if na_base and os.environ.get("COZMO_FACE_BASE", "0") != "1":
            return False
        self.ligar(na_base=na_base)
        agora = time.monotonic()
        self._busca_ativa = True
        self._busca_ate = agora + duracao_s
        self._ultimo_rosto = 0.0
        self._ultimo_scan = 0.0
        self._lock_rosto = False
        return True

    def tick(self, permitido: bool = True) -> None:
        if not self.ativo or not permitido:
            return

        agora = time.monotonic()

        if self._amostra_luz_ate > 0:
            if agora >= self._amostra_luz_ate:
                self._amostra_luz_ate = 0.0
                self.desligar()
                logger.debug("Amostra de luz encerrada.")
                return
            self._processar_fila_imagem(luz_apenas=True)
            return

        if self._busca_ativa and agora >= self._busca_ate:
            self._busca_ativa = False
            self.desligar()
            logger.debug("Busca de rosto encerrada.")
            return

        self._processar_fila_imagem()

        if not self._busca_ativa:
            return

        # Mantém rastreio suave entre frames da câmera.
        if self.rastreando:
            self._aplicar_rastreio()
        elif agora - self._ultimo_rosto > FACE_PERDIDO_S:
            if self._lock_rosto:
                self._emitir_evento(
                    PerceptionEvent(kind=PerceptionEventKind.FACE_LOST)
                )
            self._lock_rosto = False
            self._parar_corpo()

        sem_rosto = agora - self._ultimo_rosto > 5.0
        if sem_rosto and not self._lock_rosto and agora - self._ultimo_scan > 6.0:
            if random.random() < self._chance_scan:
                self._varrer_cabeca()
                self._ultimo_scan = agora

    def _parar_corpo(self) -> None:
        try:
            self.cli.stop_all_motors()
        except Exception:
            pass
        self._corpo_desde = 0.0

    def _suavizar(self, ox: float, oy: float) -> None:
        a = FACE_SMOOTH
        self._smooth_x = self._smooth_x * (1 - a) + ox * a
        self._smooth_y = self._smooth_y * (1 - a) + oy * a

    def _aplicar_rastreio(self) -> None:
        agora = time.monotonic()
        sx, sy = self._smooth_x, self._smooth_y
        min_a = robot.MIN_HEAD_ANGLE.radians
        max_a = robot.MAX_HEAD_ANGLE.radians
        centro = angulo_cabeca_neutro()
        faixa = (max_a - min_a) * 0.42

        # Rosto abaixo do centro → inclina cabeça para baixo (relativo ao neutro).
        alvo_head = centro + sy * faixa
        alvo_head = max(min_a, min(max_a, alvo_head))
        cur = self.cli.head_angle.radians

        if (
            agora - self._ultimo_head >= FACE_TRACK_MIN_S
            and abs(alvo_head - cur) >= DEADBAND_Y
        ):
            self.cli.set_head_angle(alvo_head, max_speed=12.0)
            self._ultimo_head = agora

        # Corpo só se FACE_CORPO_MESA=1 (desligado por padrão).
        if self._na_base or em_base(self.cli) or not FACE_CORPO_MESA:
            return

        if self._corpo_desde > 0 and agora - self._corpo_desde > FACE_BODY_MAX_S:
            self._parar_corpo()
            self._corpo_desde = 0.0
            return

        if agora - self._ultimo_body < FACE_TRACK_MIN_S:
            return

        if abs(sx) < FACE_BODY_START:
            self._parar_corpo()
            self._corpo_desde = 0.0
            return

        vel = min(FACE_BODY_VEL, int(abs(sx) * 80))
        vel = max(10, min(vel, 18))
        if self._corpo_desde <= 0:
            self._corpo_desde = agora
        if sx > DEADBAND_X:
            self.cli.drive_wheels(-vel, vel)
        elif sx < -DEADBAND_X:
            self.cli.drive_wheels(vel, -vel)
        self._ultimo_body = agora

    def _on_imagem(self, _cli: "pycozmo.Client", imagem: Image.Image) -> None:
        """Só enfileira — OpenCV NÃO pode rodar na thread UDP (mata ping → COZMO 01)."""
        if not self.ativo:
            return
        if not self._busca_ativa and self._amostra_luz_ate <= 0:
            return
        try:
            self._img_q.put_nowait(imagem)
        except queue.Full:
            try:
                self._img_q.get_nowait()
            except queue.Empty:
                pass
            try:
                self._img_q.put_nowait(imagem)
            except queue.Full:
                pass

    def _processar_fila_imagem(self, *, luz_apenas: bool = False) -> None:
        agora = time.monotonic()
        intervalo = 0.35 if luz_apenas else self._intervalo_efetivo
        if agora - self._ultimo_frame < intervalo:
            return
        try:
            imagem = self._img_q.get_nowait()
        except queue.Empty:
            return
        self._ultimo_frame = agora
        self._analisar_imagem(imagem, luz_apenas=luz_apenas)

    def _analisar_imagem(self, imagem: Image.Image, *, luz_apenas: bool = False) -> None:
        cinza = np.array(imagem.convert("L"))
        media_luz = float(cinza.mean()) if cinza.size else 255.0
        self._emitir_evento(
            PerceptionEvent(
                kind=PerceptionEventKind.LIGHT_LEVEL,
                value=media_luz,
                data={"base": self._na_base},
            )
        )
        if self._detector_luz is not None:
            try:
                self._detector_luz.amostrar(imagem)  # type: ignore[attr-defined]
            except Exception:
                pass
        if luz_apenas or self._cascade is None:
            return

        self._emitir_movimento(cinza)
        faces = self._cascade.detectMultiScale(
            cinza,
            scaleFactor=1.12,
            minNeighbors=4,
            minSize=(24, 24),
        )
        if len(faces) == 0:
            if self._lock_rosto and time.monotonic() - self._ultimo_rosto > FACE_PERDIDO_S:
                agora = time.monotonic()
                if agora - self._ultimo_face_lost_emit > FACE_PERDIDO_S:
                    self._ultimo_face_lost_emit = agora
                    self._emitir_evento(
                        PerceptionEvent(kind=PerceptionEventKind.FACE_LOST)
                    )
            return

        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
        cx_rosto = x + w / 2.0
        cy_rosto = y + h / 2.0
        cx_img = cinza.shape[1] / 2.0
        cy_img = cinza.shape[0] / 2.0

        ox = (cx_rosto - cx_img) / max(cx_img, 1.0)
        oy = (cy_rosto - cy_img) / max(cy_img, 1.0)
        ox = max(-1.0, min(1.0, ox))
        oy = max(-1.0, min(1.0, oy))

        if not self._lock_rosto:
            self._lock_rosto = True
            proc_base = (
                self._na_base
                and os.environ.get("COZMO_PROC_FACE_BASE", "1") == "1"
            )
            if not proc_base:
                self.cli.cancel_anim()
            logger.info("Rosto detectado — seguindo.")

        self._ultimo_rosto = time.monotonic()
        self._emitir_evento(
            PerceptionEvent(
                kind=PerceptionEventKind.FACE_SEEN,
                data={"x": ox, "y": oy, "base": self._na_base},
            )
        )
        self._busca_ate = max(self._busca_ate, self._ultimo_rosto + FACE_EXTEND_S)
        self._suavizar(ox, oy)
        self._aplicar_rastreio()

    def _emitir_movimento(self, cinza: np.ndarray) -> None:
        pequeno = cinza[::8, ::8].astype(np.int16, copy=False)
        if self._prev_motion_frame is None or self._prev_motion_frame.shape != pequeno.shape:
            self._prev_motion_frame = pequeno.copy()
            return
        diff = float(np.mean(np.abs(pequeno - self._prev_motion_frame)))
        self._prev_motion_frame = pequeno.copy()
        lim = float(os.environ.get("FACE_MOTION_DIFF", "18"))
        if diff >= lim:
            self._emitir_evento(
                PerceptionEvent(
                    kind=PerceptionEventKind.MOTION_HINT,
                    value=diff,
                    data={"base": self._na_base},
                )
            )

    def _varrer_cabeca(self) -> None:
        cur = self.cli.head_angle.radians
        passo = 0.06 * self._scan_dir
        min_a = robot.MIN_HEAD_ANGLE.radians
        max_a = robot.MAX_HEAD_ANGLE.radians
        centro = angulo_cabeca_neutro()
        teto = min(max_a, centro + 0.12)
        piso = max(min_a, centro - 0.10)
        novo = cur + passo
        if novo >= teto:
            self._scan_dir = -1
            novo = teto
        elif novo <= piso:
            self._scan_dir = 1
            novo = piso
        self.cli.set_head_angle(novo, max_speed=8.0)

    def tocar_busca(self, grupos_disponiveis: set[str]) -> None:
        candidatos = (
            "LookInPlaceForFacesHeadMovePause",
            "InteractWithFaceTrackingIdle",
            "FeedingIdleSearchForFaces_Normal",
        )
        ok = [g for g in candidatos if g in grupos_disponiveis]
        if not ok:
            return
        nome = random.choice(ok)
        if em_base(self.cli) or self._na_base:
            from cozmo_companion.core.motor_cozmo import tocar_clip_base_seguro

            if tocar_clip_base_seguro(self.cli, nome, hold_s=5.0):
                return
        try:
            self.cli.play_anim_group(nome)
        except Exception:
            pass
