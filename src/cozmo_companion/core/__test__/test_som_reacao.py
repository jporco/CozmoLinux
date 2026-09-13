"""Testes — reacoes sonoras do Cozmo a barulho ambiente."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from cozmo_companion.core import som_reacao
from cozmo_companion.core.animation_director import AnimationDirector
from cozmo_companion.core.anims import ContextoAnim
from cozmo_companion.core.companion_voz import CompanionVoz, REACOES_BARULHO, REACOES_LATIDO


class FakeCompanion(CompanionVoz):
    def __init__(self) -> None:
        self._iniciar_voz()
        self.cli = MagicMock()
        self.volume = 18000
        self._base = MagicMock(preso_na_base=True)
        self._vida = MagicMock()
        self._fila = MagicMock()
        self._fila.livre = True
        self._fila.enviar_anim.return_value = True
        self._anim_director = AnimationDirector()
        self._ctx_anim = MagicMock(return_value=ContextoAnim.BASE)
        self._gov = MagicMock(ultimo_rx_ok=True)
        self._monitor_rx = MagicMock()
        self._falando = False
        self._llm_ocupado = False
        self._periodo_quieto_ativo = MagicMock(return_value=False)
        self._na_base_efetivo = MagicMock(return_value=True)
        self._marcar_udp_quieto = MagicMock()


class TestSomReacao(unittest.TestCase):
    def test_pacotes_susto(self) -> None:
        pkts = som_reacao.pacotes_som_reacao("susto")
        self.assertGreaterEqual(len(pkts), 8)
        self.assertTrue(all(getattr(pkt, "samples", b"") for pkt in pkts))

    def test_latido_tem_frase_sonora_sem_estalo_unico(self) -> None:
        pkts = som_reacao.pacotes_som_reacao("latido")
        self.assertGreaterEqual(len(pkts), 12)
        self.assertTrue(all(len(getattr(pkt, "samples", b"")) == 744 for pkt in pkts))

    def test_barulho_chama_animacao_oficial_com_som_leve(self) -> None:
        c = FakeCompanion()
        with (
            patch("cozmo_companion.core.som_reacao.tocar_som_reacao") as tocar,
            patch("cozmo_companion.display.rosto.solicitar_reacao_visual") as reacao,
            patch(
                "cozmo_companion.core.motor_cozmo.tocar_clip_base_seguro",
                return_value=True,
            ) as visual,
        ):
            c.cli.animation_groups = {g: MagicMock() for g in REACOES_BARULHO}
            c._stt_fila.put(("som", "barulho", 6400.0))
            c._processar_stt()
        visual.assert_not_called()
        c._fila.enviar_anim.assert_called_once()
        reacao.assert_called_once_with("sound", frames=5)
        tocar.assert_called_once()
        c._vida.registrar_interacao.assert_called_once()

    def test_latido_texto_dispara_animacao_sem_som_sintetico(self) -> None:
        c = FakeCompanion()
        with (
            patch("cozmo_companion.core.som_reacao.tocar_som_reacao") as tocar,
            patch(
                "cozmo_companion.core.motor_cozmo.tocar_clip_base_seguro",
                return_value=True,
            ) as visual,
        ):
            c.cli.animation_groups = {g: MagicMock() for g in REACOES_LATIDO}
            c._tratar_texto_ouvido("ao")
        visual.assert_not_called()
        c._fila.enviar_anim.assert_called_once()
        tocar.assert_not_called()

    def test_volume_reacao_recebe_boost(self) -> None:
        cli = MagicMock()
        with (
            patch.dict(
                "os.environ",
                {"SOM_REACAO_VOLUME_BOOST": "4500", "SOM_REACAO_PACOTES": "2"},
            ),
            patch("cozmo_companion.core.charger.em_base", return_value=False),
            patch("cozmo_companion.core.som_reacao.rx_frames", return_value=10),
            patch("cozmo_companion.core.som_reacao.pulso_ping"),
            patch("cozmo_companion.core.som_reacao._enviar_sinal_udp"),
            patch("cozmo_companion.core.som_reacao._respiro_udp"),
            patch("cozmo_companion.core.som_reacao.estabilizar_pos_audio"),
            patch("cozmo_companion.core.motor_cozmo.modo_tts_preparar", return_value=(False, False)),
            patch("cozmo_companion.core.motor_cozmo.modo_tts_restaurar"),
            patch("cozmo_companion.core.motor_cozmo.ping_oob"),
        ):
            self.assertTrue(som_reacao.tocar_som_reacao(cli, tipo="latido", volume=60000))
        cli.set_volume.assert_called_once_with(64500)


if __name__ == "__main__":
    unittest.main()
