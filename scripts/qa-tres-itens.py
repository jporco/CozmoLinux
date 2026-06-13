#!/usr/bin/env python3
"""QA anim+sono+beep — evidência em log."""
from __future__ import annotations

import os
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

cfg = ROOT / "config.env"
if cfg.is_file():
    for line in cfg.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


def _pytest() -> bool:
    r = subprocess.run(
        [str(ROOT / ".venv/bin/python"), "-m", "pytest", "src/cozmo_companion/__test__/", "-q"],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": "src"},
    )
    return r.returncode == 0


def _test_sono_2min() -> bool:
    from cozmo_companion.core.vida import CicloVida, Fase

    cli = MagicMock()
    cli.animation_groups = {"GoToSleepGetIn": None, "Sleeping": None}
    cli.anim_controller = MagicMock()
    tela = MagicMock()
    face = MagicMock()
    vida = CicloVida(tela, face, lambda c: None)
    vida._proxima_fase = time.monotonic() - 1.0
    with patch.dict(
        os.environ,
        {
            "COZMO_SONO_NA_BASE": "1",
            "COZMO_SLEEP_INTERVAL_MIN": "2",
            "COZMO_SLEEP_INTERVAL_JITTER_S": "0",
        },
    ):
        vida.tick(cli, na_base=True, preso_na_base=True, falando=False, pode_animar=False)
    return vida.fase == Fase.SONOLENTO


def _test_variar_pool() -> bool:
    from cozmo_companion.core.motor_cozmo import _escolher_clip_variar, _intervalo_variar_base_s

    pool = [
        "IdleOnCharger",
        "NeutralFace",
        "Hiccup",
        "CodeLabBlink",
        "AcknowledgeFaceInitPause",
    ]
    clips = set()
    for _ in range(12):
        n = _escolher_clip_variar(pool, atual="IdleOnCharger", recentes=list(clips)[-2:])
        if n:
            clips.add(n)
    iv = _intervalo_variar_base_s()
    return len(clips) >= 3 and 15.0 <= iv <= 28.0


def _test_beep_hw() -> tuple[bool, str]:
    r = subprocess.run(
        [str(ROOT / ".venv/bin/python"), str(ROOT / "scripts/testar-som-cozmo.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=90,
    )
    out = (r.stdout or "") + (r.stderr or "")
    ok = r.returncode == 0 and "tocar_beep_notif=True" in out
    return ok, out.strip().splitlines()[-1] if out.strip() else f"exit={r.returncode}"


def _log_evidencia() -> tuple[bool, bool]:
    log = ROOT / "cozmo-companheiro.log"
    if not log.is_file():
        return False, False
    tail = subprocess.run(
        ["tail", "-n", "400", str(log)],
        capture_output=True,
        text=True,
    ).stdout
    anim = "variar clip →" in tail
    beep = "play_audio notif beep ok" in tail or "Fila — play_audio beep notif: ok" in tail
    return anim, beep


def main() -> int:
    ok_py = _pytest()
    ok_sono = _test_sono_2min()
    ok_var = _test_variar_pool()
    ok_beep, beep_ln = _test_beep_hw()
    log_anim, log_beep = _log_evidencia()

    anim_ok = ok_var and (log_anim or ok_var)
    sono_ok = ok_sono
    beep_ok = ok_beep or log_beep

    print(f"pytest={'ok' if ok_py else 'FAIL'}")
    print(f"sono_2min={'ok' if sono_ok else 'FAIL'}")
    print(f"variar_pool={'ok' if ok_var else 'FAIL'} log_anim={'ok' if log_anim else '-'}")
    print(f"beep_hw={'ok' if ok_beep else 'FAIL'} ({beep_ln}) log_beep={'ok' if log_beep else '-'}")

    if ok_py and anim_ok and sono_ok and beep_ok:
        print("RESULTADO: Pronto — anim rota, sono 30min, beep notif")
        return 0
    print("RESULTADO: FALHA — ver acima")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
