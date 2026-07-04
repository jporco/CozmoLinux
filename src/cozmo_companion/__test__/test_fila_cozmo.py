"""Testes da fila serial Cozmo."""

from __future__ import annotations

import os
import time
import unittest
from unittest.mock import MagicMock, patch

import cozmo_companion.core.motor_cozmo as motor
from cozmo_companion.core.fila_cozmo import EstadoFila, FilaCozmo, ItemFila, TipoItem
from cozmo_companion.core.governador import GovernadorCozmo


class TestFilaCozmo(unittest.TestCase):
    def setUp(self) -> None:
        motor._base_oled_loop_hold_ate = 0.0
        os.environ["COZMO_FILA_ATIVA"] = "1"
        os.environ["COZMO_MAX_TTS_SINAL_WORDS"] = "1"
        os.environ["COZMO_MAX_OLED_CHARS"] = "16"
        os.environ["COZMO_FILA_TIMEOUT_S"] = "0.15"
        self.gov = GovernadorCozmo()
        self.gov._tokens = 50.0
        self.tocadas: list[tuple[str, ...]] = []
        self.oleds: list[str] = []
        self.sinais: list[str] = []
        self.sons: list[bool] = []

        self.fila = FilaCozmo(
            self.gov,
            tocar_grupo=self._tocar,
            mostrar_oled=self._oled,
            executar_sinal=self._sinal,
            executar_som=self._som,
            na_base=lambda: True,
            usa_procedural=lambda: True,
        )

    def _tocar(self, grupos: tuple[str, ...], *, prioridade: bool = False) -> None:
        self.tocadas.append(grupos)

    def _oled(
        self,
        texto: str,
        *,
        segundos: float = 8.0,
        scroll: bool = False,
        passo_s: float = 1.0,
        forcado: bool = False,
    ) -> None:
        del segundos, scroll, passo_s, forcado
        self.oleds.append(texto)

    def _sinal(self, texto: str) -> bool:
        self.sinais.append(texto)
        return True

    def _som(self) -> bool:
        self.sons.append(True)
        return True

    def test_vazia_apos_drenar_oled(self) -> None:
        self.fila.enviar_oled("Mesa", segundos=0.2, prioridade=True)
        cli = MagicMock()
        cli.battery_voltage = 4.0
        ac = cli.anim_controller
        ac.procedural_face_enabled = False
        ac.playing_animation = False
        ac.playing_audio = False
        self.assertFalse(self.fila.vazia)
        ok = self.fila.drenar(cli, timeout_s=1.5)
        self.assertTrue(ok)
        self.assertTrue(self.fila.vazia)
        self.assertEqual(self.oleds, ["Mesa"])

    def test_fim_oled_forcado_base_restaura_keeper(self) -> None:
        self.fila.enviar_oled("Livre", segundos=0.05, prioridade=True, forcado=True)
        cli = MagicMock()
        cli.battery_voltage = 4.0
        with patch(
            "cozmo_companion.core.motor_cozmo.liberar_base_oled_loop_hold"
        ) as liberar:
            with patch.object(self.fila, "_restaurar_rosto_pos_item") as restaurar:
                self.fila.tick(cli)
                time.sleep(0.14)
                self.fila.tick(cli)
        liberar.assert_called()
        restaurar.assert_called_with(cli)

    def test_rejeita_tts_pesado(self) -> None:
        self.assertFalse(self.fila.enviar_sinal_tts("uma duas palavras"))
        self.assertEqual(len(self.fila._fila), 0)

    def test_ordem_serial_anim_oled_tts(self) -> None:
        self.fila.enviar_anim(("NeutralFace",))
        self.fila.enviar_oled("Telegram", segundos=0.15)
        self.fila.enviar_sinal_tts("Ei")
        cli = MagicMock()
        cli.battery_voltage = 4.0
        ac = cli.anim_controller
        ac.procedural_face_enabled = True
        ac.playing_animation = True
        ac.playing_audio = False
        ac.animations_enabled = True

        self.fila.tick(cli)
        self.assertEqual(self.tocadas, [("NeutralFace",)])
        self.assertEqual(self.fila.estado, EstadoFila.ANIM)

        ac.playing_animation = False
        self.fila.tick(cli)
        self.fila.tick(cli)
        self.assertEqual(self.oleds, ["Telegram"])
        time.sleep(0.2)
        self.fila.tick(cli)
        self.assertEqual(self.sinais, ["Ei"])

    def test_notif_oled_na_base(self) -> None:
        self.fila.na_base = lambda: True
        with patch.dict(
            os.environ,
            {
                "NOTIF_OLED_NA_BASE": "1",
                "COZMO_BASE_OLED_CHARGER": "1",
                "COZMO_OLED_NA_BASE": "0",
                "NOTIF_ANIM": "0",
            },
        ):
            ok = self.fila.enviar_notif_resumida(
                "Steam",
                "Steam: update",
                3.0,
                grupos_anim=(),
                prioridade=True,
            )
        self.assertTrue(ok)
        tipos = [i.tipo for i in self.fila._fila]
        self.assertIn(TipoItem.OLED, tipos)

    def test_notif_pipeline(self) -> None:
        os.environ["COZMO_NOTIF_ANIM_FIRST"] = "1"
        os.environ["COZMO_NOTIF_ANIM_NA_BASE"] = "1"
        os.environ["NOTIF_SOM_PRIMEIRO"] = "0"
        self.fila.enviar_notif_resumida(
            "Discord",
            "Discord: oi",
            6.0,
            grupos_anim=("InterestedFace",),
            som_grupo="Hiccup",
        )
        self.assertGreaterEqual(len(self.fila._fila), 3)
        tipos = [i.tipo for i in self.fila._fila]
        self.assertEqual(tipos[0], TipoItem.ANIM)
        self.assertIn(TipoItem.OLED, tipos)
        self.assertNotIn(TipoItem.TTS, tipos)

    def test_notif_som_primeiro_ordem(self) -> None:
        with patch.dict(
            os.environ,
            {
                "NOTIF_OLED_PRIMEIRO": "0",
                "NOTIF_SOM_PRIMEIRO": "1",
                "NOTIF_ANIM": "0",
                "COZMO_NOTIF_ANIM_FIRST": "0",
            },
        ):
            self.fila.enviar_notif_resumida(
                "Discord",
                "Discord: oi",
                0.2,
                grupos_anim=(),
                som_beep=True,
                prioridade=True,
                pausar_loop_ja=True,
            )
        tipos = [i.tipo for i in self.fila._fila]
        self.assertEqual(tipos[0], TipoItem.SOM)
        self.assertEqual(tipos[1], TipoItem.OLED)
        cli = MagicMock()
        ac = cli.anim_controller
        ac.procedural_face_enabled = False
        ac.playing_animation = False
        ac.playing_audio = False
        self.fila.tick(cli)
        self.assertEqual(self.sons, [True])
        self.assertEqual(self.oleds, [])
        ac.playing_animation = False
        ac.playing_audio = False
        self.fila.tick(cli)
        self.assertEqual(self.oleds, ["Discord"])

    def test_notif_beep_usa_play_audio(self) -> None:
        with patch.dict(
            os.environ,
            {
                "NOTIF_OLED_PRIMEIRO": "0",
                "NOTIF_SOM_PRIMEIRO": "1",
                "NOTIF_ANIM": "0",
                "COZMO_NOTIF_ANIM_FIRST": "0",
                "NOTIF_SOM_MODO": "beep",
            },
        ):
            self.fila.enviar_notif_resumida(
                "Discord",
                "Discord: oi",
                0.2,
                grupos_anim=(),
                som_beep=True,
                prioridade=True,
                pausar_loop_ja=True,
            )
        tipos = [i.tipo for i in self.fila._fila]
        self.assertEqual(tipos[0], TipoItem.SOM)
        self.assertEqual(tipos[1], TipoItem.OLED)
        self.assertNotIn(TipoItem.TTS, tipos)

    def test_notif_sinal_modo_usa_som_udp(self) -> None:
        with patch.dict(
            os.environ,
            {
                "NOTIF_OLED_PRIMEIRO": "0",
                "NOTIF_SOM_PRIMEIRO": "1",
                "NOTIF_ANIM": "0",
                "COZMO_NOTIF_ANIM_FIRST": "0",
                "NOTIF_SOM_MODO": "sinal",
            },
        ):
            self.fila.enviar_notif_resumida(
                "Discord",
                "Discord: oi",
                0.2,
                grupos_anim=(),
                som_beep=True,
                prioridade=True,
                pausar_loop_ja=True,
            )
        tipos = [i.tipo for i in self.fila._fila]
        self.assertEqual(tipos[0], TipoItem.SOM)
        self.assertNotIn(TipoItem.TTS, tipos)

    def test_timeout_anim_libera_fila(self) -> None:
        self.fila.enviar_anim(("A",))
        self.fila.enviar_oled("X", segundos=0.15)
        cli = MagicMock()
        ac = cli.anim_controller
        ac.procedural_face_enabled = False
        ac.playing_animation = True
        ac.playing_audio = False
        self.fila.tick(cli)
        time.sleep(0.2)
        self.fila.tick(cli)
        self.assertFalse(self.fila._anim_aguardando)
        self.fila.tick(cli)
        time.sleep(0.2)
        self.fila.tick(cli)
        self.assertEqual(self.oleds, ["X"])

    def test_pausar_bloqueia_tick(self) -> None:
        self.fila.enviar_oled("A", segundos=1.0)
        self.fila.pausar(30.0)
        cli = MagicMock()
        self.fila.tick(cli)
        self.assertEqual(self.oleds, [])

    def test_prioridade_frente(self) -> None:
        self.fila.enviar_oled("B", segundos=1.0)
        self.fila.enviar_sinal_tts("Oi", prioridade=True)
        self.assertEqual(self.fila._fila[0].tts, "Oi")

    def test_notif_duas_telas_espera_app(self) -> None:
        self.fila.enviar_notif_resumida(
            "Steam",
            "Steam: update",
            0.25,
            grupos_anim=(),
            prioridade=True,
            titulo_oled="Update pronto",
            seg_titulo=0.15,
            pausar_loop_ja=True,
        )
        cli = MagicMock()
        ac = cli.anim_controller
        ac.procedural_face_enabled = False
        ac.playing_animation = False
        ac.playing_audio = False
        t0 = time.monotonic()
        self.fila.tick(cli)
        self.assertEqual(self.oleds, ["Steam"])
        self.fila.tick(cli)
        self.assertEqual(self.oleds, ["Steam"])
        time.sleep(0.3)
        self.fila.tick(cli)
        self.assertEqual(self.oleds, ["Steam", "Update pronto"])
        self.assertGreaterEqual(time.monotonic() - t0, 0.24)

    def test_carinho_base_ordem_oled_tts(self) -> None:
        os.environ["CARINHO_OLED_HOLD_S"] = "0.05"
        os.environ["CARINHO_OLED_S"] = "0.05"
        self.fila.enviar_carinho_base("^^", "Ai")
        tipos = [i.tipo for i in self.fila._fila]
        self.assertEqual(tipos[0], TipoItem.OLED)
        self.assertEqual(tipos[1], TipoItem.QUIET)
        self.assertEqual(tipos[2], TipoItem.TTS)
        cli = MagicMock()
        self.fila.drenar(cli, timeout_s=2.0)
        self.assertEqual(self.oleds, ["^^"])
        self.assertEqual(self.sinais, ["Ai"])

    def test_restaura_procedural_apos_anim(self) -> None:
        self.fila.usa_procedural = lambda: False
        self.fila.enviar_anim(("InterestedFace",))
        cli = MagicMock()
        ac = cli.anim_controller
        ac.procedural_face_enabled = True
        ac.playing_animation = True
        ac.playing_audio = False
        self.fila.tick(cli)
        ac.playing_animation = False
        with patch(
            "cozmo_companion.core.motor_cozmo.modo_base_olhos",
        ) as modo:
            self.fila.tick(cli)
            modo.assert_called_once_with(cli)

    @patch.object(GovernadorCozmo, "reservar", side_effect=[True, False])
    def test_notif_sem_reserva_parcial(self, _res: MagicMock) -> None:
        with patch.dict(
            os.environ,
            {
                "NOTIF_OLED_PRIMEIRO": "0",
                "NOTIF_SOM_PRIMEIRO": "1",
                "NOTIF_ANIM": "0",
                "COZMO_NOTIF_ANIM_FIRST": "0",
            },
        ):
            ok = self.fila.enviar_notif_resumida(
                "Discord",
                "Discord: oi",
                0.2,
                grupos_anim=(),
                som_beep=True,
                prioridade=True,
                pausar_loop_ja=True,
            )
        self.assertFalse(ok)
        self.assertEqual(len(self.fila._fila), 0)

    @patch.object(GovernadorCozmo, "reservar", return_value=False)
    def test_sem_budget_ainda_enfileira_anim(self, _res: MagicMock) -> None:
        """ANIM não reserva no enqueue — quem reserva de verdade é tocar_grupo
        no despacho (2 reservas na mesma janela sempre derrubava a 2ª)."""
        self.assertTrue(self.fila.enviar_anim(("X",)))
        self.assertEqual(len(self.fila._fila), 1)


if __name__ == "__main__":
    unittest.main()
