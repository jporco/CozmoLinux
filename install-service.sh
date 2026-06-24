#!/usr/bin/env bash
# Habilita o Cozmo companheiro no boot (systemd user + linger).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

"$ROOT/setup.sh"

# Para processo manual antigo
pkill -f "python.*companheiro.py" 2>/dev/null || true
pkill -f "python -m cozmo_companion" 2>/dev/null || true

mkdir -p "$HOME/.config/systemd/user"
cp "$ROOT/systemd/cozmo-companion.service" "$HOME/.config/systemd/user/"

# Wi-Fi do Cozmo reconecta sozinho
nmcli connection modify Cozmo_31CE41 connection.autoconnect yes 2>/dev/null || true

# Ollama para conversa inteligente (opcional)
if systemctl list-unit-files ollama.service &>/dev/null; then
  sudo systemctl enable --now ollama.service 2>/dev/null || true
  if command -v ollama &>/dev/null; then
    ollama pull llama3.2:1b 2>/dev/null || true
  fi
fi

loginctl enable-linger "$USER" 2>/dev/null || true

systemctl --user daemon-reload
systemctl --user enable --now cozmo-companion.service

echo ""
echo "Serviço cozmo-companion ativo."
echo "  status: systemctl --user status cozmo-companion"
echo "  log:    tail -f $ROOT/cozmo-companheiro.log"
echo "  parar:  systemctl --user stop cozmo-companion"
