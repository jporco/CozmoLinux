"""Leitura de saúde — log, ping, serviço systemd."""

from __future__ import annotations

import json
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from cozmo_companion.core.paths import health_file

ROBOT_IP = "172.31.1.1"
SERVICE = "cozmo-companion.service"
LOCK_FILE = Path("/tmp/cozmo-companion.lock")

_TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")
_SESSAO_RE = re.compile(
    r"Sessão Cozmo: estado=(\S+) ping=(\S+) ([\d.]+)V .* udp rx=(\d+) tx=(\d+) .* ratio=([\d.]+)"
)
_ERRO_RE = re.compile(
    r"(sem resposta UDP|Conexão perdida|Falha ao conectar|UDP saturado|COZMO 01)"
)
_HEARTBEAT_RE = re.compile(
    r"(Governador .*rx=OK|Base OLED (keeper TX|: variar clip|: keeper|: vivo)|Vivo preso_na_base=True)"
)


def _parse_ts(linha: str) -> float | None:
    m = _TS_RE.match(linha)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").timestamp()
    except ValueError:
        return None


@dataclass(frozen=True)
class SessaoLog:
    estado: str
    ping: str
    bateria_v: float
    rx: int
    tx: int
    ratio: float
    linha: str
    idade_s: float


@dataclass(frozen=True)
class Saude:
    servico_ativo: bool
    ping_ok: bool
    sessao: SessaoLog | None
    erros_recentes: int
    ultimo_erro: str | None
    carregando: bool | None
    na_base: bool | None


