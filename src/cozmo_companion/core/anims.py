"""Catálogo de animações Cozmo — originais, filtradas por contexto (base/mesa)."""

from __future__ import annotations

import logging
import os
import random
from enum import Enum
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    import pycozmo

logger = logging.getLogger("cozmo.anims")

# Grupos que movem rodas ou saem da base — proibidos na carga.
PROIBIDOS_NA_BASE = (
    "Drive",
    "Walk",
    "GoTo",
    "Roll",
    "Patrol",
    "Explore",
    "Pickup",
    "OffCharger",
    "OnCharger",  # animação de sair da base
    "Onboarding",
    "RequestGame",
    "Play",
    "Sphinx",
    "Quiz",
    "Needs",
    "Track",
    "Path",
    "Navigate",
    "TurnTowards",
    "TurnAway",
    "Backup",
    "Forward",
    "BodyPause",
    "BodyMove",
    "BodyTurn",
    "Pounce",
    "Cliff",
    "Fall",
    "Stuck",
    "Deliver",
    "Hiking",
    "DroneMode",
    "FeedingDriving",
)

class ContextoAnim(Enum):
    """Onde o Cozmo está — define quais animações podem rodar."""

    BASE = "base"  # preso na base (botão BASE)
    CARREGADOR = "carregador"  # MESA no carregador — só cabeça/braço
    MESA = "mesa"  # livre na mesa


def detectar_contexto_anim(*, preso_na_base: bool, no_carregador: bool) -> ContextoAnim:
    if preso_na_base:
        return ContextoAnim.BASE
    if not no_carregador:
        return ContextoAnim.CARREGADOR
    return ContextoAnim.MESA

_SEGUROS_NA_BASE = frozenset(
    {
        "IdleOnCharger",
        "PlacedOnCharger",
        "IdleOnChargerCharging",
        "GoToSleepGetIn",
        "GoToSleepGetOut",
        "GoToSleepSleeping",
        "GoToSleepOff",
        "StartSleeping",
        "Sleeping",
        "sleeploop",
        "gotoSleep_sleeping",
        "GuardDogSleepLoop",
        "Hiccup",
        "HiccupGetIn",
        "CodeLabHiccup",
        "ConnectWakeUp",
        "ConnectWakeUp_SevereEnergy",
        "ConnectWakeUp_SevereRepair",
        "HikingWakeUpOffCharger",
        "VC_StartledWakeup",
        "OnboardingWakeUpDriveOffCharger",
        "LookInPlaceForFacesHeadMovePause",
        "InteractWithFaceTrackingIdle",
        "ReactToPokeReaction",
        "NeutralFace",
        "InterestedFace",
        "CodeLabHiccup",
        "FeedingIdleSearchForFaces_Normal",
    }
)

# Sono na base (só ciclo vida dormindo — separado do acordado).
GRUPOS_BASE_SONO_SEM_RODAS = frozenset(
    {
        "GoToSleepGetIn",
        "GoToSleepSleeping",
        "Sleeping",
        "sleeploop",
        "gotoSleep_sleeping",
        "GuardDogSleepLoop",
    }
)

# Só rosto/cabeça leve na base — sem LookInPlace/Feeding (mexem o corpo).
GRUPOS_BASE_OLED_SEGUROS = (
    "IdleOnCharger",
    "NeutralFace",
    "InterestedFace",
    "LookInPlaceForFacesHeadMovePause",
    "CodeLabBlink",
    "CodeLabSquint1",
    "CodeLabUnimpressed",
    "Hiccup",
    "CodeLabHiccup",
    "Boredom",
)

