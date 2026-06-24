"""Loop contínuo OLED na base — play_anim_ppclip, sem keepalive congelado."""

import time
import unittest
from unittest.mock import MagicMock, patch

import cozmo_companion.core.motor_cozmo as motor


class TestBaseOledAnimLoop(unittest.TestCase):
    def setUp(self) -> None:
        motor._clip_loop_stop.set()
        motor._parar_loop_clip_base(timeout=0.1)
        motor._parar_oled_keepalive_base()
        motor._modo_sono_oled = False
        motor._sono_oled_texto_ativo = False
        motor._base_oled_loop_hold_ate = 0.0
        motor._base_oled_loop_hold_desde = 0.0

    def test_anim_loop_ativo_por_env(self) -> None:
        with patch.dict("os.environ", {"COZMO_BASE_OLED_ANIM_LOOP": "1"}):
            self.assertTrue(motor._base_oled_anim_loop_ativo())
        with patch.dict("os.environ", {"COZMO_BASE_OLED_ANIM_LOOP": "0"}):
            self.assertFalse(motor._base_oled_anim_loop_ativo())

    def test_iniciar_keepalive_ignorado_com_anim_loop(self) -> None:
        cli = MagicMock()
        with patch.dict(
            "os.environ",
            {"COZMO_BASE_OLED_ANIM_LOOP": "1", "COZMO_BASE_OLED_KEEPALIVE": "1"},
        ):
            with patch.object(motor, "iniciar_loop_clip_base") as iniciar:
                motor.iniciar_oled_keepalive_base(cli)
        iniciar.assert_not_called()
        self.assertIsNone(motor._oled_keepalive_thread)

    def test_exibir_clip_delega_loop_externo(self) -> None:
        cli = MagicMock()
        with patch.dict("os.environ", {"COZMO_BASE_OLED_ANIM_LOOP": "1"}):
            with patch(
                "cozmo_companion.core.motor_cozmo.base_oled_usa_charger",
                return_value=True,
            ):
                with patch(
                    "cozmo_companion.core.motor_cozmo._frames_clip_oled",
                    return_value=(MagicMock(),) * 10,
                ):
                    with patch.object(
                        motor, "iniciar_loop_clip_base", return_value=True
                    ) as iniciar:
                        with patch(
                            "cozmo_companion.core.anim_base_patch.play_grupo_sem_rodas_na_base",
                            return_value=True,
                        ) as play:
                            motor._exibir_clip_base(cli, "CodeLabBlink", forcar=False)
        iniciar.assert_called_once_with(cli)
        play.assert_not_called()

    def test_exibir_clip_forcar_toca_direto(self) -> None:
        cli = MagicMock()
        with patch.dict("os.environ", {"COZMO_BASE_OLED_ANIM_LOOP": "1"}):
            with patch(
                "cozmo_companion.core.motor_cozmo.base_oled_usa_charger",
                return_value=True,
            ):
                with patch(
                    "cozmo_companion.core.motor_cozmo._frames_clip_oled",
                    return_value=(MagicMock(),) * 10,
                ):
                    with patch.object(
                        motor, "iniciar_loop_clip_base", return_value=True
                    ) as iniciar:
                        with patch(
                            "cozmo_companion.core.anim_base_patch.play_grupo_sem_rodas_na_base",
                            return_value=True,
                        ) as play:
                            motor._exibir_clip_base(cli, "GoToSleepGetIn", forcar=True)
        iniciar.assert_not_called()
        play.assert_called_once()

    def test_duracao_grupo_s(self) -> None:
        cli = MagicMock()
        with patch(
            "cozmo_companion.core.motor_cozmo._frames_clip_oled",
            return_value=(MagicMock(),) * 10,
        ):
            self.assertAlmostEqual(motor._duracao_grupo_s(cli, "X"), 10 * 0.033 + 0.3)

    def test_display_keeper_ignorado_com_anim_loop(self) -> None:
        cli = MagicMock()
        with patch.dict("os.environ", {"COZMO_BASE_OLED_ANIM_LOOP": "1"}):
            with patch.object(motor, "_garantir_base_oled_anim_loop", return_value=True) as garantir:
                motor._iniciar_display_keeper(cli, 7.0, grupo="CodeLabBlink")
        garantir.assert_called_once_with(cli)

    def test_iniciar_loop_clip_bloqueado_no_sono(self) -> None:
        cli = MagicMock()
        motor.definir_modo_sono_oled(True)
        with patch.dict("os.environ", {"COZMO_BASE_OLED_ANIM_LOOP": "1"}):
            with patch.object(motor, "_clip_loop_vivo", return_value=False):
                with patch.object(motor, "_parar_display_keeper"):
                    with patch.object(motor, "_parar_oled_keepalive_base"):
                        with patch.object(motor, "_parar_charger_worker"):
                            self.assertTrue(motor.iniciar_loop_clip_base(cli))
        motor.definir_modo_sono_oled(False)
        motor._sono_oled_texto_ativo = True
        with patch.dict("os.environ", {"COZMO_BASE_OLED_ANIM_LOOP": "1"}):
            self.assertFalse(motor.iniciar_loop_clip_base(cli))
        motor._sono_oled_texto_ativo = False

    def test_ligar_oled_base_sono_so_zzz(self) -> None:
        cli = MagicMock()
        motor._sono_oled_texto_ativo = True
        with patch.object(motor, "manter_sono_oled_texto") as manter:
            with patch.object(motor, "modo_charger_oled") as modo:
                motor.ligar_oled_base(cli, forcar=True, preso_na_base=True)
        manter.assert_called_once_with(cli)
        modo.assert_not_called()
        motor._sono_oled_texto_ativo = False

    def test_ligar_oled_base_sono_ppclip(self) -> None:
        cli = MagicMock()
        motor.definir_modo_sono_oled(True)
        with patch.dict("os.environ", {"COZMO_SONO_OLED_TEXTO": "0"}):
            with patch.object(motor, "manter_sono_ppclip") as manter:
                with patch.object(motor, "modo_charger_oled") as modo:
                    motor.ligar_oled_base(cli, forcar=True, preso_na_base=True)
            manter.assert_called_once_with(cli)
            modo.assert_not_called()
        motor.definir_modo_sono_oled(False)

    def test_segurar_loop_impede_iniciar(self) -> None:
        cli = MagicMock()
        motor.segurar_base_oled_loop(30.0)
        with patch.dict("os.environ", {"COZMO_BASE_OLED_ANIM_LOOP": "1"}):
            self.assertFalse(motor.iniciar_loop_clip_base(cli))
        motor._base_oled_loop_hold_ate = 0.0
        motor._base_oled_loop_hold_desde = 0.0

    def test_hold_max_15s(self) -> None:
        motor._base_oled_loop_hold_ate = 0.0
        motor._base_oled_loop_hold_desde = 0.0
        with patch.dict(
            "os.environ",
            {
                "COZMO_BASE_OLED_HOLD_MAX_S": "15",
                "COZMO_BASE_OLED_HOLD_STACK": "1",
            },
        ):
            motor.segurar_base_oled_loop(30.0)
            self.assertTrue(motor.base_oled_loop_segurado())
            motor.segurar_base_oled_loop(30.0)
            restante = motor._base_oled_loop_hold_ate - motor._base_oled_loop_hold_desde
            self.assertLessEqual(restante, 15.01)
        motor._base_oled_loop_hold_ate = 0.0
        motor._base_oled_loop_hold_desde = 0.0

    def test_liberar_hold(self) -> None:
        motor._base_oled_loop_hold_ate = 0.0
        motor._base_oled_loop_hold_desde = 0.0
        motor.segurar_base_oled_loop(20.0)
        self.assertTrue(motor.base_oled_loop_segurado())
        motor.liberar_base_oled_loop_hold(motivo="teste")
        self.assertFalse(motor.base_oled_loop_segurado())

    def test_expirar_hold_chama_restaurar(self) -> None:
        cli = MagicMock()
        cli.anim_controller.playing_audio = False
        cli.anim_controller.playing_animation = False
        cli.anim_controller.queue.is_empty.return_value = True
        agora = time.monotonic()
        motor._base_oled_loop_hold_desde = agora - 20.0
        motor._base_oled_loop_hold_ate = agora - 1.0
        with patch.dict("os.environ", {"COZMO_BASE_OLED_ANIM_LOOP": "1"}):
            with patch.object(motor, "rx_link_ok", return_value=True):
                with patch.object(motor, "_base_oled_anim_loop_ativo", return_value=True):
                    with patch.object(
                        motor, "_garantir_base_oled_anim_loop", return_value=True
                    ) as garantir:
                        self.assertTrue(motor.expirar_hold_oled_base(cli))
        garantir.assert_called_once()
        motor._base_oled_loop_hold_ate = 0.0
        motor._base_oled_loop_hold_desde = 0.0

    def test_expirar_hold_nao_estoura_antes_do_stack(self) -> None:
        cli = MagicMock()
        cli.anim_controller.playing_audio = False
        cli.anim_controller.playing_animation = False
        cli.anim_controller.queue.is_empty.return_value = True
        agora = time.monotonic()
        motor._base_oled_loop_hold_desde = agora - 10.0
        motor._base_oled_loop_hold_ate = agora + 8.0
        with patch.dict(
            "os.environ",
            {
                "COZMO_BASE_OLED_HOLD_MAX_S": "8",
                "COZMO_BASE_OLED_HOLD_STACK": "2.5",
            },
        ):
            self.assertFalse(motor.expirar_hold_oled_base(cli))
            self.assertTrue(motor.base_oled_loop_segurado())
        motor._base_oled_loop_hold_ate = 0.0
        motor._base_oled_loop_hold_desde = 0.0

    def test_oled_charger_vivo_com_anim_loop(self) -> None:
        cli = MagicMock()
        th = MagicMock(is_alive=lambda: True)
        motor._clip_loop_thread = th
        self.assertTrue(motor.oled_charger_vivo(cli))
        motor._clip_loop_thread = None

    def test_oled_sessao_viva_sem_rx_link(self) -> None:
        cli = MagicMock()
        with patch.object(motor, "rx_link_ok", return_value=False):
            with patch.object(motor, "base_oled_usa_charger", return_value=True):
                self.assertFalse(motor._oled_sessao_viva(cli))
        with patch.object(motor, "rx_link_ok", return_value=True):
            with patch.object(motor, "base_oled_usa_charger", return_value=True):
                self.assertTrue(motor._oled_sessao_viva(cli))

    def test_cortar_flood_para_ppclip_sem_rx(self) -> None:
        cli = MagicMock()
        motor._clip_loop_thread = MagicMock(is_alive=lambda: True)
        with patch.object(motor, "rx_link_ok", return_value=False):
            with patch.object(motor, "_parar_base_oled_anim_loop") as parar:
                motor.cortar_flood_udp_base(cli)
        parar.assert_called_once()
        motor._clip_loop_thread = None

    def test_cortar_flood_preserva_ppclip_com_rx(self) -> None:
        cli = MagicMock()
        motor._clip_loop_thread = MagicMock(is_alive=lambda: True)
        with patch.object(motor, "rx_link_ok", return_value=True):
            with patch.object(motor, "_oled_sessao_viva", return_value=True):
                with patch.object(motor, "_parar_base_oled_anim_loop") as parar:
                    motor.cortar_flood_udp_base(cli)
        parar.assert_not_called()
        motor._clip_loop_thread = None


if __name__ == "__main__":
    unittest.main()