def ping_robo(timeout_s: float = 2.0) -> bool:
    try:
        r = subprocess.run(
            ["ping", "-c1", f"-W{int(timeout_s)}", ROBOT_IP],
            capture_output=True,
            timeout=timeout_s + 2,
        )
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _pid_vivo(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        r = subprocess.run(
            ["ps", "-p", str(pid), "-o", "args="],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if r.returncode != 0:
            return False
        cmd = (r.stdout or "").strip()
        return "cozmo_companion" in cmd and "guardian" not in cmd
    except (OSError, subprocess.TimeoutExpired):
        return False


def companion_via_lock() -> bool:
    """Companion manual (nohup) — lock com PID vivo."""
    if not LOCK_FILE.is_file():
        return False
    try:
        pid = int(LOCK_FILE.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return False
    return _pid_vivo(pid)


def servico_systemd_ativo() -> bool:
    try:
        r = subprocess.run(
            ["systemctl", "--user", "is-active", SERVICE],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return r.stdout.strip() in ("active", "activating", "reloading")
    except (OSError, subprocess.TimeoutExpired):
        return False


def servico_ativo() -> bool:
    return servico_systemd_ativo() or companion_via_lock()


def _tail_linhas(caminho: Path, max_linhas: int) -> list[str]:
    """Últimas N linhas sem ler o arquivo inteiro (log pode ter centenas de MB)."""
    try:
        with caminho.open("rb") as f:
            f.seek(0, 2)
            pos = f.tell()
            if pos <= 0:
                return []
            bloco = 65536
            dados = b""
            while pos > 0 and dados.count(b"\n") <= max_linhas:
                ler = min(bloco, pos)
                pos -= ler
                f.seek(pos)
                dados = f.read(ler) + dados
            return dados.decode("utf-8", errors="replace").splitlines()[-max_linhas:]
    except OSError:
        return []


def _parse_sessao(linha: str, ts: float | None) -> SessaoLog | None:
    m = _SESSAO_RE.search(linha)
    if not m:
        return None
    idade = max(0.0, time.time() - ts) if ts else 999.0
    return SessaoLog(
        estado=m.group(1),
        ping=m.group(2),
        bateria_v=float(m.group(3)),
        rx=int(m.group(4)),
        tx=int(m.group(5)),
        ratio=float(m.group(6)),
        linha=linha.strip(),
        idade_s=idade,
    )


def _sessao_com_idade(sessao: SessaoLog, idade_s: float) -> SessaoLog:
    return SessaoLog(
        estado=sessao.estado,
        ping=sessao.ping,
        bateria_v=sessao.bateria_v,
        rx=sessao.rx,
        tx=sessao.tx,
        ratio=sessao.ratio,
        linha=sessao.linha,
        idade_s=idade_s,
    )


def ler_log(
    caminho: Path,
    *,
    janela_erro_s: float = 120.0,
    max_linhas: int = 300,
) -> Saude:
    erros = 0
    ultimo_erro: str | None = None
    sessao: SessaoLog | None = None
    carregando: bool | None = None
    na_base: bool | None = None
    agora = time.time()
    corte = agora - janela_erro_s

    if caminho.is_file():
        try:
            bloco = _tail_linhas(caminho, max_linhas)
            ultimo_ok = corte
            ultimo_heartbeat: float | None = None
            for linha in bloco:
                if "Companheiro vivo." in linha or "PyCozmo conectado" in linha:
                    ts = _parse_ts(linha)
                    if ts:
                        ultimo_ok = ts
                if _HEARTBEAT_RE.search(linha):
                    ts = _parse_ts(linha)
                    if ts:
                        ultimo_heartbeat = ts
                        ultimo_ok = max(ultimo_ok, ts)
            corte_erros = max(corte, ultimo_ok)

            for linha in reversed(bloco):
                ts = _parse_ts(linha)
                if sessao is None:
                    s = _parse_sessao(linha, ts)
                    if s:
                        sessao = s
                if _ERRO_RE.search(linha) and ts and ts >= corte_erros:
                    erros += 1
                    if ultimo_erro is None:
                        ultimo_erro = linha.strip()[-120:]
                if ts and ts >= corte:
                    if "carregando=True" in linha:
                        carregando = True
                    elif "carregando=False" in linha:
                        carregando = False
                    if "Na base:" in linha or "preso_na_base=True" in linha:
                        na_base = True
                    if "saiu da base" in linha.lower():
                        na_base = False
            if sessao is not None and ultimo_heartbeat is not None:
                sessao = _sessao_com_idade(
                    sessao,
                    max(0.0, agora - ultimo_heartbeat),
                )
        except OSError:
            pass

    return Saude(
        servico_ativo=servico_ativo(),
        ping_ok=ping_robo(),
        sessao=sessao,
        erros_recentes=erros,
        ultimo_erro=ultimo_erro,
        carregando=carregando,
        na_base=na_base,
    )


def ler_json(caminho: Path) -> Saude | None:
    """Lê o heartbeat estruturado do loop principal.

    Retorna ``None`` somente quando o arquivo não existe ou é inválido; nesse
    caso o guardian pode recorrer ao parser de log por compatibilidade.
    """
    try:
        raw = json.loads(caminho.read_text(encoding="utf-8"))
        ts = datetime.fromisoformat(str(raw["ts"]))
        estado = str(raw["estado"])
        rx = int(raw["rx"])
        tx = int(raw["tx"])
        bateria = float(raw["bateria_v"])
        ratio = float(raw.get("ratio_acum", tx / max(rx, 1)))
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    idade = max(0.0, time.time() - ts.timestamp())
    rx_ok = bool(raw.get("rx_ok", True))
    sessao = SessaoLog(
        estado=estado,
        ping="OK" if rx_ok else "FAIL",
        bateria_v=bateria,
        rx=rx,
        tx=tx,
        ratio=ratio,
        linha="health-json",
        idade_s=idade,
    )
    preso = raw.get("preso_base")
    return Saude(
        servico_ativo=servico_ativo(),
        ping_ok=ping_robo(),
        sessao=sessao,
        erros_recentes=0,
        ultimo_erro=None,
        carregando=None,
        na_base=bool(preso) if preso is not None else None,
    )


def ler_saude(root: Path, log_path: Path) -> Saude:
    """JSON é a fonte primária; log existe apenas como fallback legado."""
    estruturada = ler_json(health_file(root))
    return estruturada if estruturada is not None else ler_log(log_path)


def sessao_morta(saude: Saude, *, ratio_limite: float = 4.0, idade_max_s: float = 90.0) -> bool:
    s = saude.sessao
    if not s:
        return False
    if s.idade_s > idade_max_s:
        return False
    if s.ratio >= ratio_limite and s.rx > 100:
        return True
    if s.ping == "FAIL":
        return True
    return False
