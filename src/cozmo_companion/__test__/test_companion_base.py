"""Comportamento na base — STT idle, carinho leve."""

import os
import time
import unittest
from unittest.mock import MagicMock, patch

from cozmo_companion.core.anims import ContextoAnim, filtrar_por_contexto
from cozmo_companion.core.animation_director import AnimationDirector
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

    def test_keeper_base_nao_bloqueia_carinho(self) -> None:
        c = MagicMock(spec=Companion)
        c._falando = False
        c._pos_tts_ativo = MagicMock(return_value=False)
        c._fila = MagicMock()
        c._fila.enviar_anim.return_value = True
        c._anim_director = AnimationDirector()
        c._ctx_anim = MagicMock(return_value=ContextoAnim.BASE)
        c._fila.livre = True
        c._na_base_efetivo = MagicMock(return_value=True)
        c._face = MagicMock(buscando=False, rastreando=False)
        c.cli = MagicMock()
        c.cli.animation_groups = {"ReactToPokeReaction": None, "InterestedFace": None}
        c.cli.anim_controller.playing_animation = False
        c.cli.anim_controller.playing_audio = False
        c.cli.anim_controller.queue.is_empty.return_value = True
        with patch("cozmo_companion.core.motor_cozmo.keeper_base_ativo", return_value=True):
            self.assertFalse(Companion._carinho_cabeca_externa(c))

    def test_carinho_base_nao_dispara_tts_por_padrao(self) -> None:
        c = MagicMock(spec=Companion)
        c._vida = MagicMock()
        c._vida.dormindo = False
        c._na_base_efetivo = MagicMock(return_value=True)
        c._periodo_quieto_ativo = MagicMock(return_value=False)
        c._falando = False
        c._pos_tts_ativo = MagicMock(return_value=False)
        c._ultimo_carinho = 0.0
        c._detector_escuro = MagicMock()
        c._monitor_rx = MagicMock()
        c._gov = MagicMock()
        c._vivo = MagicMock()
        c._carinho = MagicMock()
        c._fila = MagicMock()
        c._fila.enviar_anim.return_value = True
        c._anim_director = AnimationDirector()
        c._ctx_anim = MagicMock(return_value=ContextoAnim.BASE)
        c._base_usa_rosto_vivo = MagicMock(return_value=True)
        c.cli = MagicMock()
        c.cli.animation_groups = {"ReactToPokeReaction": None, "InterestedFace": None}
        with patch.dict(os.environ, {"CARINHO_TTS_NA_BASE": "0"}):
            with patch("cozmo_companion.core.charger.carga_prioritaria", return_value=False):
                with patch("cozmo_companion.core.companion.audio_na_base", return_value=True):
                    with (
                        patch(
                            "cozmo_companion.core.motor_cozmo.manter_oled_base_ativo"
                        ) as manter,
                        patch(
                            "cozmo_companion.display.rosto.solicitar_reacao_visual"
                        ) as reacao,
                    ):
                        Companion._ao_carinho_cabeca(c)
        c._fila.enviar_sinal_tts.assert_not_called()
        c._fila.enviar_anim.assert_called_once()
        reacao.assert_called_once_with("pet", frames=6)
        manter.assert_not_called()

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

    def test_wifi_recuperado_reabre_udp_sem_sincronizar_cliente_velho(self) -> None:
        c = MagicMock(spec=Companion)
        c._reconectar_sessao_udp = MagicMock(return_value=True)
        c.cli = MagicMock()
        c._base = MagicMock()
        c._base.preso_na_base = True
        c._base.mesa_escolhida = False
        c._recuperador = MagicMock()
        with patch("cozmo_companion.core.charger.em_base", return_value=True):
            with patch("cozmo_companion.core.charger.definir_oled_preso_na_base") as definir:
                self.assertTrue(Companion._reabrir_udp_apos_wifi(c))
        c._reconectar_sessao_udp.assert_called_once_with(
            silencioso=False,
            forcado=True,
            cozmo01=True,
        )
        self.assertTrue(c._base._preso_na_base)
        self.assertFalse(c._base._mesa_escolhida)
        definir.assert_called_once_with(True)
        self.assertEqual(c._recuperador.stall_consecutivo, 0)

    def test_wifi_recuperado_preserva_modo_livre(self) -> None:
        c = MagicMock(spec=Companion)
        c._reconectar_sessao_udp = MagicMock(return_value=True)
        c.cli = MagicMock()
        c._base = MagicMock()
        c._base.preso_na_base = False
        c._base.mesa_escolhida = True
        c._recuperador = MagicMock()
        with patch("cozmo_companion.core.charger.em_base", return_value=False):
            with patch("cozmo_companion.core.charger.definir_oled_preso_na_base") as definir:
                self.assertTrue(Companion._reabrir_udp_apos_wifi(c))
        c._reconectar_sessao_udp.assert_called_once_with(
            silencioso=False,
            forcado=True,
            cozmo01=True,
        )
        self.assertFalse(c._base._preso_na_base)
        self.assertTrue(c._base._mesa_escolhida)
        definir.assert_called_once_with(False)
        self.assertEqual(c._recuperador.stall_consecutivo, 0)

    def test_reset_cozmo01_nao_e_bloqueado_por_frame_enviado(self) -> None:
        c = MagicMock(spec=Companion)
        c._ultimo_reconnect_udp = 0.0
        c._sessao_guard = MagicMock()
        c._sessao_guard.tentar_reconectar.return_value = False
        c._na_base_efetivo = MagicMock(return_value=True)
        with patch(
            "cozmo_companion.core.companion.permitir_reset_udp_cozmo01",
            return_value=True,
        ), patch.dict(os.environ, {"COZMO_BASE_STABLE_OLED": "0"}):
            ok = Companion._reconectar_sessao_udp(
                c, silencioso=False, forcado=True, cozmo01=True
            )
        self.assertFalse(ok)
        c._sessao_guard.tentar_reconectar.assert_called_once_with(forcar=True)

    def test_reset_cozmo01_duplicado_respeita_estabilizacao(self) -> None:
        c = MagicMock(spec=Companion)
        c._ultimo_reconnect_udp = time.monotonic() - 10.0
        c._sessao_guard = MagicMock()
        with patch(
            "cozmo_companion.core.companion.permitir_reset_udp_cozmo01",
            return_value=True,
        ), patch.dict(
            os.environ,
            {"COZMO01_POST_RESET_MIN_S": "60", "COZMO_BASE_STABLE_OLED": "0"},
        ):
            ok = Companion._reconectar_sessao_udp(
                c, silencioso=False, forcado=True, cozmo01=True
            )
        self.assertTrue(ok)
        c._sessao_guard.tentar_reconectar.assert_not_called()

    def test_reset_cozmo01_bloqueado_no_oled_estavel(self) -> None:
        c = MagicMock(spec=Companion)
        c.cli = MagicMock()
        c._monitor_rx = MagicMock()
        c._gov = MagicMock()
        c._gov._medidor = MagicMock()
        c._garantir_rosto_base = MagicMock()
        c._sessao_guard = MagicMock()
        c._na_base_efetivo = MagicMock(return_value=True)
        with patch(
            "cozmo_companion.core.companion.permitir_reset_udp_cozmo01",
            return_value=True,
        ), patch(
            "cozmo_companion.core.companion.despertar_sessao_leve"
        ) as despertar, patch(
            "cozmo_companion.core.motor_cozmo.ligar_oled_base",
            return_value=True,
        ) as ligar_oled, patch.dict(
            os.environ,
            {"COZMO_BASE_STABLE_OLED": "1", "COZMO_BASE_STABLE_ALLOW_RESET": "0"},
        ):
            ok = Companion._reconectar_sessao_udp(
                c, silencioso=False, forcado=True, cozmo01=True
            )
        self.assertFalse(ok)
        despertar.assert_called_once_with(c.cli, c._monitor_rx, c._gov._medidor)
        ligar_oled.assert_called_once_with(c.cli, forcar=True)
        c._garantir_rosto_base.assert_called_once_with()
        c._sessao_guard.tentar_reconectar.assert_not_called()

    def test_reset_cozmo01_estavel_nao_bloqueia_fora_da_base(self) -> None:
        c = MagicMock(spec=Companion)
        c._ultimo_reconnect_udp = 0.0
        c._sessao_guard = MagicMock()
        c._sessao_guard.tentar_reconectar.return_value = False
        c._na_base_efetivo = MagicMock(return_value=False)
        with patch(
            "cozmo_companion.core.companion.permitir_reset_udp_cozmo01",
            return_value=True,
        ), patch.dict(
            os.environ,
            {"COZMO_BASE_STABLE_OLED": "1", "COZMO_BASE_STABLE_ALLOW_RESET": "0"},
        ):
            ok = Companion._reconectar_sessao_udp(
                c, silencioso=False, forcado=True, cozmo01=True
            )
        self.assertFalse(ok)
        c._sessao_guard.tentar_reconectar.assert_called_once_with(forcar=True)