# Variação na base — patch imobiliza clip; estes grupos são só expressão OLED.
GRUPOS_BASE_OLED_VARIAR = GRUPOS_BASE_OLED_SEGUROS + (
    "LookInPlaceForFacesHeadMovePause",
    "InteractWithFaceTrackingIdle",
    "FeedingIdleSearchForFaces_Normal",
    "Hiccup",
    "HiccupGetIn",
    "CodeLabHiccup",
    "CodeLabBlink",
    "CodeLabSquint1",
    "CodeLabSquint2",
    "CodeLabUnimpressed",
    "CodeLabFrustrated",
    "CodeLabWin",
    "CodeLabLose",
    "Boredom",
    "ScoutBeg",
    "Victory",
    "LoseGame",
    # Expressões de olhos do firmware (validadas contra animation_groups reais).
    "CodeLabAmazed",
    "CodeLabBored",
    "CodeLabCelebrate",
    "CodeLabChatty",
    "CodeLabCurious",
    "CodeLabDejected",
    "CodeLabExcited",
    "CodeLabHappy",
    "CodeLabHeadsUp",
    "CodeLabIDK",
    "CodeLabIdle",
    "CodeLabReactHappy",
    "CodeLabSneeze",
    "CodeLabStaring",
    "CodeLabThinking",
    "CodeLabTwitch",
    "CodeLabUnhappy",
    "CodeLabVictory",
    "CodeLabWhew",
    "CodeLabWondering",
    "CodeLabYes",
    "CodeLabYuck",
    "CodeLabVampire",
    "CodeLabZombie",
    # Idles expressivos de modos/jogos (sem rodas após patch).
    "NothingToDoBoredIdle",
    "NothingToDoBoredIntro",
    "NothingToDoBoredOutro",
    "PeekABooIdle",
    "PatternGuessThinking",
    "MeetCozmoScanningIdle",
    "CozmoSaysIdle",
    "SparkIdle",
    "GameSetupIdle",
    "RepairIdleFullyRepaired",
    "FeedingIdleSearch_Normal",
)

# Quebram no worker charger ou encaixe barulhento — não sortear.
GRUPOS_BASE_OLED_VARIAR_BLOQUEIO = frozenset(
    {
        "PlacedOnCharger",
        "DizzyReactionSoft",
        "CodeLabWhoa",
        "CodeLab123Go",
        "CodeLabDog",
        "CodeLabCat",
        "CodeLabChicken",
        "CodeLabDuck",
        "CodeLabFrog",
        "CodeLabSheep",
        "CodeLabRooster",
        "CodeLabTiger",
        "CodeLabElephant",
        "CodeLabCow",
        "NothingToDoBoredEvent",
        "AcknowledgeFaceNamed",
        "IdleOnChargerCharging",
        "GoToSleepGetIn",
        "GoToSleepSleeping",
        "Sleeping",
        "StartSleeping",
        "sleeploop",
        "GameSetupIdle",
        "RepairIdleFullyRepaired",
        "SparkIdle",
        "CozmoSaysIdle",
        "BuildPyramidLookForFace",
        "NothingToDoBoredIntro",
        "NothingToDoBoredIdle",
    }
)

_MARCADORES_OLED_EXTRA = (
    "Face",
    "LookInPlace",
    "Hiccup",
    "CodeLab",
    "InteractWithFace",
    "Scout",
    "Bored",
    "Frustrated",
    "Victory",
    "LoseGame",
    "FeedingIdle",
)

GRUPOS_BASE_OLED_OLHOS_PRIORIDADE = GRUPOS_BASE_OLED_VARIAR

_OLHOS_OLED_BLOQUEIO = (
    "BodyPause",
    "BodyMove",
    "BodyTurn",
    "OffCharger",
    "Drive",
    "Walk",
    "Pounce",
    "Cliff",
    "Startled",
    "Surprise",
    "Cube",
    "Hiking",
    "Deliver",
    "Path",
    "Navigate",
    "Roll",
    "Patrol",
    "Explore",
    "SearchForFaces",
    "FeedingIdle",
)

# Sem “bater com a mão” / susto na base (patch de rodas não cobre gesto agressivo).
_MARCADORES_BLOQUEIO_TOQUE = (
    "Poke",
    "Startled",
    "Surprise",
    "Frustrated",
    "Block",
    "Bark",
    "Whoa",
    "123Go",
)

GRUPOS_BASE_ESPIAR_ESCURO = (
    "NeutralFace",
    "InterestedFace",
    "CodeLabBlink",
    "LookInPlaceForFacesHeadMovePause",
    "IdleOnCharger",
)

