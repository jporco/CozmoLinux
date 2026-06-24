#!/usr/bin/env python3
"""Atalho legado — usa o módulo cozmo_companion."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from cozmo_companion.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
