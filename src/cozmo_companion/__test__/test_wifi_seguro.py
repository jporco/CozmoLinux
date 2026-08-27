"""Testes — modo seguro Wi-Fi (Cozmo offline)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from cozmo_companion.core.conexao import (
    aguardar_cozmo_online,
    cozmo_ssid_visivel,
    pode_tentar_wifi,
    reconectar_wifi,
    wifi_modo_seguro,
    wlan0_preso_cozmo,
)


def test_monitor_rx_nao_mantem_sessao_morta_por_ratio_historico():
    """Sem RX e sem ARP/ping, ratio acumulado baixo não mantém OLED enviando."""
    from cozmo_companion.core.conexao import MonitorRx

    monitor = MonitorRx()
    monitor._rx = 100
    monitor._tx = 100
    monitor._rx_em = 100.0
    cli = MagicMock()
    dados = {
        "recv_frames": 100,
        "sent_frames": 110,
        "bateria_v": 4.2,
        "status": "0x1",
    }
    with (
        patch("cozmo_companion.core.conexao.diagnostico", return_value=dados),
        patch("cozmo_companion.core.conexao.cozmo_alcanavel", return_value=False),
        patch("cozmo_companion.core.conexao.procedural_ativo", return_value=False),
        patch("cozmo_companion.core.conexao.time.monotonic", return_value=130.0),
        patch.dict("os.environ", {"COZMO_RX_HARD_DEAD_S": "20"}, clear=False),
    ):
        assert monitor.tick(cli) is False


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


@patch("cozmo_companion.core.conexao.liberar_wlan0_cozmo")
@patch("cozmo_companion.core.conexao.subprocess.run")
@patch("cozmo_companion.core.conexao.pode_tentar_wifi", return_value=True)
@patch("cozmo_companion.core.conexao.wlan0_preso_cozmo", return_value=True)
@patch("cozmo_companion.core.conexao.cozmo_rota_ap", return_value=False)
@patch("cozmo_companion.core.conexao.cozmo_alcanavel", return_value=False)
def test_reconectar_wifi_preso_nao_desconecta_interface(
    _ping, _rota, _preso, _pode, run, liberar
):
    """Recuperação não pode emitir `nmcli dev disconnect` no rádio do Cozmo."""
    run.return_value.returncode = 2
    run.return_value.stdout = ""
    run.return_value.stderr = ""

    assert reconectar_wifi() is False
    liberar.assert_not_called()


@patch("cozmo_companion.core.conexao.time.sleep")
@patch("cozmo_companion.core.conexao.time.monotonic", return_value=1000.0)
@patch("cozmo_companion.core.conexao.reconectar_wifi", return_value=True)
@patch("cozmo_companion.core.conexao.pode_tentar_wifi", return_value=True)
@patch("cozmo_companion.core.conexao.wlan0_preso_cozmo", return_value=False)
@patch("cozmo_companion.core.conexao.cozmo_ssid_visivel", return_value=True)
@patch("cozmo_companion.core.conexao.cozmo_alcanavel", side_effect=[False, True])
def test_ap_detectado_reconecta_sem_esperar_backoff(
    _ping,
    ssid,
    _preso,
    pode,
    reconectar,
    _mono,
    _sleep,
):
    assert aguardar_cozmo_online(120) is True
    ssid.assert_called_once_with(rescan=True)
    pode.assert_called_once_with(forcado=False)
    reconectar.assert_called_once_with(forcado=False)


@patch("cozmo_companion.core.conexao.cozmo_rota_ap", return_value=False)
@patch("cozmo_companion.core.conexao.subprocess.run")
def test_scan_offline_respeita_intervalo_proprio(mock_run, _rota):
    import cozmo_companion.core.conexao as conexao

    anterior = conexao._ultimo_rescan_wifi
    conexao._ultimo_rescan_wifi = 50.0
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = ""
    try:
        with patch("cozmo_companion.core.conexao.time.monotonic", return_value=100.0):
            with patch.dict(
                "os.environ",
                {
                    "COZMO_WIFI_RESCAN_S": "10",
                    "COZMO_WIFI_RESCAN_OFFLINE_S": "60",
                },
                clear=False,
            ):
                assert cozmo_ssid_visivel(rescan=True) is False
    finally:
        conexao._ultimo_rescan_wifi = anterior

    assert mock_run.call_count == 1
    assert mock_run.call_args.args[0] == ["nmcli", "-t", "-f", "SSID,SIGNAL", "dev", "wifi", "list"]


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
