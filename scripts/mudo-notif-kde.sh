#!/usr/bin/env bash
# Silencia sons de notificação KDE (plasmashell/libcanberra) — som Cozmo fica no robô.
set -euo pipefail
kwriteconfig6 --file plasmanotifyrc --group Applications --group cursor --key PlaySound --type bool -- false
kwriteconfig6 --file plasmanotifyrc --group Applications --group cozmo-companion --key PlaySound --type bool -- false
kwriteconfig6 --file plasmanotifyrc --group Applications --group cozmo-pw-trace --key PlaySound --type bool -- false
# Notificações globais (só se ainda ouvir som do Plasma após desligar por app):
if [[ "${1:-}" == "--global" ]]; then
  kwriteconfig6 --file kdeglobals --group Sounds --key Enable --type bool -- false
  echo "Sounds Enable=false (global). Reinicie sessão ou plasmashell para aplicar."
else
  echo "PlaySound=false para cursor/cozmo. Use --global para mutar todos os sons KDE."
fi
