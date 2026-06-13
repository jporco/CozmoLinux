#!/usr/bin/env python3
"""Identifica hardware/firmware do Cozmo e indica se OTA é necessário."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAFE_2381 = Path.home() / ".pycozmo/assets/cozmo_resources/config/engine/firmware/cozmo.safe"
ALVO = 2381

# HW5 = fall 2017, botão off, cor 0-3 (doc PyCozmo hardware_versions)


def _ler_assinatura_safe(path: Path) -> dict:
    raw = path.read_bytes()[:1024].decode("utf-8", errors="ignore").rstrip("\0")
    return json.loads(raw)


def main() -> int:
    if subprocess.run(["ping", "-c1", "-W2", "172.31.1.1"], capture_output=True).returncode != 0:
        print("FAIL: Cozmo inalcançável (172.31.1.1)")
        return 1

    import pycozmo

    cli = pycozmo.Client(enable_procedural_face=False)
    cli.start()
    try:
        cli.connect()
        cli.wait_for_robot(timeout=30)
        sig = cli.robot_fw_sig or {}
        ver = int(sig.get("version", 0))
        hw = cli.body_hw_version
        sn = cli.serial_number
        cor = getattr(cli.body_color, "value", cli.body_color)
    finally:
        try:
            cli.disconnect()
            cli.stop()
        except Exception:
            pass

    print("=== Cozmo — identificação ===")
    print(f"Body HW version : {hw}  (5 = produção 2017, botão off)")
    print(f"Body S/N        : 0x{sn:08x}" if sn else "Body S/N        : ?")
    print(f"Cor             : {cor}")
    print(f"Firmware atual  : {ver}  ({sig.get('date', '?')})")
    print(f"PyCozmo alvo    : {ALVO}")

    if SAFE_2381.is_file():
        alvo_sig = _ler_assinatura_safe(SAFE_2381)
        bate = sig.get("bodySig") == alvo_sig.get("bodySig") and ver == ALVO
        print(f"Assinatura body : {'OK (2381 oficial)' if bate else 'DIVERGENTE'}")
    else:
        print(f"Arquivo .safe   : não encontrado em {SAFE_2381}")
        print("  Rode: pycozmo_resources.py download")

    if hw not in (4, 5, 6, 7):
        print("\nAVISO: HW desconhecido — não atualizar OTA sem confirmar modelo.")
        return 2

    if ver == ALVO:
        print("\nConclusão: firmware já é a versão adequada para HW5 + PyCozmo.")
        print("Travamentos/COZMO 01 são sessão UDP no PC — não precisa reflash.")
        return 0

    if ver > 10000:
        print("\nAVISO: firmware de fábrica/recovery detectado.")
        print(f"Recomendado: OTA para v{ALVO} com pycozmo_update.py")
        return 3

    if ver < ALVO:
        print(f"\nFirmware antigo (v{ver}). Pode atualizar para v{ALVO}.")
        print(f"  systemctl --user stop cozmo-companion")
        print(f"  pycozmo_update.py {SAFE_2381}")
        return 3

    print(f"\nFirmware v{ver} >= alvo — sem ação.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
