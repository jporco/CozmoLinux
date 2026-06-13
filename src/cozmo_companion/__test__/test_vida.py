"""Testes do ciclo de vida."""

import os
import time
import unittest
from unittest.mock import MagicMock, patch

from cozmo_companion.core.anims import escolher, filtrar_na_base
from cozmo_companion.core.vida import (
    AWAKE_APOS_DESPERTAR,
    CicloVida,
    Fase,
    _duracao_sono_s,
    _intervalo_acordado_s,
)


class TestVida(unittest.TestCase):
    def test_intervalo_sono_env(self) -> None:
        with patch.dict(
            os.environ,
            {"COZMO_SLEEP_INTERVAL_MIN": "30", "COZMO_SLEEP_INTERVAL_JITTER_S": "0"},
        ):
            lo, hi = _intervalo_acordado_s()
        self.assertEqual(lo, 30 * 60)
        self.assertEqual(hi, 30 * 60)

    def test_duracao_sono_env(self) -> None:
        with patch.dict(
            os.environ,
            {"COZMO_SLEEP_DURATION_MIN": "40", "COZMO_SLEEP_DURATION_JITTER_S": "0"},
        ):
            lo, hi = _duracao_sono_s()
        self.assertEqual(lo, 40 * 60)
        self.assertEqual(hi, 40 * 60)

    def test_filtra_drive(self):
        g = {"DriveOffCharger", "Sleeping", "NeutralFace"}
        ok = filtrar_na_base(("DriveOffCharger", "Sleeping"), g)
        self.assertIn("Sleeping", ok)
        self.assertNotIn("DriveOffCharger", ok)

    def test_escolher_na_base(self):
        g = {"DriveOffCharger", "IdleOnCharger"}
        nome = escolher(g, ("DriveOffCharger", "IdleOnCharger"), na_base=True)
        self.assertIn(nome, ("IdleOnCharger",))
        self.assertNotEqual(nome, "DriveOffCharger")

    def test_acordar_por_toque(self):
        cli = MagicMock()
        cli.animation_groups = {
            "GoToSleepGetOut": None,
            "Sleeping": None,
        }
        ac = MagicMock()
        cli.anim_controller = ac
        tela = MagicMock()
        face = MagicMock()
        vida = CicloVida(tela, face, lambda c: None)
        vida.fase = Fase.DORMINDO
        self.assertTrue(vida.acordar_por_toque(cli))
        self.assertEqual(vida.fase, Fase.ACORDADO)
        tela.clarear.assert_called()
        tela.mostrar.assert_called()

    def test_acordar_para_voz_ja_acordado(self) -> None:
        cli = MagicMock()
        cli.anim_controller = MagicMock()
        tela = MagicMock()
        face = MagicMock()
        vida = CicloVida(tela, face, lambda c: None)
        vida.fase = Fase.ACORDADO
        vida.acordar_para_voz(cli, preso_na_base=True)
        self.assertEqual(vida.fase, Fase.ACORDADO)
        tela.mostrar.assert_called()

    def test_interacao_acorda(self):
        tela = MagicMock()
        face = MagicMock()
        vida = CicloVida(tela, face, lambda c: None)
        vida.fase = Fase.DORMINDO
        vida.registrar_interacao(10.0, cli=MagicMock(), motivo="teste")
        self.assertEqual(vida.fase, Fase.ACORDADO)
        tela.clarear.assert_called_once()

    def test_interacao_sem_cli_nao_acorda_dormindo(self) -> None:
        tela = MagicMock()
        face = MagicMock()
        vida = CicloVida(tela, face, lambda c: None)
        vida.fase = Fase.DORMINDO
        vida.registrar_interacao(12.0, motivo="carinho")
        self.assertEqual(vida.fase, Fase.DORMINDO)
        tela.clarear.assert_not_called()

    def test_carinho_nao_bloqueia_sono_15min(self) -> None:
        tela = MagicMock()
        face = MagicMock()
        vida = CicloVida(tela, face, lambda c: None)
        agora = time.monotonic()
        vida.registrar_interacao(25.0, motivo="carinho")
        self.assertLess(vida._interacao_ate, agora + 30.0)

    def test_falando_nao_renova_sono_cada_tick(self) -> None:
        cli = MagicMock()
        cli.animation_groups = {"GoToSleepGetIn": None}
        cli.anim_controller = MagicMock()
        tela = MagicMock()
        face = MagicMock()
        vida = CicloVida(tela, face, lambda c: None)
        vida._proxima_fase = time.monotonic() + 3600.0
        with patch.dict(os.environ, {"COZMO_SONO_NA_BASE": "1"}):
            vida.tick(
                cli,
                na_base=True,
                preso_na_base=True,
                falando=True,
                pode_animar=False,
                pode_camera=False,
            )
            t1 = vida._interacao_ate
            for _ in range(10):
                vida.tick(
                    cli,
                    na_base=True,
                    preso_na_base=True,
                    falando=True,
                    pode_animar=False,
                    pode_camera=False,
                )
        self.assertLess(t1 - time.monotonic(), 30.0)
        self.assertEqual(vida._interacao_ate, t1)

    def test_timer_sono_dispara_apos_intervalo(self) -> None:
        cli = MagicMock()
        cli.animation_groups = {"GoToSleepGetIn": None, "Sleeping": None}
        cli.anim_controller = MagicMock()
        tela = MagicMock()
        face = MagicMock()
        vida = CicloVida(tela, face, lambda c: None)
        vida._proxima_fase = time.monotonic() - 1.0
        with patch.dict(
            os.environ,
            {
                "COZMO_SONO_NA_BASE": "1",
                "COZMO_SLEEP_INTERVAL_MIN": "1",
                "COZMO_SLEEP_INTERVAL_JITTER_S": "0",
            },
        ):
            vida.tick(
                cli,
                na_base=True,
                preso_na_base=True,
                falando=False,
                pode_animar=False,
                pode_camera=False,
            )
        self.assertEqual(vida.fase, Fase.SONOLENTO)

    def test_sonolento_entra_dormindo_na_base(self) -> None:
        cli = MagicMock()
        cli.animation_groups = {"GoToSleepGetIn": None, "Sleeping": None}
        cli.anim_controller = MagicMock()
        tela = MagicMock()
        face = MagicMock()
        vida = CicloVida(tela, face, lambda c: None)
        vida.fase = Fase.SONOLENTO
        vida._proxima_fase = time.monotonic() - 1.0
        with patch.dict(
            os.environ,
            {
                "COZMO_SONO_NA_BASE": "1",
                "SONO_TELA_ESCURA": "0",
                "COZMO_SONO_OLED_TEXTO": "0",
            },
        ):
            with patch(
                "cozmo_companion.core.motor_cozmo.entrar_sono_base_oled",
                return_value=True,
            ):
                with patch(
                    "cozmo_companion.core.motor_cozmo.manter_sono_ppclip",
                    return_value=None,
                ):
                    vida.tick(
                        cli,
                        na_base=True,
                        preso_na_base=True,
                        falando=False,
                        pode_animar=True,
                        pode_camera=False,
                    )
        self.assertEqual(vida.fase, Fase.DORMINDO)

    def test_despertar_bloqueia_sono_15min(self):
        cli = MagicMock()
        cli.animation_groups = {"GoToSleepGetOut": None}
        cli.anim_controller = MagicMock()
        tela = MagicMock()
        face = MagicMock()
        vida = CicloVida(tela, face, lambda c: None)
        vida.fase = Fase.DORMINDO
        vida.despertar(cli, motivo="notif")
        self.assertEqual(vida.fase, Fase.ACORDADO)
        agora = time.monotonic()
        self.assertGreaterEqual(vida._interacao_ate, agora + AWAKE_APOS_DESPERTAR - 1.0)

    def test_acordar_usa_getout(self):
        cli = MagicMock()
        cli.animation_groups = {
            "GoToSleepGetOut": None,
            "Surprise": None,
        }
        cli.anim_controller = MagicMock()
        tela = MagicMock()
        face = MagicMock()
        tocadas: list[tuple[str, ...]] = []
        vida = CicloVida(tela, face, lambda c: tocadas.append(c))
        vida.fase = Fase.DORMINDO
        with patch.dict("os.environ", {"COZMO_BASE_OLED_MODE": "anim"}):
            vida._acordar(cli)
        self.assertEqual(vida.fase, Fase.ACORDADO)
        self.assertEqual(len(tocadas), 1)

    def test_acordar_para_voz_sem_sono_nao_crasha(self):
        cli = MagicMock()
        cli.animation_groups = {"Surprise": None}
        cli.anim_controller = MagicMock()
        tela = MagicMock()
        face = MagicMock()
        vida = CicloVida(tela, face, lambda c: None)
        vida.fase = Fase.ACORDADO
        with patch.dict("os.environ", {"COZMO_PROC_FACE_BASE": "1"}):
            vida.acordar_para_voz(cli)
        self.assertEqual(vida.fase, Fase.ACORDADO)

    def test_ronco_durante_sono(self):
        cli = MagicMock()
        cli.animation_groups = {
            "Sleeping": None,
            "Hiccup": None,
        }
        tela = MagicMock()
        face = MagicMock()
        vida = CicloVida(tela, face, lambda c: None)
        vida.fase = Fase.DORMINDO
        vida._proximo_ronco = 0.0
        vida._proximo_loop_sono = 1e12
        import cozmo_companion.core.vida as vida_mod

        old_chance = vida_mod.SONO_RONCO_CHANCE
        vida_mod.SONO_RONCO_CHANCE = 1.0
        try:
            vida._tick_ronco(cli)
        finally:
            vida_mod.SONO_RONCO_CHANCE = old_chance
        cli.play_anim_group.assert_called_with("Hiccup")

    def test_sono_nao_para_ppclip(self) -> None:
        cli = MagicMock()
        cli.animation_groups = {"GoToSleepGetIn": None, "Sleeping": None}
        cli.anim_controller = MagicMock()
        tela = MagicMock()
        face = MagicMock()
        vida = CicloVida(tela, face, lambda c: None)
        with patch.dict(
            os.environ,
            {
                "COZMO_SONO_NA_BASE": "1",
                "SONO_TELA_ESCURA": "0",
                "COZMO_SONO_OLED_TEXTO": "0",
            },
        ):
            with patch(
                "cozmo_companion.core.motor_cozmo.entrar_sono_base_oled",
                return_value=True,
            ) as entrar:
                with patch(
                    "cozmo_companion.core.motor_cozmo.manter_sono_ppclip",
                    return_value=None,
                ):
                    vida._iniciar_sono(cli)
        entrar.assert_called_once_with(cli)
        self.assertEqual(vida.fase, Fase.DORMINDO)
        tela.mostrar.assert_not_called()
        tela = MagicMock()
        face = MagicMock()
        face.iniciar_busca.return_value = False
        vida = CicloVida(tela, face, lambda c: None)
        with patch.dict("os.environ", {"COZMO_FACE_BASE": "0", "SEMPRE_VIVO": "1"}):
            ok = vida.abrir_camera_curta(10.0, na_base=True)
        self.assertFalse(ok)
        face.iniciar_busca.assert_not_called()

    def test_camera_base_janela_curta(self) -> None:
        tela = MagicMock()
        face = MagicMock()
        face.iniciar_busca.return_value = True
        vida = CicloVida(tela, face, lambda c: None)
        with patch.dict("os.environ", {"COZMO_FACE_BASE": "1", "BASE_CAM_ON_MAX_S": "10"}):
            ok = vida.abrir_camera_curta(14.0, na_base=True)
        self.assertTrue(ok)
        face.iniciar_busca.assert_called_once()
        args, _ = face.iniciar_busca.call_args
        self.assertLessEqual(args[0], 10.0)

    def test_falando_nao_reseta_sonolento(self) -> None:
        cli = MagicMock()
        cli.animation_groups = {"GoToSleepGetIn": None}
        cli.anim_controller = MagicMock()
        tela = MagicMock()
        face = MagicMock()
        vida = CicloVida(tela, face, lambda c: None)
        vida.fase = Fase.SONOLENTO
        vida._proxima_fase = time.monotonic() + 120.0
        with patch.dict(os.environ, {"COZMO_SONO_NA_BASE": "1"}):
            vida.tick(
                cli,
                na_base=True,
                preso_na_base=True,
                falando=True,
                pode_animar=False,
                pode_camera=False,
            )
        self.assertEqual(vida.fase, Fase.SONOLENTO)

    def test_anim_base_usa_tocar_callback(self) -> None:
        cli = MagicMock()
        cli.animation_groups = {"CodeLabBlink": None, "NeutralFace": None}
        cli.anim_controller = MagicMock()
        tela = MagicMock()
        face = MagicMock()
        face.buscando = False
        tocadas: list[tuple[str, ...]] = []
        vida = CicloVida(tela, face, lambda c: tocadas.append(c))
        vida.fase = Fase.ACORDADO
        vida._proxima_anim_base = time.monotonic() - 1.0
        with patch.dict(
            os.environ,
            {"BASE_ANIM_CHANCE": "1", "COZMO_SONO_NA_BASE": "0"},
        ):
            with patch("random.random", return_value=0.0):
                vida.tick(
                    cli,
                    na_base=True,
                    preso_na_base=True,
                    falando=False,
                    pode_animar=True,
                )
        self.assertEqual(len(tocadas), 1)

    def test_sonolento_agenda_descanso(self) -> None:
        cli = MagicMock()
        cli.animation_groups = {"CodeLabBlink": None, "GoToSleepGetIn": None}
        cli.anim_controller = MagicMock()
        tela = MagicMock()
        face = MagicMock()
        vida = CicloVida(tela, face, lambda c: None)
        with patch.dict(
            os.environ,
            {"SONOLENTO_MIN_S": "60", "SONOLENTO_MAX_S": "60"},
        ):
            with patch(
                "cozmo_companion.core.motor_cozmo.tocar_clip_base_seguro",
                return_value=True,
            ):
                vida._sonolento(cli, preso_na_base=True)
        self.assertEqual(vida.fase, Fase.SONOLENTO)
        self.assertGreater(vida._proxima_anim_descanso, 0.0)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONPATH", "src")
    unittest.main()
