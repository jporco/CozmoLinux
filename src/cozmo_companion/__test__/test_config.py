from cozmo_companion.core.config import network_tuning


def test_network_tuning_defaults_unicos(monkeypatch) -> None:
    for nome in (
        "COZMO_WIFI_OFFLINE_RETRY_S",
        "COZMO_BASE_TX_STALL",
        "COZMO_UDP_DELTA_TX_SAT",
        "COZMO_PROC_RX_STALL_S",
        "COZMO_RX_STALL_PARADO_S",
    ):
        monkeypatch.delenv(nome, raising=False)
    cfg = network_tuning()
    assert cfg.wifi_offline_retry_s == 20
    assert cfg.base_tx_stall == 280
    assert cfg.udp_delta_tx_sat == 500
    assert cfg.proc_rx_stall_s == 120
    assert cfg.rx_stall_parado_s == 18


def test_network_tuning_respeita_env(monkeypatch) -> None:
    monkeypatch.setenv("COZMO_BASE_TX_STALL", "333")
    assert network_tuning().base_tx_stall == 333
