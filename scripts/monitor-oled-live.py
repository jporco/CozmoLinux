#!/usr/bin/env python3
"""Monitor leve do OLED/base.

Grava JSONL com saúde, últimos eventos críticos e capturas opcionais da webcam.
Uso:
  scripts/monitor-oled-live.py --duration 900 --interval 10 --webcam
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HEALTH = ROOT / "data" / "cozmo-saude.json"
LOG = ROOT / "cozmo-companheiro.log"
OUT = ROOT / "outputs" / "oled-monitor"

PATTERNS = (
    "COZMO 01",
    "rx=STALL",
    "Base OLED",
    "OLED adaptativo",
    "resgate visual",
    "tela",
    "keeper",
    "clip oficial",
)


def read_health() -> dict:
    try:
        return json.loads(HEALTH.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"error": f"health: {exc}"}


def tail_events(max_lines: int = 900, keep: int = 16) -> list[str]:
    try:
        lines = LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-max_lines:]
    except Exception as exc:
        return [f"log: {exc}"]
    hits = [line for line in lines if any(p in line for p in PATTERNS)]
    return hits[-keep:]


def capture_webcam(path: Path) -> bool:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "v4l2",
        "-video_size",
        "640x480",
        "-i",
        "/dev/video0",
        "-frames:v",
        "1",
        str(path),
    ]
    return subprocess.run(cmd, cwd=ROOT).returncode == 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=int, default=900)
    ap.add_argument("--interval", type=float, default=10.0)
    ap.add_argument("--webcam", action="store_true")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    started = datetime.now().strftime("%Y%m%d-%H%M%S")
    jsonl = OUT / f"oled-monitor-{started}.jsonl"
    end = time.monotonic() + max(1, args.duration)
    i = 0
    while time.monotonic() < end:
        ts = datetime.now().isoformat(timespec="seconds")
        frame = None
        if args.webcam:
            frame_path = OUT / f"frame-{started}-{i:04d}.jpg"
            if capture_webcam(frame_path):
                frame = str(frame_path)
        rec = {
            "ts": ts,
            "health": read_health(),
            "events": tail_events(),
            "webcam": frame,
        }
        with jsonl.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(json.dumps(rec, ensure_ascii=False))
        i += 1
        time.sleep(max(1.0, args.interval))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
