"""Testes do helper de espera do QA automático."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "qa-ate-passar.py"


def _load_qa():
    spec = importlib.util.spec_from_file_location("qa_ate_passar", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class TestAguardarResposta(unittest.TestCase):
    def test_encontra_padrao_no_log(self) -> None:
        qa = _load_qa()
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "cozmo.log"
            voz = Path(tmp) / "voz.cmd"
            qa.LOG = log
            qa.VOZ = voz
            log.write_text("boot\n", encoding="utf-8")
            off = qa.log_offset()

            def escrever_depois() -> None:
                time.sleep(0.6)
                voz.unlink(missing_ok=True)
                with log.open("a", encoding="utf-8") as f:
                    f.write("Util tela: que horas são → 12:00\n")
                    f.write("Sinal: Hora | tela: 12:00\n")

            import threading

            voz.write_text("cozmo que horas são\n", encoding="utf-8")
            threading.Thread(target=escrever_depois, daemon=True).start()
            trecho = qa.aguardar_resposta(off, ("Util tela", "Sinal: Hora"), 3.0)
            self.assertIn("Sinal: Hora", trecho)


if __name__ == "__main__":
    unittest.main()
