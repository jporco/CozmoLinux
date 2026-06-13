"""Ponto de entrada: python -m cozmo_companion"""

from __future__ import annotations

import argparse
import logging
import sys

from cozmo_companion.core.companion import executar
from cozmo_companion.core.singleton import adquirir_instancia_unica


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Cozmo companheiro — voz, conversa e carga na base."
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    if not adquirir_instancia_unica():
        return 1

    return executar(log_level="DEBUG" if args.verbose else "INFO")


if __name__ == "__main__":
    sys.exit(main())
