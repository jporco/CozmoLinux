"""Renderiza texto na telinha OLED do Cozmo (128x32).

PyCozmo: imagens passam pelo AnimationController (~30 fps), não por conn.send
paralelo — ver https://pycozmo.readthedocs.io/en/stable/ (Display + procedural_face).
Com procedural ativo, desligar antes de texto estático e religar ao terminar.
"""

from __future__ import annotations

import os
import re
import time
from functools import lru_cache
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont
from pycozmo import image_encoder, protocol_encoder

if TYPE_CHECKING:
    import pycozmo

LARGURA = 128
ALTURA = 32
MAX_CHARS = 16
_FONTE_TAM = int(os.environ.get("COZMO_OLED_FONT_SIZE", "10"))
_TELA_MIN_S = float(os.environ.get("TELA_MIN_S", "6"))
_TELA_SCROLL_PASSO = float(os.environ.get("TELA_SCROLL_PASSO_S", "0.85"))
_TELA_PRIO: dict[str, int] = {
    "sono": 50,
    "notif": 40,
    "util": 30,
    "espirito": 20,
    "default": 10,
}

# TTF com Latin-Extended — nunca PCF/bitmap (ter-u12b não tem ç/ã/õ).
_FONTES_UNICODE = (
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/TTF/NotoSans-Regular.ttf",
    "/usr/share/fonts/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/TTF/LiberationSans-Regular.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
)


@lru_cache(maxsize=1)
def _fonte() -> ImageFont.ImageFont:
    raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    local = os.path.join(raiz, "data", "fonts", "DejaVuSans.ttf")
    for caminho in (local, *_FONTES_UNICODE):
        if not caminho or not os.path.isfile(caminho):
            continue
        try:
            return ImageFont.truetype(caminho, _FONTE_TAM)
        except OSError:
            continue
    return ImageFont.load_default()


