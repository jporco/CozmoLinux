"""Testes motor_cozmo — porta PyCozmo."""

import os
import threading
import time
import unittest
from unittest.mock import MagicMock, call, patch

from pycozmo import robot

from cozmo_companion.core import motor_cozmo as motor
from cozmo_companion.core.motor_cozmo import (
    angulo_cabeca_neutro,
    animar_grupo,
    base_proc_hz,
    cabeca_base_neutra,
    enviar_oled,
    instalar_anim_id_seguro,
    instalar_charger_display_guard,
    modo_base_olhos,
    modo_charger_oled,
    modo_tts_preparar,
    olhos_procedural,
    _normalizar_anim_id,
)


class TestMotorCozmo(unittest.TestCase):
    def setUp(self) -> None:
        import cozmo_companion.core.motor_cozmo as motor

        motor._charger_keeper_ativo = False
        motor._charger_slow_anim = False
        motor._charger_stream_sessao = False
        motor._charger_oled_nome = None
        motor._ultimo_charger_play = 0.0
        motor._charger_replay_pendente = False
        motor._charger_replay_em_voo = False
        motor._charger_worker_thread = None
        motor._charger_worker_thread = None
        motor._charger_worker_stop.clear()
        motor._sono_oled_texto_ativo = False
        motor._modo_sono_oled = False
        motor._base_oled_loop_hold_ate = 0.0
        motor._base_oled_loop_hold_desde = 0.0
        motor._base_oled_anim_loop_pausado_ate = 0.0

    def test_sono_oled_texto_bloqueia_ppclip(self) -> None:
        cli = MagicMock()
        cli.animation_groups = {"Sleeping": MagicMock(), "IdleOnCharger": MagicMock()}
        with patch.dict(
            os.environ,
            {"SONO_TELA_ESCURA": "0", "COZMO_SONO_OLED_TEXTO": "1"},
        ):
            with patch(
                "cozmo_companion.core.anims.pool_sono_oled_base",
                return_value=["Sleeping"],
            ):
                self.assertTrue(motor.sono_oled_usa_texto())
                motor.ativar_sono_oled_texto(cli)
                self.assertTrue(motor.sono_oled_texto_ativo())
                self.assertTrue(motor.base_oled_loop_segurado())
                cli.play_anim_group.assert_called_with("Sleeping")
                self.assertFalse(motor.iniciar_loop_clip_base(cli))
                motor.desativar_sono_oled_texto()
                self.assertFalse(motor.sono_oled_texto_ativo())
        min_a = robot.MIN_HEAD_ANGLE.radians
        max_a = robot.MAX_HEAD_ANGLE.radians
        meio = (max_a + min_a) / 2.0
        neutro = angulo_cabeca_neutro()
        self.assertGreater(neutro, meio)

    def test_cabeca_base_neutra_so_se_precisa(self) -> None:
        cli = MagicMock()
        cli.head_angle.radians = angulo_cabeca_neutro()
        with patch.dict("os.environ", {"BASE_HEAD_RESET": "1"}):
            cabeca_base_neutra(cli)
        cli.set_head_angle.assert_not_called()

    def test_modo_charger_carga_cheia_stream_awake(self) -> None:
        cli = MagicMock()
        ac = cli.anim_controller
        ac.playing_animation = False
        ac.playing_audio = False
        ac.thread = MagicMock(is_alive=lambda: True)
        cli.animation_groups = {
            "IdleOnCharger": MagicMock(),
            "NeutralFace": MagicMock(),
        }
        with patch.dict(
            "os.environ",
            {
                "COZMO_BASE_OLED_MODE": "proc",
                "COZMO_BASE_OLED_CHARGER_FULL": "1",
                "COZMO_BASE_KEEPER_VIVO": "0",
                "COZMO_CHARGER_PLAY_STREAM": "1",
                "COZMO_CHARGER_STREAM_NA_CHEIA": "1",
                "COZMO_BASE_STABLE_OLED": "0",
                "COZMO_CHARGER_AWAKE_IDLE": "IdleOnCharger",
            },
        ):
            with patch(
                "cozmo_companion.core.motor_cozmo.base_oled_usa_charger",
                return_value=True,
            ):
                with patch(
                    "cozmo_companion.core.motor_cozmo.base_oled_carga_cheia_ativo",
                    return_value=True,
                ):
                    with patch(
                        "cozmo_companion.core.charger.base_oled_estavel",
                        return_value=False,
                    ):
                        with patch(
                            "cozmo_companion.core.motor_cozmo._ativar_charger_stream",
                            return_value=True,
                        ) as stream:
                            with patch(
                                "cozmo_companion.core.charger.carga_firmware_pausada",
                                return_value=True,
                            ):
                                with patch(
                                    "cozmo_companion.core.charger.carregando",
                                    return_value=False,
                                ):
                                    with patch(
                                        "cozmo_companion.core.charger.em_base",
                                        return_value=True,
                                    ):
                                        with patch(
                                            "cozmo_companion.core.charger.bateria_pct",
                                            return_value=100,
                                        ):
                                            with patch(
                                                "cozmo_companion.core.motor_cozmo._charger_worker_vivo",
                                                return_value=False,
                                            ):
                                                modo_charger_oled(cli, forcar=True)
        stream.assert_called_once()
        args = stream.call_args[0]
        self.assertEqual(args[1], "IdleOnCharger")

    def test_cancel_guard_permite_worker(self) -> None:
        import cozmo_companion.core.motor_cozmo as motor

        cli = MagicMock()
        orig = MagicMock()
        cli.cancel_anim = orig
        motor._charger_worker_thread = threading.current_thread()
        with patch.dict("os.environ", {"COZMO_CHARGER_PLAY_STREAM": "1"}):
            with patch(
                "cozmo_companion.core.motor_cozmo.base_oled_usa_charger",
                return_value=True,
            ):
                motor._cozmo_cancel_guard = False
                cli._cozmo_cancel_guard = False
                motor.instalar_guard_cancel_anim_base(cli)
                cli.cancel_anim()
        orig.assert_called_once()
        motor._charger_worker_thread = None

    def test_oled_charger_vivo_com_keeper(self) -> None:
        import cozmo_companion.core.motor_cozmo as motor

        cli = MagicMock()
        motor._charger_stream_sessao = True
        motor._charger_keeper_ativo = True
        th = MagicMock(is_alive=lambda: True)
        with patch.object(motor, "_display_thread", th):
            with patch.object(motor, "_display_lock"):
                self.assertTrue(motor.oled_charger_vivo(cli))
        motor._charger_keeper_ativo = False
        motor._charger_stream_sessao = False
        motor._charger_worker_thread = None

    def test_stream_estavel_com_keeper_sem_worker(self) -> None:
        import cozmo_companion.core.motor_cozmo as motor

        cli = MagicMock()
        motor._charger_stream_sessao = True
        th = MagicMock(is_alive=lambda: True)
        with patch.dict(
            "os.environ",
            {"COZMO_CHARGER_PLAY_STREAM": "0"},
        ):
            with patch(
                "cozmo_companion.core.motor_cozmo.base_oled_usa_charger",
                return_value=True,
            ):
                with patch.object(motor, "_display_thread", th):
                    with patch.object(motor, "_display_lock"):
                        self.assertTrue(motor._stream_oled_estavel(cli))
        motor._charger_stream_sessao = False

    def test_ligar_oled_base_preso_usa_charger(self) -> None:
        from cozmo_companion.core.motor_cozmo import ligar_oled_base

        cli = MagicMock()
        with patch.dict(
            "os.environ",
            {
                "COZMO_BASE_OLED_MODE": "proc",
                "COZMO_CHARGER_PLAY_STREAM": "1",
            },
        ):
            with patch(
                "cozmo_companion.core.motor_cozmo.modo_charger_oled",
                return_value=True,
            ) as charger:
                ligar_oled_base(cli, preso_na_base=True)
        charger.assert_called_once()

    def test_candidatos_charger_carga_cheia_olhos_acordados(self) -> None:
        from cozmo_companion.core.motor_cozmo import _candidatos_charger_oled

        cli = MagicMock()
        cli.animation_groups = {
            "IdleOnCharger": MagicMock(),
            "NeutralFace": MagicMock(),
            "InteractWithFaceTrackingIdle": MagicMock(),
        }
        with patch.dict(
            "os.environ",
            {"COZMO_CHARGER_AWAKE_IDLE": "InteractWithFaceTrackingIdle"},
        ):
            with patch("cozmo_companion.core.charger.em_base", return_value=True):
                with patch(
                    "cozmo_companion.core.charger.bateria_pct", return_value=100
                ):
                    cand = _candidatos_charger_oled(
                        cli, carga_pausada=True, carregando_agora=False
                    )
        self.assertEqual(cand[0], "IdleOnCharger")
        self.assertNotEqual(cand[0], "InteractWithFaceTrackingIdle")

    def test_candidatos_100pct_carregando_olhos_acordados(self) -> None:
        from cozmo_companion.core.motor_cozmo import _candidatos_charger_oled

        cli = MagicMock()
        cli.animation_groups = {
            "IdleOnChargerCharging": MagicMock(),
            "IdleOnCharger": MagicMock(),
        }
        with patch.dict(
            "os.environ",
            {
                "COZMO_CHARGER_AWAKE_IDLE": "InteractWithFaceTrackingIdle",
                "BATTERY_CHARGE_STOP_PCT": "90",
            },
        ):
            with patch("cozmo_companion.core.charger.na_base_oled", return_value=True):
                with patch(
                    "cozmo_companion.core.charger.em_modo_carga_base",
                    return_value=False,
                ):
                    with patch(
                        "cozmo_companion.core.charger.bateria_pct", return_value=50
                    ):
                        cand = _candidatos_charger_oled(
                            cli, carga_pausada=False, carregando_agora=True
                        )
        self.assertEqual(cand[0], "IdleOnChargerCharging")

    def test_modo_base_olhos_carga_cheia_usa_charger_stream(self) -> None:
        cli = MagicMock()
        ac = cli.anim_controller
        ac.playing_animation = False
        ac.playing_audio = False
        ac.queue.is_empty.return_value = True
        ac.thread = MagicMock(is_alive=lambda: True)
        with patch.dict(
            "os.environ",
            {
                "COZMO_BASE_OLED_MODE": "proc",
                "COZMO_BASE_OLED_CHARGER": "1",
                "COZMO_BASE_OLED_CHARGER_FULL": "1",
                "COZMO_CHARGER_PLAY_STREAM": "1",
                "COZMO_CHARGER_OLED_KEEPER": "0",
                "COZMO_BASE_STABLE_OLED": "0",
            },
        ):
            with patch("cozmo_companion.core.charger.na_base_oled", return_value=True):
                with patch(
                    "cozmo_companion.core.motor_cozmo.base_oled_carga_cheia_ativo",
                    return_value=False,
                ):
                    with patch(
                        "cozmo_companion.core.motor_cozmo.ligar_oled_base",
                    ) as ligar:
                        modo_base_olhos(cli)
        ligar.assert_called_once_with(cli, forcar=False, preso_na_base=True)
        ac.enable_procedural_face.assert_not_called()

    def test_base_oled_usa_proc_vivo_false_com_stream_off(self) -> None:
        from cozmo_companion.core.motor_cozmo import base_oled_usa_proc_vivo

        cli = MagicMock()
        with patch.dict(
            "os.environ",
            {"COZMO_CHARGER_PLAY_STREAM": "0", "COZMO_BASE_OLED_MODE": "proc"},
        ):
            with patch("cozmo_companion.core.charger.na_base_oled", return_value=True):
                self.assertFalse(base_oled_usa_proc_vivo(cli))

    def test_base_stable_bloqueia_stream_e_proc_30fps_mas_permite_loop_explicito(
        self,
    ) -> None:
        from cozmo_companion.core.motor_cozmo import (
            _base_oled_anim_loop_ativo,
            _charger_play_stream,
            base_oled_usa_proc_vivo,
        )

        cli = MagicMock()
        with patch.dict(
            "os.environ",
            {
                "COZMO_BASE_STABLE_OLED": "1",
                "COZMO_CHARGER_PLAY_STREAM": "1",
                "COZMO_BASE_OLED_ANIM_LOOP": "1",
                "COZMO_BASE_OLED_MODE": "proc",
            },
        ):
            with patch("cozmo_companion.core.charger.na_base_oled", return_value=True):
                self.assertFalse(_charger_play_stream(cli))
                self.assertTrue(_base_oled_anim_loop_ativo())
                self.assertFalse(base_oled_usa_proc_vivo(cli))

        with patch.dict(
            "os.environ",
            {
                "COZMO_BASE_STABLE_OLED": "1",
                "COZMO_CHARGER_PLAY_STREAM": "1",
                "COZMO_BASE_OLED_ANIM_LOOP": "auto",
                "COZMO_BASE_OLED_MODE": "proc",
            },
        ):
            self.assertFalse(_base_oled_anim_loop_ativo())

    def test_modo_livre_estavel_nao_liga_face_procedural(self) -> None:
        from cozmo_companion.core.motor_cozmo import modo_mesa_vivo

        cli = MagicMock()
        ac = cli.anim_controller
        with patch.dict(
            "os.environ",
            {"COZMO_BASE_STABLE_OLED": "1", "COZMO_LIVRE_PROC_FACE": "0"},
        ):
            with patch("cozmo_companion.core.motor_cozmo.rx_link_ok", return_value=True):
                with patch("cozmo_companion.core.conexao.cozmo_alcanavel", return_value=True):
                    modo_mesa_vivo(cli)
        ac.enable_procedural_face.assert_called_once_with(False)
        ac.enable_animations.assert_called_once_with(True)

    def test_modo_livre_instavel_nao_liga_anim_controller(self) -> None:
        from cozmo_companion.core.motor_cozmo import modo_mesa_vivo

        cli = MagicMock()
        ac = cli.anim_controller
        with patch("cozmo_companion.core.motor_cozmo.rx_link_ok", return_value=False):
            modo_mesa_vivo(cli)
        ac.enable_procedural_face.assert_not_called()
        ac.enable_animations.assert_not_called()

    def test_base_oled_usa_pulse_off_carga_cheia_stream(self) -> None:
        from cozmo_companion.core.motor_cozmo import (
            base_oled_usa_proc_vivo,
            base_oled_usa_pulse,
        )

        cli = MagicMock()
        with patch.dict(
            "os.environ",
            {
                "COZMO_BASE_OLED_MODE": "proc",
                "COZMO_BASE_OLED_CHARGER_FULL": "1",
                "COZMO_CHARGER_PLAY_STREAM": "1",
                "COZMO_BASE_PULSE_PROC": "1",
            },
        ):
            with patch("cozmo_companion.core.charger.em_base", return_value=True):
                with patch(
                    "cozmo_companion.core.motor_cozmo.base_oled_carga_cheia_ativo",
                    return_value=True,
                ):
                    self.assertFalse(base_oled_usa_proc_vivo(cli))
                    self.assertFalse(base_oled_usa_pulse(cli))

    def test_modo_base_olhos_direto_sem_flood(self) -> None:
        cli = MagicMock()
        cli.head_angle.radians = robot.MIN_HEAD_ANGLE.radians
        ac = cli.anim_controller
        ac.playing_animation = False
        ac.playing_audio = False
        import cozmo_companion.core.motor_cozmo as motor

        motor._ultimo_pulse_base = 0.0
        with patch.dict(
            "os.environ",
            {"BASE_HEAD_RESET": "1", "COZMO_BASE_OLED_MODE": "direct"},
        ):
            with patch(
                "cozmo_companion.display.rosto.pkt_rosto_procedural",
                return_value=MagicMock(),
            ):
                modo_base_olhos(cli)
        ac.enable_animations.assert_called_with(False)
        cli.conn.send.assert_called()
        cli.set_head_angle.assert_not_called()

    def test_enviar_oled_fila(self) -> None:
        cli = MagicMock()
        pkt = MagicMock()
        with patch.dict(
            "os.environ",
            {"COZMO_OLED_DIRECT": "0", "COZMO_BASE_OLED_MODE": "anim"},
        ):
            with patch.object(motor, "_burst_oled_display_image") as burst:
                enviar_oled(cli, pkt)
        burst.assert_called_once_with(cli, pkt)
        cli.anim_controller.display_image.assert_not_called()

    def test_enviar_audio_direto_sem_flood(self) -> None:
        cli = MagicMock()
        pkt = MagicMock()
        ac = cli.anim_controller
        ac.animations_enabled = True
        ac.procedural_face_enabled = False
        with patch.dict("os.environ", {"COZMO_BASE_OLED_MODE": "direct"}):
            from cozmo_companion.core.motor_cozmo import enviar_audio_fila

            enviar_audio_fila(cli, pkt)
        ac.enable_animations.assert_called_with(False)
        self.assertNotIn(
            call(True),
            ac.enable_animations.call_args_list,
        )
        sent = [c.args[0] for c in cli.conn.send.call_args_list]
        self.assertIn(pkt, sent)

    def test_base_proc_hz_respeita_config(self) -> None:
        with patch.dict("os.environ", {"COZMO_BASE_PROC_HZ": "2"}):
            self.assertEqual(base_proc_hz(), 2.0)

    def test_modo_tts_preparar_charger_nao_desliga_anim(self) -> None:
        cli = MagicMock()
        ac = cli.anim_controller
        ac.procedural_face_enabled = False
        ac.animations_enabled = True
        with patch.dict(
            "os.environ",
            {"COZMO_BASE_OLED_MODE": "proc", "COZMO_BASE_OLED_CHARGER_FULL": "1"},
        ):
            with patch(
                "cozmo_companion.core.charger.em_base",
                return_value=True,
            ):
                with patch(
                    "cozmo_companion.core.motor_cozmo.base_oled_usa_charger",
                    return_value=True,
                ):
                    with patch(
                        "cozmo_companion.core.motor_cozmo.base_oled_carga_cheia_ativo",
                        return_value=True,
                    ):
                        modo_tts_preparar(cli)
        self.assertNotIn(call(True), ac.enable_animations.call_args_list)

    def test_modo_tts_preparar_direto_sem_flood(self) -> None:
        cli = MagicMock()
        ac = cli.anim_controller
        ac.procedural_face_enabled = False
        ac.animations_enabled = False
        with patch.dict("os.environ", {"COZMO_BASE_OLED_MODE": "direct"}):
            from cozmo_companion.core.motor_cozmo import modo_tts_preparar

            modo_tts_preparar(cli)
        self.assertNotIn(
            call(True),
            ac.enable_animations.call_args_list,
        )

    def test_modo_charger_stream_liga_anim(self) -> None:
        cli = MagicMock()
        cli._next_anim_id = 250
        cli.animation_groups = {"IdleOnCharger": MagicMock()}
        ac = cli.anim_controller
        ac.playing_animation = False
        ac.playing_audio = False
        ac.thread = MagicMock(is_alive=lambda: True)
        ac.animations_enabled = True
        ac.queue.is_empty.return_value = True
        with patch.dict(
            "os.environ",
            {
                "COZMO_BASE_OLED_MODE": "proc",
                "COZMO_BASE_OLED_CHARGER_FULL": "1",
                "COZMO_CHARGER_PLAY_STREAM": "1",
                "COZMO_CHARGER_OLED_KEEPER": "0",
                "COZMO_CHARGER_SLOW_ANIM": "0",
                "COZMO_BASE_STABLE_OLED": "0",
                "COZMO_BASE_KEEPER_VIVO": "0",
            },
        ):
            with patch(
                "cozmo_companion.core.motor_cozmo.base_oled_usa_charger",
                return_value=True,
            ):
                with patch(
                    "cozmo_companion.core.motor_cozmo.base_oled_carga_cheia_ativo",
                    return_value=False,
                ):
                    with patch(
                        "cozmo_companion.core.charger.carga_firmware_pausada",
                        return_value=False,
                    ):
                        with patch(
                            "cozmo_companion.core.charger.carregando",
                            return_value=True,
                        ):
                            with patch("cozmo_companion.core.charger.em_base", return_value=True):
                                with patch(
                                    "cozmo_companion.core.charger.bateria_pct",
                                    return_value=50,
                                ):
                                    with patch(
                                        "cozmo_companion.core.motor_cozmo.iniciar_loop_charger",
                                    ):
                                        with patch(
                                            "cozmo_companion.core.motor_cozmo._garantir_charger_worker",
                                            return_value=True,
                                        ) as worker:
                                            modo_charger_oled(cli, forcar=True)
        worker.assert_called()

    def test_replay_charger_respeita_fila(self) -> None:
        import cozmo_companion.core.motor_cozmo as motor

        cli = MagicMock()
        ac = cli.anim_controller
        ac.playing_animation = False
        ac.playing_audio = False
        ac.queue.is_empty.return_value = False
        motor._ultimo_charger_play = 0.0
        with patch.dict("os.environ", {"COZMO_CHARGER_PLAY_STREAM": "0"}):
            with patch(
                "cozmo_companion.core.motor_cozmo.base_oled_usa_charger",
                return_value=True,
            ):
                ok = motor._replay_anim_charger(cli, "IdleOnCharger")
        self.assertTrue(ok)
        cli.play_anim_group.assert_not_called()

    def test_pulso_carga_cheia_charger_nao_desliga_anim(self) -> None:
        cli = MagicMock()
        ac = cli.anim_controller
        ac.playing_animation = True
        ac.playing_audio = False
        import cozmo_companion.core.motor_cozmo as motor

        motor._ultimo_wake_carga_cheia = 0.0
        motor._charger_keeper_ativo = True
        with patch.dict(
            "os.environ",
            {
                "COZMO_FULL_CHARGE_WAKE": "1",
                "COZMO_CHARGER_PLAY_STREAM": "1",
                "COZMO_CHARGER_OLED_KEEPER": "1",
            },
        ):
            with patch(
                "cozmo_companion.core.charger.carga_firmware_pausada",
                return_value=True,
            ):
                with patch(
                    "cozmo_companion.core.motor_cozmo.base_oled_usa_charger",
                    return_value=True,
                ):
                    with patch(
                        "cozmo_companion.core.motor_cozmo._tick_charger_oled",
                        return_value=True,
                    ) as tick:
                        from cozmo_companion.core.motor_cozmo import pulso_oled_carga_cheia

                        pulso_oled_carga_cheia(cli)
        ac.enable_animations.assert_not_called()
        tick.assert_called_once_with(cli)

    def test_modo_charger_handshake_sem_flood(self) -> None:
        cli = MagicMock()
        cli.animation_groups = {"IdleOnCharger": MagicMock()}
        ac = cli.anim_controller
        ac.playing_animation = False
        ac.playing_audio = False
        ac.thread = None
        with patch.dict(
            "os.environ",
            {
                "COZMO_BASE_OLED_MODE": "proc",
                "COZMO_BASE_OLED_CHARGER_FULL": "1",
                "COZMO_CHARGER_PLAY_STREAM": "0",
                "COZMO_CHARGER_OLED_KEEPER": "1",
                "COZMO_CHARGER_SLOW_ANIM": "0",
                "COZMO_BASE_STABLE_OLED": "0",
                "COZMO_BASE_KEEPER_VIVO": "0",
            },
        ):
            with patch(
                "cozmo_companion.core.motor_cozmo.base_oled_usa_charger",
                return_value=True,
            ):
                with patch(
                    "cozmo_companion.core.motor_cozmo.base_oled_carga_cheia_ativo",
                    return_value=False,
                ):
                    with patch(
                        "cozmo_companion.core.charger.carga_firmware_pausada",
                        return_value=True,
                    ):
                        with patch(
                            "cozmo_companion.core.charger.carregando",
                            return_value=False,
                        ):
                            with patch("cozmo_companion.core.charger.em_base", return_value=True):
                                with patch(
                                    "cozmo_companion.core.charger.bateria_pct",
                                    return_value=100,
                                ):
                                    with patch(
                                        "cozmo_companion.core.motor_cozmo.base_oled_usa_proc_vivo",
                                        return_value=False,
                                    ):
                                        with patch(
                                            "cozmo_companion.core.motor_cozmo.iniciar_loop_charger",
                                        ):
                                            modo_charger_oled(cli, forcar=True)
        ac.enable_animations.assert_called_with(False)
        cli.play_anim_group.assert_not_called()

    def test_animar_base_bloqueada_modo_direto(self) -> None:
        cli = MagicMock()
        with patch.dict("os.environ", {"COZMO_BASE_OLED_MODE": "direct"}):
            self.assertFalse(
                animar_grupo(cli, "DriveOffCharger", na_base=True, procedural_antes=True)
            )
        cli.play_anim_group.assert_not_called()

    def test_guard_oled_nao_limpa_na_base(self) -> None:
        cli = MagicMock()
        ac = cli.anim_controller
        pkt = MagicMock(image=b"\xaa\xbb")
        ac.last_image_pkt = pkt
        cleared = []

        def _orig_clear() -> None:
            cleared.append(1)
            ac.last_image_pkt = MagicMock(image=b"\x3f\x3f")

        ac._clear_last_image_pkt = _orig_clear
        ac._on_animation_ended = MagicMock()
        ac._cozmo_charger_guard = False
        ac._cozmo_anim_base_guard = False
        with patch(
            "cozmo_companion.core.motor_cozmo.base_oled_usa_charger",
            return_value=True,
        ):
            instalar_charger_display_guard(cli)
            ac._clear_last_image_pkt()
            ac._on_animation_ended(cli, None)
        self.assertEqual(cleared, [])
        self.assertIs(ac.last_image_pkt, pkt)

    def test_anim_loop_auto_com_stream_off(self) -> None:
        import cozmo_companion.core.motor_cozmo as motor

        with patch.dict(
            "os.environ",
            {
                "COZMO_BASE_OLED_ANIM_LOOP": "auto",
                "COZMO_BASE_STABLE_OLED": "0",
                "COZMO_CHARGER_PLAY_STREAM": "0",
                "COZMO_BASE_OLED_MODE": "proc",
            },
        ):
            self.assertTrue(motor._base_oled_anim_loop_ativo())
        with patch.dict(
            "os.environ",
            {
                "COZMO_BASE_OLED_ANIM_LOOP": "auto",
                "COZMO_BASE_STABLE_OLED": "0",
                "COZMO_CHARGER_PLAY_STREAM": "1",
            },
        ):
            self.assertFalse(motor._base_oled_anim_loop_ativo())

    def test_vigiar_nao_desliga_anim_com_loop_keeper(self) -> None:
        from cozmo_companion.core.motor_cozmo import vigiar_flood_base

        cli = MagicMock()
        ac = cli.anim_controller
        ac.thread = None
        ac.procedural_face_enabled = False
        ac.animations_enabled = False
        import cozmo_companion.core.motor_cozmo as motor

        motor._charger_keeper_ativo = True
        motor._charger_stream_sessao = True
        with patch.dict(
            "os.environ",
            {
                "COZMO_CHARGER_PLAY_STREAM": "0",
                "COZMO_BASE_OLED_ANIM_LOOP": "auto",
                "COZMO_BASE_STABLE_OLED": "0",
                "COZMO_BASE_KEEPER_VIVO": "0",
            },
        ):
            with patch(
                "cozmo_companion.core.motor_cozmo.rx_link_ok",
                return_value=True,
            ):
                with patch(
                    "cozmo_companion.core.motor_cozmo.base_oled_carga_cheia_ativo",
                    return_value=False,
                ):
                    with patch(
                        "cozmo_companion.core.motor_cozmo.base_oled_usa_charger",
                        return_value=True,
                    ):
                        with patch(
                            "cozmo_companion.core.motor_cozmo._clip_loop_vivo",
                            return_value=False,
                        ):
                            with patch(
                                "cozmo_companion.core.motor_cozmo.base_oled_loop_segurado",
                                return_value=False,
                            ):
                                with patch(
                                    "cozmo_companion.core.motor_cozmo._garantir_base_oled_anim_loop",
                                    return_value=True,
                                ) as garantir:
                                    vigiar_flood_base(cli)
        garantir.assert_called_once_with(cli)
        ac.enable_animations.assert_not_called()

    def test_vigiar_nao_mata_clip_keeper_carga_cheia(self) -> None:
        from cozmo_companion.core.motor_cozmo import vigiar_flood_base

        cli = MagicMock()
        ac = cli.anim_controller
        ac.thread = None
        ac.procedural_face_enabled = False
        ac.animations_enabled = False
        with patch.dict("os.environ", {"COZMO_CHARGER_PLAY_STREAM": "0"}):
            with patch(
                "cozmo_companion.core.motor_cozmo.rx_link_ok",
                return_value=True,
            ):
                with patch(
                    "cozmo_companion.core.motor_cozmo.keeper_base_ativo",
                    return_value=True,
                ):
                    with patch(
                        "cozmo_companion.core.motor_cozmo.base_oled_usa_charger",
                        return_value=True,
                    ):
                        with patch(
                            "cozmo_companion.core.motor_cozmo.base_oled_carga_cheia_ativo",
                            return_value=True,
                        ):
                            with patch(
                                "cozmo_companion.core.motor_cozmo._parar_display_keeper"
                            ) as parar:
                                vigiar_flood_base(cli)
        parar.assert_not_called()

    def test_oled_keeper_vivo_nao_toca_ppclip_quando_loop_off(self) -> None:
        cli = MagicMock()
        cli.animation_groups = {"IdleOnCharger": MagicMock()}
        cli.battery_voltage = 4.43
        with patch.dict("os.environ", {"COZMO_BASE_OLED_ANIM_LOOP": "0"}):
            with patch(
                "cozmo_companion.core.motor_cozmo._candidatos_charger_oled",
                return_value=("IdleOnCharger",),
            ):
                with patch(
                    "cozmo_companion.core.motor_cozmo._pool_oled_com_frames",
                    return_value=(),
                ):
                    with patch(
                        "cozmo_companion.core.motor_cozmo._iniciar_keeper_clip_oled_base",
                        return_value=True,
                    ) as keeper:
                        with patch(
                            "cozmo_companion.core.motor_cozmo._exibir_clip_base",
                            return_value=True,
                        ) as ppclip:
                            motor._ativar_oled_keeper_vivo(cli, time.monotonic())
        keeper.assert_called_once_with(cli, "IdleOnCharger")
        ppclip.assert_not_called()

    def test_tick_charger_keeper_nao_reenvia_frame_fora_do_keeper(self) -> None:
        cli = MagicMock()
        motor._charger_keeper_ativo = True
        motor._charger_stream_sessao = True
        motor._charger_oled_nome = "IdleOnCharger"
        cli.anim_controller.last_image_pkt = MagicMock()
        try:
            with patch.object(motor, "base_oled_usa_charger", return_value=True):
                with patch.object(motor, "base_oled_carga_cheia_ativo", return_value=True):
                    with patch.object(motor, "keeper_base_ativo", return_value=True):
                        with patch.object(motor, "_refresh_sessao_oled_leve"):
                            self.assertTrue(motor._tick_charger_oled(cli))
            cli.conn.send.assert_not_called()
        finally:
            motor._charger_keeper_ativo = False
            motor._charger_stream_sessao = False
            motor._charger_oled_nome = None

    def test_tick_charger_keeper_desliga_anim_controller(self) -> None:
        cli = MagicMock()
        ac = cli.anim_controller
        ac.thread = MagicMock(is_alive=lambda: False)
        motor._charger_keeper_ativo = True
        motor._charger_stream_sessao = True
        motor._charger_oled_nome = "IdleOnCharger"
        try:
            with patch.object(motor, "base_oled_usa_charger", return_value=True):
                with patch.object(motor, "base_oled_carga_cheia_ativo", return_value=True):
                    with patch.object(motor, "keeper_base_ativo", return_value=True):
                        with patch.object(motor, "_refresh_sessao_oled_leve"):
                            self.assertTrue(motor._tick_charger_oled(cli))
        finally:
            motor._charger_keeper_ativo = False
            motor._charger_stream_sessao = False
            motor._charger_oled_nome = None
        ac.enable_procedural_face.assert_called_with(False)
        ac.enable_animations.assert_called_with(False)

    def test_parar_flood_anim_keeper_desliga_thread_anim(self) -> None:
        cli = MagicMock()
        ac = cli.anim_controller
        th = MagicMock(is_alive=lambda: True)
        ac.thread = th
        with patch.object(motor, "keeper_base_ativo", return_value=True):
            with patch.object(motor, "base_oled_carga_cheia_ativo", return_value=True):
                motor.parar_flood_anim(cli)
        ac.enable_procedural_face.assert_called_with(False)
        ac.enable_animations.assert_called_with(False)
        cli.cancel_anim.assert_called()
        th.join.assert_called()

    def test_enviar_audio_base_charger_nao_usa_play_audio(self) -> None:
        cli = MagicMock()
        pkt = MagicMock()
        with patch.object(motor, "base_oled_usa_charger", return_value=True):
            motor.enviar_audio_fila(cli, pkt, manter_face=True)
        cli.conn.send.assert_called_with(pkt)
        cli.anim_controller.play_audio.assert_not_called()
        self.assertNotIn(call(True), cli.anim_controller.enable_animations.call_args_list)

    def test_variar_clip_loop_off_forca_keeper_frames(self) -> None:
        cli = MagicMock()
        cli.animation_groups.keys.return_value = ["IdleOnCharger", "Hiccup"]
        motor._ultimo_variar_clip = 0.0
        motor._charger_stream_sessao = True
        motor._charger_keeper_ativo = False
        try:
            with patch.dict(
                os.environ,
                {
                    "COZMO_BASE_OLED_ANIM_LOOP": "0",
                    "COZMO_BASE_VARIAR_CHANCE": "1",
                    "COZMO_CHARGER_PLAY_STREAM": "0",
                },
            ):
                with patch(
                    "cozmo_companion.core.charger.base_oled_estavel",
                    return_value=False,
                ):
                    with patch(
                        "cozmo_companion.core.charger.carga_prioritaria",
                        return_value=False,
                    ):
                        with patch(
                            "cozmo_companion.core.ambiente_escuro.detector_escuro"
                        ) as escuro:
                            escuro.return_value.escuro = False
                            with patch.object(motor, "rx_link_ok", return_value=True):
                                with patch.object(
                                    motor, "base_oled_usa_charger", return_value=True
                                ):
                                    with patch.object(
                                        motor,
                                        "_pool_oled_com_frames",
                                        return_value=("Hiccup",),
                                    ):
                                        with patch.object(
                                            motor,
                                            "_iniciar_keeper_clip_oled_base",
                                            return_value=True,
                                        ) as keeper:
                                            self.assertTrue(
                                                motor.variar_clip_base_oled(
                                                    cli, forcado=True
                                                )
                                            )
        finally:
            motor._charger_keeper_ativo = False
            motor._charger_stream_sessao = False
            motor._ultimo_variar_clip = 0.0
        keeper.assert_called_once_with(cli, "Hiccup")

    def test_anim_base_usa_keeper_quando_loop_off(self) -> None:
        cli = MagicMock()
        with patch.dict("os.environ", {"COZMO_BASE_OLED_ANIM_LOOP": "0"}):
            with patch(
                "cozmo_companion.core.anims.permitido_sem_rodas_na_base",
                return_value=True,
            ):
                with patch(
                    "cozmo_companion.core.motor_cozmo.base_oled_usa_charger",
                    return_value=True,
                ):
                    with patch(
                        "cozmo_companion.core.motor_cozmo._iniciar_keeper_clip_oled_base",
                        return_value=True,
                    ) as keeper:
                        with patch(
                            "cozmo_companion.core.anim_base_patch.play_grupo_sem_rodas_na_base",
                            return_value=True,
                        ) as ppclip:
                            self.assertTrue(
                                animar_grupo(
                                    cli,
                                    "HiccupGetIn",
                                    na_base=True,
                                    procedural_antes=True,
                                )
                            )
        keeper.assert_called_once_with(cli, "HiccupGetIn")
        ppclip.assert_not_called()

    def test_normalizar_anim_id_wrap_256(self) -> None:
        cli = MagicMock()
        cli._next_anim_id = 256
        aid = _normalizar_anim_id(cli)
        self.assertEqual(aid, 1)
        self.assertEqual(cli._next_anim_id, 1)

    def test_instalar_anim_id_seguro_wrap(self) -> None:
        cli = MagicMock()
        cli._cozmo_anim_id_seguro = False
        cli._next_anim_id = 255
        chamadas: list[int] = []

        def orig(_pp: object) -> None:
            chamadas.append(int(cli._next_anim_id))
            cli._next_anim_id = int(cli._next_anim_id) + 1

        cli.play_anim_ppclip = orig
        instalar_anim_id_seguro(cli)
        pp = object()
        cli.play_anim_ppclip(pp)
        cli.play_anim_ppclip(pp)
        self.assertEqual(chamadas[0], 255)
        self.assertEqual(chamadas[1], 1)
        self.assertEqual(cli._next_anim_id, 2)

    def test_executar_ppclip_core_normaliza_256(self) -> None:
        cli = MagicMock()
        cli._next_anim_id = 256
        usados: list[int] = []

        def core(_pp: object) -> None:
            usados.append(int(cli._next_anim_id))
            cli._next_anim_id = int(cli._next_anim_id) + 1

        cli._cozmo_ppclip_core = core
        motor._executar_ppclip_core(cli, object())
        self.assertEqual(usados, [1])
        self.assertEqual(cli._next_anim_id, 2)

    def test_variar_clip_bloqueado_quando_oled_segurado(self) -> None:
        motor.segurar_base_oled_loop(30.0)
        try:
            cli = MagicMock()
            cli.animation_groups = {"IdleOnCharger": object()}
            with patch.object(motor, "_base_anim_loop_vivo", return_value=False):
                with patch.object(motor, "base_oled_usa_charger", return_value=True):
                    with patch.object(motor, "_charger_stream_sessao", True):
                        self.assertFalse(motor.variar_clip_base_oled(cli))
        finally:
            motor._base_oled_loop_hold_ate = 0.0
            motor._base_oled_loop_hold_desde = 0.0

    @patch("cozmo_companion.core.conexao.cozmo_alcanavel", return_value=True)
    @patch("cozmo_companion.core.motor_cozmo.rx_link_ok", return_value=True)
    @patch("cozmo_companion.core.motor_cozmo.base_oled_loop_segurado", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.base_oled_usa_charger", return_value=True)
    def test_detectar_cozmo01_timeout_oled(
        self,
        _charger,
        _hold,
        _rx,
        _ping,
    ) -> None:
        motor._ultimo_exibir_clip_em = time.monotonic() - 40.0
        cli = MagicMock()
        self.assertFalse(motor.detectar_cozmo01_suspeito(cli))
        motor._ultimo_exibir_clip_em = time.monotonic()
        self.assertFalse(motor.detectar_cozmo01_suspeito(cli))

    @patch("cozmo_companion.core.conexao.cozmo_alcanavel", return_value=True)
    @patch("cozmo_companion.core.conexao.cozmo_rota_ap", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.rx_link_ok", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.base_oled_loop_segurado", return_value=False)
    def test_detectar_cozmo01_rx_morto(self, _hold, _rx, _rota, _ping) -> None:
        motor._ultimo_exibir_clip_em = 0.0
        motor._rx_off_desde = time.monotonic() - 12.0
        cli = MagicMock()
        self.assertTrue(motor.detectar_cozmo01_suspeito(cli))
        motor._rx_off_desde = time.monotonic()
        self.assertFalse(motor.detectar_cozmo01_suspeito(cli))
        motor._rx_off_desde = 0.0

    @patch("cozmo_companion.core.conexao.cozmo_alcanavel", return_value=True)
    @patch("cozmo_companion.core.conexao.cozmo_rota_ap", return_value=True)
    @patch("cozmo_companion.core.motor_cozmo.rx_link_ok", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.base_oled_loop_segurado", return_value=False)
    def test_detectar_cozmo01_rx_morto_preserva_frame_oled_recente(
        self,
        _hold,
        _rx,
        _rota,
        _ping,
    ) -> None:
        motor._rx_off_desde = time.monotonic() - 30.0
        motor._ultimo_exibir_clip_em = time.monotonic()
        cli = MagicMock()
        with patch.dict(os.environ, {"COZMO_BASE_OLED_TX_RX_STALL_GRACE_S": "180"}):
            self.assertFalse(motor.detectar_cozmo01_suspeito(cli))
        motor._ultimo_exibir_clip_em = time.monotonic() - 120.0
        self.assertFalse(motor.detectar_cozmo01_suspeito(cli))
        with patch.dict(os.environ, {"COZMO01_RX_DEAD_ROUTE_S": "20"}):
            self.assertTrue(motor.detectar_cozmo01_suspeito(cli))
        motor._rx_off_desde = 0.0
        motor._ultimo_exibir_clip_em = 0.0

    @patch("cozmo_companion.core.conexao.cozmo_alcanavel", return_value=True)
    @patch("cozmo_companion.core.motor_cozmo._sequencia_recuperar_cozmo01", return_value=True)
    @patch("cozmo_companion.core.motor_cozmo.rx_link_ok", return_value=True)
    def test_recuperar_cozmo01_respeita_cooldown(self, _rx, seq, _ping) -> None:
        cli = MagicMock()
        monitor = MagicMock()
        motor._ultimo_recuperar_cozmo01 = time.monotonic()
        self.assertFalse(motor.recuperar_cozmo01_auto(cli, monitor))
        seq.assert_not_called()
        self.assertTrue(motor.recuperar_cozmo01_auto(cli, monitor, forcar=True))
        seq.assert_called_once()

    @patch("cozmo_companion.core.conexao.cozmo_alcanavel", return_value=True)
    @patch("cozmo_companion.core.motor_cozmo._sequencia_recuperar_cozmo01", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.rx_link_ok", return_value=False)
    def test_recuperar_cozmo01_falha_nao_reseta_medidores(self, _rx, _seq, _ping) -> None:
        cli = MagicMock()
        monitor = MagicMock()
        medidor = MagicMock()
        motor._ultimo_recuperar_cozmo01 = 0.0
        self.assertFalse(
            motor.recuperar_cozmo01_auto(cli, monitor, medidor, forcar=True)
        )
        monitor.sincronizar.assert_not_called()
        medidor.reset.assert_not_called()

    def test_segurar_hold_stack(self) -> None:
        motor._base_oled_loop_hold_ate = 0.0
        motor._base_oled_loop_hold_desde = 0.0
        try:
            with patch.dict(
                os.environ,
                {"COZMO_BASE_OLED_HOLD_MAX_S": "10", "COZMO_BASE_OLED_HOLD_STACK": "2"},
            ):
                motor.segurar_base_oled_loop(8.0)
                t0 = motor._base_oled_loop_hold_ate
                motor.segurar_base_oled_loop(12.0)
                self.assertGreater(motor._base_oled_loop_hold_ate, t0)
                self.assertLessEqual(
                    motor._base_oled_loop_hold_ate,
                    motor._base_oled_loop_hold_desde + 20.0,
                )
        finally:
            motor._base_oled_loop_hold_ate = 0.0
            motor._base_oled_loop_hold_desde = 0.0

    def test_pode_tocar_anim_direto_bloqueia_fila(self) -> None:
        cli = MagicMock()
        cli.anim_controller.playing_audio = False
        self.assertFalse(
            motor.pode_tocar_anim_direto(cli, fila_ocupada=True, falando=False)
        )
        self.assertTrue(
            motor.pode_tocar_anim_direto(cli, fila_ocupada=False, falando=False)
        )

    @patch("cozmo_companion.core.motor_cozmo._base_oled_anim_loop_ativo", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.base_oled_usa_charger", return_value=True)
    @patch("cozmo_companion.core.motor_cozmo._iniciar_keeper_clip_oled_base", return_value=True)
    def test_tocar_clip_base_seguro(self, keeper, _charger, _loop) -> None:
        cli = MagicMock()
        self.assertTrue(motor.tocar_clip_base_seguro(cli, "CodeLabBlink"))
        keeper.assert_called_once_with(cli, "CodeLabBlink")
        self.assertFalse(motor.tocar_clip_base_seguro(cli, "DriveStuckOffCharger"))

    @patch("cozmo_companion.core.motor_cozmo.tocar_clip_base_seguro", return_value=True)
    @patch("cozmo_companion.core.motor_cozmo._charger_usa_keeper", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo._base_oled_anim_loop_ativo", return_value=True)
    @patch("cozmo_companion.core.motor_cozmo.base_oled_usa_charger", return_value=True)
    def test_animar_grupo_base_usa_ppclip(self, _charger, _loop, _keeper, tocar) -> None:
        cli = MagicMock()
        self.assertTrue(
            animar_grupo(cli, "CodeLabBlink", na_base=True, procedural_antes=True)
        )
        tocar.assert_called_once_with(cli, "CodeLabBlink")

    @patch("cozmo_companion.core.motor_cozmo.base_oled_usa_charger", return_value=True)
    @patch("cozmo_companion.core.motor_cozmo.modo_charger_oled")
    @patch("cozmo_companion.core.motor_cozmo._base_oled_anim_loop_ativo", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo._clip_loop_vivo", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.base_oled_loop_segurado", return_value=False)
    def test_religar_pos_notif_loop_off_usa_keeper(
        self, _hold, _clip, _loop, modo, _charger
    ) -> None:
        cli = MagicMock()
        motor.religar_base_oled_pos_notif(cli)
        modo.assert_called_once_with(cli, forcar=True)


class TestOledAntiEstatico(unittest.TestCase):
    def test_oled_hz_reduz_por_fase(self) -> None:
        with patch.dict(
            os.environ,
            {
                "COZMO_OLED_HZ_VERDE": "4",
                "COZMO_OLED_HZ_AMARELO": "3",
                "COZMO_OLED_HZ_LARANJA": "1",
                "COZMO_OLED_HZ_VERMELHO": "1.0",
            },
        ):
            self.assertEqual(motor.oled_hz_para_fase("verde", 4), 4)
            self.assertEqual(motor.oled_hz_para_fase("amarelo", 4), 3)
            self.assertEqual(motor.oled_hz_para_fase("laranja", 4), 1)
            self.assertEqual(motor.oled_hz_para_fase("vermelho", 4), 1.0)

    def test_frame_pequeno_aciona_resgate_oled(self) -> None:
        pkt = MagicMock()
        pkt.image = b"\x00" * 12
        with patch.dict(os.environ, {"COZMO_OLED_RESCUE_MIN_BYTES": "64"}):
            self.assertTrue(motor._imagem_fraca_para_resgate(pkt))

    def test_resgate_oled_envia_rosto_visivel(self) -> None:
        cli = MagicMock()
        pkt = MagicMock()
        pkt.image = b"olhos-visiveis" * 8
        with (
            patch("cozmo_companion.display.rosto.pkt_rosto_procedural", return_value=pkt),
            patch.object(motor, "_handshake_frame_oled") as handshake,
        ):
            self.assertTrue(motor._semear_oled_resgate(cli, motivo="teste"))
        handshake.assert_called_once_with(cli, force=True)
        cli.conn.send.assert_called_once_with(pkt)
        self.assertEqual(cli.anim_controller.last_image_pkt, pkt)

    def test_resgate_oled_recente(self) -> None:
        motor._ultimo_exibir_clip_grupo = "resgate_oled"
        motor._ultimo_exibir_clip_em = time.monotonic()
        self.assertTrue(motor.oled_resgate_recente(2.0))
        motor._ultimo_exibir_clip_grupo = "IdleOnCharger"
        self.assertFalse(motor.oled_resgate_recente(2.0))

    def test_oled_fase_degrada_imediato_para_keeper(self) -> None:
        cli = MagicMock()
        motor._oled_fase_aplicada = "verde"
        motor._oled_fase_observada = "verde"
        with (
            patch.object(motor, "modo_sono_oled_ativo", return_value=False),
            patch.object(motor, "_parar_loop_clip_base") as parar,
            patch.object(motor, "_parar_display_keeper"),
            patch.object(motor, "_iniciar_display_keeper") as iniciar,
            patch.object(motor, "_keeper_clip_hz", return_value=4.0),
        ):
            self.assertTrue(motor.ajustar_oled_fase_link(cli, "laranja"))
        parar.assert_called_once()
        iniciar.assert_called_once()
        self.assertEqual(iniciar.call_args.args[1], 1.0)
        motor._oled_fase_aplicada = "verde"
        motor._oled_fase_observada = "verde"

    def test_stable_keeper_base_usa_clip_oficial_default(self) -> None:
        cli = MagicMock()
        motor._charger_oled_nome = None
        with (
            patch.dict(
                os.environ,
                {
                    "COZMO_BASE_STABLE_OLED": "1",
                    "COZMO_BASE_OLED_CHARGER": "1",
                    "COZMO_OLED_KEEPER_MAX_HZ": "0.8",
                    "COZMO_OLED_VERDE_KEEPER_HZ": "0.8",
                },
            ),
            patch.object(motor, "base_oled_usa_charger", return_value=True),
            patch.object(motor, "_oled_sessao_viva", return_value=True),
            patch.object(motor, "_iniciar_display_keeper") as iniciar,
        ):
            self.assertTrue(motor.manter_oled_base_ativo(cli))
        iniciar.assert_called_once_with(cli, 0.8, grupo="IdleOnCharger")

    def test_watchdog_anim_presa_cancela_uma_vez(self) -> None:
        cli = MagicMock()
        cli.anim_controller.playing_animation = True
        cli.anim_controller.playing_audio = False
        agora = time.monotonic()
        novo, cancelou = motor.vigiar_anim_presa(
            cli, agora - 10.0, limite_s=2.0
        )
        self.assertEqual(novo, 0.0)
        self.assertTrue(cancelou)
        cli.cancel_anim.assert_called_once_with()

    def test_watchdog_anim_livre_zera_timer(self) -> None:
        cli = MagicMock()
        cli.anim_controller.playing_animation = False
        cli.anim_controller.playing_audio = False
        self.assertEqual(motor.vigiar_anim_presa(cli, 123.0), (0.0, False))

    def test_oled_estatico_demais(self) -> None:
        cli = MagicMock()
        cli.anim_controller.playing_animation = True
        cli.anim_controller.playing_audio = False
        cli.anim_controller.queue.is_empty.return_value = True
        with patch.dict(os.environ, {"COZMO_OLED_MAX_ESTATICO_S": "18"}):
            motor._ultimo_exibir_clip_em = time.monotonic() - 20.0
            with patch.object(motor, "rx_link_ok", return_value=True):
                self.assertFalse(motor._oled_estatico_demais(cli))
            motor._ultimo_exibir_clip_em = time.monotonic() - 20.0
            cli.anim_controller.playing_animation = False
            with patch.object(motor, "base_oled_loop_segurado", return_value=False):
                self.assertTrue(motor._oled_estatico_demais(cli))
            motor._ultimo_exibir_clip_em = time.monotonic()
            self.assertFalse(motor._oled_estatico_demais(cli))

    @patch("cozmo_companion.core.motor_cozmo._exibir_clip_base", return_value=True)
    @patch("cozmo_companion.core.motor_cozmo._garantir_base_oled_anim_loop", return_value=True)
    @patch("cozmo_companion.core.motor_cozmo._base_oled_anim_loop_ativo", return_value=True)
    @patch("cozmo_companion.core.motor_cozmo._oled_tx_permitido", return_value=True)
    @patch("cozmo_companion.core.motor_cozmo.base_oled_usa_charger", return_value=True)
    @patch("cozmo_companion.core.motor_cozmo._oled_anim_vivo", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.base_oled_loop_segurado", return_value=False)
    def test_forcar_movimento_oled_base(
        self, _hold, _anim, _charger, _tx, _loop_on, _g, _ex
    ) -> None:
        cli = MagicMock()
        cli.animation_groups = {"CodeLabBlink": None}
        cli.anim_controller.playing_audio = False
        cli.anim_controller.playing_animation = False
        cli.anim_controller.queue.is_empty.return_value = True
        with patch.object(motor, "_escolher_proximo_clip_base", return_value="CodeLabBlink"):
            self.assertTrue(motor._forcar_movimento_oled_base(cli))


if __name__ == "__main__":
    unittest.main()
