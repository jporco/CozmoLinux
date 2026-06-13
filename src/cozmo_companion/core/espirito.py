"""Espírito autônomo — humor, escolhas, atitude e vida própria do Cozmo."""

from __future__ import annotations

import logging
import os
import random
import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable

from cozmo_companion.core.anims import (
    GRUPOS_BASE_IDLE,
    GRUPOS_BASE_VIVO,
    GRUPOS_CURIOSO,
    GRUPOS_MESA,
    GRUPOS_MESA_CARREGADOR,
    GRUPOS_REACAO,
    ContextoAnim,
    filtrar_por_contexto,
)

logger = logging.getLogger("cozmo.espirito")

INTERVALO_MIN = float(os.environ.get("ESPIRITO_MIN_S", "22"))
INTERVALO_MAX = float(os.environ.get("ESPIRITO_MAX_S", "55"))
MESA_INTERVALO_MIN = float(os.environ.get("ESPIRITO_MESA_MIN_S", "6"))
MESA_INTERVALO_MAX = float(os.environ.get("ESPIRITO_MESA_MAX_S", "14"))


class Humor(Enum):
    CURIOSO = auto()
    ANIMADO = auto()
    BRINCALHAO = auto()
    ENTEDIADO = auto()
    CARINHOSO = auto()
    SONOLENTO = auto()


class Acao(Enum):
    NADA = auto()
    ANIM = auto()
    ATITUDE = auto()
    GESTO = auto()
    OLHAR = auto()
    EXPLORAR = auto()
    FALA = auto()
    TELA = auto()


GRUPOS_ATITUDE = (
    "Surprise",
    "ReactToPokeReaction",
    "ReactToPokeStartled",
    "InterestedFace",
    "HappyBirthdayCozmoReaction",
    "CubePounceSuccess",
    "CubeReactionHappy",
    "LookInPlaceForFacesHeadMovePause",
)

GRUPOS_BRINCALHAO = GRUPOS_ATITUDE + (
    "ReactToCliff",
    "NeutralFace",
)

TELAS_ESPONTANEAS = (
    "hmm?",
    "…",
    "beep",
    "oi?",
    "hehe",
    "👀",
    "zZz?",
    "opa",
)


@dataclass
class ContextoVida:
    na_base: bool
    carregando: bool
    falando: bool
    llm_ocupado: bool
    dormindo: bool
    explorando: bool
    face_ativo: bool
    bateria_pct: int
    grupos: set[str]
    contexto_anim: ContextoAnim = ContextoAnim.MESA


@dataclass
class Plano:
    acao: Acao
    grupos: tuple[str, ...] = ()
    duracao: float = 0.0
    texto_tela: str = ""
    prompt_fala: str = ""