_PROIBIDOS_RODAS_NA_BASE = frozenset(
    {
        "Surprise",
        "ReactToPokeStartled",
        "ReactToCliff",
        "CubePounceSuccess",
        "HappyBirthdayCozmoReaction",
        "CubeReactionHappy",
    }
)

# Preferências por humor — nomes reais do firmware Cozmo.
GRUPOS_SONO_ENTRADA = (
    "GoToSleepGetIn",
    "StartSleeping",
    "GoToSleepSleeping",
)

GRUPOS_SONO = (
    "GoToSleepSleeping",
    "Sleeping",
    "sleeploop",
    "gotoSleep_sleeping",
    "GuardDogSleepLoop",
    "StartSleeping",
)

GRUPOS_SONO_RONCO = (
    "Hiccup",
    "HiccupGetIn",
    "CodeLabHiccup",
)

GRUPOS_BASE_IDLE = (
    "PlacedOnCharger",
    "IdleOnCharger",
    "NeutralFace",
    "InterestedFace",
    "LookInPlaceForFacesHeadMovePause",
    "InteractWithFaceTrackingIdle",
    "FeedingIdleSearchForFaces_Normal",
)

# Gestos expressivos na base — sem som de encaixe (PlacedOnCharger).
GRUPOS_BASE_VIVO = (
    "NeutralFace",
    "InterestedFace",
    "LookInPlaceForFacesHeadMovePause",
    "InteractWithFaceTrackingIdle",
    "ReactToPokeReaction",
    "Hiccup",
    "HiccupGetIn",
    "CodeLabHiccup",
    "CodeLabBlink",
    "CodeLabSquint1",
    "CodeLabUnimpressed",
    "Boredom",
    "ScoutBeg",
    "Victory",
    "LoseGame",
)

# Sonolento / descanso — olhos pesados, sem entrar no sono profundo.
GRUPOS_BASE_DESCANSO = (
    "CodeLabBlink",
    "CodeLabSquint1",
    "CodeLabUnimpressed",
    "Boredom",
    "NeutralFace",
    "InterestedFace",
    "Hiccup",
    "HiccupGetIn",
    "GoToSleepGetIn",
)

GRUPOS_BASE_CABECA = GRUPOS_BASE_VIVO

# Clips OLED na base — só cabeça/olhos, sem rodas.
GRUPOS_BASE_OLED_ROTACAO = GRUPOS_BASE_OLED_OLHOS_PRIORIDADE

GRUPOS_SOM_CARGA = frozenset(
    {
        "PlacedOnCharger",
        "IdleOnCharger",
    }
)

GRUPOS_REACAO = (
    "ReactToPokeReaction",
    "ReactToPokeStartled",
    "Surprise",
    "InterestedFace",
    "HappyBirthdayCozmoReaction",
    "CubePounceSuccess",
    "CubeReactionHappy",
    "CodeLabAmazed",
    "CodeLabExcited",
    "CodeLabWhoa",
)

GRUPOS_CURIOSO = (
    "LookInPlaceForFacesHeadMovePause",
    "InteractWithFaceTrackingIdle",
    "FeedingIdleSearchForFaces_Normal",
    "NeutralFace",
    "InterestedFace",
)

GRUPOS_MESA = (
    "LookInPlaceForFacesHeadMovePause",
    "InteractWithFaceTrackingIdle",
    "FeedingIdleSearchForFaces_Normal",
    "NeutralFace",
    "InterestedFace",
    "ReactToPokeReaction",
    "Surprise",
    "ReactToPokeStartled",
    "HappyBirthdayCozmoReaction",
    "CubeReactionHappy",
    "CubePounceSuccess",
    "CodeLabAmazed",
    "CodeLabCurious",
    "CodeLabExcited",
    "CodeLabHappy",
    "CodeLabReactHappy",
    "CodeLabVictory",
    "CodeLabWhew",
    "CodeLabWondering",
    "CodeLabYes",
    "CodeLabChicken",
    "CodeLabDuck",
    "CodeLabFrog",
    "CodeLabSheep",
    "CodeLabDancingMambo",
    "CodeLabCelebrate",
    "CodeLabEnergyEat",
    "CodeLabWin",
    "CodeLabDizzy",
    "CodeLabTwitch",
)

