"""Testes — recuperador COZMO 01 unificado."""

from __future__ import annotations

import os
import time
import unittest
from unittest.mock import MagicMock, patch

from cozmo_companion.core.cozmo01_recovery import RecuperadorCozmo01
from cozmo_companion.core.governador import FaseLink, TickGovernador


def _tick(*, rx_ok: bool = True) -> TickGovernador:
    return TickGovernador(
        fase=FaseLink.VERDE if rx_ok else FaseLink.VERMELHO,
        reduzir_trafego=False,
        abortar_flood=False,
        rx_ok=rx_ok,
        wifi_ok=True,
        pedir_wifi=False,
        pedir_recuperar=not rx_ok,
        ratio=0.0,
        ratio_ema=0.0,
    )


class TestRecuperadorCozmo01(unittest.TestCase):
    def setUp(self) -> None:
        self._env = patch.dict(os.environ, {"COZMO_BASE_STABLE_OLED": "0"})
        self._env.start()

    def tearDown(self) -> None:
        self._env.stop()

    def test_stall_só_zera_com_drx(self) -> None:
        rec = RecuperadorCozmo01()
        cli = MagicMock()
        med = MagicMock()
        med.amostra.return_value = (0, 50, 0.0)
        g = _tick(rx_ok=True)
        rec.atualizar_stall(cli, g, med, busy=False, quieto=False)
        self.assertEqual(rec.stall_consecutivo, 0)

        med.amostra.return_value = (0, 300, 0.0)
        g2 = _tick(rx_ok=True)
        rec.atualizar_stall(cli, g2, med, busy=False, quieto=False)
        self.assertGreater(rec.stall_consecutivo, 0)

    @patch("cozmo_companion.core.cozmo01_recovery.cozmo_alcanavel", return_value=True)
    @patch("cozmo_companion.core.cozmo01_recovery.cozmo_rota_ap", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.rx_morto_s", return_value=30.0)
    @patch("cozmo_companion.core.motor_cozmo.rx_link_ok", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.detectar_cozmo01_suspeito", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.recuperar_cozmo01_auto", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.cortar_flood_udp_base")
    def test_reset_emergencia_1_falha(self, *_mocks) -> None:
        rec = RecuperadorCozmo01()
        rec.cozmo01_falhas = 1
        cli = MagicMock()
        monitor = MagicMock()
        med = MagicMock()
        med.amostra.return_value = (0, 400, 0.0)
        g = _tick(rx_ok=False)
        with patch(
            "cozmo_companion.core.motor_cozmo.oled_charger_vivo",
            return_value=False,
        ):
            with patch(
                "cozmo_companion.core.motor_cozmo.oled_frame_recente",
                return_value=False,
            ):
                with patch.dict(
                    os.environ,
                    {"COZMO01_RESET_FAILS": "1", "COZMO01_EMERG_COOLDOWN_S": "5"},
                ):
                    r = rec.tick_base(
                        cli,
                        g,
                        monitor,
                        med,
                        busy=False,
                        quieto=False,
                        na_base=True,
                        ultimo_reconnect_udp=0.0,
                        reconnect_udp=lambda: True,
                        recuperar_inplace=lambda: True,
                    )
        self.assertTrue(r.reset_udp)

    @patch("cozmo_companion.core.cozmo01_recovery.cozmo_alcanavel", return_value=True)
    @patch("cozmo_companion.core.motor_cozmo.recuperar_cozmo01_auto", return_value=True)
    @patch("cozmo_companion.core.motor_cozmo.ping_sessao_base")
    @patch("cozmo_companion.core.motor_cozmo.pulso_sync_base")
    @patch("cozmo_companion.core.motor_cozmo.cortar_flood_udp_base")
    def test_preventiva_drx_zero(self, _cortar, _pulso, _ping, _rec, _alc) -> None:
        rec = RecuperadorCozmo01()
        cli = MagicMock()
        monitor = MagicMock()
        med = MagicMock()
        med.amostra.return_value = (0, 200, 0.0)
        g = _tick(rx_ok=True)
        r = rec.tick_base(
            cli,
            g,
            monitor,
            med,
            busy=False,
            quieto=False,
            na_base=True,
            ultimo_reconnect_udp=0.0,
            reconnect_udp=lambda: False,
            recuperar_inplace=lambda: False,
        )
        self.assertTrue(r.in_place)
        _rec.assert_called()

    @patch("cozmo_companion.core.cozmo01_recovery.cozmo_alcanavel", return_value=True)
    @patch("cozmo_companion.core.cozmo01_recovery.cozmo_rota_ap", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.rx_morto_s", return_value=30.0)
    @patch("cozmo_companion.core.motor_cozmo.rx_link_ok", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.detectar_cozmo01_suspeito", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.cortar_flood_udp_base")
    def test_reset_apos_falhas(self, *_mocks) -> None:
        rec = RecuperadorCozmo01()
        rec.cozmo01_falhas = 3
        cli = MagicMock()
        monitor = MagicMock()
        med = MagicMock()
        med.amostra.return_value = (0, 400, 0.0)
        g = _tick(rx_ok=False)
        with patch(
            "cozmo_companion.core.motor_cozmo.oled_charger_vivo",
            return_value=False,
        ):
            with patch(
                "cozmo_companion.core.motor_cozmo.oled_frame_recente",
                return_value=False,
            ):
                with patch.dict(os.environ, {"COZMO01_RESET_FAILS": "3"}):
                    r = rec.tick_base(
                        cli,
                        g,
                        monitor,
                        med,
                        busy=False,
                        quieto=False,
                        na_base=True,
                        ultimo_reconnect_udp=0.0,
                        reconnect_udp=lambda: True,
                        recuperar_inplace=lambda: True,
                    )
        self.assertTrue(r.reset_udp)
        self.assertEqual(rec.cozmo01_falhas, 0)

    @patch("cozmo_companion.core.cozmo01_recovery.cozmo_alcanavel", return_value=True)
    @patch("cozmo_companion.core.cozmo01_recovery.cozmo_rota_ap", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.rx_morto_s", return_value=30.0)
    @patch("cozmo_companion.core.motor_cozmo.rx_link_ok", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.detectar_cozmo01_suspeito", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.recuperar_cozmo01_auto", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.oled_charger_vivo", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.oled_frame_recente", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.cortar_flood_udp_base")
    def test_modo_estavel_bloqueia_reset_udp(self, *_mocks) -> None:
        rec = RecuperadorCozmo01()
        rec.cozmo01_falhas = 3
        cli = MagicMock()
        monitor = MagicMock()
        med = MagicMock()
        med.amostra.return_value = (0, 400, 0.0)
        g = _tick(rx_ok=False)
        reconnect = MagicMock(return_value=True)
        with patch.dict(
            os.environ,
            {
                "COZMO_BASE_STABLE_OLED": "1",
                "COZMO_BASE_STABLE_ALLOW_RESET": "0",
                "COZMO01_RESET_FAILS": "1",
            },
        ):
            r = rec.tick_base(
                cli,
                g,
                monitor,
                med,
                busy=False,
                quieto=False,
                na_base=True,
                ultimo_reconnect_udp=0.0,
                reconnect_udp=reconnect,
                recuperar_inplace=lambda: True,
            )
        self.assertFalse(r.reset_udp)
        reconnect.assert_not_called()

    @patch("cozmo_companion.core.cozmo01_recovery.cozmo_alcanavel", return_value=True)
    @patch("cozmo_companion.core.motor_cozmo.rx_link_ok", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.detectar_cozmo01_suspeito", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.recuperar_cozmo01_auto", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.cortar_flood_udp_base")
    def test_rx_stall_nao_usa_inplace(self, _cortar, _rec, _det, _rx, _alc) -> None:
        rec = RecuperadorCozmo01()
        cli = MagicMock()
        monitor = MagicMock()
        med = MagicMock()
        med.amostra.return_value = (0, 400, 0.0)
        g = _tick(rx_ok=False)
        inplace = MagicMock(return_value=True)
        with patch(
            "cozmo_companion.core.motor_cozmo.oled_charger_vivo",
            return_value=False,
        ):
            with patch(
                "cozmo_companion.core.motor_cozmo.oled_frame_recente",
                return_value=False,
            ):
                with patch.dict(os.environ, {"COZMO01_EMERG_COOLDOWN_S": "999"}):
                    r = rec.tick_base(
                        cli,
                        g,
                        monitor,
                        med,
                        busy=False,
                        quieto=False,
                        na_base=True,
                        ultimo_reconnect_udp=time.monotonic(),
                        reconnect_udp=lambda: False,
                        recuperar_inplace=inplace,
                    )
        self.assertFalse(r.in_place)
        inplace.assert_not_called()

    @patch("cozmo_companion.core.cozmo01_recovery.cozmo_alcanavel", return_value=True)
    @patch("cozmo_companion.core.cozmo01_recovery.cozmo_rota_ap", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.rx_morto_s", return_value=30.0)
    @patch("cozmo_companion.core.motor_cozmo.oled_charger_vivo", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.rx_link_ok", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.detectar_cozmo01_suspeito", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.recuperar_cozmo01_auto", return_value=True)
    @patch("cozmo_companion.core.motor_cozmo.cortar_flood_udp_base")
    @patch("cozmo_companion.core.motor_cozmo.ping_sessao_base")
    @patch("cozmo_companion.core.motor_cozmo.pulso_sync_base")
    def test_failsafe_rx_morto_forca_reset(self, *_mocks) -> None:
        """RX morto contínuo > teto força reset mesmo com preventiva 'OK' e busy."""
        rec = RecuperadorCozmo01()
        cli = MagicMock()
        monitor = MagicMock()
        med = MagicMock()
        med.amostra.return_value = (0, 400, 0.0)
        g = _tick(rx_ok=False)
        with patch(
            "cozmo_companion.core.motor_cozmo.oled_frame_recente",
            return_value=False,
        ):
            with patch.dict(
                os.environ,
                {"COZMO01_RX_DEAD_MAX_S": "12", "COZMO01_EMERG_COOLDOWN_S": "3"},
            ):
                r = rec.tick_base(
                    cli,
                    g,
                    monitor,
                    med,
                    busy=True,
                    quieto=False,
                    na_base=True,
                    ultimo_reconnect_udp=0.0,
                    reconnect_udp=lambda: True,
                    recuperar_inplace=lambda: True,
                )
        self.assertTrue(r.reset_udp)
        self.assertEqual(rec.cozmo01_falhas, 0)

    @patch("cozmo_companion.core.cozmo01_recovery.cozmo_alcanavel", return_value=True)
    @patch("cozmo_companion.core.cozmo01_recovery.cozmo_rota_ap", return_value=True)
    @patch("cozmo_companion.core.motor_cozmo.rx_morto_s", return_value=30.0)
    @patch("cozmo_companion.core.motor_cozmo.oled_charger_vivo", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.oled_frame_recente", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.rx_link_ok", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.detectar_cozmo01_suspeito", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.recuperar_cozmo01_auto", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.cortar_flood_udp_base")
    @patch("cozmo_companion.core.motor_cozmo.ping_sessao_base")
    @patch("cozmo_companion.core.motor_cozmo.pulso_sync_base")
    def test_rota_ap_viva_adia_reset_rx_morto(self, *_mocks) -> None:
        rec = RecuperadorCozmo01()
        rec.cozmo01_falhas = 3
        rec.stall_consecutivo = 3
        cli = MagicMock()
        monitor = MagicMock()
        med = MagicMock()
        med.amostra.return_value = (0, 500, 0.0)
        g = _tick(rx_ok=False)
        reconnect = MagicMock(return_value=True)
        with patch.dict(
            os.environ,
            {
                "COZMO01_RX_DEAD_MAX_S": "12",
                "COZMO01_RX_DEAD_ROUTE_S": "90",
                "COZMO01_RESET_FAILS": "3",
                "COZMO01_RESET_STALL_TICKS": "2",
                "COZMO01_EMERG_COOLDOWN_S": "0",
            },
        ):
            r = rec.tick_base(
                cli,
                g,
                monitor,
                med,
                busy=False,
                quieto=False,
                na_base=True,
                ultimo_reconnect_udp=0.0,
                reconnect_udp=reconnect,
                recuperar_inplace=lambda: True,
            )
        self.assertFalse(r.reset_udp)
        reconnect.assert_not_called()

    @patch("cozmo_companion.core.cozmo01_recovery.cozmo_alcanavel", return_value=True)
    @patch("cozmo_companion.core.motor_cozmo.rx_morto_s", return_value=30.0)
    @patch("cozmo_companion.core.motor_cozmo.oled_charger_vivo", return_value=True)
    @patch("cozmo_companion.core.motor_cozmo.rx_link_ok", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.detectar_cozmo01_suspeito", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.recuperar_cozmo01_auto", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.cortar_flood_udp_base")
    @patch("cozmo_companion.core.motor_cozmo.ping_sessao_base")
    @patch("cozmo_companion.core.motor_cozmo.pulso_sync_base")
    def test_keeper_vivo_nao_segura_reset_com_tx_alto(self, *_mocks) -> None:
        rec = RecuperadorCozmo01()
        cli = MagicMock()
        monitor = MagicMock()
        med = MagicMock()
        med.amostra.return_value = (0, 400, 0.0)
        g = _tick(rx_ok=False)
        with patch.dict(
            os.environ,
            {"COZMO01_RX_DEAD_MAX_S": "12", "COZMO01_KEEPER_RX_DEAD_MAX_S": "180"},
        ):
            r = rec.tick_base(
                cli,
                g,
                monitor,
                med,
                busy=False,
                quieto=False,
                na_base=True,
                ultimo_reconnect_udp=0.0,
                reconnect_udp=lambda: True,
                recuperar_inplace=lambda: True,
            )
        self.assertTrue(r.reset_udp)
        self.assertFalse(r.in_place)

    @patch("cozmo_companion.core.cozmo01_recovery.cozmo_alcanavel", return_value=True)
    @patch("cozmo_companion.core.motor_cozmo.rx_morto_s", return_value=30.0)
    @patch("cozmo_companion.core.motor_cozmo.oled_frame_recente", return_value=True)
    @patch("cozmo_companion.core.motor_cozmo.oled_charger_vivo", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.rx_link_ok", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.detectar_cozmo01_suspeito", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.recuperar_cozmo01_auto", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.cortar_flood_udp_base")
    @patch("cozmo_companion.core.motor_cozmo.ping_sessao_base")
    @patch("cozmo_companion.core.motor_cozmo.pulso_sync_base")
    def test_frame_oled_recente_nao_segura_reset_com_tx_alto(self, *_mocks) -> None:
        rec = RecuperadorCozmo01()
        cli = MagicMock()
        monitor = MagicMock()
        med = MagicMock()
        med.amostra.return_value = (0, 400, 0.0)
        g = _tick(rx_ok=False)
        reconnect = MagicMock(return_value=True)
        with patch.dict(
            os.environ,
            {"COZMO01_RX_DEAD_MAX_S": "12", "COZMO01_KEEPER_RX_DEAD_MAX_S": "180"},
        ):
            r = rec.tick_base(
                cli,
                g,
                monitor,
                med,
                busy=False,
                quieto=False,
                na_base=True,
                ultimo_reconnect_udp=0.0,
                reconnect_udp=reconnect,
                recuperar_inplace=lambda: True,
            )
        self.assertTrue(r.reset_udp)
        self.assertFalse(r.in_place)
        reconnect.assert_called_once()

    @patch("cozmo_companion.core.cozmo01_recovery.cozmo_alcanavel", return_value=True)
    @patch("cozmo_companion.core.motor_cozmo.rx_morto_s", return_value=3.0)
    @patch("cozmo_companion.core.motor_cozmo.oled_frame_recente", return_value=True)
    @patch("cozmo_companion.core.motor_cozmo.oled_charger_vivo", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.rx_link_ok", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.detectar_cozmo01_suspeito", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.recuperar_cozmo01_auto", return_value=False)
    @patch("cozmo_companion.core.motor_cozmo.cortar_flood_udp_base")
    @patch("cozmo_companion.core.motor_cozmo.ping_sessao_base")
    @patch("cozmo_companion.core.motor_cozmo.pulso_sync_base")
    def test_frame_oled_recente_segura_apenas_com_tx_baixo(self, *_mocks) -> None:
        rec = RecuperadorCozmo01()
        cli = MagicMock()
        monitor = MagicMock()
        med = MagicMock()
        med.amostra.return_value = (0, 80, 0.0)
        g = _tick(rx_ok=False)
        reconnect = MagicMock(return_value=True)
        with patch.dict(
            os.environ,
            {"COZMO01_RX_DEAD_MAX_S": "12", "COZMO01_KEEPER_RX_DEAD_MAX_S": "180"},
        ):
            r = rec.tick_base(
                cli,
                g,
                monitor,
                med,
                busy=False,
                quieto=False,
                na_base=True,
                ultimo_reconnect_udp=0.0,
                reconnect_udp=reconnect,
                recuperar_inplace=lambda: True,
            )
        self.assertFalse(r.reset_udp)
        self.assertTrue(r.in_place)
        reconnect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
