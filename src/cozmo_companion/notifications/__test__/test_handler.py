"""Testes — handler de notificações."""

from __future__ import annotations

import os
import time
import unittest
from unittest.mock import MagicMock, patch

from cozmo_companion.notifications.core.handler import (
    _grupo_som_notif,
    aplicar_notificacao,
)
from cozmo_companion.notifications.core.listener import Notificacao


class TestNotifHandler(unittest.TestCase):
    def test_aplica_na_fila(self) -> None:
        host = MagicMock()
        host._falando = False
        host._llm_ocupado = False
        host._modo_udp_leve = False
        host._monitor_rx = MagicMock()
        host._ultima_notif = 0.0
        host._na_base_efetivo.return_value = True
        host._vida.em_sono = False
        host._fila.enviar_notif_resumida.return_value = True
        host._fila.ocupada = False
        n = Notificacao("Firefox", "Nova aba", "")
        with patch.dict(
            os.environ,
            {
                "NOTIF_ENABLED": "1",
                "NOTIF_NA_BASE": "1",
                "NOTIF_ANIM": "0",
                "NOTIF_SOM": "1",
                "NOTIF_SOM_PRIMEIRO": "1",
            },
        ):
            ok = aplicar_notificacao(host, n, carregando=True, preso_na_base=True)
        self.assertTrue(ok)
        host._fila.enviar_notif_resumida.assert_called_once()
        args, kwargs = host._fila.enviar_notif_resumida.call_args
        self.assertEqual(args[0], "Firefox")
        self.assertTrue(kwargs.get("som_beep"))
        self.assertIsNone(kwargs.get("sinal_tts"))

    def test_segura_loop_base_por_5s(self) -> None:
        host = MagicMock()
        host._falando = False
        host._llm_ocupado = False
        host._modo_udp_leve = False
        host._monitor_rx = MagicMock()
        host._ultima_notif = 0.0
        host._na_base_efetivo.return_value = True
        host._vida.em_sono = False
        host._fila.enviar_notif_resumida.return_value = True
        host._fila.ocupada = False
        n = Notificacao("Steam", "Update", "corpo")
        with patch.dict(
            os.environ,
            {
                "NOTIF_ENABLED": "1",
                "NOTIF_NA_BASE": "1",
                "NOTIF_ANIM": "0",
                "NOTIF_SOM": "1",
                "NOTIF_OLED_DUPLO": "1",
                "NOTIF_OLED_APP_S": "3",
                "NOTIF_OLED_TITULO_S": "2",
                "NOTIF_PAUSE_LOOP_S": "12",
                "NOTIF_HOLD_MAX_S": "12",
                "COZMO_BASE_OLED_HOLD_MAX_S": "12",
            },
        ):
            with patch(
                "cozmo_companion.core.motor_cozmo.segurar_base_oled_loop",
            ) as segurar:
                with patch(
                    "cozmo_companion.core.motor_cozmo.pausar_base_oled_para_texto",
                ):
                    ok = aplicar_notificacao(host, n, carregando=True, preso_na_base=True)
        self.assertTrue(ok)
        self.assertGreaterEqual(segurar.call_count, 1)
        hold = max(c[0][0] for c in segurar.call_args_list)
        self.assertLessEqual(hold, 12.0)
        self.assertGreaterEqual(hold, 5.0)

    def test_fila_pause_curta(self) -> None:
        host = MagicMock()
        host._falando = False
        host._llm_ocupado = False
        host._modo_udp_leve = False
        host._ultima_notif = 0.0
        host._na_base_efetivo.return_value = True
        host._vida.em_sono = False
        host._monitor_rx = MagicMock()
        host._fila.enviar_notif_resumida.return_value = True
        host._fila.ocupada = False
        n = Notificacao("Firefox", "Nova aba", "")
        with patch.dict(
            os.environ,
            {
                "NOTIF_ENABLED": "1",
                "NOTIF_NA_BASE": "1",
                "NOTIF_ANIM": "0",
                "NOTIF_FILA_PAUSE_S": "0.35",
                "NOTIF_OLED_DUPLO": "1",
                "NOTIF_OLED_APP_S": "3",
                "NOTIF_OLED_TITULO_S": "2",
            },
        ):
            with patch(
                "cozmo_companion.core.motor_cozmo.segurar_base_oled_loop",
            ):
                with patch(
                    "cozmo_companion.core.motor_cozmo.pausar_base_oled_para_texto",
                ):
                    aplicar_notificacao(host, n, carregando=True, preso_na_base=True)
        host._fila.pausar.assert_called_once()
        self.assertLessEqual(host._fila.pausar.call_args[0][0], 0.5)

    def test_simples_so_app_4s(self) -> None:
        host = MagicMock()
        host._falando = False
        host._llm_ocupado = False
        host._modo_udp_leve = False
        host._monitor_rx = MagicMock()
        host._ultima_notif = 0.0
        host._na_base_efetivo.return_value = True
        host._vida.em_sono = False
        host._fila.enviar_notif_resumida.return_value = True
        host._fila.ocupada = False
        n = Notificacao("org.telegram.desktop", "Nova msg", "corpo longo")
        with patch.dict(
            os.environ,
            {
                "NOTIF_ENABLED": "1",
                "NOTIF_NA_BASE": "1",
                "NOTIF_ANIM": "0",
                "NOTIF_SOM": "1",
                "NOTIF_SOM_PRIMEIRO": "1",
                "NOTIF_OLED_DUPLO": "0",
                "NOTIF_OLED_APP_S": "4",
            },
        ):
            ok = aplicar_notificacao(host, n, carregando=True, preso_na_base=True)
        self.assertTrue(ok)
        args, kwargs = host._fila.enviar_notif_resumida.call_args
        self.assertEqual(args[0], "Telegram")
        self.assertEqual(args[1], "Telegram")
        self.assertEqual(args[2], 4.0)
        self.assertTrue(kwargs.get("som_beep"))
        self.assertIsNone(kwargs.get("titulo_oled"))
        self.assertEqual(kwargs.get("seg_titulo"), 0.0)

    def test_grupo_som_padrao_beep(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            self.assertEqual(_grupo_som_notif(), "beep")

    def test_grupo_som_desligado(self) -> None:
        with patch.dict(os.environ, {"NOTIF_SOM_MODO": "off"}):
            self.assertEqual(_grupo_som_notif(), "")

    def test_sem_som_quando_desligado(self) -> None:
        host = MagicMock()
        host._falando = False
        host._llm_ocupado = False
        host._modo_udp_leve = False
        host._monitor_rx = MagicMock()
        host._ultima_notif = 0.0
        host._na_base_efetivo.return_value = True
        host._vida.em_sono = False
        host._fila.enviar_notif_resumida.return_value = True
        host._fila.ocupada = False
        n = Notificacao("Discord", "x", "")
        with patch.dict(
            os.environ,
            {"NOTIF_ENABLED": "1", "NOTIF_NA_BASE": "1", "NOTIF_SOM": "0"},
        ):
            aplicar_notificacao(host, n, carregando=True, preso_na_base=True)
        kwargs = host._fila.enviar_notif_resumida.call_args[1]
        self.assertFalse(kwargs.get("som_beep"))

    def test_notificacao_acorda_ambiente_escuro(self) -> None:
        host = MagicMock()
        host._falando = False
        host._llm_ocupado = False
        host._modo_udp_leve = False
        host._monitor_rx = MagicMock()
        host._detector_escuro = MagicMock()
        host._ultima_notif = 0.0
        host._na_base_efetivo.return_value = True
        host._vida.dormindo = True
        host._vida.em_sono = True
        host._fila.enviar_notif_resumida.return_value = True
        host._fila.ocupada = False
        n = Notificacao("Discord", "x", "")
        with patch.dict(
            os.environ,
            {"NOTIF_ENABLED": "1", "NOTIF_NA_BASE": "1", "COZMO_ESCURO_DESPERTAR_S": "120"},
        ):
            aplicar_notificacao(host, n, carregando=True, preso_na_base=True)
        host._detector_escuro.marcar_despertar.assert_called_once_with(120.0)
        host._vida.despertar.assert_called_once()

    def test_cooldown_bloqueia(self) -> None:
        host = MagicMock()
        host._falando = False
        host._llm_ocupado = False
        host._modo_udp_leve = False
        host._monitor_rx = MagicMock()
        host._ultima_notif = time.monotonic()
        host._na_base_efetivo.return_value = True
        n = Notificacao("Discord", "x", "")
        with patch.dict(
            os.environ,
            {"NOTIF_ENABLED": "1", "NOTIF_COOLDOWN_S": "60"},
        ):
            ok = aplicar_notificacao(host, n, carregando=False, preso_na_base=True)
        self.assertFalse(ok)
        host._fila.enviar_notif_resumida.assert_not_called()


if __name__ == "__main__":
    unittest.main()
