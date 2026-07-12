"""Testes boot — sessão fresca sem reset COZMO 01."""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

from cozmo_companion.core.conexao import sessao_parece_fresca


class TestSessaoBoot(unittest.TestCase):
    def _cli(self, rx: int, tx: int = 50, ok: bool = True) -> MagicMock:
        cli = MagicMock()
        cli.conn.recv_thread.received_frames = rx
        cli.conn.send_thread.sent_frames = tx
        cli.battery_voltage = 4.2
        cli.robot_status = 0x1310
        if not ok:
            cli.battery_voltage = 0.0
            cli.robot_status = 0
        return cli

    def test_fresca_rx_baixo(self) -> None:
        self.assertTrue(sessao_parece_fresca(self._cli(63)))

    def test_stale_rx_alto(self) -> None:
        self.assertFalse(sessao_parece_fresca(self._cli(1500)))

    def test_nao_fresca_sem_conexao(self) -> None:
        self.assertFalse(sessao_parece_fresca(self._cli(63, ok=False)))

    @patch.dict(os.environ, {"COZMO_BOOT_FRESH_SESSION": "0"})
    def test_boot_nao_reconecta_fresca(self) -> None:
        from cozmo_companion.core.companion import Companion

        c = MagicMock(spec=Companion)
        c.cli = self._cli(64)
        c._na_base_efetivo = MagicMock(return_value=True)
        c._monitor_rx = MagicMock()
        c._gov = MagicMock()
        c._reconectar_sessao_udp = MagicMock()
        Companion._sessao_fresca_no_boot(c)
        c._reconectar_sessao_udp.assert_not_called()

    @patch.dict(os.environ, {"COZMO_BOOT_FRESH_SESSION": "1"})
    @patch("cozmo_companion.core.companion.cozmo_alcanavel", return_value=True)
    @patch("cozmo_companion.core.companion.diagnostico", return_value={"recv_frames": 64})
    def test_boot_reset_explicito_limpa_cozmo01(self, _diag, _alc) -> None:
        from cozmo_companion.core.companion import Companion

        c = MagicMock(spec=Companion)
        c.cli = self._cli(64)
        c._monitor_rx = MagicMock()
        c._gov = MagicMock()
        c._reconectar_sessao_udp = MagicMock(return_value=True)
        Companion._sessao_fresca_no_boot(c)
        c._reconectar_sessao_udp.assert_called_once_with(
            silencioso=False, forcado=True, cozmo01=True
        )
