#!/usr/bin/env python3
"""Recuperação manual para tela física presa em COZMO 01.

Uso esperado:
  systemctl --user stop cozmo-companion.service
  scripts/force-cozmo01-reset.py
  systemctl --user start cozmo-companion.service

Este script existe porque o firmware pode continuar exibindo COZMO 01 mesmo com
ping/RX saudáveis no PC. Nesse caso, mandar mais frames não prova que a OLED
mudou; é preciso fechar a sessão UDP de forma explícita e reabrir devagar.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _reexec_venv() -> None:
    venv_python = ROOT / ".venv" / "bin" / "python"
    if venv_python.exists() and Path(sys.executable) != venv_python:
        os.environ["PYTHONPATH"] = str(ROOT / "src")
        os.execv(str(venv_python), [str(venv_python), *sys.argv])


def _load_env() -> None:
    cfg = ROOT / "config.env"
    if not cfg.exists():
        return
    for line in cfg.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


def main() -> int:
    _reexec_venv()
    _load_env()
    if "--dry-import-test" in sys.argv:
        import pycozmo  # noqa: F401

        print(f"OK import pycozmo via {sys.executable}")
        return 0
    os.environ["COZMO_COZMO01_RESET_UDP"] = "1"
    os.environ["COZMO_BASE_STABLE_ALLOW_RESET"] = "1"
    os.environ.setdefault("COZMO01_DISCONNECT_PAUSE_S", "8")

    from cozmo_companion.core.conexao import (
        abrir_cliente,
        aguardar_ping,
        diagnostico,
        fechar_cliente,
    )
    from cozmo_companion.core.anim_base_patch import instalar_play_anim_sem_rodas_na_base
    from cozmo_companion.core.charger import definir_oled_preso_na_base
    from cozmo_companion.core.motor_cozmo import (
        _exibir_clip_base,
        _handshake_frame_oled,
        ligar_oled_base,
        resetar_sessao_oled_base,
    )
    from cozmo_companion.display.rosto import pkt_rosto_procedural

    print("Abrindo sessão atual para reset UDP forçado...")
    cli = abrir_cliente(log_level="WARNING", protocol_log_level="ERROR", robot_log_level="ERROR")
    try:
        d = diagnostico(cli)
        print(f"antes: rx={d['recv_frames']} tx={d['sent_frames']}")
        fechar_cliente(
            cli,
            pausa=float(os.environ.get("COZMO01_DISCONNECT_PAUSE_S", "8")),
            forcado=True,
        )
    finally:
        cli = None

    if not aguardar_ping(float(os.environ.get("COZMO_RECONNECT_WAIT_PING_S", "25"))):
        print("FAIL: Cozmo não voltou no ping depois do reset UDP.")
        return 2

    print("Reabrindo sessão e acordando OLED...")
    cli = abrir_cliente(log_level="WARNING", protocol_log_level="ERROR", robot_log_level="ERROR")
    try:
        cli.load_anims()
        instalar_play_anim_sem_rodas_na_base(cli, preso_na_base_fn=lambda: True)
        definir_oled_preso_na_base(True)
        resetar_sessao_oled_base(fase_inicial="laranja")
        ligar_oled_base(cli, forcar=True, preso_na_base=True)

        ac = cli.anim_controller
        for i in range(12):
            pkt = pkt_rosto_procedural(cli)
            if i == 0:
                _handshake_frame_oled(cli, force=True)
            cli.conn.send(pkt)
            ac.last_image_pkt = pkt
            time.sleep(0.25)

        for nome in ("CodeLabReactHappy", "CodeLabReactCurious"):
            try:
                _exibir_clip_base(cli, nome, forcar=True)
                time.sleep(2.5)
                break
            except Exception as exc:
                print(f"WARN: clip {nome} falhou: {exc}")

        d = diagnostico(cli)
        print(f"depois: rx={d['recv_frames']} tx={d['sent_frames']}")
        print("OK: sessão resetada e OLED rearmado.")
        return 0
    finally:
        if cli is not None:
            fechar_cliente(cli, pausa=0.5, forcado=False)


if __name__ == "__main__":
    raise SystemExit(main())
