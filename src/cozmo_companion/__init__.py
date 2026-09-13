"""Cozmo companion — PC cérebro, Cozmo executor via fila serial."""

from pathlib import Path


def _ler_versao() -> str:
    try:
        return (Path(__file__).resolve().parents[2] / "VERSION").read_text().strip()
    except OSError:
        return "3.1.0"


__version__ = _ler_versao()
