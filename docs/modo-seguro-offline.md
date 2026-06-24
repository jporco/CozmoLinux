# Modo seguro — Cozmo offline

Quando o Cozmo está desligado, o companion **não mexe no Wi-Fi do PC** (node-red, sunshine, tailscale, etc. intactos).

## O que mudou

- `COZMO_WIFI_SAFE=1` — só conecta ao AP `Cozmo_*` se ele aparecer no scan
- `conectar-cozmo.sh` — exit 2 silencioso se robô ausente; sem `nmcli radio wifi on` agressivo
- `ExecStartPre` do systemd — removido `nmcli radio wifi on` no boot
- Companion — backoff 120–600s entre tentativas; log a cada 5 min (não flood)
- Guardian — Wi-Fi só se AP visível; cooldown 300s; `Restart=on-failure`
- Notificações — cooldown 45s / 60s na base
- COZMO01 — cooldown auto 45s (menos agressivo)

## Quando ligar o Cozmo (3 passos)

1. **Liga o Cozmo** — encaixa na base, levanta o braço (telinha acende)
2. **Aguarda ~30s** — AP Wi-Fi `Cozmo_xxxx` aparece; PC reconecta sozinho
3. **Pronto** — `cozmo-companion.service` já sobe sozinho; se precisar: `systemctl --user restart cozmo-companion`

Não precisa reiniciar o PC nem matar outros serviços.
