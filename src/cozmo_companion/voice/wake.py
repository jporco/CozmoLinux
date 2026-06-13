"""Wake word 'Cozmo' — fala o nome e depois a pergunta."""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Callable, Optional

logger = logging.getLogger("cozmo.wake")

# Vosk PT não tem "cozmo" — costuma transcrever como "cosmo" ou "oração".
PALAVRAS_ATIVACAO = tuple(
    dict.fromkeys(
        w.strip().lower()
        for w in os.environ.get("WAKE_WORDS", "cozmo,cosmo").split(",")
        if w.strip()
    )
)

# Alias só de wake (Vosk ouve "cozmo" como "oração") — não aceita "que oração".
VOSK_WAKE_ALIASES = tuple(
    dict.fromkeys(
        w.strip().lower()
        for w in os.environ.get("WAKE_VOSK_ALIASES", "oração,oracao").split(",")
        if w.strip()
    )
)

_WAKE_RE = re.compile(r"\b(cozmo|cosmo)\b", re.IGNORECASE)
_ORACAO_WAKE_RE = re.compile(r"^(oração|oracao)\b", re.IGNORECASE)
# Vosk: "Cozmo que horas" → "que oração que horas" — wake só com pergunta depois
_QUE_ORACAO_WAKE_RE = re.compile(
    r"^que\s+(?:a\s+)?(oração|oracao)\b\s+(.+)$",
    re.IGNORECASE,
)


def _normalizar(texto: str) -> str:
    t = texto.lower()
    t = re.sub(r"[^\w\sáàâãéêíóôõúüç]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _alias_vosk_no_inicio(texto: str) -> bool:
    t = _normalizar(texto)
    if t in VOSK_WAKE_ALIASES:
        return True
    return bool(_ORACAO_WAKE_RE.match(t))


def _que_oracao_pergunta(texto: str) -> str | None:
    """Alias Vosk: 'que oração que horas' = wake + pergunta."""
    t = _normalizar(texto)
    m = _QUE_ORACAO_WAKE_RE.match(t)
    if not m:
        return None
    resto = m.group(2).strip(" ,.:-–—")
    return resto if len(resto) >= 2 else None


def contem_wake(texto: str) -> bool:
    if _WAKE_RE.search(texto):
        return True
    if _alias_vosk_no_inicio(texto):
        return True
    if _que_oracao_pergunta(texto):
        return True
    t = _normalizar(texto)
    palavras = set(t.split())
    return any(w in palavras for w in PALAVRAS_ATIVACAO)


def _posicao_wake(texto_norm: str) -> tuple[int, str] | None:
    m = _QUE_ORACAO_WAKE_RE.match(texto_norm)
    if m:
        return 0, f"que {m.group(1)}"
    m = _ORACAO_WAKE_RE.match(texto_norm)
    if m:
        return m.start(), m.group(0)
    m = _WAKE_RE.search(texto_norm)
    if m:
        return m.start(), m.group(0)
    for w in sorted(PALAVRAS_ATIVACAO, key=len, reverse=True):
        idx = texto_norm.find(w)
        if idx >= 0:
            return idx, w
    if texto_norm in VOSK_WAKE_ALIASES:
        return 0, texto_norm
    return None


def extrair_pergunta(texto: str) -> Optional[str]:
    """Retorna pergunta após 'cozmo ...' na mesma frase, ou None."""
    original = texto.strip()
    t = _normalizar(original)
    que_oracao = _que_oracao_pergunta(original)
    if que_oracao:
        return que_oracao
    pos = _posicao_wake(t)
    if not pos:
        return None
    idx, palavra = pos
    resto = original[idx + len(palavra) :].strip(" ,.:-–—")
    if len(resto) >= 2:
        return resto
    return None


def parcial_wake_pronto(texto: str) -> bool:
    """Parcial só dispara se já tiver pergunta — evita 'oração' sozinho cortar a frase."""
    if extrair_pergunta(texto):
        return True
    t = _normalizar(texto)
    if len(t.split()) <= 1:
        return False
    return contem_wake(texto)


class WakeWord:
    """Ativa com 'Cozmo' e aceita a pergunta em seguida."""

    def __init__(
        self,
        ao_pergunta: Callable[[str], None],
        ao_acordar: Optional[Callable[[], None]] = None,
        timeout_s: Optional[float] = None,
    ):
        self.ao_pergunta = ao_pergunta
        self.ao_acordar = ao_acordar
        self.timeout = float(
            timeout_s if timeout_s is not None else os.environ.get("WAKE_TIMEOUT_S", "9")
        )
        self._aguardando = False
        self._aguardando_ate = 0.0

    def _acordar(self) -> None:
        self._aguardando = True
        self._aguardando_ate = time.monotonic() + self.timeout
        logger.info("Wake word — aguardando pergunta (%.0fs)", self.timeout)
        if self.ao_acordar:
            self.ao_acordar()

    def _enviar_pergunta(self, pergunta: str) -> None:
        self._aguardando = False
        logger.info("Pergunta: %s", pergunta)
        self.ao_pergunta(pergunta)

    def processar(self, texto: str) -> bool:
        texto = texto.strip()
        if len(texto) < 2:
            return False

        pergunta = extrair_pergunta(texto)
        if pergunta:
            self._enviar_pergunta(pergunta)
            return True

        if contem_wake(texto):
            self._acordar()
            return True

        if self._aguardando:
            if time.monotonic() <= self._aguardando_ate:
                self._enviar_pergunta(texto)
                return True
            self._aguardando = False

        return False

    @property
    def aguardando(self) -> bool:
        return self._aguardando and time.monotonic() <= self._aguardando_ate

    def encerrar_espera(self) -> None:
        self._aguardando = False