class Espirito:
    """Decide o que o Cozmo faz sozinho — animações, gestos, exploração, fala."""

    def __init__(self) -> None:
        self.humor = Humor.CURIOSO
        self._proxima = time.monotonic() + random.uniform(INTERVALO_MIN, INTERVALO_MAX)
        self._entedimento = 0.0
        self._energia = 0.65
        self._ultima_interacao = time.monotonic()
        self._acoes_desde_fala = 0

    @property
    def entediado(self) -> bool:
        return self.humor == Humor.ENTEDIADO or self._entedimento > 0.55

    def registrar_interacao(self, segundos: float = 30.0) -> None:
        agora = time.monotonic()
        self._ultima_interacao = agora
        self._entedimento = max(0.0, self._entedimento - 0.35)
        self._energia = min(1.0, self._energia + 0.25)
        if self.humor == Humor.ENTEDIADO:
            self.humor = random.choice((Humor.CURIOSO, Humor.ANIMADO, Humor.CARINHOSO))
        self._proxima = min(self._proxima, agora + random.uniform(8, 18))

    def _evoluir_humor(self, ctx: ContextoVida) -> None:
        agora = time.monotonic()
        ocioso = agora - self._ultima_interacao
        self._entedimento = min(1.0, self._entedimento + ocioso / 600.0)
        self._energia = max(0.2, self._energia - 0.002)

        if ctx.dormindo:
            self.humor = Humor.SONOLENTO
            return

        if self._entedimento > 0.7:
            self.humor = Humor.ENTEDIADO
        elif self._energia > 0.75 and not ctx.na_base:
            self.humor = random.choice((Humor.ANIMADO, Humor.BRINCALHAO))
        elif ocioso > 180:
            self.humor = Humor.CURIOSO
        elif random.random() < 0.08:
            self.humor = random.choice(list(Humor))

    def _pesos(self, ctx: ContextoVida) -> dict[Acao, float]:
        h = self.humor
        p: dict[Acao, float] = {
            Acao.GESTO: 1.2,
            Acao.OLHAR: 1.0,
            Acao.TELA: 0.6,
            Acao.FALA: 0.5,
        }

        if ctx.carregando:
            p[Acao.ANIM] = 0.0
            p[Acao.EXPLORAR] = 0.0
            p[Acao.ATITUDE] = 0.0
            p[Acao.FALA] = 0.0
            p[Acao.GESTO] = 2.5
            p[Acao.OLHAR] = 1.8 if not ctx.face_ativo else 0.1
            p[Acao.TELA] = 1.0
        elif ctx.na_base:
            p[Acao.EXPLORAR] = 0.0
            p[Acao.ANIM] = 0.6
            p[Acao.ATITUDE] = 0.0
            p[Acao.OLHAR] = 0.0
            p[Acao.GESTO] = 2.5
            p[Acao.TELA] = 0.9
            p[Acao.FALA] = 0.0
        else:
            p[Acao.EXPLORAR] = 2.5 if not ctx.explorando else 0.15
            p[Acao.ANIM] = 2.4
            p[Acao.ATITUDE] = 2.0
            p[Acao.OLHAR] = 1.6
            p[Acao.GESTO] = 1.8
            p[Acao.FALA] = 1.6 if os.environ.get("ESPIRITO_FALA", "0") == "1" else 0.8
            p[Acao.TELA] = 0.9

        if h == Humor.ENTEDIADO:
            p[Acao.FALA] += 1.5
            p[Acao.EXPLORAR] += 0.8
            p[Acao.ATITUDE] += 0.6
        elif h == Humor.BRINCALHAO:
            p[Acao.ATITUDE] += 1.2
            p[Acao.EXPLORAR] += 0.6
            p[Acao.FALA] += 0.5
        elif h == Humor.CURIOSO:
            p[Acao.OLHAR] += 1.0
            p[Acao.EXPLORAR] += 0.5
        elif h == Humor.CARINHOSO:
            p[Acao.GESTO] += 0.8
            p[Acao.FALA] += 0.7
        elif h == Humor.ANIMADO:
            p[Acao.ANIM] += 1.0
            p[Acao.ATITUDE] += 0.8
        elif h == Humor.SONOLENTO:
            p[Acao.GESTO] = 0.3
            p[Acao.TELA] = 0.2

        if ctx.falando or ctx.llm_ocupado:
            return {Acao.NADA: 1.0}

        if self._acoes_desde_fala >= 4:
            p[Acao.FALA] += 1.2

        if ctx.na_base:
            p[Acao.OLHAR] = 0.0
            p[Acao.EXPLORAR] = 0.0

        return p

    def _escolher_acao(self, ctx: ContextoVida) -> Acao:
        pesos = self._pesos(ctx)
        acoes = list(pesos.keys())
        vals = [max(0.01, pesos[a]) for a in acoes]
        return random.choices(acoes, weights=vals, k=1)[0]

    def _montar_plano(self, ctx: ContextoVida, acao: Acao) -> Plano | None:
        h = self.humor
        g = ctx.grupos

        if acao == Acao.GESTO:
            return Plano(Acao.GESTO, duracao=random.uniform(4, 10))

        if acao == Acao.OLHAR:
            return Plano(Acao.OLHAR, duracao=random.uniform(6, 14))

        if acao == Acao.EXPLORAR:
            if ctx.na_base or ctx.explorando:
                return None
            return Plano(Acao.EXPLORAR)

        if acao == Acao.TELA:
            return Plano(Acao.TELA, texto_tela=random.choice(TELAS_ESPONTANEAS))

        if acao == Acao.FALA:
            prompts = {
                Humor.ENTEDIADO: "Como robô entediado, diga uma frase curta pedindo atenção.",
                Humor.BRINCALHAO: "Como robô brincalhão, faça uma piada ou brincadeira curta.",
                Humor.CURIOSO: "Como robô curioso, pergunte algo curto ao usuário.",
                Humor.CARINHOSO: "Como robô carinhoso, diga algo fofo e curto.",
                Humor.ANIMADO: "Como robô animado, comemore algo aleatório em uma frase.",
                Humor.SONOLENTO: "Como robô com sono, resmungue algo curto e engraçado.",
            }
            return Plano(
                Acao.FALA,
                prompt_fala=prompts.get(h, "Diga algo espontâneo e curto como robô companheiro."),
            )

        if acao == Acao.ATITUDE:
            pool = GRUPOS_BRINCALHAO if h == Humor.BRINCALHAO else GRUPOS_ATITUDE
            pool = filtrar_por_contexto(pool, g, ctx.contexto_anim)
            if not pool:
                pool = filtrar_por_contexto(GRUPOS_REACAO, g, ctx.contexto_anim)
            return Plano(Acao.ATITUDE, grupos=pool)

        if acao == Acao.ANIM:
            if ctx.contexto_anim == ContextoAnim.MESA:
                pool = GRUPOS_MESA + GRUPOS_CURIOSO + GRUPOS_ATITUDE
            elif ctx.contexto_anim == ContextoAnim.CARREGADOR:
                pool = GRUPOS_MESA_CARREGADOR + GRUPOS_CURIOSO
            else:
                pool = GRUPOS_BASE_VIVO + GRUPOS_CURIOSO
            pool = filtrar_por_contexto(pool, g, ctx.contexto_anim)
            return Plano(Acao.ANIM, grupos=pool)

        return None

    def _agendar(self, acao: Acao, ctx: ContextoVida) -> None:
        agora = time.monotonic()
        if ctx.na_base:
            base = random.uniform(INTERVALO_MIN, INTERVALO_MAX)
            if ctx.carregando:
                base *= float(os.environ.get("ESPIRITO_BASE_MULT", "1.5"))
            else:
                base *= float(os.environ.get("ESPIRITO_BASE_MULT", "1.5"))
        else:
            base = random.uniform(MESA_INTERVALO_MIN, MESA_INTERVALO_MAX)
            base *= float(os.environ.get("ESPIRITO_MESA_MULT", "0.85"))
        if self.entediado:
            base *= 0.65
        if acao in (Acao.ATITUDE, Acao.EXPLORAR, Acao.FALA):
            base *= 1.2
        self._proxima = agora + base
        if acao == Acao.FALA:
            self._acoes_desde_fala = 0
        else:
            self._acoes_desde_fala += 1

    def tick(self, ctx: ContextoVida) -> Plano | None:
        if ctx.falando or ctx.llm_ocupado or ctx.dormindo:
            return None
        agora = time.monotonic()
        if agora < self._proxima:
            return None

        self._evoluir_humor(ctx)
        acao = self._escolher_acao(ctx)
        if acao == Acao.NADA:
            self._proxima = agora + random.uniform(15, 30)
            return None

        plano = self._montar_plano(ctx, acao)
        if plano is None:
            self._proxima = agora + random.uniform(12, 25)
            return None

        self._agendar(acao, ctx)
        logger.info(
            "Espírito [%s] → %s%s",
            self.humor.name,
            acao.name,
            f" ({plano.grupos[0]})" if plano.grupos else "",
        )
        return plano
