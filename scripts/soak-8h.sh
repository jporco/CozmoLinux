#!/usr/bin/env bash
# Soak test 8h — monitora, reconecta Wi-Fi, reinicia companion se morrer.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG="${ROOT}/cozmo-soak-8h.log"
DUR_S="${1:-28800}"
INTERVAL="${COZMO_SOAK_INTERVAL_S:-60}"
END=$(( $(date +%s) + DUR_S ))
LOCK="/tmp/cozmo-companion.lock"
FLOCK="/tmp/cozmo-soak-8h.lock"
ALERTS=0
CRITICOS=0

exec 9>"$FLOCK"
if ! flock -n 9; then
  echo "[$(date -Iseconds)] soak 8h já em execução — abortando duplicata" | tee -a "$LOG"
  exit 0
fi

log() { echo "[$(date -Iseconds)] $*" | tee -a "$LOG"; }

companion_pid() {
  if [[ -f "$LOCK" ]]; then
    local pid
    pid="$(tr -d ' \n' <"$LOCK" 2>/dev/null || true)"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      echo "$pid"
      return 0
    fi
  fi
  pgrep -f '[.]venv/bin/python -m cozmo_companion$' 2>/dev/null | head -1 || true
}

start_companion() {
  log "RESTART companion"
  pkill -f '[.]venv/bin/python -m cozmo_companion$' 2>/dev/null || true
  sleep 2
  rm -f "$LOCK"
  cd "$ROOT"
  set -a
  # shellcheck source=/dev/null
  source "$ROOT/config.env"
  set +a
  export PYTHONPATH="$ROOT/src"
  export NOTIF_PC_BEEP=0
  nohup "$ROOT/.venv/bin/python" -m cozmo_companion >>"$ROOT/cozmo-companheiro.log" 2>&1 &
  sleep 8
}

wifi_ok() {
  ping -c1 -W2 172.31.1.1 >/dev/null 2>&1
}

wifi_reconnect() {
  if nmcli -t -f SSID dev wifi list 2>/dev/null | grep -qi '^Cozmo_'; then
    log "AUTO-FIX ping FAIL — reconectando Wi-Fi"
    COZMO_WIFI_SAFE=1 bash "$ROOT/conectar-cozmo.sh" >>"$LOG" 2>&1 || true
    return 0
  fi
  log "AUTO-FIX ping FAIL — AP Cozmo não visível"
  return 1
}

log_metrics() {
  local tail_n="${1:-400}"
  local gov cozmo01 stall drx dtx rd fase rx
  gov="$(tail -n "$tail_n" "$ROOT/cozmo-companheiro.log" 2>/dev/null | grep 'Governador fase=' | tail -1 | tr -d '\n' || true)"
  cozmo01="$(tail -n +"$LOG_START_LINES" "$ROOT/cozmo-companheiro.log" 2>/dev/null | grep -c 'COZMO 01 — seq' 2>/dev/null || echo 0)"
  stall="$(tail -n +"$LOG_START_LINES" "$ROOT/cozmo-companheiro.log" 2>/dev/null | grep -c 'rx=STALL' 2>/dev/null || echo 0)"
  cozmo01="${cozmo01//[$'\n\r ']/}"
  stall="${stall//[$'\n\r ']/}"
  drx="$(sed -n 's/.*drx=\([0-9]*\).*/\1/p' <<<"$gov" | tail -1)"
  dtx="$(sed -n 's/.*dtx=\([0-9]*\).*/\1/p' <<<"$gov" | tail -1)"
  rd="$(sed -n 's/.*rd=\([0-9.]*\).*/\1/p' <<<"$gov" | tail -1)"
  fase="$(sed -n 's/.*fase=\([^ ]*\).*/\1/p' <<<"$gov" | tail -1)"
  rx="$(sed -n 's/.*rx=\([^ ]*\).*/\1/p' <<<"$gov" | tail -1)"
  echo "$cozmo01|$stall|$drx|$dtx|$rd|$fase|$rx|$gov"
}

INICIO=$(date +%s)
LOG_START_LINES="$(wc -l < "$ROOT/cozmo-companheiro.log" 2>/dev/null | tr -d ' \n' || echo 0)"
FIM_HUMAN="$(date -d "@$END" '+%Y-%m-%d %H:%M:%S %z' 2>/dev/null || date -r "$END" '+%Y-%m-%d %H:%M:%S %z' 2>/dev/null || echo "?")"
log "=== SOAK 8h inicio dur=${DUR_S}s interval=${INTERVAL}s pid=$$ fim_est=${FIM_HUMAN} ==="

while [[ $(date +%s) -lt $END ]]; do
  elapsed=$(( $(date +%s) - INICIO ))
  pid="$(companion_pid || true)"
  if [[ -z "$pid" ]]; then
    log "ALERTA companion morto — restart"
    ALERTS=$((ALERTS + 1))
    start_companion
    pid="$(companion_pid || true)"
  fi

  ping_s="OK"
  if ! wifi_ok; then
    ping_s="FAIL"
    ALERTS=$((ALERTS + 1))
    wifi_reconnect || true
  fi

  IFS='|' read -r cozmo01 stall drx dtx rd fase rx gov <<<"$(log_metrics 400)"
  log "t=${elapsed}s pid=${pid:-?} ping=${ping_s} drx=${drx:-?} dtx=${dtx:-?} rd=${rd:-?} rx=${rx:-?} fase=${fase:-?} cozmo01=${cozmo01} stall=${stall} alerts=${ALERTS} criticos=${CRITICOS}"

  if [[ "${stall:-0}" -gt 5 ]] || [[ "${cozmo01:-0}" -gt 2 && "${rx:-OK}" == "STALL" ]]; then
    CRITICOS=$((CRITICOS + 1))
    log "CRITICO stall=${stall} cozmo01=${cozmo01} — auto-fix"
    if [[ "$ping_s" == "FAIL" ]]; then
      wifi_reconnect || true
    fi
    if [[ -n "$pid" ]] && ! kill -0 "$pid" 2>/dev/null; then
      start_companion
    elif [[ -n "$pid" ]] && [[ "${cozmo01:-0}" -gt 2 ]]; then
      log "CRITICO cozmo01 persistente — restart companion"
      start_companion
      pid="$(companion_pid || true)"
    fi
  fi

  sleep "$INTERVAL"
done

log "=== SOAK 8h fim elapsed=$(( $(date +%s) - INICIO ))s alerts=${ALERTS} criticos=${CRITICOS} ==="
