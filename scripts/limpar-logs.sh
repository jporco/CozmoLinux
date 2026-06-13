#!/usr/bin/env bash
# Limpa logs do cozmo-companion — mantém cauda útil, não mata o processo.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LINHAS="${COZMO_LOG_KEEP_LINES:-12000}"

trim() {
  local f="$1" n="$2" min="${3:-5242880}"
  [[ -f "$f" ]] || return 0
  local sz
  sz=$(stat -c%s "$f" 2>/dev/null || echo 0)
  if (( sz < min )); then
    return 0
  fi
  echo "trim $f ($(numfmt --to=iec "$sz" 2>/dev/null || echo "${sz}B")) → ${n} linhas"
  tail -n "$n" "$f" > "${f}.tmp"
  cat "${f}.tmp" > "$f"
  rm -f "${f}.tmp"
}

trim "$ROOT/cozmo-companheiro.log" "$LINHAS"
trim "$ROOT/guardian.log" 3000 262144
truncate -s 0 "$ROOT/.cursor/debug-5e34e1.log" 2>/dev/null || true
truncate -s 0 "$ROOT/.cursor/debug-trace.log" 2>/dev/null || true
rm -f "$ROOT/logs/"*.log 2>/dev/null || true
echo "OK — logs enxutos ($(date -Iseconds))"
