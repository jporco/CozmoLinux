#!/usr/bin/env bash
# Monitor Cozmo ~40 min — bateria, UDP, ping, serviço.
set -euo pipefail
ROOT="/mnt/G/PROJETOS/cozmo-companion"
LOG="${ROOT}/cozmo-watch-40m.log"
DUR_S="${1:-2400}"
END=$(( $(date +%s) + DUR_S ))
INTERVAL="${COZMO_WATCH_INTERVAL_S:-180}"

echo "=== watch inicio $(date -Iseconds) dur=${DUR_S}s interval=${INTERVAL}s ===" >>"$LOG"

while [[ $(date +%s) -lt $END ]]; do
  {
    echo "--- $(date -Iseconds) ---"
    echo -n "service="
    systemctl --user is-active cozmo-companion.service 2>/dev/null || echo "?"
    if ping -c1 -W2 172.31.1.1 >/dev/null 2>&1; then
      echo "ping=OK"
    else
      echo "ping=FAIL"
    fi
    echo "log_tail:"
    tail -4 "${ROOT}/cozmo-companheiro.log" 2>/dev/null || true
    echo "alertas:"
    rg -i "bateria:|vermelho|laranja|parando|falhou|stall|sem carga|economia|priorizando carga|TX sem RX" \
      "${ROOT}/cozmo-companheiro.log" 2>/dev/null | tail -6 || true
  } >>"$LOG" 2>&1
  sleep "$INTERVAL"
done

echo "=== watch fim $(date -Iseconds) ===" >>"$LOG"