GRUPOS_MESA_CARREGADOR = (
    "LookInPlaceForFacesHeadMovePause",
    "InteractWithFaceTrackingIdle",
    "FeedingIdleSearchForFaces_Normal",
    "NeutralFace",
    "InterestedFace",
    "ReactToPokeReaction",
)

GRUPOS_CARETAS = (
    "Surprise",
    "InterestedFace",
    "NeutralFace",
    "ReactToPokeReaction",
    "ReactToPokeStartled",
    "HappyBirthdayCozmoReaction",
)

GRUPOS_CARETAS_BASE = (
    "InterestedFace",
    "NeutralFace",
    "ReactToPokeReaction",
    "LookInPlaceForFacesHeadMovePause",
)

GRUPOS_SUSTO = (
    "ReactToPokeStartled",
    "Surprise",
    "ReactToCliff",
    "ReactToPokeReaction",
)

GRUPOS_SUSTO_BASE = (
    "ReactToPokeReaction",
    "InterestedFace",
    "NeutralFace",
)

GRUPOS_CARINHO_BASE = (
    "ReactToPokeReaction",
    "NeutralFace",
    "InterestedFace",
    "LookInPlaceForFacesHeadMovePause",
)

GRUPOS_CARINHO_MESA = GRUPOS_CARINHO_BASE + (
    "Surprise",
    "HappyBirthdayCozmoReaction",
)

GRUPOS_LATIDO_BASE = (
    "ReactToPokeReaction",
    "CodeLabAmazed",
    "CodeLabWhew",
    "NeutralFace",
    "InterestedFace",
)

GRUPOS_LATIDO_MESA = GRUPOS_LATIDO_BASE + (
    "Surprise",
    "CubePounceSuccess",
)

GRUPOS_ACORDAR = (
    "GoToSleepGetOut",
    "ConnectWakeUp",
    "HikingWakeUpOffCharger",
    "VC_StartledWakeup",
    "ConnectWakeUp_SevereEnergy",
    "ConnectWakeUp_SevereRepair",
    "OnboardingWakeUpDriveOffCharger",
)

GRUPOS_ACORDAR_TOQUE = (
    "GoToSleepGetOut",
    "ConnectWakeUp",
    "VC_StartledWakeup",
    "HikingWakeUpOffCharger",
    "Surprise",
    "ReactToPokeStartled",
    "ReactToPokeReaction",
    "InterestedFace",
    "NeutralFace",
)


def _proibido_na_base(nome: str) -> bool:
    if nome in _SEGUROS_NA_BASE:
        return False
    return any(p in nome for p in PROIBIDOS_NA_BASE)


def permitido_sem_rodas_na_base(nome: str) -> bool:
    """Na base: permite clips de olhos/carga; bloqueia só drive/saída da base."""
    if nome in _PROIBIDOS_RODAS_NA_BASE:
        return False
    if nome in _SEGUROS_NA_BASE:
        return True
    return not _proibido_na_base(nome)


def permitido_anim_normal_base(nome: str) -> bool:
    """Olhos/cabeça na base — sem rodas e sem toque/susto (mãozinha)."""
    if not permitido_sem_rodas_na_base(nome):
        return False
    return not any(m in nome for m in _MARCADORES_BLOQUEIO_TOQUE)


def _eh_clip_olhos_oled(nome: str) -> bool:
    return permitido_sem_rodas_na_base(nome)


def _candidatos_sao_sono(candidatos: Iterable[str]) -> bool:
    for c in candidatos:
        if c in GRUPOS_BASE_SONO_SEM_RODAS:
            return True
    return False


def filtrar_sono_na_base(
    candidatos: Iterable[str],
    disponiveis: set[str],
) -> tuple[str, ...]:
    ok = [
        c
        for c in candidatos
        if c in disponiveis and c in GRUPOS_BASE_SONO_SEM_RODAS
    ]
    return tuple(ok) if ok else ("GoToSleepSleeping", "Sleeping")


