#!/usr/bin/env python3
"""Probe read-only da sessão Cozmo — diagnóstico + stall RX (duas amostras)."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.chdir(ROOT)

# Carrega config do projeto
for name in ("config.env", "config.guardian.env"):
    p = ROOT / name
    if p.is_file():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

from cozmo_companion.core.conexao import (  # noqa: E402
    MonitorRx,
    cozmo_alcanavel,
    diagnostico,
    ratio_udp,
    sessao_viva,
)


def _amostra(cli, rx: MonitorRx, label: str) -> dict:
    d = diagnostico(cli)
    ok = rx.tick(cli)
    r = ratio_udp(cli)
    out = {
        "label": label,
        "rx": d["recv_frames"],
        "tx": d["sent_frames"],
        "ratio": round(r, 3),
        "rx_ok": ok,
        "bateria": round(d["bateria_v"], 2),
        "status": d["status"],
        "vivo": sessao_viva(cli),
    }
    print(
        f"[{label}] rx={out['rx']} tx={out['tx']} ratio={out['ratio']} "
        f"rx_ok={out['rx_ok']} V={out['bateria']} status={out['status']}"
    )
    return out


def main() -> int:
    if not cozmo_alcanavel():
        print("FAIL: ping 172.31.1.1")
        return 1

    from pycozmo import client as cozmo_client

    print("Conectando (probe read-only)...")
    cli = cozmo_client.Client(enable_procedural_face=True)
    try:
        cli.start()
        cli.connect()
        cli.wait_for_robot(timeout=25)
    except Exception as exc:
        print(f"FAIL connect: {exc}")
        return 2

    rx = MonitorRx()
    rx.sincronizar(cli)
    a1 = _amostra(cli, rx, "t0")
    intervalo = float(os.environ.get("COZMO_PROBE_INTERVAL_S", "15"))
    print(f"Aguardando {intervalo:.0f}s...")
    time.sleep(intervalo)
    a2 = _amostra(cli, rx, f"t+{intervalo:.0f}s")

    drx = a2["rx"] - a1["rx"]
    dtx = a2["tx"] - a1["tx"]
    print(f"Delta: drx={drx} dtx={dtx}")
    if drx == 0 and dtx > int(os.environ.get("GOV_TX_DELTA_STALL", "100")):
        print("ALERTA: RX parado com TX subindo — stall real (não idle saudável)")
    elif drx > 0:
        print("OK: RX ainda incrementa — link vivo")
    else:
        print("INFO: RX parado, TX baixo — idle na base (esperado)")

    try:
        cli.disconnect()
        cli.stop()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
