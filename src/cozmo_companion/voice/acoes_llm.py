"""Ações físicas decididas pelo LLM — animação + tela além da fala."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum

from cozmo_companion.core.anims import GRUPOS_REACAO, GRUPOS_SONO
from cozmo_companion.voice.resposta import encurtar_fala

logger = logging.getLogger("cozmo.acoes")

ACOES_PROMPT = (
    "Além de falar, escolha UMA ação física que combine com o momento:\n"
    "carinho (afeto), triste (solidariedade), feliz (comemorar), surpresa (espanto), "
    "curioso (investigar), animado (energia), conforto (acalmar tristeza), "
    "dancar (dançar/brincar), explorar (andar pela mesa), dormir (cochilar), nada (só falar).\n"
    "Na base carregando prefira carinho, triste, conforto, curioso ou nada — evite explorar.\n"
    "Responda EXATAMENTE neste formato, sem markdown:\n"
    "FALA: sua frase curta em português\n"
    "ACAO: nome_da_acao"
)


class AcaoEmocional(str, Enum):
    NADA = "nada"
    CARINHO = "carinho"
    TRISTE = "triste"
    FELIZ = "feliz"
    SURPRESA = "surpresa"
    CURIOSO = "curioso"
    ANIMADO = "animado"
    CONFORTO = "conforto"
    DANCAR = "dancar"
    EXPLORAR = "explorar"
    DORMIR = "dormir"


@dataclass
class RespostaCozmo:
    fala: str
    acao: AcaoEmocional = AcaoEmocional.NADA
    tela: str = ""


GRUPOS_POR_ACAO: dict[AcaoEmocional, tuple[str, ...]] = {
    AcaoEmocional.CARINHO: (
        "ReactToPokeReaction",
        "NeutralFace",
        "InterestedFace",
        "Surprise",
    ),
    AcaoEmocional.TRISTE: ("NeutralFace", "InterestedFace"),
    AcaoEmocional.FELIZ: (
        "HappyBirthdayCozmoReaction",
        "CubeReactionHappy",
        "Surprise",
        "ReactToPokeReaction",
    ),
    AcaoEmocional.SURPRESA: ("Surprise", "ReactToPokeStartled", "ReactToPokeReaction"),
    AcaoEmocional.CURIOSO: (
        "LookInPlaceForFacesHeadMovePause",
        "InterestedFace",
        "InteractWithFaceTrackingIdle",
        "FeedingIdleSearchForFaces_Normal",
    ),
    AcaoEmocional.ANIMADO: GRUPOS_REACAO,
    AcaoEmocional.CONFORTO: (
        "ReactToPokeReaction",
        "NeutralFace",
        "InterestedFace",
    ),
    AcaoEmocional.DANCAR: (
        "HappyBirthdayCozmoReaction",
        "CubeReactionHappy",
        "CubePounceSuccess",
        "Surprise",
        "ReactToPokeReaction",
    ),
    AcaoEmocional.EXPLORAR: (
        "LookInPlaceForFacesHeadMovePause",
        "InterestedFace",
        "NeutralFace",
    ),
    AcaoEmocional.DORMIR: GRUPOS_SONO,
    AcaoEmocional.NADA: (),
}

TELA_POR_ACAO: dict[AcaoEmocional, str] = {
    AcaoEmocional.TRISTE: "…",
    AcaoEmocional.FELIZ: ":)",
    AcaoEmocional.CARINHO: "<3",
    AcaoEmocional.CONFORTO: "♥",
    AcaoEmocional.SURPRESA: "!?",
    AcaoEmocional.CURIOSO: "?",
    AcaoEmocional.ANIMADO: "beep!",
    AcaoEmocional.DANCAR: "♪",
    AcaoEmocional.EXPLORAR: "→",
    AcaoEmocional.DORMIR: "zZz",
}

_ALIASES: dict[str, AcaoEmocional] = {
    "carinho": AcaoEmocional.CARINHO,
    "carinhoso": AcaoEmocional.CARINHO,
    "afeto": AcaoEmocional.CARINHO,
    "triste": AcaoEmocional.TRISTE,
    "tristeza": AcaoEmocional.TRISTE,
    "feliz": AcaoEmocional.FELIZ,
    "alegre": AcaoEmocional.FELIZ,
    "surpresa": AcaoEmocional.SURPRESA,
    "espanto": AcaoEmocional.SURPRESA,
    "curioso": AcaoEmocional.CURIOSO,
    "animado": AcaoEmocional.ANIMADO,
    "conforto": AcaoEmocional.CONFORTO,
    "acalmar": AcaoEmocional.CONFORTO,
    "dancar": AcaoEmocional.DANCAR,
    "dança": AcaoEmocional.DANCAR,
    "danca": AcaoEmocional.DANCAR,
    "explorar": AcaoEmocional.EXPLORAR,
    "explora": AcaoEmocional.EXPLORAR,
    "dormir": AcaoEmocional.DORMIR,
    "sono": AcaoEmocional.DORMIR,
    "cochilar": AcaoEmocional.DORMIR,
    "nada": AcaoEmocional.NADA,
    "none": AcaoEmocional.NADA,
}

_INFERIR_USUARIO: tuple[tuple[tuple[str, ...], AcaoEmocional], ...] = (
    (("estou triste", "tô triste", "to triste", "me sinto mal", "estou mal", "deprimido", "chateado", "quase morri"), AcaoEmocional.CONFORTO),
    (("triste", "tristeza", "chorando", "chorei", "solidão", "sozinho"), AcaoEmocional.TRISTE),
    (("feliz", "alegre", "animado", "massa", "legal demais", "consegui", "venci"), AcaoEmocional.FELIZ),
    (("medo", "assustado", "susto", "nossa", "caramba"), AcaoEmocional.SURPRESA),
    (("como funciona", "por que", "porque", "explica", "conta"), AcaoEmocional.CURIOSO),
    (("obrigado", "valeu", "te amo", "carinho", "abraço"), AcaoEmocional.CARINHO),
    (("dança", "danca", "dancar", "dançar", "baila"), AcaoEmocional.DANCAR),
    (("explora", "explorar", "vai lá", "vai la", "anda"), AcaoEmocional.EXPLORAR),
    (("dorme", "dormir", "boa noite", "cochila", "vai dormir", "sono"), AcaoEmocional.DORMIR),
)


def _normalizar_acao(raw: str) -> AcaoEmocional:
    chave = re.sub(r"[^a-záàâãéêíóôõúç]", "", raw.strip().lower())
    if chave in _ALIASES:
        return _ALIASES[chave]
    for nome, acao in _ALIASES.items():
        if nome in chave or chave in nome:
            return acao
    return AcaoEmocional.NADA


def parse_resposta_bruta(texto: str) -> RespostaCozmo:
    """Extrai FALA e ACAO do output do Ollama."""
    texto = texto.strip()
    if not texto:
        return RespostaCozmo(fala="")

    fala = ""
    acao = AcaoEmocional.NADA
    linhas_restantes: list[str] = []

    for linha in texto.splitlines():
        upper = linha.strip().upper()
        if upper.startswith("FALA:"):
            fala = linha.split(":", 1)[1].strip()
        elif upper.startswith("ACAO:") or upper.startswith("AÇÃO:"):
            acao = _normalizar_acao(linha.split(":", 1)[1])
        else:
            linhas_restantes.append(linha.strip())

    if not fala:
        fala = " ".join(linhas_restantes).strip()
        fala = re.sub(r"^\s*[\"']|[\"']\s*$", "", fala)

    fala = encurtar_fala(fala, max_palavras=6, max_chars=40)

    return RespostaCozmo(fala=fala, acao=acao, tela=TELA_POR_ACAO.get(acao, ""))


def inferir_acao_do_usuario(usuario: str) -> AcaoEmocional:
    u = usuario.lower()
    for gatilhos, acao in _INFERIR_USUARIO:
        if any(g in u for g in gatilhos):
            return acao
    return AcaoEmocional.NADA


def resolver_acao(resposta: RespostaCozmo, usuario: str) -> AcaoEmocional:
    if resposta.acao != AcaoEmocional.NADA:
        return resposta.acao
    return inferir_acao_do_usuario(usuario)


def grupos_para_acao(acao: AcaoEmocional) -> tuple[str, ...]:
    return GRUPOS_POR_ACAO.get(acao, ())


def tela_para_acao(acao: AcaoEmocional, tela_llm: str = "") -> str:
    if tela_llm.strip():
        return tela_llm.strip()[:16]
    return TELA_POR_ACAO.get(acao, "")


def acao_requer_explorar(acao: AcaoEmocional) -> bool:
    return acao == AcaoEmocional.EXPLORAR


def acao_requer_sono(acao: AcaoEmocional) -> bool:
    return acao == AcaoEmocional.DORMIR


def acao_bloqueada_na_carga(acao: AcaoEmocional) -> bool:
    """Evita motor/TTS pesado enquanto carrega."""
    return acao in (
        AcaoEmocional.EXPLORAR,
        AcaoEmocional.DANCAR,
        AcaoEmocional.ANIMADO,
    )


def espirito_para_acao_emocional(humor_name: str, acao_espirito: str) -> AcaoEmocional:
    """Mapeia humor + ação do espírito autônomo para o catálogo LLM."""
    h = humor_name.upper()
    a = acao_espirito.upper()

    if a == "EXPLORAR":
        return AcaoEmocional.EXPLORAR
    if a == "OLHAR":
        return AcaoEmocional.CURIOSO
    if a == "GESTO" and h == "CARINHOSO":
        return AcaoEmocional.CARINHO
    if a == "ATITUDE":
        return AcaoEmocional.DANCAR if h == "BRINCALHAO" else AcaoEmocional.ANIMADO
    if a == "ANIM":
        return AcaoEmocional.DANCAR if h == "BRINCALHAO" else AcaoEmocional.ANIMADO
    if a == "TELA" and h == "SONOLENTO":
        return AcaoEmocional.DORMIR
    if a == "FALA":
        return {
            "ENTEDIADO": AcaoEmocional.ANIMADO,
            "CARINHOSO": AcaoEmocional.CARINHO,
            "BRINCALHAO": AcaoEmocional.DANCAR,
            "CURIOSO": AcaoEmocional.CURIOSO,
            "SONOLENTO": AcaoEmocional.DORMIR,
            "ANIMADO": AcaoEmocional.FELIZ,
        }.get(h, AcaoEmocional.NADA)
    return AcaoEmocional.NADA
