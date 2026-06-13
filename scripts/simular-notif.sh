#!/usr/bin/env bash
# Simula notificação KDE para testar OLED do Cozmo (dbus Notify).
set -euo pipefail
APP="${1:-cozmo-teste}"
TITULO="${2:-Alerta simulado}"
CORPO="${3:-Teste cozmo-companion}"
exec notify-send -a "$APP" "$TITULO" "$CORPO"
