"""Testes do guardian — saúde e política."""

from __future__ import annotations

import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from cozmo_companion.guardian.core.health import SessaoLog, Saude, ler_log, sessao_morta
from cozmo_companion.guardian.core.policy import AcaoGuardian, EstadoGuardian, decidir


def _ts(offset_s: float = 0) -> str:
    return datetime.fromtimestamp(time.time() + offset_s).strftime("%Y-%m-%d %H:%M:%S")


class TestHealth(unittest.TestCase):
    def test_servico_ativo_detecta_lock_manual(self) -> None:
        from cozmo_companion.guardian.core.health import servico_ativo

        with patch(
            "cozmo_companion.guardian.core.health.servico_systemd_ativo",
            return_value=False,
        ):
            with patch(
                "cozmo_companion.guardian.core.health.companion_via_lock",
                return_value=True,
            ):
                self.assertTrue(servico_ativo())

    def test_parse_sessao(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "log"
            log.write_text(
                f"{_ts(-30)},338 cozmo.conexao INFO "
                "Sessão Cozmo: estado=CONNECTED ping=OK 4.24V status=0x3310 "
                "udp rx=719 tx=770 desc=0 ratio=1.1\n"
                f"{_ts(-5)},903 cozmo.companion ERROR "
                "Robô sem resposta UDP (6/6) — COZMO 01 provável\n",
                encoding="utf-8",
            )
            with patch("cozmo_companion.guardian.core.health.servico_ativo", return_value=True):
                with patch("cozmo_companion.guardian.core.health.ping_robo", return_value=True):
                    s = ler_log(log)
            self.assertIsNotNone(s.sessao)
            assert s.sessao is not None
            self.assertEqual(s.sessao.rx, 719)
            self.assertEqual(s.sessao.ratio, 1.1)
            self.assertGreaterEqual(s.erros_recentes, 1)

    def test_sessao_morta_ratio(self) -> None:
        saude = Saude(
            servico_ativo=True,
            ping_ok=True,
            sessao=SessaoLog("CONNECTED", "OK", 4.0, 3000, 15000, 5.0, "", 10.0),
            erros_recentes=0,
            ultimo_erro=None,
            carregando=True,
            na_base=True,
        )
        self.assertTrue(sessao_morta(saude))

    def test_erros_antigos_ignorados(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "log"
            log.write_text(
                "2020-01-01 00:00:00,000 cozmo.companion ERROR "
                "Robô sem resposta UDP (6/6) — COZMO 01 provável\n"
                "2026-05-31 10:00:00,338 cozmo.conexao INFO "
                "Sessão Cozmo: estado=CONNECTED ping=OK 4.24V status=0x3310 "
                "udp rx=719 tx=770 desc=0 ratio=1.1\n",
                encoding="utf-8",
            )
            with patch("cozmo_companion.guardian.core.health.servico_ativo", return_value=True):
                with patch("cozmo_companion.guardian.core.health.ping_robo", return_value=True):
                    s = ler_log(log)
            self.assertEqual(s.erros_recentes, 0)

    def test_heartbeat_oled_renova_idade_da_sessao(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "log"
            log.write_text(
                f"{_ts(-380)},000 cozmo.conexao INFO "
                "Sessão Cozmo: estado=CONNECTED ping=OK 4.24V status=0x3310 "
                "udp rx=719 tx=770 desc=0 ratio=1.1\n"
                f"{_ts(-10)},000 cozmo.motor INFO "
                "Base OLED keeper TX: CodeLabHiccup frame 0/32 (2.5 Hz)\n",
                encoding="utf-8",
            )
            with patch("cozmo_companion.guardian.core.health.servico_ativo", return_value=True):
                with patch("cozmo_companion.guardian.core.health.ping_robo", return_value=False):
                    s = ler_log(log)
            self.assertIsNotNone(s.sessao)
            assert s.sessao is not None
            self.assertLess(s.sessao.idade_s, 30.0)


class TestManutencao(unittest.TestCase):
    def test_trim_respeita_intervalo(self) -> None:
        from cozmo_companion.guardian.core.manutencao import manter_logs
        from cozmo_companion.guardian.core.policy import EstadoGuardian

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            (root / "scripts" / "limpar-logs.sh").write_text("#!/bin/bash\nexit 0\n")
            estado = EstadoGuardian()
            estado.ultimo_trim_log = time.monotonic()
            with patch("subprocess.run") as run:
                self.assertFalse(manter_logs(root, estado))
                run.assert_not_called()

    def test_trim_executa_script(self) -> None:
        from cozmo_companion.guardian.core.manutencao import manter_logs
        from cozmo_companion.guardian.core.policy import EstadoGuardian

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            (root / "scripts" / "limpar-logs.sh").write_text("#!/bin/bash\necho ok\n")
            estado = EstadoGuardian()
            with patch("subprocess.run") as run:
                from subprocess import CompletedProcess

                run.return_value = CompletedProcess(
                    args=["limpar-logs.sh"],
                    returncode=0,
                    stdout="OK\n",
                )
                self.assertTrue(manter_logs(root, estado))
                run.assert_called_once()


class TestPolicy(unittest.TestCase):
    def test_reinicia_servico_ativo_com_health_json_estagnado(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data").mkdir()
            velho = datetime.fromtimestamp(time.time() - 600).isoformat(timespec="seconds")
            (root / "data" / "cozmo-saude.json").write_text(
                '{"ts": "' + velho + '"}', encoding="utf-8"
            )
            saude = Saude(True, True, None, 0, None, True, True)
            estado = EstadoGuardian()
            estado.iniciado_em = time.monotonic() - 300
            with patch.dict("os.environ", {"GUARDIAN_HEALTH_STALE_S": "240"}):
                acao = decidir(saude, estado, root=root)
            self.assertEqual(acao, AcaoGuardian.REINICIAR_TRAVADO)

    def test_boot_grace_nao_reinicia_por_json_do_boot_anterior(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data").mkdir()
            velho = datetime.fromtimestamp(time.time() - 3600).isoformat(timespec="seconds")
            (root / "data" / "cozmo-saude.json").write_text(
                '{"ts": "' + velho + '"}', encoding="utf-8"
            )
            saude = Saude(True, True, None, 0, None, True, True)
            with patch.dict("os.environ", {"GUARDIAN_BOOT_GRACE_S": "180"}):
                acao = decidir(saude, EstadoGuardian(), root=root)
            self.assertEqual(acao, AcaoGuardian.NADA)

    def test_reinicia_so_apos_morto_longo(self) -> None:
        estado = EstadoGuardian()
        estado.servico_off_desde = time.monotonic() - 250.0
        saude = Saude(False, False, None, 0, None, None, None)
        acao = decidir(saude, estado, root=Path("/tmp"))
        self.assertEqual(acao, AcaoGuardian.REINICIAR)

    def test_nao_reinicia_servico_recém_parado(self) -> None:
        estado = EstadoGuardian()
        estado.servico_off_desde = time.monotonic() - 5.0
        saude = Saude(False, False, None, 0, None, None, None)
        acao = decidir(saude, estado, root=Path("/tmp"))
        self.assertEqual(acao, AcaoGuardian.NADA)

    def test_sessao_fresh_com_ping_ok_bloqueia_wifi(self) -> None:
        estado = EstadoGuardian()
        saude = Saude(
            True,
            True,
            SessaoLog("CONNECTED", "OK", 4.0, 500, 600, 1.1, "", 30.0),
            0,
            None,
            None,
            None,
        )
        acao = decidir(saude, estado, root=Path("/tmp"))
        self.assertEqual(acao, AcaoGuardian.NADA)

    def test_sessao_fresh_com_ping_fail_mantem_udp(self) -> None:
        estado = EstadoGuardian()
        saude = Saude(
            True,
            False,
            SessaoLog("CONNECTED", "OK", 4.0, 500, 600, 1.1, "", 30.0),
            0,
            None,
            None,
            None,
        )
        with patch(
            "cozmo_companion.core.conexao.cozmo_ssid_visivel",
            return_value=True,
        ):
            acao = decidir(saude, estado, root=Path("/tmp"))
        self.assertEqual(acao, AcaoGuardian.NADA)

    def test_wifi_sem_reiniciar_quando_ping_falha(self) -> None:
        estado = EstadoGuardian()
        saude = Saude(True, False, None, 5, "erro", None, None)
        with patch(
            "cozmo_companion.core.conexao.cozmo_ssid_visivel",
            return_value=True,
        ):
            acao = decidir(saude, estado, root=Path("/tmp"))
        self.assertEqual(acao, AcaoGuardian.WIFI_APENAS)

    def test_wifi_offline_nao_mexe_rede(self) -> None:
        estado = EstadoGuardian()
        saude = Saude(True, False, None, 0, None, None, None)
        with patch(
            "cozmo_companion.core.conexao.cozmo_ssid_visivel",
            return_value=False,
        ):
            with patch(
                "cozmo_companion.core.conexao.wlan0_preso_cozmo",
                return_value=False,
            ):
                acao = decidir(saude, estado, root=Path("/tmp"))
        self.assertEqual(acao, AcaoGuardian.NADA)

    def test_wifi_wlan0_preso_tenta_reconectar(self) -> None:
        estado = EstadoGuardian()
        saude = Saude(True, False, None, 0, None, None, None)
        with patch(
            "cozmo_companion.core.conexao.cozmo_ssid_visivel",
            return_value=False,
        ):
            with patch(
                "cozmo_companion.core.conexao.wlan0_preso_cozmo",
                return_value=True,
            ):
                acao = decidir(saude, estado, root=Path("/tmp"))
        self.assertEqual(acao, AcaoGuardian.WIFI_APENAS)

    def test_erros_udp_nao_reinicia(self) -> None:
        estado = EstadoGuardian()
        saude = Saude(
            True,
            True,
            SessaoLog("CONNECTED", "OK", 4.0, 100, 5000, 5.0, "", 5.0),
            10,
            "sem resposta UDP",
            True,
            True,
        )
        acao = decidir(saude, estado, root=Path("/tmp"))
        self.assertEqual(acao, AcaoGuardian.NADA)


if __name__ == "__main__":
    unittest.main()
