"""Comportamento na base — STT idle, carinho leve."""

import os
import time
import unittest
from unittest.mock import MagicMock, patch

from cozmo_companion.core.anims import ContextoAnim, filtrar_por_contexto
from cozmo_companion.core.companion import Companion, GRUPOS_CARINHO


class TestCompanionBase(unittest.TestCase):
    def test_grupos_carinho_so_react(self) -> None:
        self.assertEqual(GRUPOS_CARINHO, ("ReactToPokeReaction",))

    def test_carinho_prioridade_nao_expande_base_vivo(self) -> None:
        disp = {
            "ReactToPokeReaction",
            "FeedingIdleSearchForFaces_Normal",
            "NeutralFace",
        }
        pool = filtrar_por_contexto(
            GRUPOS_CARINHO,
            disp,
            ContextoAnim.BASE,
            sem_som_carga=True,
        )
        self.assertEqual(pool, ("ReactToPokeReaction",))
        self.assertNotIn("FeedingIdleSearchForFaces_Normal", pool)

    def test_carinho_recente_grace(self) -> None:
        c = MagicMock(spec=Companion)
        c._ultimo_carinho = time.monotonic()
        with patch.dict(os.environ, {"CARINHO_LINK_GRACE_S": "5"}):
            self.assertTrue(Companion._carinho_recente(c))
        c._ultimo_carinho = time.monotonic() - 10.0
        with patch.dict(os.environ, {"CARINHO_LINK_GRACE_S": "5"}):
            self.assertFalse(Companion._carinho_recente(c))

    def test_stt_idle_rms_na_base(self) -> None:
        c = MagicMock(spec=Companion)
        c.ouvinte = MagicMock()
        c._na_base_efetivo = MagicMock(return_value=True)
        c._wake = MagicMock()
        c._wake.aguardando = False
        c._falando = False
        c._stt_base_wake_ate = 0.0
        c._modo_atual = None
        with patch.dict(
            os.environ,
            {
                "COZMO_STT_IDLE_BASE": "1",
                "STT_RMS_IDLE_BASE": "50",
                "COZMO_STT_NA_BASE": "0",
            },
        ):
            Companion._ajustar_stt_base(c)
        c.ouvinte.ajustar_rms.assert_called_with(50)
        c.ouvinte.resume.assert_called()

    def test_na_base_efetivo_nao_reentra_quieto_tts(self) -> None:
        c = MagicMock(spec=Companion)
        c.cli = MagicMock()
        c.cli.robot_status = 0
        c.cli.robot_picked_up = False
        c._base = MagicMock()
        c._vida = MagicMock()
        c._gov = MagicMock()
        c._recuperador = MagicMock()
        c._base.preso_na_base = True
        c._base.mesa_escolhida = False
        c._vida.dormindo = False
        c._udp_quieto_ate = 0.0
        c._ultimo_reconnect_udp = 0.0
        c._gov.ultimo_rx_ok = True
        c._recuperador.stall_consecutivo = 0
        with patch("cozmo_companion.core.companion.modo_botao", return_value=True):
            with patch.object(
                Companion,
                "_periodo_quieto_ativo",
                side_effect=AssertionError("recursao"),
            ):
                self.assertTrue(Companion._na_base_efetivo(c))
