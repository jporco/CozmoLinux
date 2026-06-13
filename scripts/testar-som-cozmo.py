#!/usr/bin/env python3
"""Teste isolado — beep OutputAudio no Cozmo (notificação)."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

cfg = ROOT / "config.env"
if cfg.exists():
    for line in cfg.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


def _ping_cozmo() -> bool:
    r = subprocess.run(
        ["ping", "-c", "1", "-W", "2", "172.31.1.1"],
        capture_output=True,
        text=True,
    )
    return r.returncode == 0


def main() -> int:
    if not _ping_cozmo():
        print("BLOQUEIO: Cozmo offline (ping 172.31.1.1 falhou)")
        return 3

    from cozmo_companion.core.conexao import abrir_cliente, diagnostico, fechar_cliente
    from cozmo_companion.notifications.core.som import pacotes_beep_notif, tocar_beep_notif

    n = len(pacotes_beep_notif())
    print(f"Pacotes beep: {n}")
    print("Conectando Cozmo...")
    cli = abrir_cliente(log_level="WARNING", protocol_log_level="ERROR", robot_log_level="ERROR")
    try:
        cli.load_anims()
        from cozmo_companion.core.anim_base_patch import instalar_play_anim_sem_rodas_na_base
        from cozmo_companion.core.charger import definir_oled_preso_na_base

        instalar_play_anim_sem_rodas_na_base(cli, preso_na_base_fn=lambda: True)
        definir_oled_preso_na_base(True)

        d0 = diagnostico(cli)
        print(f"rx={d0['recv_frames']} tx={d0['sent_frames']}")

        vol = int(os.environ.get("COZMO_VOLUME", "49500"))
        try:
            cli.set_volume(vol)
        except Exception:
            pass
        ok = tocar_beep_notif(cli, manter_face=True, volume=vol)
        time.sleep(0.5)
        d1 = diagnostico(cli)
        dtx = d1["sent_frames"] - d0["sent_frames"]
        print(f"tocar_beep_notif={ok} dtx={dtx} vol={vol}")
        if not ok:
            return 2
        if dtx < 2:
            print("WARN: pouco TX — áudio pode não ter saído")
            return 2
        print("OK: som enviado (ouça no robô)")
        return 0
    finally:
        fechar_cliente(cli, pausa=0.5)


if __name__ == "__main__":
    raise SystemExit(main())
