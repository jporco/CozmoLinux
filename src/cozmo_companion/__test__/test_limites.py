"""Testes dos limites do cérebro (PC → Cozmo)."""

import os
import time
import unittest
from unittest.mock import MagicMock, patch

from cozmo_companion.core.conexao import (
    MonitorRx,
    MedidorUdp,
    ratio_udp,
    udp_leve_por_delta,
    udp_saturado_por_delta,
)
from cozmo_companion.core.limites import limites


class TestLimites(unittest.TestCase):
    def test_defaults(self):
        lim = limites()
        self.assertEqual(lim.udp_ratio_leve, 1.35)
        self.assertEqual(lim.udp_ratio_max, 1.75)
        self.assertEqual(lim.tts_max_base, 1)

    def test_ratio_udp_boot_baixo(self):
        cli = MagicMock()
        with patch(
            "cozmo_companion.core.conexao.diagnostico",
            return_value={"sent_frames": 200, "recv_frames": 10},
        ):
            self.assertEqual(ratio_udp(cli), 0.0)
    def test_delta_saturado_rx_parado(self) -> None:
        self.assertTrue(udp_saturado_por_delta(0, 400))
        self.assertFalse(udp_saturado_por_delta(10, 100))

    def test_delta_leve(self) -> None:
        self.assertTrue(udp_leve_por_delta(0, 500, 0.0))
        self.assertFalse(udp_leve_por_delta(30, 100, 3.0))

    def test_medidor_janela(self) -> None:
        m = MedidorUdp(janela_s=30.0)
        cli = MagicMock()
        t0 = time.monotonic()
        with patch(
            "cozmo_companion.core.conexao.diagnostico",
            side_effect=[
                {"recv_frames": 100, "sent_frames": 200},
                {"recv_frames": 130, "sent_frames": 350},
            ],
        ):
            drx, dtx, rd = m.amostra(cli)
            self.assertEqual(drx, 0)
            m._hist.append((t0 - 25.0, 100, 200))
            m._hist.append((time.monotonic(), 130, 350))
            drx2, dtx2, _ = m.amostra(cli)
        self.assertEqual(drx2, 30)
        self.assertEqual(dtx2, 150)

    def test_monitor_rx_idle_tx_quieto(self) -> None:
        rx = MonitorRx()
        rx._rx = 1000
        rx._tx = 200
        rx._rx_em = __import__("time").monotonic()
        cli = MagicMock()
        with patch(
            "cozmo_companion.core.conexao.diagnostico",
            return_value={"sent_frames": 210, "recv_frames": 1000},
        ):
            self.assertTrue(rx.tick(cli))

    def test_monitor_rx_stall_tx_sobe_ratio_baixo_ok(self) -> None:
        """TX sobe sem RX com ratio saudável (anim) — não é stall."""
        rx = MonitorRx()
        rx._rx = 55_834
        rx._tx = 11_000
        rx._rx_em = __import__("time").monotonic()
        cli = MagicMock()
        with patch(
            "cozmo_companion.core.conexao.diagnostico",
            return_value={"sent_frames": 18_821, "recv_frames": 55_834},
        ):
            self.assertTrue(rx.tick(cli))

    def test_monitor_rx_procedural_nao_stall(self) -> None:
        """Procedural 30fps: RX subindo na janela = link ok."""
        rx = MonitorRx()
        rx._rx = 770
        rx._tx = 2000
        rx._rx_em = __import__("time").monotonic()
        cli = MagicMock()
        ac = cli.anim_controller
        ac.procedural_face_enabled = True
        ac.animations_enabled = True
        with patch.dict("os.environ", {"COZMO_BASE_OLED_MODE": "anim"}):
            with patch(
                "cozmo_companion.core.conexao.diagnostico",
                return_value={"sent_frames": 2100, "recv_frames": 800},
            ):
                self.assertTrue(rx.tick(cli))

    def test_monitor_rx_ppclip_ping_ok_nao_stall(self) -> None:
        """ppclip na base: TX baixo sem drx na janela — link vivo até ppclip_stall_s."""
        rx = MonitorRx()
        rx._rx = 55_834
        rx._tx = 11_000
        rx._rx_em = __import__("time").monotonic() - 45.0
        cli = MagicMock()
        with patch.dict(
            "os.environ",
            {
                "COZMO_CHARGER_PLAY_STREAM": "0",
                "COZMO_BASE_OLED_ANIM_LOOP": "auto",
                "COZMO_PPCLIP_RX_STALL_S": "120",
            },
        ):
            with patch(
                "cozmo_companion.core.conexao.cozmo_alcanavel",
                return_value=True,
            ):
                with patch(
                    "cozmo_companion.core.motor_cozmo.ppclip_base_ativo",
                    return_value=True,
                ):
                    with patch(
                        "cozmo_companion.core.conexao.diagnostico",
                        return_value={"sent_frames": 11_050, "recv_frames": 55_834},
                    ):
                        self.assertTrue(rx.tick(cli))

    def test_monitor_rx_ppclip_flood_sem_drx_e_stall(self) -> None:
        """ppclip + dtx≈600 na janela interna — stall real (≠ COZMO 01 mascarado)."""
        rx = MonitorRx()
        rx._rx = 924
        rx._tx = 450
        rx._rx_em = __import__("time").monotonic() - 15.0
        cli = MagicMock()
        with patch(
            "cozmo_companion.core.conexao.cozmo_alcanavel",
            return_value=True,
        ):
            with patch(
                "cozmo_companion.core.motor_cozmo.ppclip_base_ativo",
                return_value=True,
            ):
                with patch(
                    "cozmo_companion.core.conexao.diagnostico",
                    return_value={"sent_frames": 1036, "recv_frames": 924},
                ):
                    self.assertFalse(rx.tick(cli))

    def test_monitor_rx_nunca_disconnect_resync(self) -> None:
        os.environ["COZMO_NEVER_DISCONNECT"] = "1"
        rx = MonitorRx()
        rx._rx = 668
        rx._tx = 4000
        rx._rx_em = __import__("time").monotonic() - 60.0
        cli = MagicMock()
        cli.battery_voltage = 4.2
        cli.robot_status = 0x1310
        ac = cli.anim_controller
        ac.procedural_face_enabled = True
        ac.animations_enabled = True
        with patch(
            "cozmo_companion.core.motor_cozmo.ppclip_base_ativo",
            return_value=False,
        ):
            with patch(
                "cozmo_companion.core.conexao.diagnostico",
                return_value={"sent_frames": 4500, "recv_frames": 668},
            ):
                self.assertFalse(rx.tick(cli))
            rx.sincronizar(cli)
            rx._rx = 668
            rx._tx = 4500
            with patch(
                "cozmo_companion.core.conexao.diagnostico",
                return_value={"sent_frames": 4520, "recv_frames": 680},
            ):
                self.assertTrue(rx.tick(cli))
        rx = MonitorRx()
        rx._rx = 1000
        rx._tx = 900
        rx._rx_em = __import__("time").monotonic() - 15.0
        cli = MagicMock()
        ac = cli.anim_controller
        ac.procedural_face_enabled = False
        ac.animations_enabled = False
        with patch(
            "cozmo_companion.core.motor_cozmo.ppclip_base_ativo",
            return_value=False,
        ):
            with patch(
                "cozmo_companion.core.conexao.diagnostico",
                return_value={"sent_frames": 2800, "recv_frames": 1000},
            ):
                self.assertFalse(rx.tick(cli))


if __name__ == "__main__":
    os.environ.setdefault("PYTHONPATH", "src")
    unittest.main()
