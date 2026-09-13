"""Leitura dos recursos de comportamento distribuídos pelo aplicativo Cozmo.

O companion adapta os sensores do PC aos gatilhos do engine, mas os nomes dos
grupos e a rota ``reactionTrigger -> behaviorID`` vêm dos arquivos originais
instalados. Não há uma segunda lista local fingindo ser o aplicativo.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path


_MAP_RELATIVE = Path("assets/animationGroupMaps/AnimationTriggerMap.json")
_REACTION_MAP_RELATIVE = Path(
    "config/engine/behaviorSystem/reactionTrigger_behavior_map.json"
)
_NOTHING_TO_DO_RELATIVE = Path("config/engine/behaviorSystem/behaviors/freeplay")

# Intenções sem reactionTrigger no engine Android continuam usando eventos do
# AnimationTriggerMap instalado.
_EVENTOS_POR_INTENCAO: dict[str, tuple[str, ...]] = {
    "ambient": (
        "IdleOnCharger",
        "NothingToDoBoredIdle",
        "NothingToDoBoredIntro",
        "NothingToDoBoredEvent",
    ),
    "sound": ("VC_NoFollowupCommand_WithFace", "VC_NoFollowupCommand_NoFace"),
    "notification": (
        "VC_NoFollowupCommand_WithFace",
        "ConnectWakeUp",
        "CodeLabBlink",
        "CodeLabChatty",
    ),
    "sleep": ("GoToSleepGetIn", "GoToSleepSleeping", "Sleeping"),
    "light": ("ConnectWakeUp", "VC_StartledWakeup", "CodeLabAmazed"),
}

# Tradução entre a percepção deste processo e os gatilhos existentes no
# reactionTrigger_behavior_map.json original.
_GATILHO_POR_INTENCAO = {
    "face_seen": "FacePositionUpdated",
    "motion": "UnexpectedMovement",
    "pet": "PetInitialDetection",
    "shake": "RobotShaken",
    "picked_up": "RobotPickedUp",
    "put_down": "PlacedOnCharger",
    "cliff": "CliffDetected",
}

# O engine C++ do app associa estes comportamentos a eventos. Esta ponte usa
# apenas eventos presentes no AnimationTriggerMap instalado; ela é necessária
# porque o processo Python não executa o binário Android.
_EVENTOS_POR_COMPORTAMENTO = {
    "AcknowledgeFace": (
        "AcknowledgeFaceUnnamed",
        "AcknowledgeFaceNamed",
        "AcknowledgeFaceInitPause",
        "InteractWithFacesInitialUnnamed",
        "InteractWithFacesInitialNamed",
    ),
    "ReactToPet": (
        "PetDetectionShort",
        "PetDetectionShort_Cat",
        "PetDetectionShort_Dog",
        "PetDetectionCat",
        "PetDetectionDog",
        "PetDetectionSneeze",
        "ReactToPokeReaction",
    ),
    "ReactToRobotShaken": (
        "DizzyShakeLoop",
        "DizzyShakeStop",
        "DizzyReactionSoft",
        "DizzyReactionMedium",
        "DizzyReactionHard",
        "DizzyStillPickedUp",
    ),
    "ReactToUnexpectedMovement": ("ReactToUnexpectedMovement",),
    "ReactToPickup": ("ReactToPickup", "DizzyStillPickedUp"),
    "ReactToImpact": ("ReactToImpact",),
    "ReactToCliff": ("ReactToCliff", "ReactToCliffDetectorStop"),
    "ReactToOnCharger": ("PlacedOnCharger", "IdleOnCharger"),
}


def _resource_root() -> Path:
    explicit = os.environ.get("COZMO_RESOURCE_DIR", "").strip()
    if explicit:
        base = Path(explicit).expanduser()
        return base / "cozmo_resources" if (base / "cozmo_resources").is_dir() else base
    return Path.home() / ".pycozmo/assets/cozmo_resources"


def _sem_comentarios(texto: str) -> str:
    """Remove comentários JSONC sem alterar conteúdo entre aspas."""
    out: list[str] = []
    i = 0
    em_string = False
    escape = False
    while i < len(texto):
        ch = texto[i]
        prox = texto[i + 1] if i + 1 < len(texto) else ""
        if em_string:
            out.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                em_string = False
            i += 1
        elif ch == '"':
            em_string = True
            out.append(ch)
            i += 1
        elif ch == "/" and prox == "/":
            fim = texto.find("\n", i)
            i = len(texto) if fim < 0 else fim
        elif ch == "/" and prox == "*":
            fim = texto.find("*/", i + 2)
            i = len(texto) if fim < 0 else fim + 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _json_recurso(relativo: Path) -> dict:
    try:
        texto = (_resource_root() / relativo).read_text(encoding="utf-8")
        raw = json.loads(_sem_comentarios(texto))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


@lru_cache(maxsize=1)
def eventos_oficiais() -> frozenset[str]:
    raw = _json_recurso(_MAP_RELATIVE)
    return frozenset(
        str(pair["CladEvent"])
        for pair in raw.get("Pairs", ())
        if isinstance(pair, dict) and isinstance(pair.get("CladEvent"), str)
    )


@lru_cache(maxsize=1)
def gatilhos_reacao_oficiais() -> dict[str, str]:
    """Mapa real reactionTrigger -> behaviorID do app instalado."""
    raw = _json_recurso(_REACTION_MAP_RELATIVE)
    return {
        str(item["reactionTrigger"]): str(item["behaviorID"])
        for item in raw.get("reactionTriggerBehaviorMap", ())
        if isinstance(item, dict)
        and isinstance(item.get("reactionTrigger"), str)
        and isinstance(item.get("behaviorID"), str)
    }


@lru_cache(maxsize=1)
def eventos_ambientais_oficiais() -> tuple[str, ...]:
    """Idles/boredom definidos no Freeplay original."""
    eventos = ["IdleOnCharger"]
    pasta = _resource_root() / _NOTHING_TO_DO_RELATIVE
    try:
        arquivos = sorted(pasta.glob("NothingToDo_*.json"))
    except OSError:
        arquivos = []
    for arquivo in arquivos:
        raw = _json_recurso(arquivo.relative_to(_resource_root()))
        gatilhos = raw.get("animTriggers", raw.get("animationTriggers", ()))
        if isinstance(gatilhos, list):
            eventos.extend(g for g in gatilhos if isinstance(g, str))
    return tuple(dict.fromkeys(eventos))


def _filtrar_eventos(eventos: tuple[str, ...], disponiveis: set[str]) -> tuple[str, ...]:
    mapa = eventos_oficiais()
    return tuple(evento for evento in eventos if evento in mapa and evento in disponiveis)


def grupos_oficiais(intent: str, disponiveis: set[str]) -> tuple[str, ...]:
    return _filtrar_eventos(_EVENTOS_POR_INTENCAO.get(intent, ()), disponiveis)


def grupos_reacao_oficiais(intent: str, disponiveis: set[str]) -> tuple[str, ...]:
    """Resolve sensor pelo behavior system e pelo AnimationTriggerMap reais."""
    gatilho = _GATILHO_POR_INTENCAO.get(intent)
    comportamento = gatilhos_reacao_oficiais().get(gatilho, "") if gatilho else ""
    return _filtrar_eventos(_EVENTOS_POR_COMPORTAMENTO.get(comportamento, ()), disponiveis)


def grupos_ambientais_oficiais(disponiveis: set[str]) -> tuple[str, ...]:
    return _filtrar_eventos(eventos_ambientais_oficiais(), disponiveis) or grupos_oficiais(
        "ambient", disponiveis
    )
