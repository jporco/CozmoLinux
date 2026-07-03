#!/usr/bin/env python3
"""Deploy dos módulos v3.0.0 solicitados."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "cozmo_companion"

MODULES: dict[str, str] = {}

MODULES["__init__.py"] = '''"""Cozmo companion — PC cérebro, Cozmo executor via fila serial."""

__version__ = "3.0.0"
'''

MODULES["core/__init__.py"] = ""

# NOTE: remaining modules appended below in deploy run

def write_all(extra: dict[str, str]) -> list[str]:
    written: list[str] = []
    all_modules = {**MODULES, **extra}
    for rel, content in all_modules.items():
        path = ROOT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(str(path))
    return written

if __name__ == "__main__":
    print("Use deploy_modules_data.py")
