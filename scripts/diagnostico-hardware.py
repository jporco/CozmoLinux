#!/usr/bin/env python3
"""Diagnóstico somente leitura: Wi-Fi, UDP, serviço e sensores registrados."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ROBOT_IP = os.environ.get("COZMO_IP", "172.31.1.1")
WIFI_IFACE = os.environ.get("COZMO_WIFI_IFACE", "wlan0")
LOG = ROOT / "cozmo-companheiro.log"


def _health_file() -> Path:
    raw = os.environ.get("COZMO_HEALTH_FILE", "").strip()
    if not raw:
        try:
            for line in (ROOT / "config.env").read_text(encoding="utf-8").splitlines():
                if line.startswith("COZMO_HEALTH_FILE="):
                    raw = line.split("=", 1)[1].strip()
                    break
        except OSError:
            pass
    return Path(raw).expanduser() if raw else ROOT / "data" / "cozmo-saude.json"


SAUDE = _health_file()


def _run(cmd: list[str], timeout: float = 5.0) -> dict[str, Any]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {
            "ok": r.returncode == 0,
            "code": r.returncode,
            "out": (r.stdout or "").strip()[-1200:],
            "err": (r.stderr or "").strip()[-800:],
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "code": None, "out": "", "err": str(exc)}


def _json_file(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _wifi() -> dict[str, Any]:
    dev = _run(
        ["nmcli", "-t", "-f", "GENERAL.STATE,GENERAL.CONNECTION", "dev", "show", WIFI_IFACE],
        timeout=4,
    )
    aps = _run(["nmcli", "-t", "-f", "SSID,SIGNAL", "dev", "wifi", "list"], timeout=8)
    cozmo_aps = []
    for line in aps.get("out", "").splitlines():
        if line.upper().startswith("COZMO_"):
            ssid, _, signal = line.partition(":")
            cozmo_aps.append({"ssid": ssid, "signal": signal})
    return {
        "iface": WIFI_IFACE,
        "device": dev,
        "route": _run(["ip", "route", "get", ROBOT_IP], timeout=3),
        "ping": _run(["ping", "-c", "1", "-W", "2", ROBOT_IP], timeout=4),
        "cozmo_aps": cozmo_aps,
    }


def _log_tail() -> dict[str, Any]:
    try:
        lines = LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-400:]
    except OSError:
        return {"exists": False}
    red = [l for l in lines if "Governador fase=vermelho" in l][-5:]
    resets = [l for l in lines if "reset UDP" in l or "COZMO 01" in l][-8:]
    notif = [l for l in lines if "Notificação" in l or "play_audio notif" in l][-8:]
    return {
        "exists": True,
        "last_red": red,
        "last_recovery": resets,
        "last_notifications": notif,
    }


def _service() -> dict[str, Any]:
    return {
        "companion": _run(["systemctl", "--user", "is-active", "cozmo-companion.service"], timeout=4),
        "guardian": _run(["systemctl", "--user", "is-active", "cozmo-guardian.service"], timeout=4),
    }


def _summary(saude: dict[str, Any] | None) -> dict[str, Any]:
    if not saude:
        return {"status": "sem data/cozmo-saude.json"}
    extra = saude.get("extra") or {}
    sessao = saude.get("sessao") or saude
    fase = extra.get("fase", saude.get("fase"))
    rx_ok = extra.get("rx_ok", saude.get("rx_ok"))
    return {
        "fase": fase,
        "rx_ok": rx_ok,
        "drx": extra.get("drx", saude.get("drx")),
        "dtx": extra.get("dtx", saude.get("dtx")),
        "ratio_janela": extra.get("ratio_janela", saude.get("ratio_janela")),
        "recv_frames": sessao.get("recv_frames", saude.get("rx")),
        "sent_frames": sessao.get("sent_frames", saude.get("tx")),
        "battery_v": sessao.get("bateria_v") or sessao.get("battery_v"),
        "robot_status": sessao.get("status", saude.get("estado")),
        "age_s": round(time.time() - float(saude.get("timestamp", time.time())), 1)
        if isinstance(saude.get("timestamp"), (int, float))
        else None,
    }


def main() -> int:
    saude = _json_file(SAUDE)
    payload = {
        "cozmo_ip": ROBOT_IP,
        "service": _service(),
        "wifi": _wifi(),
        "health_summary": _summary(saude),
        "health_raw": saude,
        "log": _log_tail(),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