def _extras_variacao_por_nome(disponiveis: set[str]) -> tuple[str, ...]:
    """Extras do firmware (olhos/gesto) — patch de rodas na reprodução."""
    cap = int(os.environ.get("COZMO_BASE_VARIAR_EXTRA_MAX", "14"))
    extras: list[str] = []
    for g in sorted(disponiveis):
        if g in GRUPOS_BASE_OLED_VARIAR_BLOQUEIO or g in extras:
            continue
        if not permitido_anim_normal_base(g):
            continue
        if not any(m in g for m in _MARCADORES_OLED_EXTRA):
            continue
        extras.append(g)
        if len(extras) >= cap:
            break
    return tuple(extras)


def pool_sono_oled_base(
    disponiveis: set[str],
    cli: "pycozmo.Client | None" = None,
) -> tuple[str, ...]:
    """Pool de sono na base (escuro) — clips sem rodas."""
    del cli
    return filtrar_sono_na_base(GRUPOS_BASE_SONO_SEM_RODAS, disponiveis)


def pool_variacao_oled_base(
    disponiveis: set[str],
    cli: "pycozmo.Client | None" = None,
) -> tuple[str, ...]:
    """Pool para variar na base — seguro na dock ou lista ampla."""
    del cli
    seguro = os.environ.get("COZMO_BASE_POOL_SEGURO", "1") == "1"
    fonte = GRUPOS_BASE_OLED_SEGUROS if seguro else GRUPOS_BASE_OLED_VARIAR
    vistos: set[str] = set()
    out: list[str] = []
    for g in fonte:
        if (
            g in disponiveis
            and g not in GRUPOS_BASE_OLED_VARIAR_BLOQUEIO
            and permitido_anim_normal_base(g)
            and g not in vistos
        ):
            out.append(g)
            vistos.add(g)
    if not seguro:
        for g in _extras_variacao_por_nome(disponiveis):
            if g not in vistos:
                out.append(g)
                vistos.add(g)
    return tuple(out)


def pool_espiar_escuro_base(
    disponiveis: set[str],
    cli: "pycozmo.Client | None" = None,
) -> tuple[str, ...]:
    """Escuro: olhadinha curta (rosto) antes de voltar ao sono."""
    del cli
    ok = [
        g
        for g in GRUPOS_BASE_ESPIAR_ESCURO
        if g in disponiveis and permitido_anim_normal_base(g)
    ]
    return tuple(ok) if ok else ("NeutralFace", "InterestedFace")


def pool_olhos_oled_base(
    disponiveis: set[str],
    cli: "pycozmo.Client | None" = None,
) -> tuple[str, ...]:
    """Alias — rotação OLED na base."""
    pool = pool_variacao_oled_base(disponiveis, cli)
    return pool if pool else ("NeutralFace", "InterestedFace", "IdleOnCharger")


def filtrar_olhos_oled_base(
    candidatos: Iterable[str],
    disponiveis: set[str],
) -> tuple[str, ...]:
    pool = pool_olhos_oled_base(disponiveis)
    ok = [c for c in candidatos if c in pool]
    return tuple(ok) if ok else pool


def filtrar_sem_som_carga(
    candidatos: Iterable[str],
    disponiveis: set[str],
) -> tuple[str, ...]:
    """Remove animações barulhentas de encaixe na base."""
    ok = [
        c
        for c in candidatos
        if c in disponiveis and c not in GRUPOS_SOM_CARGA
    ]
    if ok:
        return tuple(ok)
    return filtrar_na_base(candidatos, disponiveis)


def filtrar_cabeca_na_base(
    candidatos: Iterable[str],
    disponiveis: set[str],
) -> tuple[str, ...]:
    """Só whitelist sem rodas na base."""
    ok = [c for c in candidatos if c in disponiveis and permitido_sem_rodas_na_base(c)]
    if ok:
        return tuple(ok)
    return pool_olhos_oled_base(disponiveis) or ("IdleOnCharger", "NeutralFace")


