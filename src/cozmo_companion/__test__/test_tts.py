"""Testes do TTS — conversão WAV → Cozmo."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from cozmo_companion.voice.tts import (
    _duracao_pkts,
    _espeak_wav,
    _load_wav,
    _pkts_sinal_sintetico,
    falar,
)


class TestTtsDuracao(unittest.TestCase):
    def test_duracao_30fps(self):
        self.assertAlmostEqual(_duracao_pkts(3), 3 / 30.0 + 0.35, places=2)


class TestTtsSinalSintetico(unittest.TestCase):
    def test_modo_sinal_nao_toca_audio_sintetico_por_padrao(self):
        from unittest.mock import MagicMock, patch

        cli = MagicMock()
        with (
            patch.dict("os.environ", {"TTS_MODO": "sinal", "TTS_SINAL_AUDIO": "0"}, clear=False),
            patch("cozmo_companion.voice.tts._enviar_sinal_udp") as enviar,
        ):
            self.assertEqual(falar(cli, "Oi"), 0)
        enviar.assert_not_called()
    def test_sinal_sintetico_gera_pacotes_cozmo(self):
        pkts = _pkts_sinal_sintetico("Oi")
        self.assertGreaterEqual(len(pkts), 3)
        self.assertTrue(all(len(pkt.samples) == 744 for pkt in pkts))

    def test_sinal_sintetico_nao_e_pacote_constante(self):
        pkt = _pkts_sinal_sintetico("Opa")[0]
        self.assertGreater(len(set(pkt.samples)), 8)


class TestTts(unittest.TestCase):
    def _wav_de(self, texto: str) -> Path:
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        caminho = Path(tmp.name)
        tmp.close()
        subprocess.run(
            ["espeak", "-v", "pt-br", "-s", "150", "-w", str(caminho), texto],
            check=True,
            capture_output=True,
        )
        self.addCleanup(caminho.unlink, missing_ok=True)
        return caminho

    def test_hora_nao_quebra_ulaw(self):
        """Frase de hora gerava byte 256 no PyCozmo original."""
        caminho = self._wav_de("São 2 horas e 30 minutos em Bagé.")
        pkts = _load_wav(caminho)
        self.assertGreater(len(pkts), 0)
        for pkt in pkts:
            self.assertEqual(len(pkt.samples), 744)
            self.assertTrue(all(0 <= b <= 255 for b in pkt.samples))

    def test_temperatura(self):
        caminho = self._wav_de("Em Bagé estão 13 graus agora.")
        pkts = _load_wav(caminho)
        self.assertGreater(len(pkts), 0)

    def test_espeak_wav_curto_nao_vazio(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        caminho = Path(tmp.name)
        tmp.close()
        self.addCleanup(caminho.unlink, missing_ok=True)
        _espeak_wav(caminho, "Oi", "pt-br")
        self.assertGreater(caminho.stat().st_size, 44)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONPATH", "src")
    unittest.main()
