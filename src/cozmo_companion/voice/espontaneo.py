"""Falas espontaneas leves: rosto visto e eco curto do ambiente."""

from __future__ import annotations

import os
import random
import re
import time
from collections import deque
from dataclasses import dataclass, field

from cozmo_companion.perception.events import PerceptionEvent, PerceptionEventKind
from cozmo_companion.voice.intent import (
    parece_alias_wake,
    parece_comando_curto,
    parece_pergunta,
    parece_ruido_tv,
    parece_saudacao,
)
from cozmo_companion.voice.sinal import comando_util, modo_sinal
from cozmo_companion.voice.wake import contem_wake


FRASES_ROSTO = (
    "Oi!",
    "Te vi!",
    "Tô te vendo!",
    "Opa!",
    "Beep!",
)

SINAIS_ECO = ("Eco", "Opa", "Beep")


def _env_bool(nome: str, padrao: bool) -> bool:
    return os.environ.get(nome, "1" if padrao else "0") == "1"


def _env_float(nome: str, padrao: float) -> float:
    try:
        return float(os.environ.get(nome, str(padrao)))
    except ValueError:
        return padrao


def _limpar_frase(texto: str) -> str:
    t = re.sub(r"\s+", " ", texto.strip())
    t = re.sub(r"[^\w\sáàâãéêíóôõúüç!?.,-]", "", t, flags=re.I)
    t = t.strip(" ,.;:-")
    return t


def frase_eco_valida(texto: str) -> str | None:
    """Filtra STT ambiente para evitar TV, wake e frases longas."""
    t = _limpar_frase(texto)
    if not t:
        return None
    low = t.lower()
    if parece_ruido_tv(low) or parece_pergunta(low) or comando_util(low):
        return None
    if contem_wake(low) or parece_alias_wake(low):
        return None
    if parece_saudacao(low) or parece_comando_curto(low):
        return None
    palavras = low.split()
    min_palavras = int(_env_float("ECO_MIN_WORDS", 2))
    max_palavras = int(_env_float("ECO_MAX_WORDS", 6))
    if not (min_palavras <= len(palavras) <= max_palavras):
        return None
    max_chars = int(_env_float("ECO_MAX_CHARS", 38))
    if len(t) > max_chars:
        return None
    return t


@dataclass
class FalaEspontanea:
    """Politica com cooldowns fortes para nao transformar o Cozmo em radio."""

    ouvidos: deque[str] = field(default_factory=lambda: deque(maxlen=8))
    ultimo_rosto_tentado: float = 0.0
    ultimo_rosto_falado: float = 0.0
    ultimo_eco: float = 0.0

    def registrar_ouvido(self, texto: str) -> None:
        frase = frase_eco_valida(texto)
        if frase is None:
            return
        if frase not in self.ouvidos:
            self.ouvidos.append(frase)

    def fala_rosto(self, evento: PerceptionEvent) -> str | None:
        if not _env_bool("ESPONTANEO_FACE_FALA", True):
            return None
        if evento.kind != PerceptionEventKind.FACE_SEEN:
            return None
        agora = time.monotonic()
        min_gap = _env_float("ESPONTANEO_FACE_MIN_GAP_S", 18.0)
        cooldown = _env_float("ESPONTANEO_FACE_COOLDOWN_S", 180.0)
        if agora - self.ultimo_rosto_tentado < min_gap:
            return None
        self.ultimo_rosto_tentado = agora
        if agora - self.ultimo_rosto_falado < cooldown:
            return None
        chance = _env_float("ESPONTANEO_FACE_CHANCE", 0.18)
        if random.random() > chance:
            return None
        self.ultimo_rosto_falado = agora
        return random.choice(FRASES_ROSTO)

    def fala_eco(self, texto_atual: str = "") -> tuple[str, str] | None:
        if not _env_bool("ECO_FRASES_ENABLED", True):
            return None
        self.registrar_ouvido(texto_atual)
        if not self.ouvidos:
            return None
        agora = time.monotonic()
        cooldown = _env_float("ECO_COOLDOWN_S", 150.0)
        if agora - self.ultimo_eco < cooldown:
            return None
        chance = _env_float("ECO_CHANCE", 0.0)
        if chance <= 0 or random.random() > chance:
            return None
        frase = random.choice(list(self.ouvidos))
        self.ultimo_eco = agora
        if modo_sinal():
            return random.choice(SINAIS_ECO), frase
        return frase, frase
