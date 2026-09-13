#!/usr/bin/env python3
"""Valida a OLED do Cozmo com envio direto e captura de camera."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageStat

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.chdir(ROOT)

for name in ("config.env", "config.guardian.env"):
    path = ROOT / name
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


def run(cmd: list[str], *, timeout: float = 15.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def service_active(service: str) -> bool:
    proc = run(["systemctl", "--user", "is-active", "--quiet", service], timeout=5)
    return proc.returncode == 0


def stop_services() -> dict[str, bool]:
    services = ["cozmo-guardian.service", "cozmo-companion.service"]
    state = {svc: service_active(svc) for svc in services}
    for svc in services:
        if state[svc]:
            run(["systemctl", "--user", "stop", svc], timeout=20)
    time.sleep(1.5)
    return state


def restore_services(state: dict[str, bool]) -> None:
    for svc in ("cozmo-companion.service", "cozmo-guardian.service"):
        if state.get(svc):
            run(["systemctl", "--user", "start", svc], timeout=25)


def get_ctrl(device: str, name: str) -> str | None:
    proc = run(["v4l2-ctl", "-d", device, f"--get-ctrl={name}"], timeout=5)
    if proc.returncode != 0 or ":" not in proc.stdout:
        return None
    return proc.stdout.rsplit(":", 1)[1].strip()


def set_ctrl(device: str, name: str, value: str | int) -> None:
    run(["v4l2-ctl", "-d", device, "-c", f"{name}={value}"], timeout=5)


def boost_camera(device: str) -> dict[str, str]:
    saved: dict[str, str] = {}
    for name in ("brightness", "contrast", "gain"):
        value = get_ctrl(device, name)
        if value is not None:
            saved[name] = value
    for name, value in (("brightness", 220), ("contrast", 64), ("gain", 255)):
        set_ctrl(device, name, value)
    time.sleep(0.4)
    return saved


def restore_camera(device: str, saved: dict[str, str]) -> None:
    for name, value in saved.items():
        set_ctrl(device, name, value)


def capture(device: str, dest: Path) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    attempts = [
        ["-input_format", "mjpeg", "-video_size", "640x480"],
        ["-input_format", "yuyv422", "-video_size", "640x480"],
    ]
    for extra in attempts:
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "v4l2",
            *extra,
            "-i",
            device,
            "-frames:v",
            "1",
            str(dest),
        ]
        proc = run(cmd, timeout=8)
        if proc.returncode == 0 and dest.is_file() and dest.stat().st_size > 0:
            return True
    return False


def parse_roi(text: str | None, image: Image.Image) -> tuple[int, int, int, int]:
    width, height = image.size
    if text:
        parts = [int(p.strip()) for p in text.replace(",", " ").split()]
        if len(parts) != 4:
            raise ValueError("--roi precisa ser 'x,y,w,h'")
        x, y, w, h = parts
    else:
        x, y, w, h = 210, 145, 260, 210
    x = max(0, min(width - 1, x))
    y = max(0, min(height - 1, y))
    w = max(1, min(width - x, w))
    h = max(1, min(height - y, h))
    return x, y, w, h


def metrics(path: Path, roi_text: str | None) -> dict[str, float | int | list[int]]:
    image = Image.open(path).convert("RGB")
    x, y, w, h = parse_roi(roi_text, image)
    crop = image.crop((x, y, x + w, y + h))
    gray = crop.convert("L")
    stat = ImageStat.Stat(gray)
    get_gray_data = getattr(gray, "get_flattened_data", gray.getdata)
    values = list(get_gray_data())
    bright = sum(1 for v in values if v >= 145)
    very_bright = sum(1 for v in values if v >= 190)
    get_rgb_data = getattr(crop, "get_flattened_data", crop.getdata)
    rgb = list(get_rgb_data())
    cyanish = 0
    for r, g, b in rgb:
        if (g >= 45 and b >= 45 and max(g, b) >= r + 18) or (g >= 120 and b >= 120):
            cyanish += 1
    return {
        "roi": [x, y, w, h],
        "mean_luma": round(float(stat.mean[0]), 3),
        "max_luma": int(stat.extrema[0][1]),
        "bright_pixels": bright,
        "very_bright_pixels": very_bright,
        "cyanish_pixels": cyanish,
    }


def draw_test_frame(kind: int) -> Image.Image:
    image = Image.new("1", (128, 32), color=0)
    draw = ImageDraw.Draw(image)
    if kind % 4 == 0:
        draw.rectangle((0, 0, 127, 31), fill=1)
    elif kind % 4 == 1:
        draw.rectangle((0, 0, 127, 31), outline=1)
        for x in range(0, 128, 8):
            draw.rectangle((x, 0, x + 3, 31), fill=1)
    elif kind % 4 == 2:
        draw.rectangle((0, 0, 127, 31), fill=1)
        font = load_font(18)
        draw.text((64, 16), "OLED OK", fill=0, font=font, anchor="mm")
    else:
        font = load_font(20)
        draw.text((64, 16), "TESTE", fill=1, font=font, anchor="mm")
        draw.rectangle((0, 0, 127, 31), outline=1)
    return image


def load_font(size: int) -> ImageFont.ImageFont:
    candidates = (
        ROOT / "data" / "fonts" / "DejaVuSans.ttf",
        Path("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/TTF/DejaVuSans.ttf"),
        Path("/usr/share/fonts/dejavu/DejaVuSans.ttf"),
    )
    for path in candidates:
        if path.is_file():
            try:
                return ImageFont.truetype(str(path), size)
            except OSError:
                pass
    return ImageFont.load_default()


def packets():
    from pycozmo import image_encoder, protocol_encoder

    out = []
    for idx in range(4):
        enc = image_encoder.ImageEncoder(draw_test_frame(idx))
        out.append(protocol_encoder.DisplayImage(image=bytes(enc.encode())))
    return out


def send_oled_patterns(
    seconds: float,
    hz: float,
    *,
    during_capture=None,
) -> dict[str, int | float | bool]:
    from pycozmo import protocol_encoder

    from cozmo_companion.core.anim_base_patch import instalar_play_anim_sem_rodas_na_base
    from cozmo_companion.core.charger import definir_oled_preso_na_base
    from cozmo_companion.core.conexao import abrir_cliente, diagnostico, fechar_cliente
    from cozmo_companion.core.motor_cozmo import (
        _desligar_anim_controller_base,
        _handshake_frame_oled,
        _reset_anim_id,
        configurar_udp_leve_base,
    )

    cli = abrir_cliente(
        log_level="WARNING",
        protocol_log_level="ERROR",
        robot_log_level="ERROR",
    )
    try:
        try:
            cli.load_anims()
        except Exception:
            pass
        instalar_play_anim_sem_rodas_na_base(cli, preso_na_base_fn=lambda: True)
        definir_oled_preso_na_base(True)
        configurar_udp_leve_base(cli)
        _desligar_anim_controller_base(cli)
        _reset_anim_id(cli)
        frames = packets()
        d0 = diagnostico(cli)
        started = time.monotonic()
        deadline = started + seconds
        interval = 1.0 / max(0.5, min(12.0, hz))
        sent = 0
        captured = False
        while time.monotonic() < deadline:
            if sent % 6 == 0:
                _handshake_frame_oled(cli, force=True)
                cli.conn.send(protocol_encoder.SyncTime())
                cli.conn.send(protocol_encoder.Ping())
            pkt = frames[sent % len(frames)]
            cli.conn.send(pkt)
            cli.anim_controller.last_image_pkt = pkt
            sent += 1
            if (
                during_capture is not None
                and not captured
                and time.monotonic() - started >= seconds * 0.45
            ):
                during_capture()
                captured = True
            time.sleep(interval)
        if during_capture is not None and not captured:
            during_capture()
        d1 = diagnostico(cli)
        return {
            "sent_patterns": sent,
            "rx_delta": int(d1["recv_frames"] - d0["recv_frames"]),
            "tx_delta": int(d1["sent_frames"] - d0["sent_frames"]),
            "battery_v": round(float(d1["bateria_v"]), 2),
            "connected": True,
        }
    finally:
        fechar_cliente(cli, pausa=0.5)


def visual_ok(before: dict, during: dict, after: dict) -> tuple[bool, dict[str, float | int]]:
    best_mean_delta = max(
        float(during["mean_luma"]) - float(before["mean_luma"]),
        float(after["mean_luma"]) - float(before["mean_luma"]),
    )
    best_bright_delta = max(
        int(during["bright_pixels"]) - int(before["bright_pixels"]),
        int(after["bright_pixels"]) - int(before["bright_pixels"]),
    )
    best_cyan_delta = max(
        int(during["cyanish_pixels"]) - int(before["cyanish_pixels"]),
        int(after["cyanish_pixels"]) - int(before["cyanish_pixels"]),
    )
    best_max_delta = max(
        int(during["max_luma"]) - int(before["max_luma"]),
        int(after["max_luma"]) - int(before["max_luma"]),
    )
    ok = (
        best_mean_delta >= 2.5
        or best_bright_delta >= 35
        or best_cyan_delta >= 60
        or best_max_delta >= 25
    )
    return ok, {
        "mean_delta": round(best_mean_delta, 3),
        "bright_delta": best_bright_delta,
        "cyan_delta": best_cyan_delta,
        "max_delta": best_max_delta,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida OLED real do Cozmo.")
    parser.add_argument("--device", default="/dev/video0")
    parser.add_argument("--seconds", type=float, default=16.0)
    parser.add_argument("--hz", type=float, default=4.0)
    parser.add_argument("--roi", default=os.environ.get("COZMO_VALIDATE_OLED_ROI"))
    parser.add_argument(
        "--out-dir",
        default=str(ROOT / "outputs" / "oled-validation"),
    )
    parser.add_argument("--no-service-manage", action="store_true")
    parser.add_argument("--no-camera-boost", action="store_true")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    before_path = out_dir / f"{stamp}-before.jpg"
    during_path = out_dir / f"{stamp}-during.jpg"
    after_path = out_dir / f"{stamp}-after.jpg"
    report_path = out_dir / f"{stamp}-report.json"

    service_state: dict[str, bool] = {}
    camera_state: dict[str, str] = {}
    report: dict[str, object] = {
        "ts": stamp,
        "device": args.device,
        "seconds": args.seconds,
        "hz": args.hz,
        "paths": {
            "before": str(before_path),
            "during": str(during_path),
            "after": str(after_path),
            "report": str(report_path),
        },
    }

    try:
        if not args.no_camera_boost:
            camera_state = boost_camera(args.device)
        before_ok = capture(args.device, before_path)
        report["before_capture"] = before_ok
        if not args.no_service_manage:
            service_state = stop_services()
            report["stopped_services"] = service_state
        during_state = {"ok": False}

        def capture_during() -> None:
            during_state["ok"] = capture(args.device, during_path)

        probe = send_oled_patterns(
            args.seconds,
            args.hz,
            during_capture=capture_during,
        )
        report["probe"] = probe
        during_ok = during_state["ok"]
        time.sleep(1.0)
        after_ok = capture(args.device, after_path)
        report["during_capture"] = during_ok
        report["after_capture"] = after_ok
        if before_ok and during_ok and after_ok:
            before_m = metrics(before_path, args.roi)
            during_m = metrics(during_path, args.roi)
            after_m = metrics(after_path, args.roi)
            ok, delta = visual_ok(before_m, during_m, after_m)
            report["metrics"] = {
                "before": before_m,
                "during": during_m,
                "after": after_m,
                "delta": delta,
                "visual_ok": ok,
            }
        else:
            ok = False
            report["metrics"] = {"visual_ok": False, "reason": "camera_capture_failed"}
    except Exception as exc:
        ok = False
        report["error"] = repr(exc)
    finally:
        if service_state and not args.no_service_manage:
            restore_services(service_state)
        if camera_state:
            restore_camera(args.device, camera_state)

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if ok else 3


if __name__ == "__main__":
    raise SystemExit(main())
