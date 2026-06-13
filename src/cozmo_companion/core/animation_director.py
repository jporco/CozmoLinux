"""Escolha de repertório por intenção sem enviar comandos ao robô."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from cozmo_companion.core.anims import (
    GRUPOS_BASE_DESCANSO,
    GRUPOS_BASE_VIVO,
    GRUPOS_CARINHO_BASE,
    GRUPOS_CARINHO_MESA,
    GRUPOS_CURIOSO,
    GRUPOS_MESA,
    GRUPOS_REACAO,
    GRUPOS_SONO,
    GRUPOS_SUSTO,
    ContextoAnim,
    filtrar_por_contexto,
    pool_variacao_oled_base,
)


class AnimIntent(str, Enum):
    AMBIENT = "ambient"
    LIGHT = "light"
    FACE_SEEN = "face_seen"
    NOTIFICATION = "notification"
    PET = "pet"
    SLEEP = "sleep"
    CLIFF = "cliff"


@dataclass(frozen=True)
class AnimationDirector:
    """Resolve intenção em grupos candidatos filtrados por contexto."""

    def pool(
        self,
        disponiveis: set[str],
        ctx: ContextoAnim,
        intent: AnimIntent,
    ) -> tuple[str, ...]:
        if intent == AnimIntent.SLEEP:
            candidatos = GRUPOS_SONO
        elif intent == AnimIntent.FACE_SEEN:
            candidatos = GRUPOS_CURIOSO + GRUPOS_BASE_VIVO
        elif intent == AnimIntent.NOTIFICATION:
            candidatos = (
                "InterestedFace",
                "CodeLabBlink",
                "LookInPlaceForFacesHeadMovePause",
                "Hiccup",
            )
        elif intent == AnimIntent.PET:
            candidatos = GRUPOS_CARINHO_BASE if ctx != ContextoAnim.MESA else GRUPOS_CARINHO_MESA
        elif intent == AnimIntent.CLIFF:
            candidatos = GRUPOS_SUSTO
        elif intent == AnimIntent.LIGHT:
            if ctx == ContextoAnim.BASE:
                return pool_variacao_oled_base(disponiveis)
            candidatos = GRUPOS_CURIOSO
        else:
            candidatos = GRUPOS_BASE_DESCANSO if ctx == ContextoAnim.BASE else GRUPOS_MESA

        return filtrar_por_contexto(
            candidatos,
            disponiveis,
            ctx,
            sem_som_carga=ctx == ContextoAnim.BASE,
        )

    def first_available(
        self,
        disponiveis: set[str],
        ctx: ContextoAnim,
        intent: AnimIntent,
    ) -> str | None:
        pool = self.pool(disponiveis, ctx, intent)
        return pool[0] if pool else None
