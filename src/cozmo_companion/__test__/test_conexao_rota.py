"""Testes — rota Wi-Fi Cozmo e reset COZMO 01."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from cozmo_companion.core.conexao import (
    cozmo_alcanavel,
    cozmo_rota_ap,
    permitir_reset_udp_cozmo01,
    sessao_viva,
)


def test_permitir_reset_cozmo01_default():
    assert permitir_reset_udp_cozmo01() is True


@patch("cozmo_companion.core.conexao.subprocess.run")
def test_rota_ap_sem_gateway(mock_run):
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "172.31.1.1 dev wlp3s0 src 172.31.1.2 uid 1000\n"
    assert cozmo_rota_ap() is True


@patch("cozmo_companion.core.conexao.subprocess.run")
def test_rota_ap_via_casa(mock_run):
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = (
        "172.31.1.1 via 192.168.1.1 dev enp6s0 src 192.168.1.110 uid 1000\n"
    )
    assert cozmo_rota_ap() is False


@patch("cozmo_companion.core.conexao.cozmo_rota_ap", return_value=False)
@patch("cozmo_companion.core.conexao.subprocess.run")
def test_alcanavel_exige_rota(mock_run, _rota):
    mock_run.return_value.returncode = 0
    assert cozmo_alcanavel() is False


def test_sessao_viva_nao_só_bateria():
    cli = MagicMock()
    cli.conn.state = 3
    cli.conn.recv_thread.received_frames = 800
    cli.conn.send_thread.sent_frames = 1200
    cli.battery_voltage = 4.2
    cli.robot_status = 0x1310
    with patch("cozmo_companion.core.conexao.socket_conectado", return_value=True):
        with patch(
            "cozmo_companion.core.conexao.MedidorUdp.amostra",
            return_value=(0, 400, 400.0),
        ):
            assert sessao_viva(cli) is False
