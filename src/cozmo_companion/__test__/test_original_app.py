"""Integração do repertório com os resources do aplicativo oficial Cozmo."""

from __future__ import annotations

from cozmo_companion.core.animation_director import AnimIntent, AnimationDirector
from cozmo_companion.core.anims import ContextoAnim, pool_variacao_oled_base
from cozmo_companion.core.original_app import (
    eventos_oficiais,
    gatilhos_reacao_oficiais,
    grupos_oficiais,
    grupos_reacao_oficiais,
)


def test_mapa_do_app_oficial_tem_gatilhos_de_interacao() -> None:
    eventos = eventos_oficiais()
    assert {"PetDetectionShort", "DizzyShakeLoop", "ReactToPokeReaction"} <= eventos


def test_diretor_prioriza_reacao_oficial_de_toque() -> None:
    disponiveis = {"PetDetectionShort", "ReactToPokeReaction", "InterestedFace"}
    pool = AnimationDirector().pool(disponiveis, ContextoAnim.BASE, AnimIntent.PET)
    assert pool == ("PetDetectionShort", "ReactToPokeReaction")


def test_mapa_de_reacoes_do_app_liga_sensor_a_comportamento() -> None:
    rotas = gatilhos_reacao_oficiais()
    assert rotas["FacePositionUpdated"] == "AcknowledgeFace"
    assert rotas["RobotShaken"] == "ReactToRobotShaken"
    disponiveis = {"DizzyShakeLoop", "DizzyShakeStop", "CodeLabDizzy"}
    assert grupos_reacao_oficiais("shake", disponiveis) == (
        "DizzyShakeLoop",
        "DizzyShakeStop",
    )


def test_pool_ambiental_vem_do_freeplay_oficial() -> None:
    disponiveis = {"NothingToDoBoredIdle", "NothingToDoBoredEvent", "IdleOnCharger"}
    assert grupos_oficiais("ambient", disponiveis)[:2] == (
        "IdleOnCharger",
        "NothingToDoBoredIdle",
    )
    pool = pool_variacao_oled_base(disponiveis)
    assert "IdleOnCharger" in pool
    assert "NothingToDoBoredEvent" in pool
