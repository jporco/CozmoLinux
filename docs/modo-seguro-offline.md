# Safe mode — Cozmo offline

When Cozmo is off, the companion **does not change your PC Wi-Fi** (your main network stays connected).

## Behaviour

- `COZMO_WIFI_SAFE=1` — only connects to `Cozmo_*` AP if visible in scan
- `conectar-cozmo.sh` — exit 2 if robot absent; no aggressive Wi-Fi toggling
- Companion — backoff between retries; sparse offline logs
- Guardian — Wi-Fi probe only when AP visible

## When you turn Cozmo on

1. Dock on charger, lift the arm (screen on)
2. Wait ~30s for `Cozmo_XXXX` Wi-Fi
3. Run `./conectar-cozmo.sh` or restart `cozmo-companion.service`

No PC reboot required.
