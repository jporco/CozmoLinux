#!/usr/bin/env bash
# CozmoLinux installer — Arch-based distributions only.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}==>${NC} $*"; }
warn()  { echo -e "${YELLOW}!!>${NC} $*"; }
fail()  { echo -e "${RED}ERROR:${NC} $*" >&2; exit 1; }

arch_based() {
  [[ -f /etc/os-release ]] || return 1
  local id like
  id="$(grep -E '^ID=' /etc/os-release | cut -d= -f2 | tr -d '"')"
  like="$(grep -E '^ID_LIKE=' /etc/os-release | cut -d= -f2 | tr -d '"' || true)"
  case "$id" in
    arch|cachyos|manjaro|endeavouros|garuda|arcolinux|artix) return 0 ;;
  esac
  [[ "$like" == *arch* ]]
}

if ! arch_based; then
  fail "CozmoLinux supports Arch-based Linux distributions only (Arch, CachyOS, Manjaro, EndeavourOS, etc.)."
fi

info "CozmoLinux install directory: $ROOT"

PACMAN_PKGS=(
  python
  python-pip
  networkmanager
  espeak-ng
  pipewire
  pipewire-pulseaudio
  portaudio
  unzip
  curl
  git
  libpulse
  dbus
)

missing=()
for pkg in "${PACMAN_PKGS[@]}"; do
  pacman -Qi "$pkg" &>/dev/null || missing+=("$pkg")
done

if ((${#missing[@]})); then
  info "Installing packages: ${missing[*]}"
  if ! command -v sudo &>/dev/null; then
    fail "sudo required to install: ${missing[*]}"
  fi
  sudo pacman -S --needed --noconfirm "${missing[@]}"
else
  info "System packages already installed."
fi

info "Python virtual environment and dependencies"
python3 -m venv .venv
.venv/bin/pip install -U pip wheel
.venv/bin/pip install -r requirements.txt
.venv/bin/pycozmo_resources.py download || warn "pycozmo assets download failed — retry later if animations are missing."

VOSK_DIR="$ROOT/data/vosk-model-small-pt-0.3"
VOSK_URL="https://alphacephei.com/vosk/models/vosk-model-small-pt-0.3.zip"
if [[ ! -d "$VOSK_DIR" ]]; then
  info "Downloading Vosk Portuguese model (~40 MB)"
  mkdir -p "$ROOT/data"
  tmp="$(mktemp -d)"
  curl -L "$VOSK_URL" -o "$tmp/vosk.zip"
  unzip -q "$tmp/vosk.zip" -d "$tmp"
  mv "$tmp/vosk-model-small-pt-0.3" "$VOSK_DIR"
  rm -rf "$tmp"
fi

if [[ ! -f "$ROOT/config.env" ]]; then
  info "Creating config.env from template"
  cp "$ROOT/config.env.example" "$ROOT/config.env"
  sed -i "s|@INSTALL_DIR@|$ROOT|g" "$ROOT/config.env"
  echo
  warn "Set your Cozmo Wi-Fi password in config.env (COZMO_WIFI_SENHA=...)"
  warn "Optional: WEATHER_CITY, WEATHER_LAT, WEATHER_LON, MIC_DEVICE"
else
  sed -i "s|@INSTALL_DIR@|$ROOT|g" "$ROOT/config.env" 2>/dev/null || true
fi

if [[ ! -f "$ROOT/config.guardian.env" ]]; then
  cp "$ROOT/config.guardian.env.example" "$ROOT/config.guardian.env"
fi

chmod +x "$ROOT/conectar-cozmo.sh" "$ROOT/bin/cozmo" "$ROOT/scripts/"*.sh 2>/dev/null || true
mkdir -p "$ROOT/data" "$ROOT/assets"
if [[ ! -f "$ROOT/assets/beep_notif.wav" ]]; then
  info "Generating notification beep WAV"
  espeak-ng -q -v pt-br -s 380 -p 80 -a 200 -w "$ROOT/assets/beep_notif.wav" bip \
    || espeak -q -v pt-br -s 380 -p 80 -a 200 -w "$ROOT/assets/beep_notif.wav" bip \
    || warn "Could not generate beep_notif.wav — notification sound may use synthetic fallback."
fi

info "Installing systemd user units"
mkdir -p "$HOME/.config/systemd/user"
for unit in cozmo-companion.service cozmo-guardian.service; do
  sed "s|@INSTALL_DIR@|$ROOT|g" "$ROOT/systemd/$unit" > "$HOME/.config/systemd/user/$unit"
done
systemctl --user daemon-reload

info "Running tests"
PYTHONPATH=src .venv/bin/python -m pytest src/cozmo_companion -q --import-mode=importlib -x || warn "Some tests failed — review output before enabling the service."

cat <<EOF

${GREEN}Installation complete.${NC}

Next steps:
  1. Edit $ROOT/config.env
     - COZMO_WIFI_SENHA=<password on Cozmo's Wi-Fi label>
     - WEATHER_CITY / WEATHER_LAT / WEATHER_LON (optional)
     - MIC_DEVICE (optional microphone name)

  2. Put Cozmo on the charger, lift the lift arm, wait for Cozmo_XXXX Wi-Fi.

  3. Connect manually (first time):
     $ROOT/conectar-cozmo.sh

  4. Start the companion (foreground):
     cd $ROOT && PYTHONPATH=src .venv/bin/python -m cozmo_companion

  5. Or enable background service (Plasma session):
     systemctl --user enable --now cozmo-companion.service
     systemctl --user enable --now cozmo-guardian.service

  Volume CLI: cozmo | cozmo + | cozmo -
  Logs: $ROOT/cozmo-companheiro.log

EOF
