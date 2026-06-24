"""Respostas curtas — evita monólogo do LLM que mata o UDP do Cozmo."""

from __future__ import annotations

import random
import re

MAX_PALAVRAS = 8
MAX_CHARS = 48

_SAUDACOES = frozenset(
    {
        "oi",
        "olá",
        "ola",
        "hey",
        "e aí",
        "e ai",
        "e",
        "opa",
        "fala",
        "beep",
        "cosmo",
        "cozmo",
    }
)

_RESPOSTAS_SAUDACAO = (
    "Oi!",
    "Beep!",
    "Opa!",
    "Fala!",
)


def encurtar_fala(texto: str, *, max_palavras: int = MAX_PALAVRAS, max_chars: int = MAX_CHARS) -> str:
    t = re.sub(r"\s+", " ", texto.strip())
    t = re.sub(r"^\s*[\"']|[\"']\s*$", "", t)
    # Remove lixo de formato quebrado do LLM.
    t = re.sub(r"\b(carinho|conforto|triste|nada|dancar|explorar|dormir)\.\s*$", "", t, flags=re.I)
    if not t:
        return ""
    # Primeira frase só.
    partes = re.split(r"(?<=[.!?])\s+", t, maxsplit=1)
    t = partes[0].strip()
    palavras = t.split()
    if len(palavras) > max_palavras:
        t = " ".join(palavras[:max_palavras]).rstrip(".,;:") + "."
    if len(t) > max_chars:
        corte = t[:max_chars].rsplit(" ", 1)[0]
        t = (corte or t[:max_chars]).rstrip(".,;") + "."
    return t


def parece_saudacao_curta(texto: str) -> bool:
    t = re.sub(r"[^\w\sáàâãéêíóôõúüç]", " ", texto.lower()).strip()
    t = re.sub(r"\s+", " ", t)
    if t in _SAUDACOES:
        return True
    return len(t.split()) <= 2 and any(t.startswith(s) for s in ("oi", "olá", "ola", "opa", "hey", "e ai", "e aí"))


def resposta_rapida(texto: str) -> str | None:
    """Resposta instantânea sem Ollama — saudações e ack."""
    t = texto.lower().strip()
    if parece_saudacao_curta(t):
        return random.choice(_RESPOSTAS_SAUDACAO)
    if t in ("obrigado", "valeu", "brigado"):
        return random.choice(("Beep! De nada!", "Por nada porco!", "Sempre!"))
    if t in ("tchau", "até", "ate", "flw", "falou"):
        return random.choice(("Tchau porco!", "Beep tchau!", "Até!"))
    if any(x in t for x in ("estou triste", "tô triste", "to triste", "estou mal", "quase morri")):
        return random.choice(("Beep...", "Tô aqui.", "Força porco!"))
    if any(x in t for x in ("estou feliz", "obrigado", "valeu")):
        return random.choice(("Beep!", "Massa!", "De nada!"))
    return None
