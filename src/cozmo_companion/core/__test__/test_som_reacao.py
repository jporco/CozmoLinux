"""Testes — reacoes sonoras do Cozmo a barulho ambiente."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from cozmo_companion.core import som_reacao
from cozmo_companion.core.companion_voz import CompanionVoz, REACOES_BARULHO


class FakeCompanion(CompanionVoz):
    def __init__(self) -> None:
        self._iniciar_voz()
        self.cli = MagicMock()
        self.volume = 18000
        self._base = MagicMock(preso_na_base=True)
        self._vida = MagicMock()
        self._fila = MagicMock()
        self._monitor_rx = MagicMock()
        self._falando = False
        self._llm_ocupado = False
        self._periodo_quieto_ativo = MagicMock(return_value=False)
        self._na_base_efetivo = MagicMock(return_value=True)
        self._marcar_udp_quieto = MagicMock()


class TestSomReacao(unittest.TestCase):
    def test_pacotes_susto(self) -> None:
        pkts = som_reacao.pacotes_som_reacao("susto")
        self.assertGreaterEqual(len(pkts), 3)
        self.assertTrue(all(getattr(pkt, "samples", b"") for pkt in pkts))

    def test_barulho_chama_som_e_animacao(self) -> None:
        c = FakeCompanion()
        with patch(
            "cozmo_companion.core.som_reacao.tocar_som_reacao",
            return_value=True,
        ) as tocar:
            c._stt_fila.put(("som", "barulho", 6400.0))
            c._processar_stt()
        c._fila.enviar_anim.assert_called_once_with(REACOES_BARULHO, prioridade=True)
        tocar.assert_called_once()
        c._vida.registrar_interacao.assert_called_once()

    def test_latido_texto_dispara_reacao(self) -> None:
        c = FakeCompanion()
        with patch(
            "cozmo_companion.core.som_reacao.tocar_som_reacao",
            return_value=True,
        ) as tocar:
            c._tratar_texto_ouvido("au au")
        tocar.assert_called_once()


if __name__ == "__main__":
    unittest.main()
