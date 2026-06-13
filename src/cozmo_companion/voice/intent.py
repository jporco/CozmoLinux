"""Detecta perguntas e comandos — resposta sem wake word quando apropriado."""

from __future__ import annotations

import os
import re

from cozmo_companion.core import hora
from cozmo_companion.voice.wake import contem_wake

_ALIASES_WAKE = frozenset(
    {
        "ação",
        "acao",
        "oracao",
        "oração",
        "cosmo",
        "cozmo",
        "ozmo",
    }
)


def parece_emocao(texto: str) -> bool:
    t = texto.lower().strip()
    gatilhos = (
        "estou triste",
        "tô triste",
        "to triste",
        "estou feliz",
        "estou mal",
        "me sinto",
        "estou com medo",
        "estou cansado",
        "estou sozinho",
        "quase morri",
    )
    return any(g in t for g in gatilhos)


def parece_pergunta(texto: str) -> bool:
    t = texto.lower().strip()
    if len(t) < 3:
        return False
    if hora.pergunta_hora(t):
        return True
    if any(k in t for k in ("temperatura", "graus", "clima", "bagé", "bage", "frio", "calor")):
        return True
    if t.endswith("?"):
        return True
    if t.startswith(("que ", "qual ", "como ", "quem ", "onde ", "quando ", "por que ", "porque ")):
        return True
    return False


def parece_ruido_tv(texto: str) -> bool:
    """Fragmentos típicos de TV/YouTube no Vosk — não responder."""
    t = re.sub(r"[^\w\sáàâãéêíóôõúüç]", " ", texto.lower()).strip()
    if any(
        k in t
        for k in (
            "cozmo",
            "cosmo",
            "ozmo",
            "coisa",
            "robô",
            "robo",
            "comando",
            "funcionando",
            "funciona",
            "bateria",
            "carreg",
        )
    ):
        return False
    if len(t.split()) >= 8 and not contem_wake(t):
        return True
    palavras_tv = frozenset(
        {
            "veja",
            "assim",
            "próximo",
            "proximo",
            "próximos",
            "proximos",
            "inscreva",
            "inscreve",
            "continua",
            "capítulo",
            "capitulo",
            "publicidade",
            "comentários",
            "comentarios",
        }
    )
    if t in palavras_tv:
        return True
    fragmentos = (
        "os próximos",
        "olá muito bom",
        "ola muito bom",
        "é extensão",
        "e extensao",
        "inscreva",
        "like e",
        "capítulo",
        "continua",
        "publicidade",
    )
    return any(f in t for f in fragmentos)


def parece_fala_dirigida(texto: str) -> bool:
    """Só frases claramente para o robô — evita TV/ruído Vosk."""
    if parece_ruido_tv(texto):
        return False
    if contem_wake(texto) or parece_alias_wake(texto):
        return True
    if parece_comando_curto(texto) or parece_saudacao(texto):
        return True
    if parece_emocao(texto):
        return True
    return parece_pergunta(texto)


def parece_saudacao(texto: str) -> bool:
    t = texto.lower().strip()
    return t in ("oi", "olá", "ola", "hey", "e aí", "e ai", "opa", "fala") or t.startswith(
        ("bom dia", "boa tarde", "boa noite")
    )


def parece_alias_wake(texto: str) -> bool:
    t = re.sub(r"[^\w\sáàâãéêíóôõúüç]", " ", texto.lower()).strip()
    return t in _ALIASES_WAKE


def parece_comando_curto(texto: str) -> bool:
    t = re.sub(r"[^\w\sáàâãéêíóôõúüç]", " ", texto.lower()).strip()
    return t in (
        "oi",
        "opa",
        "hey",
        "fala",
        "beep",
        "ajuda",
        "help",
        "sim",
        "não",
        "nao",
        "para",
        "stop",
    ) or t in _ALIASES_WAKE


def aceitar_sem_wake(texto: str, *, na_base: bool) -> bool:
    if os.environ.get("WAKE_OBRIGATORIO", "0") == "1":
        return contem_wake(texto)
    return len(texto.strip()) >= 1


def parece_interacao(texto: str) -> bool:
    return parece_fala_dirigida(texto)
