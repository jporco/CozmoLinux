#!/usr/bin/env python3
"""Probe OLED na base — play_anim + keeper; confirma frames no robô."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# config.env
cfg = ROOT / "config.env"
if cfg.exists():
    for line in cfg.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


def main() -> int:
    from cozmo_companion.core.conexao import abrir_cliente, diagnostico, fechar_cliente
    from cozmo_companion.core.motor_cozmo import (
        _frames_clip_oled,
        ligar_oled_base,
        modo_charger_oled,
        variar_clip_base_oled,
    )

    print("Conectando Cozmo...")
    cli = abrir_cliente(log_level="WARNING", protocol_log_level="ERROR", robot_log_level="ERROR")
    try:
        cli.load_anims()
        from cozmo_companion.core.anim_base_patch import instalar_play_anim_sem_rodas_na_base
        from cozmo_companion.core.charger import definir_oled_preso_na_base

        instalar_play_anim_sem_rodas_na_base(cli, preso_na_base_fn=lambda: True)
        definir_oled_preso_na_base(True)

        d0 = diagnostico(cli)
        print(f"rx={d0['recv_frames']} tx={d0['sent_frames']} V={cli.battery_voltage:.2f}")

        ok = modo_charger_oled(cli, forcar=True)
        print(f"modo_charger_oled: {ok}")
        time.sleep(4.0)
        d1 = diagnostico(cli)
        print(f"após boot OLED rx={d1['recv_frames']} tx={d1['sent_frames']}")

        for nome in ("IdleOnCharger", "NeutralFace", "CodeLabBlink"):
            n = len(_frames_clip_oled(cli, nome))
            print(f"  frames OLED {nome}: {n}")

        time.sleep(2.0)
        if variar_clip_base_oled(cli, forcado=True):
            print("variar_clip: OK")
        time.sleep(5.0)
        d2 = diagnostico(cli)
        drx = d2["recv_frames"] - d1["recv_frames"]
        dtx = d2["sent_frames"] - d1["sent_frames"]
        print(f"após variar drx={drx} dtx={dtx} ratio={d2['sent_frames']/max(d2['recv_frames'],1):.2f}")
        if drx < 5 and dtx > 80:
            print("WARN: muito TX pouco RX — risco COZMO 01")
            return 2
        print("OK: link respondeu")
        return 0
    finally:
        fechar_cliente(cli, pausa=0.5)


if __name__ == "__main__":
    raise SystemExit(main())
