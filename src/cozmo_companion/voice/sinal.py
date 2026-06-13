"""TTS mínimo — uma palavra/som chama atenção; detalhe fica na tela OLED."""

from __future__ import annotations

import os
import random
import re

from cozmo_companion.core import hora
from cozmo_companion.voice.resposta import encurtar_fala, parece_saudacao_curta

_CLIMA_KW = ("temperatura", "graus", "calor", "frio", "clima", "bagé", "bage", "chuva", "grau")


def comando_util(texto: str) -> bool:
    """Comandos curtos que funcionam na base sem dizer Cozmo."""
    t = re.sub(r"[^\w\sáàâãéêíóôõúüç]", " ", texto.lower()).strip()
    t = re.sub(r"\s+", " ", t)
    if not t or len(t) > 48:
        return False
    if parece_hora(texto) or parece_clima(texto):
        return True
    if t in (
        "tempo",
        "hora",
        "horas",
        "clima",
        "temperatura",
        "graus",
        "o tempo",
        "a hora",
    ):
        return True
    return False


def audio_na_base() -> bool:
    return os.environ.get("TTS_AUDIO_NA_BASE", "1") == "1"


def modo_sinal() -> bool:
    return os.environ.get("TTS_MODO", "sinal").strip().lower() == "sinal"


def parece_clima(texto: str) -> bool:
    u = texto.lower().strip()
    if re.search(r"\btempo\b", u):
        return True
    return any(k in u for k in _CLIMA_KW)


def parece_hora(texto: str) -> bool:
    u = texto.lower().strip()
    return hora.pergunta_hora(texto) or u in ("hora", "horas")


def sinal_para(pergunta: str = "", fala: str = "") -> str:
    """Uma palavra curta — indicador de que há algo na tela."""
    padrao = os.environ.get("TTS_SINAL_PADRAO", "Beep")
    u = pergunta.lower().strip()
    f = fala.strip()

    if parece_hora(u) or (f and parece_hora(f)):
        return "Hora"
    if parece_clima(u) or (f and parece_clima(f)):
        return "Tempo"
    if parece_saudacao_curta(u) or (f and parece_saudacao_curta(f)):
        return random.choice(("Oi", "Opa", "Beep"))
    if "au" in u or re.search(r"\bau\b", f, re.I):
        return "Au"

    if f:
        palavra = re.sub(r"[^\wáàâãéêíóôõúüçÁÀÂÃÉÊÍÓÔÕÚÜÇ]", "", f.split()[0])
        if palavra:
            lim = int(os.environ.get("TTS_SINAL_MAX_CHARS", "10"))
            palavra = palavra[:lim]
            return palavra[0].upper() + palavra[1:] if len(palavra) > 1 else palavra.upper()
    return padrao


def texto_tela_de_fala(fala: str, *, max_len: int = 16) -> str:
    t = encurtar_fala(fala.strip(), max_palavras=10, max_chars=48)
    if not t:
        return ""
    return t[:max_len]
