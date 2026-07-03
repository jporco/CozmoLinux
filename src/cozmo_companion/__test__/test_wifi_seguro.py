"""Testes — modo seguro Wi-Fi (Cozmo offline)."""

from __future__ import annotations

from unittest.mock import patch

from cozmo_companion.core.conexao import (
    pode_tentar_wifi,
    reconectar_wifi,
    wifi_modo_seguro,
    wlan0_preso_cozmo,
)


def test_wifi_modo_seguro_default():
    with patch.dict("os.environ", {"COZMO_WIFI_SAFE": "1"}, clear=False):
        assert wifi_modo_seguro() is True


@patch("cozmo_companion.core.conexao.wlan0_preso_cozmo", return_value=False)
@patch("cozmo_companion.core.conexao.cozmo_rota_ap", return_value=True)
@patch("cozmo_companion.core.conexao.cozmo_alcanavel", return_value=False)
@patch("cozmo_companion.core.conexao.cozmo_ssid_visivel", return_value=False)
def test_pode_tentar_wifi_bloqueia_sem_ap(_ssid, _ping, _rota, _preso):
    with patch.dict("os.environ", {"COZMO_WIFI_SAFE": "1"}, clear=False):
        assert pode_tentar_wifi() is False


@patch("cozmo_companion.core.conexao.wlan0_preso_cozmo", return_value=True)
@patch("cozmo_companion.core.conexao.cozmo_rota_ap", return_value=False)
@patch("cozmo_companion.core.conexao.cozmo_alcanavel", return_value=False)
@patch("cozmo_companion.core.conexao.cozmo_ssid_visivel", return_value=False)
@patch("cozmo_companion.core.conexao.time.monotonic", return_value=5000.0)
def test_pode_tentar_wifi_liberado_wlan0_preso(_mono, _ssid, _ping, _rota, _preso):
    with patch.dict(
        "os.environ",
        {"COZMO_WIFI_SAFE": "1", "COZMO_WIFI_ROUTE_RETRY_S": "15"},
        clear=False,
    ):
        assert pode_tentar_wifi() is True


@patch("cozmo_companion.core.conexao.wlan0_preso_cozmo", return_value=False)
@patch("cozmo_companion.core.conexao.cozmo_rota_ap", return_value=False)
@patch("cozmo_companion.core.conexao.cozmo_alcanavel", return_value=False)
@patch("cozmo_companion.core.conexao.time.monotonic", return_value=5000.0)
def test_pode_tentar_wifi_rota_errada(_mono, _ping, _rota, _preso):
    with patch.dict(
        "os.environ",
        {"COZMO_WIFI_SAFE": "1", "COZMO_WIFI_ROUTE_RETRY_S": "15"},
        clear=False,
    ):
        assert pode_tentar_wifi(forcado=True) is True


@patch("cozmo_companion.core.conexao.wlan0_preso_cozmo", return_value=False)
@patch("cozmo_companion.core.conexao.cozmo_rota_ap", return_value=True)
@patch("cozmo_companion.core.conexao.cozmo_alcanavel", return_value=False)
@patch("cozmo_companion.core.conexao.cozmo_ssid_visivel", return_value=True)
@patch("cozmo_companion.core.conexao.time.monotonic", return_value=1000.0)
def test_pode_tentar_wifi_permitido_com_ap(_mono, _ssid, _ping, _rota, _preso):
    with patch.dict(
        "os.environ",
        {"COZMO_WIFI_SAFE": "1", "COZMO_WIFI_COOLDOWN_S": "25"},
        clear=False,
    ):
        assert pode_tentar_wifi() is True


@patch("cozmo_companion.core.conexao.wlan0_preso_cozmo", return_value=False)
@patch("cozmo_companion.core.conexao.cozmo_rota_ap", return_value=True)
@patch("cozmo_companion.core.conexao.cozmo_alcanavel", return_value=False)
@patch("cozmo_companion.core.conexao.cozmo_ssid_visivel", return_value=False)
@patch("cozmo_companion.core.conexao.subprocess.run")
def test_reconectar_wifi_offline_nao_executa_script(mock_run, _ssid, _ping, _rota, _preso):
    with patch.dict("os.environ", {"COZMO_WIFI_SAFE": "1"}, clear=False):
        assert reconectar_wifi() is False
        mock_run.assert_not_called()


@patch("cozmo_companion.core.conexao.subprocess.run")
def test_wlan0_connecting_nao_e_preso(mock_run):
    """Handshake em progresso NUNCA é 'preso' — derrubar aqui mata a conexão."""
    import cozmo_companion.core.conexao as conexao

    conexao._wlan0_preso_desde = 0.0
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = (
        "GENERAL.STATE:50 (connecting (configuring))\n"
        "GENERAL.CONNECTION:Cozmo_31CE41\n"
    )
    with patch("cozmo_companion.core.conexao.cozmo_rota_ap", return_value=False):
        with patch("cozmo_companion.core.conexao.cozmo_alcanavel", return_value=False):
            assert wlan0_preso_cozmo() is False


@patch("cozmo_companion.core.conexao.subprocess.run")
def test_wlan0_preso_so_apos_carencia(mock_run):
    """Conectado a Cozmo_* sem rota: só vira 'preso' após carência contínua."""
    import cozmo_companion.core.conexao as conexao

    conexao._wlan0_preso_desde = 0.0
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = (
        "GENERAL.STATE:100 (connected)\n"
        "GENERAL.CONNECTION:Cozmo_31CE41\n"
    )
    with patch("cozmo_companion.core.conexao.cozmo_rota_ap", return_value=False):
        with patch("cozmo_companion.core.conexao.cozmo_alcanavel", return_value=False):
            with patch.dict("os.environ", {"COZMO_WLAN0_PRESO_GRACA_S": "15"}, clear=False):
                with patch("cozmo_companion.core.conexao.time.monotonic", return_value=1000.0):
                    assert wlan0_preso_cozmo() is False  # arma o contador
                with patch("cozmo_companion.core.conexao.time.monotonic", return_value=1020.0):
                    assert wlan0_preso_cozmo() is True  # 20s > carência
