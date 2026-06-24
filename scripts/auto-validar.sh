#!/usr/bin/env bash
# Valida pipeline + injeta frases no companion (data/voz.cmd) quando ping OK.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p data
source config.env 2>/dev/null || true
export PYTHONPATH="$ROOT/src"

if [[ -x "$ROOT/scripts/test-pipeline-voz.sh" ]]; then
  bash "$ROOT/scripts/test-pipeline-voz.sh" >/tmp/cozmo-test-pipeline.log 2>&1 || {
    tail -20 /tmp/cozmo-test-pipeline.log
    exit 1
  }
else
  "${PYTHON:-$ROOT/.venv/bin/python}" -m pytest \
    src/cozmo_companion/__test__/test_wake.py \
    src/cozmo_companion/__test__/test_intent.py \
    src/cozmo_companion/__test__/test_tts.py \
    src/cozmo_companion/__test__/test_notificacoes.py \
    src/cozmo_companion/__test__/test_fila_cozmo.py \
    -q >/tmp/cozmo-test-pipeline.log 2>&1 || {
      tail -40 /tmp/cozmo-test-pipeline.log
      exit 1
    }
fi

if ! ping -c1 -W2 172.31.1.1 >/dev/null 2>&1; then
  bash "$ROOT/conectar-cozmo.sh" || true
fi

if ! ping -c1 -W2 172.31.1.1 >/dev/null 2>&1; then
  echo "Cozmo offline — código OK, aguardando Wi-Fi do robô"
  exit 0
fi

for frase in oi "cozmo que horas são" "estou triste"; do
  echo "$frase" > "$ROOT/data/voz.cmd"
  sleep 22
done

grep "COZMO 01\|sem resposta UDP" "$ROOT/cozmo-companheiro.log" | tail -3 || echo "Sem COZMO 01 recente"
tail -15 "$ROOT/cozmo-companheiro.log" | grep -E "Voz injetada|Responde|Falando|ERROR" | tail -10
