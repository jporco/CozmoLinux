#!/usr/bin/env python3
"""QA OLED na base — ping, liga keeper, observa variar clip no log."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "cozmo-companheiro.log"
IP = os.environ.get("COZMO_IP", "172.31.1.1")


def ping_ok() -> bool:
    r = subprocess.run(
        ["ping", "-c", "1", "-W", "2", IP],
        capture_output=True,
    )
    return r.returncode == 0


def tail_log(marker: str, since_pos: int) -> list[str]:
    if not LOG.exists():
        return []
    data = LOG.read_text(errors="replace")
    lines = data[since_pos:].splitlines()
    return [ln for ln in lines if marker in ln]


def main() -> int:
    os.chdir(ROOT)
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))

    if not ping_ok():
        print(f"FAIL: Cozmo {IP} sem ping — ligue Wi-Fi/base")
        return 2

    pos = LOG.stat().st_size if LOG.exists() else 0
    print(f"OK: ping {IP}")
    print("Aguardando 90s — keeper + variar clip no log...")
    fim = time.time() + 90.0
    variar: list[str] = []
    keeper: list[str] = []
    erros: list[str] = []
    while time.time() < fim:
        chunk = LOG.read_text(errors="replace")[pos:] if LOG.exists() else ""
        pos = LOG.stat().st_size if LOG.exists() else 0
        for ln in chunk.splitlines():
            if "RecursionError" in ln or "maximum recursion" in ln:
                erros.append(ln)
            if "variar clip" in ln:
                variar.append(ln)
            if (
                "clip oficial" in ln
                or "keeper clip" in ln
                or "Base OLED: keeper" in ln
                or "Base OLED: vivo" in ln
            ):
                keeper.append(ln)
        time.sleep(5.0)

    if erros:
        print("FAIL: RecursionError no log:")
        for e in erros[-3:]:
            print(" ", e)
        return 1
    if not keeper:
        print("WARN: sem linha keeper — companion rodando?")
    if len(variar) < 1:
        print("WARN: sem 'variar clip' em 90s (intervalo COZMO_BASE_VARIAR_S)")
    else:
        clips = re.findall(r"variar clip → (\S+)", "\n".join(variar))
        print(f"OK: {len(variar)} variações — clips: {', '.join(dict.fromkeys(clips))}")
    if keeper:
        print("OK: keeper:", keeper[-1][-120:])
    return 0 if not erros and (keeper or variar) else 3


if __name__ == "__main__":
    raise SystemExit(main())
