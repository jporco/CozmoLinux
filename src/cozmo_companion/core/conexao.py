"""Saúde da sessão UDP — diagnóstico e reconnect seguro."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from collections import deque
from pathlib import Path

logger = logging.getLogger("cozmo.conexao")

ROOT = Path(os.environ.get("COZMO_COMPANION_ROOT", "/mnt/G/PROJETOS/cozmo-companion"))
ROBOT_IP = os.environ.get("COZMO_IP", "172.31.1.1")

_ESTADO_NOME = {1: "IDLE", 2: "CONNECTING", 3: "CONNECTED"}
_ultimo_aviso_wifi_setup = 0.0
_ultimo_wifi_tentativa = 0.0
_ultimo_log_offline = 0.0
_ultimo_rescan_wifi = 0.0
_wlan0_preso_desde = 0.0


def cozmo_rota_ap() -> bool:
    """True se o tráfego para o Cozmo não sai pelo gateway da rede de casa."""
    try:
        r = subprocess.run(
            ["ip", "route", "get", ROBOT_IP],
            capture_output=True,
            text=True,
            timeout=3,
        )
        linha = (r.stdout or "").strip()
        if r.returncode != 0 or ROBOT_IP not in linha:
            return False
        if " via " in linha:
            return False
        return " dev " in linha
    except (OSError, subprocess.TimeoutExpired):
        return False


def _iface_wifi() -> str:
    return os.environ.get("COZMO_WIFI_IFACE", "wlan0")


def wlan0_estado() -> tuple[str, str]:
    """Estado NM e conexão ativa do Wi-Fi (ex.: connecting, Cozmo_*)."""
    try:
        r = subprocess.run(
            ["nmcli", "-t", "-f", "GENERAL.STATE,GENERAL.CONNECTION", "dev", "show", _iface_wifi()],
            capture_output=True,
            text=True,
            timeout=5,
        )
        estado = ""
        conexao = ""
        for linha in (r.stdout or "").splitlines():
            if linha.startswith("GENERAL.STATE:"):
                estado = linha.split(":", 1)[1].strip().lower()
            elif linha.startswith("GENERAL.CONNECTION:"):
                conexao = linha.split(":", 1)[1].strip()
        return estado, conexao
    except (OSError, subprocess.TimeoutExpired):
        return "", ""


def wlan0_preso_cozmo() -> bool:
    """wlan0 em Cozmo_* morto de forma PERSISTENTE — nunca durante o handshake.

    O bug antigo derrubava o wlan0 no meio da conexão (estado transitório
    'connecting'/'config', rota ainda não subiu), criando um loop conectar→derrubar
    que impedia QUALQUER comunicação com o robô. Aqui: estados transitórios nunca
    contam como preso, e só liberamos após carência contínua sem rota/ping.
    """
    global _wlan0_preso_desde
    estado, conexao = wlan0_estado()
    if not conexao.upper().startswith("COZMO_"):
        _wlan0_preso_desde = 0.0
        return False
    # Handshake/DHCP/auth em progresso → está conectando, não derrubar.
    transitorio = (
        "connecting" in estado
        or "prepare" in estado
        or "config" in estado  # cobre "(config)" e "(ip config)"
        or "ip check" in estado
        or "need auth" in estado
        or "secondaries" in estado
    )
    if transitorio:
        _wlan0_preso_desde = 0.0
        return False
    if cozmo_rota_ap() and cozmo_alcanavel():
        _wlan0_preso_desde = 0.0
        return False
    # Conectado a Cozmo_* mas sem rota/ping — candidato a preso; exige persistência
    # para dar tempo da rota/DHCP subir antes de qualquer disconnect.
    agora = time.monotonic()
    if _wlan0_preso_desde <= 0:
        _wlan0_preso_desde = agora
        return False
    graca = float(os.environ.get("COZMO_WLAN0_PRESO_GRACA_S", "15"))
    return agora - _wlan0_preso_desde >= graca


def liberar_wlan0_cozmo() -> bool:
    """Desconecta wlan0 preso em Cozmo_* sem carrier."""
    if not wlan0_preso_cozmo():
        return False
    try:
        subprocess.run(
            ["nmcli", "dev", "disconnect", _iface_wifi()],
            capture_output=True,
            timeout=8,
        )
        logger.info("wlan0 liberado (estava preso em Cozmo).")
        return True
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("Falha ao liberar wlan0: %s", exc)
        return False


def nunca_desconectar_wifi() -> bool:
    return os.environ.get("COZMO_NEVER_DISCONNECT", "1") == "1"


def cozmo_alcanavel() -> bool:
    if not cozmo_rota_ap():
        return False
    # Firmware do Cozmo dorme o rádio quando o tráfego é esparso: a 1ª resposta
    # pode levar centenas de ms a ~1s. -W2 dava falso "offline"/wifi=FAIL e disparava
    # recuperação à toa. 2 tentativas com timeout maior tolera o wake do rádio.
    timeout_s = os.environ.get("COZMO_PING_TIMEOUT_S", "4")
    try:
        r = subprocess.run(
            ["ping", "-c1", "-W", timeout_s, ROBOT_IP],
            capture_output=True,
            timeout=float(timeout_s) + 1.5,
        )
        if r.returncode == 0:
            return True
        r2 = subprocess.run(
            ["ping", "-c1", "-W", timeout_s, ROBOT_IP],
            capture_output=True,
            timeout=float(timeout_s) + 1.5,
        )
        return r2.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def permitir_reset_udp_cozmo01() -> bool:
    return os.environ.get("COZMO_COZMO01_RESET_UDP", "1") == "1"


def wifi_modo_seguro() -> bool:
    return os.environ.get("COZMO_WIFI_SAFE", "1") == "1"


def cozmo_ssid_visivel(*, rescan: bool = False) -> bool:
    """True se AP Cozmo_* visível ou já conectado na rede do robô."""
    if cozmo_rota_ap():
        return True
    try:
        if rescan:
            global _ultimo_rescan_wifi
            intervalo = float(os.environ.get("COZMO_WIFI_RESCAN_S", "600"))
            if time.monotonic() - _ultimo_rescan_wifi >= intervalo:
                _ultimo_rescan_wifi = time.monotonic()
                subprocess.run(
                    ["nmcli", "dev", "wifi", "rescan"],
                    capture_output=True,
                    timeout=8,
                )
                time.sleep(1.5)
        lista = subprocess.run(
            ["nmcli", "-t", "-f", "SSID,SIGNAL", "dev", "wifi", "list"],
            capture_output=True,
            text=True,
            timeout=8,
        )
        for linha in (lista.stdout or "").splitlines():
            ssid = linha.split(":", 1)[0] if linha else ""
            if ssid.upper().startswith("COZMO_"):
                return True
    except (OSError, subprocess.TimeoutExpired):
        pass
    return False


def pode_tentar_wifi(*, forcado: bool = False) -> bool:
    """Modo seguro: não mexe no Wi-Fi do PC se Cozmo offline ou cooldown."""
    if cozmo_alcanavel() and cozmo_rota_ap():
        return False

    preso = wlan0_preso_cozmo()
    rota_errada = not cozmo_rota_ap()

    if forcado or rota_errada or preso:
        cooldown = float(
            os.environ.get(
                "COZMO_WIFI_ROUTE_RETRY_S",
                os.environ.get("COZMO_WIFI_OFFLINE_RETRY_S", "20"),
            )
        )
        if time.monotonic() - _ultimo_wifi_tentativa < cooldown:
            return preso or rota_errada
        return True

    if not wifi_modo_seguro():
        cooldown = float(os.environ.get("COZMO_WIFI_COOLDOWN_S", "60"))
        if time.monotonic() - _ultimo_wifi_tentativa < cooldown:
            return False
        return True

    rescan = time.monotonic() - _ultimo_wifi_tentativa >= float(
        os.environ.get("COZMO_WIFI_RESCAN_OFFLINE_S", "90")
    )
    if not cozmo_ssid_visivel(rescan=rescan):
        if nunca_desconectar_wifi() and preso:
            cooldown = float(os.environ.get("COZMO_WIFI_OFFLINE_RETRY_S", "20"))
            return time.monotonic() - _ultimo_wifi_tentativa >= cooldown
        return False
    cooldown = float(os.environ.get("COZMO_WIFI_COOLDOWN_S", "60"))
    if time.monotonic() - _ultimo_wifi_tentativa < cooldown:
        return False
    return True


def log_offline_quieto(msg: str = "Cozmo offline — aguardando (sem mexer Wi-Fi PC).") -> None:
    global _ultimo_log_offline
    debounce = float(os.environ.get("COZMO_OFFLINE_LOG_S", "300"))
    agora = time.monotonic()
    if agora - _ultimo_log_offline >= debounce:
        _ultimo_log_offline = agora
        logger.info(msg)


def aguardar_cozmo_online(timeout_s: float) -> bool:
    """Espera ping com backoff — só tenta Wi-Fi se AP Cozmo visível."""
    global _ultimo_wifi_tentativa
    fim = time.monotonic() + timeout_s
    while time.monotonic() < fim:
        if cozmo_alcanavel():
            return True
        time.sleep(2.0)
    visivel = cozmo_ssid_visivel(rescan=True)
    if (visivel or wlan0_preso_cozmo() or not cozmo_rota_ap()) and pode_tentar_wifi(
        forcado=not cozmo_rota_ap()
    ):
        _ultimo_wifi_tentativa = time.monotonic()
        if reconectar_wifi(forcado=not cozmo_rota_ap()):
            return cozmo_alcanavel()
    else:
        log_offline_quieto()
    return cozmo_alcanavel()


def reconectar_wifi(*, forcado: bool = False) -> bool:
    if cozmo_alcanavel() and cozmo_rota_ap():
        logger.debug("Ping OK — mantendo Wi-Fi atual.")
        return True

    if wlan0_preso_cozmo():
        liberar_wlan0_cozmo()
        forcado = True

    if not pode_tentar_wifi(forcado=forcado):
        log_offline_quieto()
        return False

    global _ultimo_wifi_tentativa
    _ultimo_wifi_tentativa = time.monotonic()

    script = ROOT / "conectar-cozmo.sh"
    if not script.is_file():
        logger.warning("Script Wi-Fi não encontrado: %s", script)
        return False
    env = os.environ.copy()
    if wifi_modo_seguro():
        env["COZMO_WIFI_SAFE"] = "1"
    try:
        proc = subprocess.run(
            ["/bin/bash", str(script)],
            capture_output=True,
            text=True,
            timeout=18,
            cwd=str(ROOT),
            env=env,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode == 0 and cozmo_alcanavel():
            logger.info("Wi-Fi Cozmo reconectado.")
            return True
        if proc.returncode == 2:
            log_offline_quieto("Cozmo ausente — Wi-Fi do PC intacto.")
            return False
        logger.warning(
            "Wi-Fi Cozmo falhou (code %d): %s",
            proc.returncode,
            out.strip()[-200:],
        )
        return cozmo_alcanavel()
    except subprocess.TimeoutExpired:
        logger.warning("Timeout ao conectar Wi-Fi do Cozmo.")
        return False
    except OSError as exc:
        logger.warning("Erro Wi-Fi: %s", exc)
        return False


def estado_socket(cli) -> int:
    try:
        return int(cli.conn.state)
    except Exception:
        return 0


def nome_estado(cli) -> str:
    return _ESTADO_NOME.get(estado_socket(cli), "?")


def socket_conectado(cli) -> bool:
    from pycozmo.conn import Connection

    return estado_socket(cli) == Connection.CONNECTED


def sessao_viva(cli) -> bool:
    """Robô ainda responde pacotes — não usar só battery_voltage cacheado (COZMO 01)."""
    try:
        d = diagnostico(cli)
        if d["recv_frames"] < int(os.environ.get("COZMO_SESSAO_RX_MIN", "12")):
            return False
        if socket_conectado(cli) and d["recv_frames"] >= 50:
            drx, dtx, _ = MedidorUdp(janela_s=8.0).amostra(cli)
            if drx <= 0 and dtx >= int(os.environ.get("GOV_TX_DELTA_STALL", "120")):
                return False
        if cli.battery_voltage > 0 and d["recv_frames"] >= 50:
            return True
        return cli.robot_status != 0 and d["recv_frames"] >= 30
    except Exception:
        return False


def conexao_ok(cli) -> bool:
    """Sessão UDP saudável — não confundir socket CONNECTED com COZMO 01."""
    return sessao_viva(cli)


def sessao_pycozmo_ativa(cli) -> bool:
    """UDP + RX recente — sem isso o robô fica na tela COZMO_xxxx (setup Wi‑Fi)."""
    if not cozmo_alcanavel():
        return False
    if not socket_conectado(cli):
        return False
    return conexao_ok(cli)


def avisar_modo_wifi_setup(cli, *, debounce_s: float = 120.0) -> bool:
    """Log claro se ping OK mas sessão morta (não fingir anim na OLED)."""
    global _ultimo_aviso_wifi_setup
    if sessao_pycozmo_ativa(cli):
        return False
    if not cozmo_alcanavel():
        return False
    agora = time.monotonic()
    if agora - _ultimo_aviso_wifi_setup < debounce_s:
        return True
    _ultimo_aviso_wifi_setup = agora
    script = ROOT / "conectar-cozmo.sh"
    logger.warning(
        "Robô em modo Wi‑Fi/setup (tela COZMO_xxxx + código) — sessão PyCozmo inativa. "
        "Conectar: bash %s && systemctl --user restart cozmo-companion",
        script,
    )
    return True


def keepalive(cli, *, leve: bool = False) -> bool:
    del leve
    return conexao_ok(cli)


def diagnostico(cli) -> dict:
    conn = getattr(cli, "conn", None)
    recv = getattr(conn, "recv_thread", None) if conn else None
    send = getattr(conn, "send_thread", None) if conn else None
    return {
        "estado": nome_estado(cli),
        "ping_wifi": cozmo_alcanavel(),
        "bateria_v": getattr(cli, "battery_voltage", 0.0),
        "status": hex(getattr(cli, "robot_status", 0)),
        "recv_frames": getattr(recv, "received_frames", 0) if recv else 0,
        "sent_frames": getattr(send, "sent_frames", 0) if send else 0,
        "discarded": getattr(recv, "discarded_frames", 0) if recv else 0,
        "recv_packets": getattr(recv, "received_packets", 0) if recv else 0,
        "recv_bytes": getattr(recv, "received_bytes", 0) if recv else 0,
    }


def log_diagnostico(cli, *, nivel: int = logging.INFO) -> dict:
    d = diagnostico(cli)
    ratio = d["sent_frames"] / max(d["recv_frames"], 1)
    logger.log(
        nivel,
        "Sessão Cozmo: estado=%s ping=%s %.2fV status=%s "
        "udp rx=%d tx=%d desc=%d ratio=%.1f",
        d["estado"],
        "OK" if d["ping_wifi"] else "FAIL",
        d["bateria_v"],
        d["status"],
        d["recv_frames"],
        d["sent_frames"],
        d["discarded"],
        ratio,
    )
    return d


def ratio_udp(cli) -> float:
    """tx/rx acumulado — engana com olhos 30 fps; preferir MedidorUdp."""
    d = diagnostico(cli)
    if d["recv_frames"] < 50:
        return 0.0
    return d["sent_frames"] / max(d["recv_frames"], 1)


class MedidorUdp:
    """Métricas na janela (drx/dtx) — ratio acumulado não serve com procedural 30 fps."""

    def __init__(self, janela_s: float | None = None) -> None:
        self._janela = float(
            janela_s if janela_s is not None else os.environ.get("COZMO_UDP_JANELA_S", "30")
        )
        self._hist: deque[tuple[float, int, int]] = deque()

    def amostra(self, cli) -> tuple[int, int, float]:
        d = diagnostico(cli)
        agora = time.monotonic()
        rx, tx = d["recv_frames"], d["sent_frames"]
        self._hist.append((agora, rx, tx))
        limite = agora - self._janela
        while self._hist and self._hist[0][0] < limite:
            self._hist.popleft()
        if len(self._hist) < 2:
            return 0, 0, 0.0
        _, r0, x0 = self._hist[0]
        drx = rx - r0
        dtx = tx - x0
        if drx <= 0:
            r_delta = float(dtx) if dtx > 80 else 0.0
        else:
            r_delta = dtx / drx
        return drx, dtx, r_delta

    def reset(self) -> None:
        self._hist.clear()


def udp_leve_por_delta(drx: int, dtx: int, r_delta: float) -> bool:
    lim = float(os.environ.get("COZMO_UDP_DELTA_RATIO_LEVE", "4.5"))
    if drx <= 0:
        return dtx > int(os.environ.get("COZMO_UDP_DELTA_TX_LEVE", "450"))
    return r_delta > lim


def udp_saturado_por_delta(drx: int, dtx: int) -> bool:
    """RX parado na janela com TX alto = sessão morta (não ratio acumulado)."""
    if drx > 0:
        return False
    return dtx >= int(os.environ.get("COZMO_UDP_DELTA_TX_SAT", "320"))


def udp_leve(cli, limite: float | None = None) -> bool:
    del limite
    return False


def udp_saturado(cli, limite: float | None = None) -> bool:
    del limite
    return False


def gravar_saude(cli, *, extra: dict | None = None) -> None:
    """Snapshot para QA automático (data/cozmo-saude.json)."""
    try:
        d = diagnostico(cli)
        path = ROOT / "data" / "cozmo-saude.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "rx": d["recv_frames"],
            "tx": d["sent_frames"],
            "ratio_acum": round(
                d["sent_frames"] / max(d["recv_frames"], 1), 3
            ),
            "bateria_v": round(d["bateria_v"], 2),
            "estado": d["estado"],
        }
        if extra:
            payload.update(extra)
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def despertar_sessao_leve(cli, monitor: MonitorRx, medidor: MedidorUdp | None = None) -> None:
    """Religa olhos e reseta baseline RX — sem fechar UDP (não mostra COZMO 01)."""
    try:
        from cozmo_companion.core.motor_cozmo import (
            acordar_cozmo01,
            acordar_oled_minimo,
            base_oled_carga_cheia_ativo,
            base_oled_minimo_ativo,
        )

        if base_oled_carga_cheia_ativo(cli) or base_oled_minimo_ativo(cli):
            acordar_oled_minimo(cli, monitor, medidor)
            return
    except Exception as exc:
        logger.debug("despertar_sessao_leve: %s", exc)
        return
    monitor.sincronizar(cli)
    if medidor is not None:
        medidor.reset()
    try:
        acordar_cozmo01(cli)
    except Exception as exc:
        logger.debug("despertar_sessao_leve: %s", exc)


def nunca_desconectar_udp() -> bool:
    return os.environ.get("COZMO_NEVER_DISCONNECT", "1") == "1"


def procedural_ativo(cli) -> bool:
    try:
        from cozmo_companion.core.motor_cozmo import (
            base_oled_carga_cheia_ativo,
            base_oled_minimo_ativo,
            base_oled_modo_direto,
            base_oled_modo_proc,
            base_oled_usa_charger,
            base_oled_usa_pulse,
            charger_oled_ativo,
            keeper_base_ativo,
        )

        if base_oled_usa_pulse(cli):
            return False
        if base_oled_usa_charger(cli) or charger_oled_ativo(cli):
            return False
        if base_oled_carga_cheia_ativo(cli):
            return False
        if base_oled_minimo_ativo(cli):
            return False
        if keeper_base_ativo():
            return True
        ac = cli.anim_controller
        if base_oled_modo_proc():
            return bool(ac.animations_enabled and ac.procedural_face_enabled)
        return bool(ac.animations_enabled and ac.procedural_face_enabled)
    except Exception:
        return False


def _ppclip_sessao_viva(cli) -> bool:
    """Base 100%: ppclip + ping + UDP CONNECTED — drx=0 na janela é normal (≠ COZMO 01)."""
    try:
        from cozmo_companion.core.motor_cozmo import ppclip_base_ativo
    except Exception:
        return False
    if not ppclip_base_ativo(cli) or not cozmo_alcanavel():
        return False
    return sessao_pycozmo_ativa(cli)


def _base_ping_protegido(cli) -> bool:
    """Base 100% + ping OK >120s: drx=0 na janela ≠ link morto (≠ COZMO 01 stall)."""
    if not cozmo_alcanavel():
        return False
    try:
        from cozmo_companion.core.motor_cozmo import (
            base_oled_carga_cheia_ativo,
            ppclip_base_ativo,
        )
    except Exception:
        return False
    if not (base_oled_carga_cheia_ativo(cli) or ppclip_base_ativo(cli)):
        return False
    return sessao_pycozmo_ativa(cli)


class MonitorRx:
    """Detecta robô parado (COZMO 01) — ignora stall durante TTS."""

    def __init__(self) -> None:
        self._rx = 0
        self._tx = 0
        self._rx_em = 0.0
        self._pausa_ate = 0.0
        self._ping_ok_desde = 0.0

    def pausar(self, segundos: float) -> None:
        self._pausa_ate = max(self._pausa_ate, time.monotonic() + max(1.0, segundos))

    def sincronizar(self, cli) -> None:
        d = diagnostico(cli)
        self._rx = d["recv_frames"]
        self._tx = d["sent_frames"]
        self._rx_em = time.monotonic()

    def tick(self, cli) -> bool:
        """True = robô ainda responde UDP."""
        em_pausa = time.monotonic() < self._pausa_ate
        d = diagnostico(cli)
        rx = d["recv_frames"]
        tx = d["sent_frames"]
        agora = time.monotonic()
        stall = float(os.environ.get("COZMO_RX_STALL_S", "30"))
        tx_stall = int(os.environ.get("GOV_TX_DELTA_STALL", "180"))
        tx_idle = int(os.environ.get("GOV_TX_IDLE_DELTA", "50"))

        if rx > self._rx:
            self._rx = rx
            self._tx = tx
            self._rx_em = agora
            self._ping_ok_desde = 0.0
            return True

        try:
            from cozmo_companion.core.motor_cozmo import ppclip_base_ativo
        except Exception:
            ppclip_base_ativo = lambda _cli: False  # type: ignore[assignment,misc]

        ratio = d["sent_frames"] / max(d["recv_frames"], 1)
        lim_idle = float(os.environ.get("GOV_RX_IDLE_RATIO_MAX", "0.95"))
        lim_alto = float(os.environ.get("GOV_RX_RATIO_ALTO", "2.0"))
        ratio_s = float(os.environ.get("COZMO_RX_STALL_RATIO_S", "12"))
        proc = procedural_ativo(cli)
        ppclip = ppclip_base_ativo(cli)
        anim_tx = proc or ppclip
        proc_stall_s = float(os.environ.get("COZMO_PROC_RX_STALL_S", "120"))
        ppclip_stall_s = float(os.environ.get("COZMO_PPCLIP_RX_STALL_S", "120"))
        proc_ratio_max = float(os.environ.get("COZMO_PROC_STALL_RATIO_MAX", "8.0"))

        tx_idle_pp = int(os.environ.get("GOV_PPCLIP_TX_IDLE_DELTA", "80"))
        tx_min = int(os.environ.get("COZMO_RX_STALL_TX_MIN", "200"))
        tx_sat = int(os.environ.get("COZMO_UDP_DELTA_TX_SAT", "320"))
        dead_s = float(os.environ.get("COZMO01_RX_DEAD_S", "8"))
        tx_delta = tx - self._tx
        rx_parado_s = agora - self._rx_em

        if (
            ppclip
            and cozmo_alcanavel()
            and rx_parado_s < ppclip_stall_s
            and tx_delta < tx_idle_pp
        ):
            return True

        # Flood sem ACK: dtx alto na janela interna — ≠ ratio acum baixo por histórico.
        # Vale mesmo durante pausa (carinho/TTS): não mascarar COZMO 01.
        if (
            rx == self._rx
            and tx_delta >= tx_sat
            and rx_parado_s >= dead_s
            and not (ppclip and cozmo_alcanavel() and tx_delta < tx_idle_pp)
        ):
            return False

        if em_pausa:
            if rx > self._rx:
                self._rx = rx
                self._tx = tx
                self._rx_em = agora
            elif (
                rx == self._rx
                and tx_delta >= tx_min
                and rx_parado_s >= dead_s
            ):
                return False
            return True

        # TX alto + RX parado = COZMO 01 — ppclip só tolera TX baixo (acima), não 120s cego.
        stall_parado = float(os.environ.get("COZMO_RX_STALL_PARADO_S", "25"))
        if proc and not ppclip:
            stall_parado = min(
                stall_parado,
                float(os.environ.get("COZMO_PROC_RX_STALL_S", "20")),
            )
        if (
            rx == self._rx
            and tx_delta >= tx_min
            and rx_parado_s >= stall_parado
            and not (proc and not ppclip and rx_parado_s < proc_stall_s)
        ):
            return False

        # Procedural 30fps: OK só se RX subiu recentemente ou TX ainda baixo (≠ flood sem ACK).
        if anim_tx and rx_parado_s < proc_stall_s and tx_delta < tx_min:
            return True

        # Ratio baixo = link saudável; não resetar _tx — senão stall nunca acumula.
        if d["recv_frames"] >= 50:
            if ratio > 0 and ratio < lim_idle:
                return True
            # Ratio alto + RX parado = sessão morrendo (procedural 30 fps flood).
            if ratio >= lim_alto and rx == self._rx:
                if tx >= self._tx + tx_stall:
                    return False
                if (agora - self._rx_em) >= ratio_s:
                    return False

        # RX parado com TX subindo — só stall se ratio acum alto (procedural na base).
        stall_rx_s = float(os.environ.get("COZMO_RX_STALL_PARADO_S", "45"))
        if (
            rx == self._rx
            and tx_delta >= tx_min
            and rx_parado_s >= stall_rx_s
            and ratio >= lim_alto
        ):
            return False

        # TX sobe, RX parado — ratio acum baixo ainda é stall (COZMO 01 com histórico RX alto).
        if rx == self._rx and tx_delta >= tx_stall:
            if rx_parado_s >= ratio_s or tx_delta >= tx_min:
                return False
            if ratio < lim_idle:
                return True

        if self._rx_em <= 0:
            self._rx_em = agora
            self._tx = tx
            return True

        if d["recv_frames"] >= 50:
            tx_quieto = tx_delta <= tx_idle
            if (
                ratio < float(os.environ.get("GOV_RX_IDLE_RATIO_MAX", "0.95"))
                and tx_quieto
            ):
                return True

        if rx == self._rx and tx_delta >= tx_min and rx_parado_s >= dead_s:
            return False
        return rx_parado_s < stall

    def reset(self) -> None:
        self._rx = 0
        self._tx = 0
        self._rx_em = 0.0
        self._pausa_ate = 0.0
        self._ping_ok_desde = 0.0


def link_rx_congelado(cli, monitor: MonitorRx, medidor: MedidorUdp) -> bool:
    """Só reconectar se RX parado de verdade (MonitorRx) + janela sem drx."""
    if monitor.tick(cli):
        return False
    drx, dtx, _ = medidor.amostra(cli)
    if drx > 0:
        return False
    return dtx >= int(os.environ.get("COZMO_UDP_DELTA_TX_SAT", "520"))


def precisa_reconectar_udp(
    cli,
    monitor: MonitorRx,
    medidor: MedidorUdp,
    *,
    rx_ok: bool,
) -> bool:
    """Reconnect só se permitido e link realmente morto (sem ping/sessão)."""
    if nunca_desconectar_udp():
        return False
    if rx_ok or procedural_ativo(cli) or sessao_viva(cli):
        return False

    drx, dtx, r_delta = medidor.amostra(cli)
    ratio_alto = float(os.environ.get("GOV_RX_RATIO_ALTO", "2.0"))
    tx_sat = int(os.environ.get("COZMO_UDP_DELTA_TX_SAT", "520"))

    if drx <= 0 and dtx >= tx_sat:
        return True
    if drx > 0:
        return r_delta >= ratio_alto
    return dtx >= tx_sat


def sessao_parece_fresca(cli, *, rx_max: int | None = None) -> bool:
    """Sessão acabou de abrir (abrir_cliente) — não precisa reset UDP no boot."""
    limite = rx_max if rx_max is not None else int(
        os.environ.get("COZMO_BOOT_RX_FRESH_MAX", "220")
    )
    d = diagnostico(cli)
    rx = d["recv_frames"]
    if rx > limite:
        return False
    if not conexao_ok(cli):
        return False
    return rx >= int(os.environ.get("COZMO_BOOT_RX_MIN", "20"))


def recuperar_sessao_inplace(cli) -> bool:
    """Recupera sessão sem desconectar — pausa procedural, sem COZMO 01 na tela."""
    try:
        from cozmo_companion.core.motor_cozmo import (
            base_oled_carga_cheia_ativo,
            renovar_sessao_base_oled,
        )

        if base_oled_carga_cheia_ativo(cli):
            return renovar_sessao_base_oled(cli)
    except Exception as exc:
        logger.debug("recuperar_inplace charger: %s", exc)
    d0 = diagnostico(cli)
    ratio_lim = float(os.environ.get("COZMO_RX_DEAD_RATIO", "8.0"))
    if d0["recv_frames"] >= 120:
        r0 = d0["sent_frames"] / max(d0["recv_frames"], 1)
        if r0 > ratio_lim:
            logger.warning(
                "In-place ignorado — ratio extremo (rx=%d ratio=%.1f)",
                d0["recv_frames"],
                r0,
            )
            return False
    logger.warning("Recuperação in-place — pausa UDP")
    rx_antes = diagnostico(cli)["recv_frames"]
    proc = procedural_ativo(cli)
    try:
        if proc:
            cli.anim_controller.enable_procedural_face(False)
        else:
            cli.cancel_anim()
            cli.stop_all_motors()
    except Exception:
        pass
    time.sleep(float(os.environ.get("COZMO_INPLACE_PAUSE_S", "1.5")))
    d = diagnostico(cli)
    rx_depois = d["recv_frames"]
    ok = rx_depois > rx_antes and (sessao_viva(cli) or socket_conectado(cli))
    if ok:
        logger.info("Recuperação in-place OK (rx %d→%d)", rx_antes, rx_depois)
        if proc or os.environ.get("COZMO_PROC_FACE_BASE", "1") == "1":
            from cozmo_companion.core.motor_cozmo import modo_base_olhos

            modo_base_olhos(cli)
    else:
        logger.warning(
            "Recuperação in-place falhou (rx %d→%d ratio=%.1f)",
            rx_antes,
            rx_depois,
            d["sent_frames"] / max(rx_depois, 1),
        )
    return ok


def aguardar_pronto(cli, timeout_s: float | None = None) -> bool:
    from pycozmo import robot

    limite = float(
        timeout_s if timeout_s is not None else os.environ.get("COZMO_READY_S", "18")
    )
    fim = time.monotonic() + limite
    while time.monotonic() < fim:
        try:
            v = cli.battery_voltage
            st = cli.robot_status
            if v >= 3.4:
                logger.info("Cozmo pronto: %.2fV status=%#x", v, st)
                return True
            if st & (
                robot.RobotStatusFlag.IS_ON_CHARGER
                | robot.RobotStatusFlag.IS_CHARGING
            ):
                logger.info("Cozmo pronto na base: %.2fV", v)
                return True
            if st != 0:
                logger.info("Cozmo pronto (status=%#x, %.2fV)", st, v)
                return True
        except Exception:
            pass
        time.sleep(0.25)

    v = getattr(cli, "battery_voltage", 0.0)
    st = getattr(cli, "robot_status", 0)
    logger.warning(
        "Cozmo sem RobotState completo após %.0fs (%.2fV status=%#x) — seguindo",
        limite,
        v,
        st,
    )
    return cozmo_alcanavel()


def abrir_cliente(
    log_level: str = "INFO",
    protocol_log_level: str = "WARNING",
    robot_log_level: str = "WARNING",
):
    import pycozmo
    from pycozmo import client as cozmo_client
    from pycozmo.run import setup_basic_logging

    # setup_basic_logging adiciona um StreamHandler novo a cada chamada sem remover
    # os antigos. Como reabrimos o cliente a cada reconexão, os handlers se acumulam
    # e cada linha do pycozmo passa a ser escrita N vezes — o I/O síncrono trava o
    # loop principal e gera falsos COZMO 01 (bola de neve). Limpa antes de reconfigurar.
    for _lg in (
        pycozmo.logger,
        pycozmo.logger_protocol,
        pycozmo.logger_robot,
        pycozmo.logger_reaction,
        pycozmo.logger_behavior,
        pycozmo.logger_animation,
    ):
        for _h in list(_lg.handlers):
            _lg.removeHandler(_h)
            try:
                _h.close()
            except Exception:
                pass
    setup_basic_logging(
        log_level=log_level,
        protocol_log_level=protocol_log_level,
        robot_log_level=robot_log_level,
    )
    timeout = float(os.environ.get("COZMO_CONNECT_TIMEOUT", "30"))
    tentativas = int(os.environ.get("COZMO_CONNECT_TRIES", "5"))
    pausa = float(os.environ.get("COZMO_CONNECT_PAUSE_S", "5"))
    from cozmo_companion.core.motor_cozmo import base_oled_modo_direto, base_oled_modo_proc

    modo_direto = base_oled_modo_direto()
    modo_proc = base_oled_modo_proc()
    charger_oled = modo_proc and (
        os.environ.get("COZMO_BASE_OLED_CHARGER", "1") == "1"
        or os.environ.get("COZMO_BASE_OLED_CHARGER_FULL", "0") == "1"
    )
    min_oled = modo_proc and os.environ.get("COZMO_BASE_OLED_MIN", "1") == "1"
    if charger_oled or min_oled:
        proc_face = False
        enable_anim = False
    else:
        proc_face = (os.environ.get("COZMO_PROC_FACE", "1") == "1") and (
            modo_proc or not modo_direto
        )
        enable_anim = modo_proc or not modo_direto
    ultimo_erro: Exception | None = None

    for n in range(tentativas):
        if not cozmo_alcanavel():
            logger.warning("Cozmo inalcançável (ping) — tentativa %d", n + 1)
            time.sleep(pausa)
            continue

        cli = cozmo_client.Client(
            enable_procedural_face=proc_face,
            enable_animations=enable_anim,
        )
        from cozmo_companion.core.pycozmo_cli import vincular_cliente

        vincular_cliente(cli.conn, cli)
        try:
            cli.start()
            cli.connect()
            cli.wait_for_robot(timeout=timeout)
            aguardar_pronto(cli)
            time.sleep(float(os.environ.get("COZMO_SETTLE_S", "1.0")))
            try:
                from pycozmo import protocol_encoder

                from cozmo_companion.core.motor_cozmo import _handshake_oled_base

                _handshake_oled_base(cli)
                cli.conn.send(protocol_encoder.SyncTime())
                cli.conn.send(protocol_encoder.Ping())
            except Exception as exc:
                logger.debug("OLED wake pós-connect: %s", exc)
            logger.info("PyCozmo conectado (tentativa %d).", n + 1)
            log_diagnostico(cli)
            from cozmo_companion.core.motor_cozmo import instalar_anim_id_seguro

            instalar_anim_id_seguro(cli)
            return cli
        except Exception as exc:
            ultimo_erro = exc
            logger.warning("Tentativa %d falhou: %s", n + 1, exc)
            fechar_cliente(cli)
            time.sleep(pausa)

    raise ultimo_erro or RuntimeError("Falha ao conectar ao Cozmo.")


def aguardar_ping(timeout_s: float = 30.0) -> bool:
    """Espera Cozmo voltar no Wi-Fi antes de reconectar UDP."""
    fim = time.monotonic() + timeout_s
    while time.monotonic() < fim:
        if cozmo_alcanavel():
            return True
        time.sleep(1.5)
    return False


def fechar_cliente(cli, *, pausa: float | None = None, forcado: bool = False) -> None:
    from pycozmo.conn import Connection

    pausa = pausa if pausa is not None else float(os.environ.get("COZMO_DISCONNECT_PAUSE_S", "12"))
    if nunca_desconectar_udp() and not forcado:
        try:
            cli.stop()
        except Exception:
            pass
        pausa = min(pausa, float(os.environ.get("COZMO_DISCONNECT_PAUSE_MIN_S", "0.3")))
        logger.info("Stop local sem Disconnect UDP — pausa %.0fs", pausa)
        time.sleep(pausa)
        return

    if forcado and nunca_desconectar_udp():
        logger.warning("COZMO 01 — Disconnect UDP forçado (reset sessão)")

    try:
        if cli.conn.state == Connection.CONNECTED:
            cli.disconnect()
    except Exception:
        pass
    try:
        cli.stop()
    except Exception:
        pass
    logger.info("Aguardando %.0fs para o Cozmo fechar sessão UDP...", pausa)
    time.sleep(pausa)


def aguardar_robot(timeout_s: float = 25.0) -> bool:
    fim = time.monotonic() + timeout_s
    while time.monotonic() < fim:
        if cozmo_alcanavel():
            return True
        time.sleep(2.0)
    return False


def recuperar_apos_queda(tentativa: int) -> None:
    """Pausa + Wi-Fi se necessário — evita loop COZMO 01."""
    base = float(os.environ.get("COZMO_RECONNECT_S", "12"))
    pausa = min(base + tentativa * 4, float(os.environ.get("COZMO_RECONNECT_MAX_S", "45")))
    logger.warning(
        "Recuperação pós-queda (tentativa %d) — pausa %.0fs",
        tentativa,
        pausa,
    )
    time.sleep(pausa)
    if (tentativa >= 2 or not cozmo_alcanavel()) and pode_tentar_wifi():
        reconectar_wifi()
        time.sleep(3.0)
