#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

[[ -d .venv ]] || "$ROOT/setup.sh"

if [[ -f config.env ]]; then
  set -a
  # shellcheck disable=SC1091
  source config.env
  set +a
fi

if ! ping -c1 -W2 172.31.1.1 >/dev/null 2>&1; then
  echo "Conectando ao Cozmo..."
  "$ROOT/conectar-cozmo.sh" "${1:-}"
fi

export PYTHONPATH="$ROOT/src"
exec "$ROOT/.venv/bin/python" -m cozmo_companion "${@}"
