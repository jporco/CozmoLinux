"""Testes do comportamento pet no modo livre."""

from __future__ import annotations

import time
import unittest
from unittest.mock import MagicMock

from cozmo_companion.core.companion import Companion
from cozmo_companion.core.pet_livre import PetLivre, PetPlano
from cozmo_companion.core.state import CozmoMode, SafetyState
from cozmo_companion.perception.events import PerceptionEvent, PerceptionEventKind


class TestPetLivre(unittest.TestCase):
    def test_evento_rosto_antecipa_reacao(self) -> None:
        pet = PetLivre()
        pet._proxima = time.monotonic() + 120.0
        pet.registrar_evento(PerceptionEvent(PerceptionEventKind.FACE_SEEN))
        self.assertLess(pet._proxima - time.monotonic(), 2.0)

    def test_modo_livre_escolhe_plano(self) -> None:
        pet = PetLivre()
        pet._proxima = 0.0
        plano = pet.escolher(livre=True, no_carregador=False, face_ativa=False)
        self.assertIsNotNone(plano)
        self.assertIn(plano.acao, ("explorar", "anim", "olhar", "gesto", "scan", "camera"))

    def test_gesto_marca_movimento_interno(self) -> None:
        pet = PetLivre()
        cli = MagicMock()
        pet.gesto_curto(cli)
        self.assertTrue(pet.movimento_interno)


class TestCompanionPetLivre(unittest.TestCase):
    def _fake_app(self) -> Companion:
        app = Companion.__new__(Companion)
        app.cli = MagicMock()
        app.cli.robot_picked_up = False
        app.cli.anim_controller = MagicMock()
        app.cli.anim_controller.playing_animation = False
        app.cli.anim_controller.playing_audio = False
        app.cli.anim_controller.queue.is_empty.return_value = True
        app._vida = MagicMock(dormindo=False)
        app._falando = False
        app._llm_ocupado = False
        app._ultimo_tts_fim = 0.0
        app._fila = MagicMock(ocupada=False)
        app._fila.livre = True
        app._gov = MagicMock(ultimo_rx_ok=True)
        app._gov.pode.return_value = True
        app._face = MagicMock(ativo=False, buscando=False, rastreando=False)
        app._explorador = MagicMock(explorando=False)
        app._pet_livre = MagicMock()
        app._pet_livre.movimento_interno = False
        app._periodo_quieto_ativo = MagicMock(return_value=False)
        app._na_base_efetivo = MagicMock(return_value=False)
        return app

    def test_animacao_livre_nao_vira_carinho(self) -> None:
        app = self._fake_app()
        app.cli.anim_controller.playing_animation = True
        self.assertTrue(Companion._carinho_cabeca_externa(app))

    def test_loop_livre_antecipa_exploracao(self) -> None:
        app = self._fake_app()
        app._safety_state = MagicMock(
            return_value=SafetyState(
                mode=CozmoMode.FREE_EXPLORE,
                effective_base=False,
                movement_allowed=True,
                wheels_allowed=True,
                lift_allowed=True,
                camera_allowed=True,
                animation_allowed=True,
            )
        )
        app._pet_livre.escolher.return_value = PetPlano("explorar")
        Companion._loop_pet_autonomo(app)
        app._explorador.tick.assert_called_once_with(app.cli)
        app._explorador.antecipar.assert_called_once()

    def test_loop_livre_reage_com_gesto_e_animacao(self) -> None:
        app = self._fake_app()
        app._safety_state = MagicMock(
            return_value=SafetyState(
                mode=CozmoMode.FREE_EXPLORE,
                effective_base=False,
                movement_allowed=True,
                wheels_allowed=True,
                lift_allowed=True,
                camera_allowed=True,
                animation_allowed=True,
            )
        )
        app._pet_livre.escolher.return_value = PetPlano("gesto", ("Surprise",))
        Companion._loop_pet_autonomo(app)
        app._pet_livre.gesto_curto.assert_called_once_with(app.cli)
        app._fila.enviar_anim.assert_called_once_with(("Surprise",), prioridade=False)


if __name__ == "__main__":
    unittest.main()
