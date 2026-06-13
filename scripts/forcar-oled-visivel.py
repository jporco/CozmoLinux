#!/usr/bin/env python3
"""Teste OLED direto no Cozmo — pare o companion antes (systemctl stop)."""
from __future__ import annotations

import os
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


def main() -> int:
    from cozmo_companion.core.conexao import abrir_cliente, diagnostico, fechar_cliente
    from cozmo_companion.core.motor_cozmo import (
        _exibir_clip_base,
        _frames_clip_oled,
        _handshake_frame_oled,
        _pool_oled_com_frames,
    )
    from cozmo_companion.display.rosto import pkt_rosto_procedural

    print("Conectando (companion deve estar PARADO)...")
    cli = abrir_cliente(log_level="WARNING", protocol_log_level="ERROR", robot_log_level="ERROR")
    try:
        cli.load_anims()
        from cozmo_companion.core.anim_base_patch import instalar_play_anim_sem_rodas_na_base
        from cozmo_companion.core.charger import definir_oled_preso_na_base

        instalar_play_anim_sem_rodas_na_base(cli, preso_na_base_fn=lambda: True)
        definir_oled_preso_na_base(True)

        from cozmo_companion.core.anims import pool_variacao_oled_base

        disp = set(cli.animation_groups.keys())
        pool = _pool_oled_com_frames(cli, pool_variacao_oled_base(disp, cli))
        print(f"Pool OLED ({len(pool)}): {', '.join(pool[:8])}")

        d0 = diagnostico(cli)
        print(f"rx={d0['recv_frames']} tx={d0['sent_frames']}")

        print("Fase 1: rosto procedural 8s (olhos devem aparecer)...")
        ac = cli.anim_controller
        for i in range(24):
            pkt = pkt_rosto_procedural(cli)
            if i == 0:
                _handshake_frame_oled(cli, force=True)
            cli.conn.send(pkt)
            ac.last_image_pkt = pkt
            time.sleep(0.33)
        d1 = diagnostico(cli)
        print(f"  procedural tx+={d1['sent_frames'] - d0['sent_frames']}")

        print("Fase 2: clips oficiais (sem rodas)...")
        for nome in pool[:4]:
            n = len(_frames_clip_oled(cli, nome))
            print(f"  → {nome} ({n} frames)")
            _exibir_clip_base(cli, nome, forcar=True)
            time.sleep(max(6.0, min(14.0, n * 0.12)))
        d2 = diagnostico(cli)
        drx = d2["recv_frames"] - d1["recv_frames"]
        dtx = d2["sent_frames"] - d1["sent_frames"]
        print(f"rx+={drx} tx+={dtx} ratio={dtx / max(drx, 1):.2f}")
        if dtx < 20:
            print("FAIL: quase nenhum TX — link morto?")
            return 2
        print("OK software — se tela continua preta, é firmware/hardware (COZMO 01).")
        return 0
    finally:
        fechar_cliente(cli, pausa=0.5)


if __name__ == "__main__":
    raise SystemExit(main())
