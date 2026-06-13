#!/usr/bin/env bash
# Instala dependências, modelo Vosk PT e serviço systemd.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

VOSK_DIR="$ROOT/data/vosk-model-small-pt-0.3"
VOSK_URL="https://alphacephei.com/vosk/models/vosk-model-small-pt-0.3.zip"

echo "==> venv + pip"
python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -r requirements.txt
.venv/bin/pycozmo_resources.py download || true

echo "==> modelo Vosk (português)"
mkdir -p "$ROOT/data"
if [[ ! -d "$VOSK_DIR" ]]; then
  tmp="$(mktemp -d)"
  curl -L "$VOSK_URL" -o "$tmp/vosk.zip"
  unzip -q "$tmp/vosk.zip" -d "$tmp"
  mv "$tmp"/vosk-model-small-pt-0.3 "$VOSK_DIR"
  rm -rf "$tmp"
fi

if [[ ! -f config.env ]]; then
  cp config.env.example config.env
  echo "Criei config.env — revise se necessário."
fi

echo "==> testes"
PYTHONPATH=src .venv/bin/python -m unittest discover -s src/cozmo_companion/__test__ -p 'test_*.py'

echo "==> comando cozmo (volume +/-)"
chmod +x "$ROOT/bin/cozmo"
mkdir -p "$HOME/.local/bin"
ln -sf "$ROOT/bin/cozmo" "$HOME/.local/bin/cozmo"

echo "Setup OK."
echo "  volume: cozmo | cozmo + | cozmo -  (PATH: ~/.local/bin ou $ROOT/bin)"
