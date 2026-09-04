#!/usr/bin/env bash
# Habilita o CozmoLinux no login (systemd user + linger).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

"$ROOT/install.sh"

mkdir -p "$HOME/.config/systemd/user"
for unit in cozmo-companion.service cozmo-guardian.service; do
  sed "s|@INSTALL_DIR@|$ROOT|g" "$ROOT/systemd/$unit" \
    > "$HOME/.config/systemd/user/$unit"
done

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
systemctl --user enable --now cozmo-guardian.service

echo ""
echo "Serviço CozmoLinux ativo."
echo "  versão: $(tr -d '[:space:]' < "$ROOT/VERSION")"
echo "  status: systemctl --user status cozmo-companion"
echo "  guardian: systemctl --user status cozmo-guardian"
echo "  log:    tail -f $ROOT/cozmo-companheiro.log"
echo "  parar:  systemctl --user stop cozmo-companion"
