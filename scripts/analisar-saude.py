#!/usr/bin/env python3
"""Pass/fail rápido: saúde JSON + trecho do log + debug trace."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "cozmo-companheiro.log"
SAUDE = ROOT / "data" / "cozmo-saude.json"
DEBUG = ROOT / ".cursor" / "debug-5e34e1.log"
REL = ROOT / "data" / "qa-relatorio.json"

FALHAS = (
    "COZMO 01 persistente",
    "Recuperação in-place falhou",
    "sem resposta UDP",
    "Link UDP congelado",
)
VERMELHO_RX_OK = re.compile(r'"fase": "vermelho".*"rx_ok": true', re.DOTALL)


def tail_lines(path: Path, n: int = 30) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return lines[-n:]
    except OSError:
        return []


def analisar(minutos_log: int = 25) -> dict:
    saude = {}
    try:
        saude = json.loads(SAUDE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass

    log_tail = tail_lines(LOG, 400)
    recent = []
    if log_tail:
        last_ts = None
        for ln in reversed(log_tail):
            if len(recent) >= 80:
                break
            recent.append(ln)
            m = re.match(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2})", ln)
            if m:
                last_ts = m.group(1)
        recent.reverse()

    falhas_log = [f for f in FALHAS if any(f in ln for ln in recent)]
    cozmo01 = [ln for ln in recent if "COZMO 01" in ln][-20:]
    carinho = [ln for ln in recent if "Carinho na cabeça" in ln][-5:]
    recon = [ln for ln in recent if "Reconexão UDP" in ln][-10:]

    dbg_bad = []
    try:
        dbg_lines = DEBUG.read_text(encoding="utf-8", errors="replace").splitlines()[-200:]
        dbg_bad = [
            ln
            for ln in dbg_lines
            if VERMELHO_RX_OK.search(ln)
        ][-5:]
    except OSError:
        pass

    rx = int(saude.get("rx") or 0)
    drx = int(saude.get("drx", -1))
    ratio = float(saude.get("ratio_janela", saude.get("ratio_acum") or 0))
    rx_ok = saude.get("rx_ok")
    fase = saude.get("fase", "?")

    if drx > 0:
        ok_ratio = 0.35 <= ratio <= 2.2
    else:
        ok_ratio = float(saude.get("ratio_acum") or 0) < 12
    ok = (
        not falhas_log
        and not dbg_bad
        and rx_ok is not False
        and (ok_ratio or fase in ("verde", "amarelo", "laranja"))
    )

    qa = {}
    try:
        qa = json.loads(REL.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass

    return {
        "pass": ok,
        "saude": saude,
        "falhas_log": falhas_log,
        "cozmo01_ultimas": cozmo01,
        "carinho": carinho,
        "reconexoes": recon,
        "vermelho_rx_ok_debug": dbg_bad,
        "qa_rodadas": len(qa.get("rodadas", [])),
        "qa_ultima_ok": (qa.get("ultima") or {}).get("ok"),
    }


def main() -> int:
    r = analisar()
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0 if r["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
