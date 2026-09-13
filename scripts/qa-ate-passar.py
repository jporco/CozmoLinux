#!/usr/bin/env python3
"""QA automático — injeta voz, lê saúde JSON + log, repete até passar ou timeout."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "cozmo-companheiro.log"
VOZ = ROOT / "data" / "voz.cmd"


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
REL = ROOT / "data" / "qa-relatorio.json"

CASOS = (
    ("hora", "cozmo que horas são", ("Util tela", "Sinal: Hora"), 36),
    ("temp", "cozmo qual a temperatura", ("Util tela", "Bagé"), 30),
    ("wake", "oi cozmo", ("Wake", "Sinal:"), 24),
)

FALHAS_RE = (
    "COZMO 01 persistente",
    "Recuperação in-place falhou",
    "sem resposta UDP",
)
# reconexão durante teste é falha só se não houver "Reconexão UDP OK" depois


def ping_ok() -> bool:
    return subprocess.run(
        ["ping", "-c1", "-W2", "172.31.1.1"],
        capture_output=True,
    ).returncode == 0


def log_offset() -> int:
    try:
        return LOG.stat().st_size
    except OSError:
        return 0


def log_novo(off: int) -> str:
    try:
        with LOG.open("rb") as f:
            f.seek(off)
            return f.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def saude() -> dict:
    try:
        return json.loads(SAUDE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def aguardar_resposta(
    off: int,
    ok_need: tuple[str, ...],
    timeout_s: float,
    *,
    frase: str = "",
) -> str:
    """Espera voz.cmd ser consumido e padrões aparecerem no log (evita sobrescrever injeção)."""
    injetada = f"Voz injetada: {frase}" if frase else ""
    fim = time.monotonic() + timeout_s
    consumido = False
    while time.monotonic() < fim:
        trecho = log_novo(off)
        if injetada and injetada not in trecho:
            time.sleep(0.25)
            continue
        if all(x in trecho for x in ok_need):
            return trecho
        if not consumido and not VOZ.is_file():
            consumido = True
        time.sleep(0.4 if consumido else 0.25)
    return log_novo(off)


def um_caso(nome: str, frase: str, ok_need: tuple[str, ...], espera: int) -> dict:
    off = log_offset()
    VOZ.parent.mkdir(parents=True, exist_ok=True)
    VOZ.write_text(frase + "\n", encoding="utf-8")
    trecho = aguardar_resposta(off, ok_need, float(espera), frase=frase)
    for _ in range(int(os.environ.get("QA_RX_OK_WAIT_S", "18"))):
        s0 = saude()
        if s0.get("rx_ok") is not False:
            break
        time.sleep(1)
    ok = all(x in trecho for x in ok_need)
    falhas = [f for f in FALHAS_RE if f in trecho]
    if "COZMO 01 persistente" in falhas and "Reconexão UDP OK" in trecho:
        falhas = [f for f in falhas if f != "COZMO 01 persistente"]
    if "Link UDP congelado" in trecho and "Reconexão UDP OK" not in trecho:
        falhas.append("Link UDP congelado")
    elif "Link UDP congelado" in falhas and "Reconexão UDP OK" in trecho:
        falhas = [f for f in falhas if f != "Link UDP congelado"]
    s = saude()
    # Critério real: resposta na voz/log. Ratio da janela procedural engana (drx=0 dtx=400).
    caso_ok = ok and not falhas
    extras: list[str] = []
    if not caso_ok:
        if s.get("rx_ok") is False:
            extras.append("rx_ok_false")
        drx = int(s.get("drx", 0))
        if (
            drx <= 0
            and s.get("rx_ok") is False
            and float(s.get("ratio_acum", 0)) > float(
                os.environ.get("QA_RATIO_ACUM_MAX", "12")
            )
        ):
            extras.append("ratio_alto")
    return {
        "caso": nome,
        "ok": caso_ok,
        "falhas": falhas + extras,
        "saude": s,
        "trecho": trecho[-1200:],
    }


def rodada() -> dict:
    if not ping_ok():
        return {"ok": False, "motivo": "ping_fail", "casos": []}
    gap = float(os.environ.get("QA_ENTRE_CASOS_S", "1.5"))
    casos: list[dict] = []
    for i, c in enumerate(CASOS):
        if i:
            time.sleep(gap)
        casos.append(um_caso(*c))
    ok = all(c["ok"] for c in casos)
    return {"ok": ok, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "casos": casos}


def main() -> int:
    minutos = float(os.environ.get("QA_MINUTOS", "12"))
    limpas = int(os.environ.get("QA_LIMPAS_SEGUIDAS", "3"))
    fim = time.monotonic() + minutos * 60
    historico: list[dict] = []
    n = 0
    while time.monotonic() < fim:
        n += 1
        r = rodada()
        historico.append(r)
        REL.write_text(
            json.dumps({"rodadas": historico, "ultima": r}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"rodada {n}: {'PASS' if r.get('ok') else 'FAIL'}")
        if not r.get("ok"):
            for c in r.get("casos", []):
                if not c.get("ok"):
                    print(f"  - {c['caso']}: falhas={c.get('falhas')}")
        else:
            print("TODOS OS CASOS PASSARAM nesta rodada")
        if r.get("ok"):
            limpas_seg = sum(1 for x in historico[-limpas:] if x.get("ok"))
            if len(historico) >= limpas and limpas_seg >= limpas:
                print(f"QA OK — {limpas} rodadas limpas")
                return 0
        time.sleep(float(os.environ.get("QA_ENTRE_RODADAS_S", "12")))
    print("QA TIMEOUT — ainda falhando")
    return 1


if __name__ == "__main__":
    sys.exit(main())
