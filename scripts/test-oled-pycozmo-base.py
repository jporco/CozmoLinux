#!/usr/bin/env python3
"""Teste OLED na base — API oficial PyCozmo (overview + examples/anim.py).

Uso (Cozmo ligado e na base):
  cd /mnt/G/PROJETOS/cozmo-companion
  .venv/bin/python scripts/test-oled-pycozmo-base.py --modo clip
  .venv/bin/python scripts/test-oled-pycozmo-base.py --modo proc
  .venv/bin/python scripts/test-oled-pycozmo-base.py --modo keeper

Modos:
  clip   — play_anim_group (30fps, igual examples/anim.py)
  proc   — enable_procedural_face (AnimationController 30fps)
  keeper — frames do clip a ~8Hz (companheiro na base 100%%, baixo UDP)
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import pycozmo
from pycozmo import event, protocol_encoder, robot

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

CLIP_BASE = os.environ.get(
    "COZMO_CHARGER_AWAKE_IDLE", "InteractWithFaceTrackingIdle"
)
KEEPER_HZ = float(os.environ.get("COZMO_BASE_FULL_KEEPER_HZ", "8"))


def _head_neutro(cli: pycozmo.Client) -> None:
    angle = (robot.MAX_HEAD_ANGLE.radians - robot.MIN_HEAD_ANGLE.radians) / 2.0
    cli.set_head_angle(angle)


def modo_clip(cli: pycozmo.Client, grupo: str, segundos: float) -> None:
    # Este script e exclusivo para uso na base. Clips oficiais tambem contem
    # keyframes de rodas/lift; sem o patch o teste pode tirar o Cozmo do dock.
    from cozmo_companion.core.anim_base_patch import (
        instalar_play_anim_sem_rodas_na_base,
    )

    cli.load_anims()
    instalar_play_anim_sem_rodas_na_base(cli, preso_na_base_fn=lambda: True)
    cli.enable_procedural_face(False)
    cli.enable_animations(True)
    print(f"play_anim_group({grupo!r}) — 30fps, corpo imobilizado na base")
    cli.play_anim_group(grupo)
    time.sleep(segundos)


def modo_proc(cli: pycozmo.Client, segundos: float) -> None:
    cli.enable_animations(True)
    cli.enable_procedural_face(True)
    print("enable_procedural_face(True) — rosto procedural 30fps")
    time.sleep(segundos)


def modo_keeper(cli: pycozmo.Client, grupo: str, segundos: float) -> None:
    from cozmo_companion.core.motor_cozmo import (
        _frames_clip_oled,
        _handshake_oled_base,
        _iniciar_display_keeper,
        parar_flood_anim,
    )

    cli.load_anims()
    parar_flood_anim(cli)
    _handshake_oled_base(cli)
    frames = _frames_clip_oled(cli, grupo)
    print(f"keeper clip {grupo!r}: {len(frames)} frames @ {KEEPER_HZ} Hz")
    _iniciar_display_keeper(cli, KEEPER_HZ, grupo=grupo)
    time.sleep(segundos)


def main() -> None:
    ap = argparse.ArgumentParser(description="Teste OLED base — PyCozmo oficial")
    ap.add_argument(
        "--modo",
        choices=("clip", "proc", "keeper"),
        default="keeper",
        help="clip=play_anim_group, proc=procedural, keeper=throttle HW5",
    )
    ap.add_argument("--grupo", default=CLIP_BASE)
    ap.add_argument("--segundos", type=float, default=45.0)
    args = ap.parse_args()

    print("Conectando (pycozmo.connect)…")
    with pycozmo.connect(enable_procedural_face=False) as cli:
        _head_neutro(cli)
        time.sleep(0.5)
        v = cli.battery_voltage
        st = cli.robot_status
        print(f"bateria={v:.2f}V status=0x{st:04x}")

        if args.modo == "clip":
            modo_clip(cli, args.grupo, args.segundos)
        elif args.modo == "proc":
            modo_proc(cli, args.segundos)
        else:
            modo_keeper(cli, args.grupo, args.segundos)

    print("OK")


if __name__ == "__main__":
    main()
