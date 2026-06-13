"""Testes do governador UDP/Wi-Fi."""

import os
import time
import unittest
from unittest.mock import MagicMock, patch

from cozmo_companion.core.governador import FaseLink, GovernadorCozmo
from cozmo_companion.core.conexao import MonitorRx


class TestGovernador(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["GOV_RATIO_PREVENCAO"] = "1.1"
        os.environ["COZMO_UDP_RATIO_LEVE"] = "1.35"
        os.environ["COZMO_UDP_RATIO_MAX"] = "1.75"

    def test_reservar_consome_budget(self) -> None:
        g = GovernadorCozmo()
        g._tokens = 10.0
        self.assertTrue(g.reservar("anim"))
        self.assertLess(g._tokens, 10.0)

    def test_reservar_bloqueia_sem_budget(self) -> None:
        g = GovernadorCozmo()
        g._fase = FaseLink.VERMELHO
        g._tokens = 0.0
        self.assertFalse(g.reservar("anim"))
        self.assertTrue(g.reservar("oled", prioridade=True) or g.pode("oled"))

    def test_quieto_nao_bloqueia_anim(self) -> None:
        g = GovernadorCozmo()
        g.marcar_quieto(30.0)
        self.assertFalse(g.reduzir_trafego())
        self.assertTrue(g.pode("anim", prioridade=True))
        self.assertFalse(g.pode("espirito"))

    @patch("cozmo_companion.core.governador.cozmo_alcanavel", return_value=True)
    @patch("cozmo_companion.core.governador.conexao_ok", return_value=True)
    @patch("cozmo_companion.core.governador.ratio_udp", return_value=2.0)
    def test_tick_vermelho_saturado(self, _ratio, _ok, _ping) -> None:
        g = GovernadorCozmo()
        rx = MonitorRx()
        cli = MagicMock()
        with patch.object(g._medidor, "amostra", return_value=(0, 400, 0.0)):
            with patch.object(rx, "tick", return_value=False):
                t = g.tick(cli, monitor_rx=rx, busy=False, quieto=False)
        self.assertEqual(t.fase, FaseLink.VERMELHO)
        self.assertTrue(t.abortar_flood)

    @patch("cozmo_companion.core.governador.cozmo_alcanavel", return_value=True)
    @patch("cozmo_companion.core.governador.cozmo_rota_ap", return_value=True)
    @patch("cozmo_companion.core.governador.conexao_ok", return_value=True)
    @patch("cozmo_companion.core.governador.ratio_udp", return_value=1.0)
    def test_tick_verde(self, _ratio, _ok, _rota, _ping) -> None:
        g = GovernadorCozmo()
        rx = MonitorRx()
        cli = MagicMock()
        with patch.object(g._medidor, "amostra", return_value=(40, 120, 1.0)):
            with patch.object(rx, "tick", return_value=True):
                t = g.tick(cli, monitor_rx=rx, busy=False, quieto=False)
        self.assertEqual(t.fase, FaseLink.VERDE)
        self.assertFalse(t.reduzir_trafego)

    @patch("cozmo_companion.core.governador.cozmo_alcanavel", return_value=True)
    @patch("cozmo_companion.core.governador.conexao_ok", return_value=True)
    @patch("cozmo_companion.core.governador.ratio_udp", return_value=0.2)
    @patch("cozmo_companion.core.governador.diagnostico")
    def test_idle_nao_recupera(
        self,
        diag_mock,
        _ratio,
        _ok,
        _ping,
    ) -> None:
        g = GovernadorCozmo()
        rx = MonitorRx()
        rx._rx = 50_000
        rx._tx = 10_000
        rx._rx_em = time.monotonic()
        diag_mock.return_value = {
            "recv_frames": 50_000,
            "sent_frames": 10_020,
            "estado": "CONNECTED",
            "ping_wifi": True,
            "bateria_v": 4.2,
            "status": "0x1310",
            "discarded": 0,
        }
        cli = MagicMock()
        with patch.object(g._medidor, "amostra", return_value=(5, 20, 4.0)):
            with patch.object(rx, "tick", return_value=True):
                t = g.tick(cli, monitor_rx=rx, busy=False, quieto=False)
        self.assertFalse(t.pedir_recuperar)

    @patch("cozmo_companion.core.governador.cozmo_alcanavel", return_value=True)
    @patch("cozmo_companion.core.governador.conexao_ok", return_value=True)
    @patch("cozmo_companion.core.governador.ratio_udp", return_value=0.34)
    @patch("cozmo_companion.core.governador.diagnostico")
    def test_tx_sobe_rx_parado_recupera(self, diag_mock, _r, _ok, _ping) -> None:
        g = GovernadorCozmo()
        rx = MonitorRx()
        rx._rx = 55_834
        rx._tx = 11_000
        rx._rx_em = time.monotonic() - 30.0
        diag_mock.return_value = {
            "recv_frames": 55_834,
            "sent_frames": 18_821,
            "estado": "CONNECTED",
            "ping_wifi": True,
            "bateria_v": 4.0,
            "status": "0x318",
            "discarded": 0,
        }
        cli = MagicMock()
        with patch.object(g._medidor, "amostra", return_value=(0, 500, 0.0)):
            with patch.object(rx, "tick", return_value=False):
                t = g.tick(cli, monitor_rx=rx, busy=False, quieto=False)
        self.assertTrue(t.pedir_recuperar)

    @patch("cozmo_companion.core.governador.cozmo_alcanavel", return_value=True)
    @patch("cozmo_companion.core.governador.cozmo_rota_ap", return_value=True)
    @patch("cozmo_companion.core.governador.conexao_ok", return_value=True)
    @patch("cozmo_companion.core.governador.ratio_udp", return_value=0.34)
    def test_procedural_rx_ok_nao_vermelho(self, _r, _ok, _rota, _ping) -> None:
        g = GovernadorCozmo()
        rx = MonitorRx()
        cli = MagicMock()
        with patch.object(g._medidor, "amostra", return_value=(0, 120, 0.0)):
            with patch.object(rx, "tick", return_value=True):
                t = g.tick(cli, monitor_rx=rx, busy=False, quieto=False)
        self.assertNotEqual(t.fase, FaseLink.VERMELHO)
        self.assertTrue(t.rx_ok)


class TestMonitorRxBasePing(unittest.TestCase):
    @patch("cozmo_companion.core.conexao.cozmo_alcanavel", return_value=True)
    @patch("cozmo_companion.core.conexao.diagnostico")
    def test_tx_alto_sem_rx_e_stall(self, diag_mock, _ping) -> None:
        """Flood UDP sem drx não pode mascarar COZMO 01 como rx OK."""
        rx = MonitorRx()
        rx._rx = 50_000
        rx._tx = 10_000
        rx._rx_em = time.monotonic() - 200.0
        diag_mock.return_value = {
            "recv_frames": 50_000,
            "sent_frames": 18_000,
        }
        cli = MagicMock()
        self.assertFalse(rx.tick(cli))

    @patch("cozmo_companion.core.conexao.cozmo_alcanavel", return_value=True)
    @patch("cozmo_companion.core.conexao.diagnostico")
    def test_pausa_carinho_nao_mascara_flood(self, diag_mock, _ping) -> None:
        """Pausa RX (carinho) não pode esconder flood sem ACK."""
        rx = MonitorRx()
        rx.pausar(60.0)
        rx._rx = 50_000
        rx._tx = 10_000
        rx._rx_em = time.monotonic() - 12.0
        diag_mock.return_value = {
            "recv_frames": 50_000,
            "sent_frames": 10_400,
        }
        cli = MagicMock()
        self.assertFalse(rx.tick(cli))


if __name__ == "__main__":
    unittest.main()
