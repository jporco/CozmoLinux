#!/usr/bin/env bash
# Evita duplicata: se companion já roda (lock), systemd considera OK.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOCK="${COZMO_LOCK_FILE:-/tmp/cozmo-companion.lock}"

if [[ -f "$LOCK" ]]; then
  pid="$(tr -d ' \n' <"$LOCK" 2>/dev/null || true)"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    if ps -p "$pid" -o args= 2>/dev/null | grep -q '[c]ozmo_companion'; then
      echo "Companion já ativo (pid $pid)"
      exit 0
    fi
  fi
fi

cd "$ROOT"
set -a
# shellcheck source=/dev/null
source "$ROOT/config.env"
set +a
export PYTHONPATH="$ROOT/src"
exec "$ROOT/.venv/bin/python" -m cozmo_companion
