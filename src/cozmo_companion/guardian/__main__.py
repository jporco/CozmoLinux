"""Guardian — monitor inteligente do Cozmo Companion."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

from cozmo_companion.guardian.core.health import ler_saude
from cozmo_companion.guardian.core.manutencao import manter_logs
from cozmo_companion.guardian.core.policy import EstadoGuardian, decidir, executar

logger = logging.getLogger("cozmo.guardian")


def _configurar_logging(*, verbose: bool, guardian_log: Path) -> None:
    nivel = logging.DEBUG if verbose else logging.INFO
    formato = logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")
    logging.basicConfig(level=nivel, format=formato._fmt)

    # No systemd, stdout/stderr ja sao anexados em guardian.log pelo unit.
    # Adicionar FileHandler nesse caso duplica cada linha.
    if os.environ.get("INVOCATION_ID"):
        return

    handler = logging.FileHandler(guardian_log, encoding="utf-8")
    handler.setFormatter(formato)
    guardian_logger = logging.getLogger("cozmo.guardian")
    if not any(
        isinstance(h, logging.FileHandler)
        and Path(getattr(h, "baseFilename", "")) == guardian_log
        for h in guardian_logger.handlers
    ):
        guardian_logger.addHandler(handler)


def main() -> int:
    parser = argparse.ArgumentParser(description="Monitor inteligente Cozmo Companion")
    parser.add_argument(
        "--root",
        default=os.environ.get(
            "COZMO_COMPANION_ROOT", "/mnt/G/PROJETOS/cozmo-companion"
        ),
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

    root = Path(args.root)
    log_path = Path(args.log or root / "cozmo-companheiro.log")
    guardian_log = root / "guardian.log"

    _configurar_logging(verbose=args.verbose, guardian_log=guardian_log)

    estado = EstadoGuardian()
    logger.info(
        "Guardian ativo — root=%s intervalo=%.0fs log=%s",
        root,
        args.intervalo,
        log_path,
    )

    while True:
        try:
            saude = ler_saude(root, log_path)
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
