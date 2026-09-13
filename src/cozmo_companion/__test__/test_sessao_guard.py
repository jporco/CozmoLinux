"""Testes — proteções de sessão UDP."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from cozmo_companion.core.conexao import MedidorUdp, MonitorRx, precisa_reconectar_udp
from cozmo_companion.core.sessao_guard import GuardSessao


def test_precisa_reconectar_nunca_com_rx_ok():
    medidor = MedidorUdp(janela_s=30)
    monitor = MonitorRx()
    cli = MagicMock()
    cli.conn.recv_thread.received_frames = 500
    cli.conn.send_thread.sent_frames = 900
    assert precisa_reconectar_udp(cli, monitor, medidor, rx_ok=True) is False


def test_precisa_reconectar_com_rx_parado(monkeypatch):
    monkeypatch.setenv("COZMO_NEVER_DISCONNECT", "0")
    medidor = MedidorUdp(janela_s=30)
    monitor = MonitorRx()
    cli = MagicMock()
    cli.anim_controller.procedural_face_enabled = False
    cli.anim_controller.animations_enabled = False
    cli.conn.recv_thread.received_frames = 500
    cli.conn.send_thread.sent_frames = 1100
    medidor.amostra(cli)
    time.sleep(0.01)
    cli.conn.send_thread.sent_frames = 1700
    assert precisa_reconectar_udp(cli, monitor, medidor, rx_ok=False) is True


def test_guard_sessao_cooldown():
    g = GuardSessao()
    assert g.tentar_reconectar() is True
    g.liberar(sucesso=True)
    assert g.tentar_reconectar() is False


def test_guard_sessao_forcado_ignora_cooldown():
    g = GuardSessao()
    assert g.tentar_reconectar() is True
    g.liberar(sucesso=True)
    assert g.tentar_reconectar(forcar=True) is True


def test_guard_circuito_abre_apos_falhas(monkeypatch):
    monkeypatch.setenv("COZMO_RECONNECT_MAX_FAIL", "2")
    monkeypatch.setenv("COZMO_RECONNECT_CIRCUIT_S", "1")
    monkeypatch.setenv("COZMO_RATIO_PREVENT_COOLDOWN_S", "0")
    g = GuardSessao()
    assert g.tentar_reconectar()
    g.liberar(sucesso=False)
    assert g.tentar_reconectar()
    g.liberar(sucesso=False)
    assert g.circuito_aberto()
