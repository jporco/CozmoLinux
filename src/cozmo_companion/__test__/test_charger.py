import os
import unittest
from unittest.mock import MagicMock, patch

from cozmo_companion.core.charger import (
    ANIMACOES_CARGA,
    BaseGuard,
    bateria_cheia,
    bateria_pct,
    definir_oled_preso_na_base,
    na_base,
    na_base_oled,
)


class TestCharger(unittest.TestCase):
    def test_na_base(self):
        cli = MagicMock()
        cli.robot_status = 0x1000  # IS_ON_CHARGER
        self.assertTrue(na_base(cli))

        cli.robot_status = 0
        self.assertFalse(na_base(cli))

    def test_na_base_oled_preso_sem_contato(self) -> None:
        cli = MagicMock()
        cli.robot_status = 0
        definir_oled_preso_na_base(False)
        self.assertFalse(na_base_oled(cli))
        definir_oled_preso_na_base(True)
        self.assertTrue(na_base_oled(cli))
        definir_oled_preso_na_base(False)

    def test_bateria_cheia(self):
        from cozmo_companion.core.charger import BATTERY_FULL_V

        cli = MagicMock()
        cli.battery_voltage = BATTERY_FULL_V + 0.05
        self.assertTrue(bateria_cheia(cli))

        cli.battery_voltage = 3.5
        self.assertFalse(bateria_cheia(cli))

    def test_bateria_pct(self):
        cli = MagicMock()
        cli.battery_voltage = 3.5
        self.assertEqual(bateria_pct(cli), 0)
        cli.battery_voltage = 4.05
        self.assertEqual(bateria_pct(cli), 100)
        cli.battery_voltage = 3.775
        self.assertGreaterEqual(bateria_pct(cli), 49)
        self.assertLessEqual(bateria_pct(cli), 51)

    def test_filtra_animacoes_perigosas(self):
        g = BaseGuard()
        filtrado = g.filtrar_animacoes(("DriveOffCharger", "Sleeping", "Hiccup"))
        self.assertIn("Sleeping", filtrado)
        self.assertNotIn("DriveOffCharger", filtrado)
        self.assertTrue(filtrado)
        self.assertTrue(all(a in ANIMACOES_CARGA for a in filtrado))


    def test_preso_na_base_histerese(self):
        g = BaseGuard()
        cli = MagicMock()
        cli.robot_status = 0x1000
        cli.battery_voltage = 4.0
        cli.robot_moving = False
        cli.robot_picked_up = False
        cli.left_wheel_speed = MagicMock(mmps=0)
        cli.right_wheel_speed = MagicMock(mmps=0)
        for _ in range(BaseGuard.TICKS_ENTRAR):
            g.tick(cli)
        self.assertTrue(g.preso_na_base)
        cli.robot_status = 0
        cli.battery_voltage = 3.52
        cli.robot_picked_up = False
        g._v_filtrada = 3.52
        prev = os.environ.get("BASE_NUNCA_SAIR")
        os.environ["BASE_NUNCA_SAIR"] = "0"
        prev_botao = os.environ.get("BASE_MODO_BOTAO")
        os.environ["BASE_MODO_BOTAO"] = "0"
        try:
            for _ in range(BaseGuard.TICKS_SAIR + 2):
                g.tick(cli)
            self.assertFalse(g.preso_na_base)
        finally:
            if prev is None:
                os.environ.pop("BASE_NUNCA_SAIR", None)
            else:
                os.environ["BASE_NUNCA_SAIR"] = prev
            if prev_botao is None:
                os.environ.pop("BASE_MODO_BOTAO", None)
            else:
                os.environ["BASE_MODO_BOTAO"] = prev_botao

    def test_nunca_sair_contato_instavel(self):
        g = BaseGuard()
        cli = MagicMock()
        cli.robot_status = 0x1000
        cli.battery_voltage = 3.9
        cli.robot_moving = False
        cli.robot_picked_up = False
        cli.left_wheel_speed = MagicMock(mmps=0)
        cli.right_wheel_speed = MagicMock(mmps=0)
        g.entrou_na_base(cli)
        cli.robot_status = 0
        cli.battery_voltage = 3.82
        prev = os.environ.get("BASE_NUNCA_SAIR")
        os.environ["BASE_NUNCA_SAIR"] = "1"
        try:
            for _ in range(BaseGuard.TICKS_SAIR + 50):
                g.tick(cli)
            self.assertTrue(g.preso_na_base)
        finally:
            if prev is None:
                os.environ.pop("BASE_NUNCA_SAIR", None)
            else:
                os.environ["BASE_NUNCA_SAIR"] = prev

    def test_liberar_pickup(self):
        g = BaseGuard()
        cli = MagicMock()
        cli.robot_status = 0
        cli.battery_voltage = 3.6
        cli.robot_moving = False
        cli.robot_picked_up = True
        cli.left_wheel_speed = MagicMock(mmps=0)
        cli.right_wheel_speed = MagicMock(mmps=0)
        g._preso_na_base = True
        g._fora_contato_desde = __import__("time").monotonic() - 2.0
        with patch.dict(os.environ, {"BASE_PICKUP_S": "0", "BASE_PICKUP_OFF_S": "1.0", "BASE_MODO_BOTAO": "0"}):
            g.registrar_pickup(cli, True)
            self.assertTrue(g.liberar_da_base(cli, motivo="pickup"))
        self.assertFalse(g.preso_na_base)

    def test_falso_pickup_ainda_na_base(self):
        g = BaseGuard()
        cli = MagicMock()
        cli.robot_status = 0x1000 | 0x2000
        cli.battery_voltage = 4.0
        cli.robot_picked_up = True
        cli.robot_moving = False
        cli.left_wheel_speed = MagicMock(mmps=0)
        cli.right_wheel_speed = MagicMock(mmps=0)
        g._preso_na_base = True
        g._fora_contato_desde = __import__("time").monotonic() - 5.0
        with patch.dict(os.environ, {"BASE_PICKUP_S": "0", "BASE_PICKUP_OFF_S": "0"}):
            self.assertFalse(g.liberar_da_base(cli, motivo="pickup"))
        self.assertTrue(g.preso_na_base)

    def test_liberar_pickup_falso_positivo(self):
        g = BaseGuard()
        cli = MagicMock()
        cli.robot_picked_up = False
        g._preso_na_base = True
        g.registrar_pickup(cli, True)
        self.assertFalse(g.liberar_da_base(cli, motivo="pickup"))
        self.assertTrue(g.preso_na_base)


    def test_saiu_da_base_so_uma_vez(self):
        g = BaseGuard()
        g._preso_na_base = True
        self.assertTrue(g.saiu_da_base(motivo="pickup"))
        self.assertFalse(g.saiu_da_base(motivo="pickup"))
        self.assertFalse(g.preso_na_base)


    def test_falso_alerta_bateria_cheia(self):
        g = BaseGuard()
        cli = MagicMock()
        cli.robot_status = 0x1000 | 0x2000
        cli.battery_voltage = 3.95
        cli.robot_moving = False
        cli.robot_picked_up = False
        cli.left_wheel_speed = MagicMock(mmps=0)
        cli.right_wheel_speed = MagicMock(mmps=0)
        g.entrou_na_base(cli)
        g._carga_pausada = True
        g._v_filtrada = 3.95
        with patch("cozmo_companion.core.charger.logger") as log:
            g.tick(cli)
            for call in log.warning.call_args_list:
                msg = call[0][0] if call[0] else ""
                self.assertNotIn("abaixo de 60%", msg)


    def test_alternar_modo_botao(self):
        g = BaseGuard()
        cli = MagicMock()
        cli.robot_status = 0
        cli.battery_voltage = 4.0
        cli.robot_moving = False
        cli.robot_picked_up = False
        cli.left_wheel_speed = MagicMock(mmps=0)
        cli.right_wheel_speed = MagicMock(mmps=0)
        prev = os.environ.get("BASE_MODO_BOTAO")
        os.environ["BASE_MODO_BOTAO"] = "1"
        try:
            g._preso_na_base = True
            g._ultimo_toggle_botao = 0.0
            self.assertFalse(g.alternar_modo_botao(cli))
            self.assertFalse(g.preso_na_base)
            g._ultimo_toggle_botao = 0.0
            self.assertTrue(g.alternar_modo_botao(cli))
            self.assertTrue(g.preso_na_base)
        finally:
            if prev is None:
                os.environ.pop("BASE_MODO_BOTAO", None)
            else:
                os.environ["BASE_MODO_BOTAO"] = prev

    def test_alternar_modo_botao_base_sempre_carga(self):
        g = BaseGuard()
        cli = MagicMock()
        cli.robot_status = 0
        cli.battery_voltage = 4.0
        prev = os.environ.get("COZMO_BASE_SEMPRE_CARGA")
        os.environ["COZMO_BASE_SEMPRE_CARGA"] = "1"
        try:
            g._preso_na_base = True
            g._ultimo_toggle_botao = 0.0
            self.assertFalse(g.alternar_modo_botao(cli))
            self.assertFalse(g.preso_na_base)
            self.assertTrue(g.mesa_escolhida)
        finally:
            if prev is None:
                os.environ.pop("COZMO_BASE_SEMPRE_CARGA", None)
            else:
                os.environ["COZMO_BASE_SEMPRE_CARGA"] = prev

    def test_pickup_libera_modo_botao(self):
        g = BaseGuard()
        cli = MagicMock()
        cli.robot_picked_up = True
        cli.robot_status = 0
        g._preso_na_base = True
        prev = os.environ.get("BASE_MODO_BOTAO")
        os.environ["BASE_MODO_BOTAO"] = "1"
        try:
            import time

            g._pickup_desde = time.monotonic() - 2.0
            g._fora_contato_desde = time.monotonic() - 2.0
            with unittest.mock.patch.object(
                g, "_confirmado_fora_da_base", return_value=True
            ):
                self.assertTrue(g.tentar_liberar_pickup(cli))
            self.assertFalse(g.preso_na_base)
        finally:
            if prev is None:
                os.environ.pop("BASE_MODO_BOTAO", None)
            else:
                os.environ["BASE_MODO_BOTAO"] = prev

    def test_pickup_ignorado_modo_botao(self):
        g = BaseGuard()
        cli = MagicMock()
        cli.robot_picked_up = True
        g._preso_na_base = True
        prev = os.environ.get("BASE_MODO_BOTAO")
        os.environ["BASE_MODO_BOTAO"] = "1"
        try:
            with unittest.mock.patch.object(
                g, "_confirmado_fora_da_base", return_value=False
            ):
                self.assertFalse(g.tentar_liberar_pickup(cli))
            self.assertTrue(g.preso_na_base)
        finally:
            if prev is None:
                os.environ.pop("BASE_MODO_BOTAO", None)
            else:
                os.environ["BASE_MODO_BOTAO"] = prev


    def test_auto_base_modo_botao(self):
        """Modo botão: tick NÃO trava — só o botão define BASE."""
        g = BaseGuard()
        cli = MagicMock()
        cli.robot_status = 0x1000
        cli.battery_voltage = 4.0
        cli.robot_moving = False
        cli.robot_picked_up = False
        cli.left_wheel_speed = MagicMock(mmps=0)
        cli.right_wheel_speed = MagicMock(mmps=0)
        prev = os.environ.get("BASE_MODO_BOTAO")
        os.environ["BASE_MODO_BOTAO"] = "1"
        try:
            g._preso_na_base = False
            g._mesa_escolhida = False
            for _ in range(BaseGuard.TICKS_ENTRAR + 5):
                g.tick(cli)
            self.assertFalse(g.preso_na_base)
            g._ultimo_toggle_botao = 0.0
            self.assertTrue(g.alternar_modo_botao(cli))
            self.assertTrue(g.preso_na_base)
        finally:
            if prev is None:
                os.environ.pop("BASE_MODO_BOTAO", None)
            else:
                os.environ["BASE_MODO_BOTAO"] = prev

    def test_mesa_fisica_bloqueada_no_carregador(self):
        g = BaseGuard()
        cli = MagicMock()
        cli.robot_status = 0x1000 | 0x2000
        cli.battery_voltage = 4.0
        cli.robot_picked_up = False
        g._preso_na_base = True
        prev = os.environ.get("BASE_MODO_BOTAO")
        os.environ["BASE_MODO_BOTAO"] = "1"
        try:
            self.assertFalse(g.saiu_da_base(cli, motivo="mesa"))
            self.assertTrue(g.preso_na_base)
        finally:
            if prev is None:
                os.environ.pop("BASE_MODO_BOTAO", None)
            else:
                os.environ["BASE_MODO_BOTAO"] = prev

    def test_auto_base_respeita_mesa_escolhida(self):
        g = BaseGuard()
        cli = MagicMock()
        cli.robot_status = 0x1000
        cli.battery_voltage = 4.0
        cli.robot_moving = False
        cli.robot_picked_up = False
        cli.left_wheel_speed = MagicMock(mmps=0)
        cli.right_wheel_speed = MagicMock(mmps=0)
        prev = os.environ.get("BASE_MODO_BOTAO")
        os.environ["BASE_MODO_BOTAO"] = "1"
        try:
            g._preso_na_base = False
            g._mesa_escolhida = True
            for _ in range(BaseGuard.TICKS_ENTRAR + 5):
                g.tick(cli)
            self.assertFalse(g.preso_na_base)
        finally:
            if prev is None:
                os.environ.pop("BASE_MODO_BOTAO", None)
            else:
                os.environ["BASE_MODO_BOTAO"] = prev


    def test_boot_modo_botao_inicia_base_no_carregador(self):
        g = BaseGuard()
        cli = MagicMock()
        cli.robot_status = 0x1000 | 0x2000
        cli.battery_voltage = 4.0
        cli.robot_picked_up = False
        cli.left_wheel_speed = MagicMock(mmps=0)
        cli.right_wheel_speed = MagicMock(mmps=0)
        prev = os.environ.get("BASE_MODO_BOTAO")
        os.environ["BASE_MODO_BOTAO"] = "1"
        try:
            g._preso_na_base = False
            g._mesa_escolhida = True
            with patch("cozmo_companion.core.charger.carregar_modo_botao", return_value=None):
                with patch("cozmo_companion.core.charger.salvar_modo_botao"):
                    na = g.inicializar_boot_modo_botao(cli)
            self.assertTrue(na)
            self.assertTrue(g.preso_na_base)
            self.assertFalse(g._mesa_escolhida)
        finally:
            if prev is None:
                os.environ.pop("BASE_MODO_BOTAO", None)
            else:
                os.environ["BASE_MODO_BOTAO"] = prev

    def test_boot_modo_botao_mesa_fora_carregador(self):
        g = BaseGuard()
        cli = MagicMock()
        cli.robot_status = 0
        cli.battery_voltage = 3.7
        cli.robot_picked_up = False
        cli.left_wheel_speed = MagicMock(mmps=0)
        cli.right_wheel_speed = MagicMock(mmps=0)
        prev_botao = os.environ.get("BASE_MODO_BOTAO")
        os.environ["BASE_MODO_BOTAO"] = "1"
        try:
            with patch("cozmo_companion.core.charger.salvar_modo_botao"):
                na = g.inicializar_boot_modo_botao(cli)
            self.assertTrue(na)
            self.assertTrue(g.preso_na_base)
        finally:
            if prev_botao is None:
                os.environ.pop("BASE_MODO_BOTAO", None)
            else:
                os.environ["BASE_MODO_BOTAO"] = prev_botao

    def test_boot_sempre_base_mesmo_com_mesa_salva(self):
        g = BaseGuard()
        cli = MagicMock()
        cli.robot_status = 0x1000
        cli.battery_voltage = 4.2
        cli.robot_picked_up = False
        cli.left_wheel_speed = MagicMock(mmps=0)
        cli.right_wheel_speed = MagicMock(mmps=0)
        prev = os.environ.get("BASE_MODO_BOTAO")
        os.environ["BASE_MODO_BOTAO"] = "1"
        try:
            with patch(
                "cozmo_companion.core.charger.carregar_modo_botao",
                return_value={"preso_na_base": False, "mesa_escolhida": True},
            ):
                with patch("cozmo_companion.core.charger.salvar_modo_botao") as salvar:
                    na = g.inicializar_boot_modo_botao(cli)
            self.assertTrue(na)
            self.assertTrue(g.preso_na_base)
            salvar.assert_called_with(preso_na_base=True, mesa_escolhida=False)
        finally:
            if prev is None:
                os.environ.pop("BASE_MODO_BOTAO", None)
            else:
                os.environ["BASE_MODO_BOTAO"] = prev

    def test_boot_modo_botao_nunca_sair_sempre_base(self):
        g = BaseGuard()
        cli = MagicMock()
        cli.robot_status = 0
        cli.battery_voltage = 3.4
        cli.robot_picked_up = False
        cli.left_wheel_speed = MagicMock(mmps=0)
        cli.right_wheel_speed = MagicMock(mmps=0)
        prev = os.environ.get("BASE_NUNCA_SAIR")
        os.environ["BASE_NUNCA_SAIR"] = "1"
        try:
            with patch(
                "cozmo_companion.core.charger.carregar_modo_botao",
                return_value={"preso_na_base": True, "mesa_escolhida": False},
            ):
                na = g.inicializar_boot_modo_botao(cli)
            self.assertTrue(na)
            self.assertTrue(g.preso_na_base)
        finally:
            if prev is None:
                os.environ.pop("BASE_NUNCA_SAIR", None)
            else:
                os.environ["BASE_NUNCA_SAIR"] = prev


if __name__ == "__main__":
    os.environ.setdefault("PYTHONPATH", "src")
    unittest.main()
