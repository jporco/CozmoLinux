#!/usr/bin/env bash
# Conecta o PC ao Wi-Fi do Cozmo (sem celular).
# COZMO_WIFI_SAFE=1: não mexe no Wi-Fi do PC se o AP Cozmo não existir.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SENHA="${1:-}"
SAFE="${COZMO_WIFI_SAFE:-1}"
IFACE="${COZMO_WIFI_IFACE:-wlan0}"

if [[ -z "$SENHA" && -f "$ROOT/config.env" ]]; then
  SENHA="$(grep -E '^COZMO_WIFI_SENHA=' "$ROOT/config.env" | cut -d= -f2- || true)"
fi

if ping -c1 -W2 172.31.1.1 >/dev/null 2>&1; then
  ip route get 172.31.1.1 2>/dev/null | grep -q ' via ' && {
    echo "Rota errada para Cozmo — reconectando Wi-Fi..."
  } || {
    echo "Já conectado. Cozmo em 172.31.1.1"
    exit 0
  }
fi

ajustar_perfil_cozmo() {
  local ssid="$1"
  [[ -z "$ssid" ]] && return 0
  nmcli connection modify "$ssid" \
    ipv4.never-default yes \
    ipv4.route-metric 850 \
    connection.autoconnect yes \
    connection.autoconnect-priority 50 \
    802-11-wireless.powersave 2 \
    >/dev/null 2>&1 || true
}

liberar_wlan0_preso() {
  local estado conexao
  estado="$(nmcli -t -f GENERAL.STATE dev show "$IFACE" 2>/dev/null | cut -d: -f2- | tr '[:upper:]' '[:lower:]' || true)"
  conexao="$(nmcli -t -f GENERAL.CONNECTION dev show "$IFACE" 2>/dev/null | cut -d: -f2- || true)"
  if [[ "$conexao" == Cozmo_* ]] && [[ "$estado" == *connecting* || "$estado" == *failed* || "$estado" == *disconnected* ]]; then
    nmcli dev disconnect "$IFACE" >/dev/null 2>&1 || true
    sleep 1
    return 0
  fi
  if ip route get 172.31.1.1 2>/dev/null | grep -q ' via '; then
    nmcli dev disconnect "$IFACE" >/dev/null 2>&1 || true
    sleep 1
  fi
  return 0
}

liberar_wlan0_preso

SSID="$(nmcli -t -f NAME connection show 2>/dev/null | grep -i '^Cozmo_' | head -1 || true)"
[[ -n "$SSID" ]] && ajustar_perfil_cozmo "$SSID"

# Modo seguro: exige AP visível antes de subir perfil (evita wlan0 preso).
if [[ "$SAFE" == "1" ]]; then
  nmcli dev wifi rescan >/dev/null 2>&1 || true
  sleep 1
  SSID_VIS="$(nmcli -t -f SSID dev wifi list 2>/dev/null | grep -i '^Cozmo_' | head -1 || true)"
  if [[ -z "$SSID_VIS" ]]; then
    if [[ -n "$SSID" ]]; then
      echo "Cozmo offline — sem AP visível (modo seguro, Wi-Fi PC intacto)."
      exit 2
    fi
    echo "Cozmo offline — sem AP visível (modo seguro, Wi-Fi PC intacto)."
    exit 2
  fi
  SSID="$SSID_VIS"
fi

if [[ -n "$SSID" ]]; then
  ajustar_perfil_cozmo "$SSID"
  nmcli radio wifi on >/dev/null 2>&1 || true
  if [[ "$SAFE" == "1" ]]; then
    nmcli connection up "$SSID" >/dev/null 2>&1 || true
  else
    nmcli connection up "$SSID" >/dev/null 2>&1 || true
  fi
  for _ in 1 2 3 4 5 6; do
    sleep 2
    if ping -c1 -W2 172.31.1.1 >/dev/null 2>&1 && ! ip route get 172.31.1.1 2>/dev/null | grep -q ' via '; then
      echo "Conectado via perfil $SSID"
      exit 0
    fi
  done
fi

if [[ "$SAFE" == "1" ]]; then
  SSID_LIST="$(nmcli -t -f SSID dev wifi list 2>/dev/null | grep -i '^Cozmo_' | head -1 || true)"
  if [[ -z "$SSID_LIST" ]]; then
    echo "Cozmo offline — sem AP visível (modo seguro, Wi-Fi PC intacto)."
    exit 2
  fi
fi

nmcli radio wifi on >/dev/null 2>&1 || true

if [[ "$SAFE" != "1" ]]; then
  nmcli dev wifi rescan >/dev/null 2>&1 || true
  sleep 2
fi

SSID="$(nmcli -t -f SSID,SIGNAL dev wifi list 2>/dev/null | grep -i '^Cozmo_' | head -1 | cut -d: -f1 || true)"
SIGNAL="$(nmcli -t -f SSID,SIGNAL dev wifi list 2>/dev/null | grep -i "^${SSID}:" | cut -d: -f2 | tr -d ' ' || echo 0)"

if [[ -n "$SSID" && "${SIGNAL:-0}" -lt 5 ]]; then
  echo "Cozmo $SSID sinal fraco (${SIGNAL:-0}) — tentando perfil salvo..."
fi

if [[ -z "$SSID" ]]; then
  if [[ "$SAFE" == "1" ]]; then
    echo "Cozmo Wi-Fi ausente — modo seguro (sem alterar rede do PC)."
    exit 2
  fi
  echo "Cozmo Wi-Fi ausente — encaixe na base e levante o braço."
  exit 1
fi

ajustar_perfil_cozmo "$SSID"

if [[ "${SIGNAL:-0}" -lt 5 ]]; then
  nmcli connection up "$SSID" >/dev/null 2>&1 || true
  for _ in 1 2 3 4 5 6 7 8; do
    sleep 2
    if ping -c1 -W2 172.31.1.1 >/dev/null 2>&1 && ! ip route get 172.31.1.1 2>/dev/null | grep -q ' via '; then
      echo "Conectado (sinal baixo)."
      exit 0
    fi
  done
  echo "Cozmo $SSID sem ping — encaixe na base, telinha ligada."
  exit 1
fi

echo "Cozmo detectado: $SSID (sinal $SIGNAL)"
if [[ -z "$SENHA" ]]; then
  echo "Senha Wi-Fi não configurada em config.env"
  exit 1
fi

if nmcli -t -f NAME connection show 2>/dev/null | grep -qx "$SSID"; then
  nmcli connection up "$SSID" || exit 1
else
  nmcli dev wifi connect "$SSID" password "$SENHA" name "$SSID" || exit 1
  ajustar_perfil_cozmo "$SSID"
fi

sleep 2
if ping -c1 -W3 172.31.1.1 >/dev/null 2>&1 && ! ip route get 172.31.1.1 2>/dev/null | grep -q ' via '; then
  echo "Conectado. Cozmo em 172.31.1.1"
  exit 0
fi

echo "Wi-Fi ok mas Cozmo sem ping — aguarde na base."
exit 1
