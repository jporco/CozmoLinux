#!/usr/bin/env python3
"""Grava módulos v3.0.0 no disco real (/mnt/G)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "cozmo_companion"


def w(rel: str, content: str) -> None:
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"wrote {rel} ({len(content)} bytes)")


def main() -> None:
    w("__init__.py", '"""Cozmo companion — PC cérebro, Cozmo executor via fila serial."""\n\n__version__ = "3.0.0"\n')
    w("core/__init__.py", "")
    w(
        "display/__init__.py",
        '''"""Display OLED e rosto procedural."""

from cozmo_companion.display.face import Tela, texto_para_pkt
from cozmo_companion.display.rosto import RostoProcedural, modo_base_olhos

__all__ = ("Tela", "texto_para_pkt", "RostoProcedural", "modo_base_olhos")
''',
    )
    w(
        "voice/__init__.py",
        '''"""Voz — wake, intent, sinal TTS."""

from cozmo_companion.voice.intent import parece_carinho, parece_hora, parece_temp
from cozmo_companion.voice.sinal import audio_na_base, sinal_para
from cozmo_companion.voice.wake import WakeWord, contem_wake, extrair_pergunta

__all__ = (
    "WakeWord",
    "audio_na_base",
    "contem_wake",
    "extrair_pergunta",
    "parece_carinho",
    "parece_hora",
    "parece_temp",
    "sinal_para",
)
''',
    )
    print("Run with module bodies loaded from co-located .src files or extend script.")


if __name__ == "__main__":
    main()