def texto_para_pkt(texto: str) -> protocol_encoder.DisplayImage:
    texto = texto.strip()[:MAX_CHARS]
    im = Image.new("1", (LARGURA, ALTURA), color=0)
    draw = ImageDraw.Draw(im)
    fonte = _fonte()
    draw.text((LARGURA // 2, ALTURA // 2), texto, fill=1, font=fonte, anchor="mm")
    enc = image_encoder.ImageEncoder(im)
    return protocol_encoder.DisplayImage(image=bytes(enc.encode()))


def janelas_scroll(texto: str, largura: int = MAX_CHARS) -> tuple[str, ...]:
    """Fatias de texto para marquee OLED."""
    t = " ".join(texto.strip().split())
    if not t:
        return ("",)
    if len(t) <= largura:
        return (t,)
    fatias: list[str] = []
    pos = 0
    passo = max(4, largura - 3)
    while pos < len(t):
        fatias.append(t[pos : pos + largura])
        pos += passo
    return tuple(fatias)


class Tela:
    """Mostra texto na face por alguns segundos sem bloquear o loop principal."""

    def __init__(self, cli: "pycozmo.Client"):
        self.cli = cli
        self._pkt: protocol_encoder.DisplayImage | None = None
        self._pkt_escuro: protocol_encoder.DisplayImage | None = None
        self._escuro = False
        self._ate = 0.0
        self._texto_atual = ""
        self._scroll_fatias: tuple[str, ...] = ()
        self._scroll_i = 0
        self._scroll_proximo = 0.0
        self._scroll_passo = _TELA_SCROLL_PASSO
        self._oled_ultimo = 0.0
        self._prioridade = 0
        self._ultimo_enviado = ""
        self._proc_pausado = False

    def _prio(self, nome: str) -> int:
        chave = f"TELA_PRIO_{nome.upper()}"
        if chave in os.environ:
            return int(os.environ[chave])
        return _TELA_PRIO.get(nome, 10)

    def ocupada(self) -> bool:
        """Texto OLED ativo — não competir com olhos procedural."""
        if self._escuro:
            return True
        return bool(self._pkt) and time.monotonic() < self._ate

    def _restaurar_procedural(self) -> None:
        from cozmo_companion.core.motor_cozmo import base_oled_modo_proc, modo_base_olhos

        self._proc_pausado = False
        if base_oled_modo_proc():
            try:
                modo_base_olhos(self.cli)
            except Exception:
                pass
            return
        if os.environ.get("COZMO_PROC_FACE", "1") != "1":
            return
        try:
            self.cli.anim_controller.enable_procedural_face(True)
        except Exception:
            pass

    def _enviar_pkt(self, pkt: protocol_encoder.DisplayImage, *, direct: bool) -> None:
        """Fila do AnimationController — evita briga com procedural a 30 fps."""
        from cozmo_companion.core.motor_cozmo import base_oled_modo_proc

        from cozmo_companion.core.motor_cozmo import base_oled_usa_pulse

        if base_oled_usa_pulse(self.cli) and not self._proc_pausado:
            return
        agora = time.monotonic()
        refresh = float(os.environ.get("COZMO_OLED_REFRESH_S", "2.5"))
        if self._prioridade >= _TELA_PRIO.get("sono", 50):
            refresh = float(os.environ.get("SONO_OLED_REFRESH_S", "1.0"))
        if not direct and agora - self._oled_ultimo < refresh:
            return
        self._oled_ultimo = agora
        from cozmo_companion.core.motor_cozmo import enviar_oled

        enviar_oled(self.cli, pkt)

    def _pode_substituir(
        self,
        texto: str,
        segundos: float,
        *,
        forcado: bool,
        prioridade: str = "default",
    ) -> bool:
        if forcado:
            return True
        agora = time.monotonic()
        if not self._pkt or agora >= self._ate:
            return True
        restante = self._ate - agora
        if texto == self._texto_atual:
            self._ate = max(self._ate, agora + max(segundos, _TELA_MIN_S))
            return False
        guard = float(os.environ.get("TELA_GUARD_S", "4"))
        prio = self._prio(prioridade)
        if prio <= self._prioridade and restante > guard:
            return False
        return restante <= guard or prio > self._prioridade

    def escurecer(self) -> None:
        """Apaga a telinha (modo sono profundo)."""
        im = Image.new("1", (LARGURA, ALTURA), color=0)
        enc = image_encoder.ImageEncoder(im)
        self._pkt_escuro = protocol_encoder.DisplayImage(image=bytes(enc.encode()))
        self._escuro = True
        self._scroll_fatias = ()
        self._texto_atual = ""
        self._ate = 0.0
        self._prioridade = 0
        self.cli.anim_controller.enable_procedural_face(False)

    def clarear(self) -> None:
        self._escuro = False
        self._pkt_escuro = None
        self._scroll_fatias = ()
        self._texto_atual = ""

    def manter_escuro(self, *, direct: bool = False) -> None:
        if self._escuro and self._pkt_escuro:
            self._enviar_pkt(self._pkt_escuro, direct=direct)

    def mostrar(
        self,
        texto: str,
        segundos: float = 8.0,
        *,
        forcado: bool = False,
        prioridade: str = "default",
    ) -> None:
        texto = texto.strip()[:MAX_CHARS]
        segundos = max(segundos, _TELA_MIN_S)
        if not self._pode_substituir(
            texto, segundos, forcado=forcado, prioridade=prioridade
        ):
            return
        self._escuro = False
        self._pkt_escuro = None
        self._scroll_fatias = ()
        self._texto_atual = texto
        self._prioridade = self._prio(prioridade)
        self._pkt = texto_para_pkt(texto)
        self._ate = time.monotonic() + segundos
        from cozmo_companion.core.motor_cozmo import base_oled_modo_proc

        if base_oled_modo_proc() and os.environ.get("COZMO_TELA_MANTEM_PROC_BASE", "1") == "1":
            self._proc_pausado = True
        else:
            self.cli.anim_controller.enable_procedural_face(False)
            self._proc_pausado = base_oled_modo_proc()
        self._ultimo_enviado = texto
        self._enviar_pkt(self._pkt, direct=False)

    def mostrar_scroll(
        self,
        texto: str,
        segundos: float = 8.0,
        *,
        passo_s: float | None = None,
        forcado: bool = False,
        prioridade: str = "default",
    ) -> None:
        """Marquee — rola texto longo antes de sumir."""
        segundos = max(segundos, _TELA_MIN_S)
        fatias = janelas_scroll(texto)
        chave = fatias[0] if fatias else ""
        if not self._pode_substituir(
            chave, segundos, forcado=forcado, prioridade=prioridade
        ):
            return
        self._escuro = False
        self._pkt_escuro = None
        self._scroll_fatias = fatias
        self._scroll_i = 0
        self._scroll_passo = passo_s if passo_s is not None else _TELA_SCROLL_PASSO
        self._scroll_proximo = time.monotonic() + self._scroll_passo
        self._texto_atual = chave
        self._prioridade = self._prio(prioridade)
        self._ate = time.monotonic() + segundos
        self._pkt = texto_para_pkt(self._scroll_fatias[0])
        from cozmo_companion.core.motor_cozmo import base_oled_modo_proc

        if base_oled_modo_proc() and os.environ.get("COZMO_TELA_MANTEM_PROC_BASE", "1") == "1":
            self._proc_pausado = True
        else:
            self.cli.anim_controller.enable_procedural_face(False)
            self._proc_pausado = base_oled_modo_proc()
        self._ultimo_enviado = chave
        self._enviar_pkt(self._pkt, direct=False)

    def renovar(self, segundos: float = 30.0) -> None:
        """Estende o texto atual sem piscar (sono zZz)."""
        if self._escuro or not self._pkt:
            return
        self._ate = time.monotonic() + max(segundos, _TELA_MIN_S)

    def tick(self, *, direct: bool = False) -> None:
        if self._escuro:
            self.manter_escuro(direct=direct)
            return
        agora = time.monotonic()
        if self._scroll_fatias and agora < self._ate:
            if agora >= self._scroll_proximo and len(self._scroll_fatias) > 1:
                self._scroll_i = (self._scroll_i + 1) % len(self._scroll_fatias)
                self._pkt = texto_para_pkt(self._scroll_fatias[self._scroll_i])
                self._texto_atual = self._scroll_fatias[self._scroll_i]
                self._scroll_proximo = agora + self._scroll_passo
            if self._pkt:
                self._enviar_pkt(self._pkt, direct=direct)
            return
        if self._pkt and agora < self._ate:
            self._enviar_pkt(self._pkt, direct=direct)
            return
        if self._ate > 0:
            self._pkt = None
            self._scroll_fatias = ()
            self._texto_atual = ""
            self._prioridade = 0
            self._ultimo_enviado = ""
            self._ate = 0.0
            self._restaurar_procedural()
