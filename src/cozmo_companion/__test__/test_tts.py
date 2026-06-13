"""Testes do TTS — conversão WAV → Cozmo."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from cozmo_companion.voice.tts import _duracao_pkts, _load_wav


class TestTtsDuracao(unittest.TestCase):
    def test_duracao_30fps(self):
        self.assertAlmostEqual(_duracao_pkts(3), 3 / 30.0 + 0.35, places=2)


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


if __name__ == "__main__":
    os.environ.setdefault("PYTHONPATH", "src")
    unittest.main()
