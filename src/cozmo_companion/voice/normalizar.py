"""Corrige transcrições erradas do Vosk antes do wake/LLM."""

from __future__ import annotations

import re

# Vosk PT confunde "cozmo/cosmo" com palavras comuns.
_SUBS = (
    (re.compile(r"\b(oração|oracao|orações|oracoes)\b", re.I), "cosmo"),
    (re.compile(r"\b(cosmo|cozmo)\b", re.I), "cosmo"),
    (re.compile(r"\bque\s+horas\s+sao\b", re.I), "que horas são"),
    (re.compile(r"\bhoras\s+sao\b", re.I), "horas são"),
)


def normalizar_vosk(texto: str) -> str:
    t = texto.strip()
    if not t:
        return t
    for rx, repl in _SUBS:
        t = rx.sub(repl, t)
    return re.sub(r"\s+", " ", t).strip()
