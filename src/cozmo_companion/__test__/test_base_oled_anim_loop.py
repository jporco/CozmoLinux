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
        motor._base_oled_anim_loop_pausado_ate = 0.0
        motor._display_generation = 0
        motor._display_keeper_grupo = None
        motor._display_keeper_hz = 0.0
        motor._charger_keeper_ativo = False

    def test_anim_loop_ativo_por_env(self) -> None:
        with patch.dict("os.environ", {"COZMO_BASE_OLED_ANIM_LOOP": "1"}):
            self.assertTrue(motor._base_oled_anim_loop_ativo())
        with patch.dict("os.environ", {"COZMO_BASE_OLED_ANIM_LOOP": "0"}):
            self.assertFalse(motor._base_oled_anim_loop_ativo())

    def test_loop_antigo_morre_quando_geracao_muda(self) -> None:
        geracao = motor._clip_loop_generation
        self.assertFalse(motor._clip_loop_cancelado(geracao))
        motor._clip_loop_generation += 1
        self.assertTrue(motor._clip_loop_cancelado(geracao))

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

    def test_backoff_bloqueia_ppclip_direto(self) -> None:
        cli = MagicMock()
        motor._base_oled_anim_loop_pausado_ate = time.monotonic() + 60.0
        with patch(
            "cozmo_companion.core.motor_cozmo.base_oled_usa_charger",
            return_value=True,
        ):
            with patch(
                "cozmo_companion.core.motor_cozmo._frames_clip_oled",
                return_value=(MagicMock(),) * 10,
            ):
                with patch.object(motor, "_iniciar_display_keeper") as keeper:
                    with patch.object(
                        motor, "_semear_oled_charger", return_value=True
                    ) as semear:
                        with patch(
                            "cozmo_companion.core.anim_base_patch.play_grupo_sem_rodas_na_base",
                            return_value=True,
                        ) as play:
                            self.assertTrue(
                                motor._exibir_clip_base(cli, "HiccupGetIn", forcar=True)
                            )
        keeper.assert_not_called()
        semear.assert_called_once_with(cli, "HiccupGetIn")
        play.assert_not_called()

    def test_backoff_permite_keepalive_explicito(self) -> None:
        cli = MagicMock()
        fake_thread = MagicMock()
        motor._base_oled_anim_loop_pausado_ate = time.monotonic() + 60.0
        with patch("cozmo_companion.core.motor_cozmo.threading.Thread", return_value=fake_thread) as thread:
            motor.iniciar_oled_keepalive_base(cli)
            thread.assert_not_called()
            motor.iniciar_oled_keepalive_base(cli, durante_backoff=True)
        fake_thread.start.assert_called_once()
        motor._oled_keepalive_thread = None

    def test_animado_desativado_bloqueia_ppclip_direto(self) -> None:
        cli = MagicMock()
        with patch.dict("os.environ", {"COZMO_BASE_OLED_ANIMATED": "0"}):
            with patch(
                "cozmo_companion.core.motor_cozmo.base_oled_usa_charger",
                return_value=True,
            ):
                with patch(
                    "cozmo_companion.core.motor_cozmo._frames_clip_oled",
                    return_value=(MagicMock(),) * 10,
                ):
                    with patch.object(
                        motor, "_semear_oled_charger", return_value=True
                    ) as semear:
                        with patch(
                            "cozmo_companion.core.anim_base_patch.play_grupo_sem_rodas_na_base",
                            return_value=True,
                        ) as play:
                            self.assertTrue(
                                motor._exibir_clip_base(cli, "IdleOnCharger", forcar=True)
                            )
        semear.assert_called_once_with(cli, "IdleOnCharger")
        play.assert_not_called()

    def test_duracao_grupo_s(self) -> None:
        cli = MagicMock()
        with patch(
            "cozmo_companion.core.motor_cozmo._frames_clip_oled",
            return_value=(MagicMock(),) * 10,
        ):
            self.assertAlmostEqual(motor._duracao_grupo_s(cli, "X"), 10 * 0.033 + 0.3)

    def test_keeper_clip_hz_aceita_baixa_frequencia(self) -> None:
        cli = MagicMock()
        with patch.dict("os.environ", {"COZMO_BASE_FULL_KEEPER_HZ": "0.10"}):
            with patch.object(motor, "base_oled_carga_cheia_ativo", return_value=True):
                self.assertAlmostEqual(motor._keeper_clip_hz(cli), 0.10)

    def test_keeper_baixa_frequencia_preserva_tempo_do_clip(self) -> None:
        with patch.dict("os.environ", {"COZMO_ANIM_SOURCE_FPS": "30"}):
            self.assertEqual(motor._passo_frames_keeper(4.0), 8)
            self.assertEqual(motor._passo_frames_keeper(6.0), 5)
            self.assertEqual(motor._passo_frames_keeper(30.0), 1)

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
        with patch.dict("os.environ", {"COZMO_BASE_OLED_LOOP_BACKOFF_S": "30"}):
            with patch.object(motor, "rx_link_ok", return_value=False):
                with patch.object(motor, "_base_oled_anim_loop_ativo", return_value=True):
                    with patch.object(motor, "iniciar_oled_keepalive_base"):
                        with patch.object(motor, "_parar_base_oled_anim_loop") as parar:
                            motor.cortar_flood_udp_base(cli)
        parar.assert_called_once()
        self.assertGreater(motor._base_oled_anim_loop_pausado_ate, time.monotonic())
        motor._clip_loop_thread = None

    def test_cortar_flood_para_display_keeper_sem_rx(self) -> None:
        cli = MagicMock()
        motor._display_thread = MagicMock(is_alive=lambda: True)
        with patch.dict("os.environ", {"COZMO_BASE_OLED_LOOP_BACKOFF_S": "30"}):
            with patch.object(motor, "rx_link_ok", return_value=False):
                with patch.object(motor, "_parar_display_keeper") as parar_keeper:
                    with patch.object(motor, "_parar_oled_keepalive_base"):
                        with patch.object(motor, "_parar_base_oled_anim_loop"):
                            with patch.object(motor, "iniciar_oled_keepalive_base"):
                                motor.cortar_flood_udp_base(cli)
        parar_keeper.assert_called()
        self.assertGreater(motor._base_oled_anim_loop_pausado_ate, time.monotonic())
        motor._display_thread = None

    def test_backoff_ppclip_desativa_anim_loop_temporariamente(self) -> None:
        cli = MagicMock()
        with patch.dict(
            "os.environ",
            {
                "COZMO_BASE_OLED_ANIM_LOOP": "1",
                "COZMO_BASE_OLED_LOOP_BACKOFF_S": "30",
            },
        ):
            with patch.object(motor, "iniciar_oled_keepalive_base"):
                with patch.object(motor, "_parar_base_oled_anim_loop") as parar:
                    motor._pausar_base_oled_anim_loop_por_stall(cli)
                    self.assertFalse(motor._base_oled_anim_loop_ativo())
        parar.assert_called_once()

    def test_cortar_flood_pausa_ppclip_mesmo_com_rx(self) -> None:
        cli = MagicMock()
        motor._clip_loop_thread = MagicMock(is_alive=lambda: True)
        with patch.dict("os.environ", {"COZMO_BASE_OLED_ANIM_LOOP": "1"}):
            with patch.object(motor, "rx_link_ok", return_value=True):
                with patch.object(motor, "_oled_sessao_viva", return_value=True):
                    with patch.object(motor, "_pausar_base_oled_anim_loop_por_stall") as pausar:
                        motor.cortar_flood_udp_base(cli)
        pausar.assert_called_once_with(cli)
        motor._clip_loop_thread = None

    def test_cortar_flood_mantem_display_keeper_com_rx(self) -> None:
        cli = MagicMock()
        motor._display_thread = MagicMock(is_alive=lambda: True)
        with patch.dict("os.environ", {"COZMO_BASE_OLED_ANIM_LOOP": "0"}):
            with patch.object(motor, "rx_link_ok", return_value=True):
                with patch.object(motor, "_base_oled_anim_loop_ativo", return_value=False):
                    with patch.object(motor, "_pausar_base_oled_anim_loop_por_stall") as pausar:
                        with patch.object(motor, "_refresh_sessao_oled_leve") as refresh:
                            motor.cortar_flood_udp_base(cli)
        pausar.assert_not_called()
        refresh.assert_called_once_with(cli)
        motor._display_thread = None

    def test_cortar_flood_recria_keeper_stale_com_rx(self) -> None:
        cli = MagicMock()
        motor._charger_keeper_ativo = True
        motor._charger_oled_nome = "Hiccup"
        with patch.dict("os.environ", {"COZMO_BASE_OLED_ANIM_LOOP": "0"}):
            with patch.object(motor, "rx_link_ok", return_value=True):
                with patch.object(motor, "_base_oled_anim_loop_ativo", return_value=False):
                    with patch.object(motor, "keeper_base_ativo", return_value=False):
                        with patch.object(motor, "_iniciar_keeper_clip_oled_base") as iniciar:
                            with patch.object(motor, "_refresh_sessao_oled_leve"):
                                motor.cortar_flood_udp_base(cli)
        iniciar.assert_called_once_with(cli, "Hiccup")
        motor._charger_keeper_ativo = False
        motor._charger_oled_nome = None

    def test_display_keeper_antigo_morre_por_geracao(self) -> None:
        geracao = motor._display_generation
        self.assertFalse(motor._display_keeper_cancelado(geracao))
        motor._display_generation += 1
        self.assertTrue(motor._display_keeper_cancelado(geracao))

    def test_display_keeper_mesmo_grupo_nao_reinicia(self) -> None:
        cli = MagicMock()
        motor._display_thread = MagicMock(is_alive=lambda: True)
        motor._display_keeper_grupo = "Hiccup"
        motor._display_keeper_hz = 0.5
        with patch.object(motor, "_parar_display_keeper") as parar:
            motor._iniciar_display_keeper(cli, 0.5, grupo="Hiccup")
        parar.assert_not_called()
        motor._display_thread = None
        motor._display_keeper_grupo = None
        motor._display_keeper_hz = 0.0

    def test_ativar_vivo_com_anim_loop_nao_toca_clip_direto(self) -> None:
        cli = MagicMock()
        cli.animation_groups.keys.return_value = [
            "IdleOnCharger",
            "CodeLabBlink",
        ]
        with patch.dict("os.environ", {"COZMO_BASE_OLED_ANIM_LOOP": "1"}):
            with patch(
                "cozmo_companion.core.motor_cozmo._pool_oled_com_frames",
                return_value=("CodeLabBlink",),
            ):
                with patch(
                    "cozmo_companion.core.motor_cozmo._garantir_base_oled_anim_loop",
                    return_value=True,
                ) as garantir:
                    with patch.object(motor, "_exibir_clip_base") as exibir:
                        self.assertTrue(motor._ativar_oled_keeper_vivo(cli, time.monotonic()))
        garantir.assert_called_once_with(cli)
        exibir.assert_not_called()


if __name__ == "__main__":
    unittest.main()
