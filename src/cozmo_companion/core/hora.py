"""Local time for weather/time replies."""

from __future__ import annotations

import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

FUSO = os.environ.get("BAGE_TZ", "America/Sao_Paulo")
CIDADE = os.environ.get("WEATHER_CITY", os.environ.get("BAGE_CIDADE", "Local"))

# Só frases explícitas — evita "agora", "outra coisa", etc.
_PADROES_HORA = (
    r"\bque horas\b",
    r"\bqué horas\b",
    r"\bhoras são\b",
    r"\bhoras sao\b",
    r"\bme diz a hora\b",
    r"\bme diga a hora\b",
    r"\bqual a hora\b",
    r"\bqual é a hora\b",
    r"\bqual e a hora\b",
    r"\bque hora é\b",
    r"\bque hora e\b",
    r"\bqué hora é\b",
    r"\bqué hora e\b",
    r"\bme fala a hora\b",
    r"\bme fala as horas\b",
)


def pergunta_hora(texto: str) -> bool:
    t = texto.lower().strip()
    return any(re.search(p, t) for p in _PADROES_HORA)


def agora() -> datetime:
    return datetime.now(ZoneInfo(FUSO))


def hora_curta() -> str:
    return agora().strftime("%H:%M")


def frase_hora() -> str:
    dt = agora()
    h, m = dt.hour, dt.minute
    if m == 0:
        return f"{h} horas"
    return f"{h} e {m}"


def texto_tela() -> str:
    return hora_curta()
