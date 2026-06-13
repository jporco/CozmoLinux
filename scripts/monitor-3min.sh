#!/usr/bin/env bash
# Monitor 3min — ratio ~1, rx OK, sem reconnect storm
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG="$ROOT/cozmo-companheiro.log"
DUR=180
INI=$(date +%s)
FIM=$((INI + DUR))
falhas=0
rec=0
stall=0
verm=0
ok_rx=0
n=0

echo "Monitor ${DUR}s — $(date -Iseconds)"

while [[ $(date +%s) -lt $FIM ]]; do
  sleep 15
  n=$((n + 1))
  trecho=$(tail -n 400 "$LOG" 2>/dev/null | tail -n 80)
  if echo "$trecho" | grep -qE "Reconexão UDP|COZMO 01 — reconexão|reset UDP"; then
    rec=$((rec + 1))
  fi
  if echo "$trecho" | grep -q "rx=STALL"; then
    stall=$((stall + 1))
  fi
  if echo "$trecho" | grep -q "fase=vermelho"; then
    verm=$((verm + 1))
  fi
  if echo "$trecho" | grep -q "rx=OK"; then
    ok_rx=$((ok_rx + 1))
  fi
  rd=$(echo "$trecho" | grep "Governador" | tail -1 | sed -n 's/.*rd=\([0-9.]*\).*/\1/p')
  echo "[$n] rd=${rd:-?} rec=$rec stall=$stall verm=$verm rx_ok_samples=$ok_rx"
done

if [[ $rec -ge 3 ]]; then falhas=$((falhas + 1)); fi
if [[ $stall -gt $((n / 2)) ]]; then falhas=$((falhas + 1)); fi
if [[ $ok_rx -lt $((n / 3)) ]]; then falhas=$((falhas + 1)); fi

notify-send -a cursor "Cozmo QA" "Monitor 3min: falhas=$falhas rec=$rec rx_ok=$ok_rx/$n" 2>/dev/null || true

if [[ $falhas -eq 0 ]]; then
  echo "OK"
  exit 0
fi
echo "FAIL falhas=$falhas"
exit 1
