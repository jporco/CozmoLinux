"""Guardian — monitor inteligente do Cozmo Companion."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

from cozmo_companion.guardian.core.health import ler_log
from cozmo_companion.guardian.core.manutencao import manter_logs
from cozmo_companion.guardian.core.policy import EstadoGuardian, decidir, executar

logger = logging.getLogger("cozmo.guardian")


from cozmo_companion.core.paths import install_root

def main() -> int:
    parser = argparse.ArgumentParser(description="Monitor inteligente Cozmo Companion")
    parser.add_argument(
        "--root",
        default=os.environ.get("COZMO_COMPANION_ROOT", str(install_root())),
    )
    parser.add_argument(
        "--intervalo",
        type=float,
        default=float(os.environ.get("GUARDIAN_INTERVAL_S", "20")),
    )
    parser.add_argument(
        "--log",
        default=None,
        help="Arquivo de log do companion",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    root = Path(args.root)
    log_path = Path(args.log or root / "cozmo-companheiro.log")
    guardian_log = root / "guardian.log"

    handler = logging.FileHandler(guardian_log, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")
    )
    logging.getLogger("cozmo.guardian").addHandler(handler)
    logging.getLogger("cozmo.guardian.actions").addHandler(handler)

    estado = EstadoGuardian()
    logger.info(
        "Guardian ativo — root=%s intervalo=%.0fs log=%s",
        root,
        args.intervalo,
        log_path,
    )

    while True:
        try:
            saude = ler_log(log_path)
            acao = decidir(saude, estado, root=root)
            s = saude.sessao
            if s:
                logger.info(
                    "Check: svc=%s ping=%s %.2fV rx=%d ratio=%.1f erros=%d → %s",
                    saude.servico_ativo,
                    "OK" if saude.ping_ok else "FAIL",
                    s.bateria_v,
                    s.rx,
                    s.ratio,
                    saude.erros_recentes,
                    acao.name,
                )
            else:
                logger.info(
                    "Check: svc=%s ping=%s erros=%d → %s",
                    saude.servico_ativo,
                    "OK" if saude.ping_ok else "FAIL",
                    saude.erros_recentes,
                    acao.name,
                )
            executar(acao, root, estado)
            manter_logs(root, estado)
        except Exception as exc:
            logger.error("Guardian erro: %s", exc, exc_info=True)
        time.sleep(args.intervalo)


if __name__ == "__main__":
    sys.exit(main())
