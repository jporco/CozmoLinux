#!/usr/bin/env bash
# Teste E2E — beep notificação (mesmo pipeline TTS/voz).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f config.env ]]; then
  set -a
  # shellcheck disable=SC1091
  source config.env
  set +a
fi

echo "=== ping Cozmo ==="
if ! ping -c 1 -W 2 172.31.1.1 >/dev/null 2>&1; then
  echo "BLOQUEIO: Cozmo offline (ping 172.31.1.1)"
  exit 3
fi
echo "ping OK"

echo "=== gerar beep_notif.wav se faltar ==="
mkdir -p assets
if [[ ! -f assets/beep_notif.wav ]]; then
  espeak -v pt-br -s 420 -p 75 -a 200 -w assets/beep_notif.wav bip
fi
ls -la assets/beep_notif.wav

echo "=== teste isolado Python ==="
. .venv/bin/activate
export PYTHONPATH=src
python scripts/testar-som-cozmo.py
PY=$?

if [[ "$PY" -ne 0 ]]; then
  exit "$PY"
fi

echo "=== companion (sem restart se active — evita SIGTERM/sono) ==="
if systemctl --user is-active cozmo-companion.service >/dev/null 2>&1; then
  echo "companion já active — skip restart"
else
  systemctl --user start cozmo-companion.service
  sleep 4
fi
systemctl --user is-active cozmo-companion.service

echo "=== notify-send ==="
notify-send -a cozmo-test-som "Teste som" "Beep Cozmo"
sleep 6

echo "=== log som notif (últimas linhas) ==="
grep -E "play_audio notif|Fila — play_audio|Notificação → beep" cozmo-companheiro.log 2>/dev/null | tail -12 || true

echo "OK script concluído"
exit 0