def filtrar_na_base(
    candidatos: Iterable[str],
    disponiveis: set[str],
) -> tuple[str, ...]:
    ok = [
        c
        for c in candidatos
        if c in disponiveis and permitido_sem_rodas_na_base(c)
    ]
    if ok:
        return tuple(ok)
    todos = [g for g in disponiveis if permitido_sem_rodas_na_base(g)]
    return tuple(todos) if todos else ("IdleOnCharger", "NeutralFace")


def todos_na_base(disponiveis: set[str]) -> tuple[str, ...]:
    return filtrar_na_base(disponiveis, disponiveis)


GRUPOS_LATIDO = GRUPOS_LATIDO_MESA


def pool_por_contexto(
    candidatos: Iterable[str],
    ctx: ContextoAnim,
) -> tuple[str, ...]:
    """Escolhe pool de preferência conforme BASE / carregador / mesa."""
    c = tuple(candidatos)
    if ctx == ContextoAnim.MESA:
        return c
    if ctx == ContextoAnim.CARREGADOR:
        return c + GRUPOS_MESA_CARREGADOR
    return c + GRUPOS_BASE_VIVO


def filtrar_por_contexto(
    candidatos: Iterable[str],
    disponiveis: set[str],
    ctx: ContextoAnim,
    *,
    sem_som_carga: bool = False,
) -> tuple[str, ...]:
    if ctx == ContextoAnim.MESA:
        ok = [c for c in candidatos if c in disponiveis]
        if ok:
            return tuple(ok)
        fallback = [g for g in GRUPOS_MESA if g in disponiveis]
        return tuple(fallback) if fallback else ("NeutralFace",)
    if ctx == ContextoAnim.BASE and _candidatos_sao_sono(candidatos):
        pool = filtrar_sono_na_base(candidatos, disponiveis)
    else:
        pool = filtrar_cabeca_na_base(candidatos, disponiveis)
    if sem_som_carga and ctx == ContextoAnim.BASE:
        sem = tuple(c for c in pool if c not in GRUPOS_SOM_CARGA)
        if sem:
            pool = sem
    if pool:
        return pool
    if ctx == ContextoAnim.CARREGADOR:
        return filtrar_cabeca_na_base(GRUPOS_MESA_CARREGADOR, disponiveis)
    return filtrar_cabeca_na_base(GRUPOS_BASE_VIVO, disponiveis)


def escolher_ctx(
    disponiveis: set[str],
    candidatos: Iterable[str],
    ctx: ContextoAnim,
    *,
    sem_som_carga: bool = False,
) -> str | None:
    pool = filtrar_por_contexto(
        candidatos,
        disponiveis,
        ctx,
        sem_som_carga=sem_som_carga,
    )
    if not pool:
        return None
    return random.choice(pool)


def filtrar_carga_ativa(
    candidatos: Iterable[str],
    disponiveis: set[str],
    animacoes_carga: frozenset[str] | set[str],
) -> tuple[str, ...]:
    """Durante carga ativa — só animações de carga ou gestos base seguros."""
    seguros = filtrar_por_contexto(
        candidatos,
        disponiveis,
        ContextoAnim.BASE,
        sem_som_carga=True,
    )
    ok = tuple(c for c in seguros if c in animacoes_carga)
    if ok:
        return ok
    fallback = tuple(c for c in GRUPOS_BASE_VIVO if c in disponiveis)
    return fallback if fallback else ("NeutralFace",)


def escolher(
    disponiveis: set[str],
    candidatos: Iterable[str],
    *,
    na_base: bool = True,
    so_cabeca: bool = False,
) -> str | None:
    if not na_base:
        ctx = ContextoAnim.MESA
    elif so_cabeca:
        ctx = ContextoAnim.BASE
    else:
        ctx = ContextoAnim.CARREGADOR
    sem_som = ctx == ContextoAnim.BASE
    return escolher_ctx(
        disponiveis,
        candidatos,
        ctx,
        sem_som_carga=sem_som,
    )


def registrar_inventario(disponiveis: set[str]) -> None:
    seguros = todos_na_base(disponiveis)
    logger.info(
        "Animações: %d grupos total, %d seguros na base",
        len(disponiveis),
        len(seguros),
    )
