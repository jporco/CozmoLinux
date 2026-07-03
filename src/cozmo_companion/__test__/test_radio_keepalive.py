"""Testes — keepalive de rádio Wi-Fi (mantém link quente, evita rajada/COZMO 01)."""

from __future__ import annotations

import socket
import time

from unittest.mock import patch

from cozmo_companion.core import radio_keepalive as rk


def test_keepalive_desativado_por_env():
    with patch.dict("os.environ", {"COZMO_RADIO_KEEPALIVE": "0"}, clear=False):
        assert rk.keepalive_ativo() is False
        assert rk.iniciar_keepalive_radio() is False


def test_keepalive_envia_pacotes_e_para():
    enviados: list[tuple[bytes, tuple[str, int]]] = []

    class FakeSock:
        def setblocking(self, _flag):
            pass

        def sendto(self, data, addr):
            enviados.append((data, addr))

        def close(self):
            pass

    with patch.dict(
        "os.environ",
        {
            "COZMO_RADIO_KEEPALIVE": "1",
            "COZMO_RADIO_KEEPALIVE_HZ": "100",
            "COZMO_RADIO_KEEPALIVE_PORT": "55001",
            "COZMO_IP": "172.31.1.1",
        },
        clear=False,
    ):
        with patch.object(socket, "socket", return_value=FakeSock()):
            assert rk.iniciar_keepalive_radio() is True
            # idempotente: segunda chamada não cria outra thread
            assert rk.iniciar_keepalive_radio() is True
            time.sleep(0.1)
            rk.parar_keepalive_radio()

    assert len(enviados) > 0
    assert enviados[0][0] == b"\x00"
    assert enviados[0][1] == ("172.31.1.1", 55001)


def test_parar_keepalive_sem_iniciar_nao_quebra():
    rk.parar_keepalive_radio()
