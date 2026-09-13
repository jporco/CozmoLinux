#!/usr/bin/env bash
# Conecta o PC ao Wi-Fi do Cozmo (sem celular).
# COZMO_WIFI_SAFE=1: não mexe no Wi-Fi do PC se o AP Cozmo não existir.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SENHA="${1:-}"
SAFE="${COZMO_WIFI_SAFE:-1}"
IFACE="${COZMO_WIFI_IFACE:-}"
NMCLI_BIN="$(type -P nmcli || true)"

# NetworkManager pode bloquear durante uma varredura ou ao trocar o MAC da
# interface. Nunca deixe esse bloqueio prender o loop de recuperação do
# companion.
nmcli() {
  [[ -n "$NMCLI_BIN" ]] || return 127
  timeout --foreground "${COZMO_NMCLI_TIMEOUT_S:-6}" "$NMCLI_BIN" "$@"
}

if [[ -z "$SENHA" && -f "$ROOT/config.env" ]]; then
  SENHA="$(grep -E '^COZMO_WIFI_SENHA=' "$ROOT/config.env" | cut -d= -f2- || true)"
fi

# O serviço recebe config.env via EnvironmentFile, mas quem chama este script
# manualmente não. Leia somente a interface salva (sem executar o arquivo nem
# carregar segredos) para ambos os caminhos usarem a mesma placa Wi-Fi.
if [[ -z "$IFACE" && -f "$ROOT/config.env" ]]; then
  IFACE="$(grep -E '^COZMO_WIFI_IFACE=' "$ROOT/config.env" | cut -d= -f2- | head -1 || true)"
fi
IFACE="${IFACE:-wlan0}"

if ping -c1 -W2 172.31.1.1 >/dev/null 2>&1; then
  ip route get 172.31.1.1 2>/dev/null | grep -q ' via ' && {
    echo "Rota errada para Cozmo — reconectando Wi-Fi..."
  } || {
    echo "Já conectado. Cozmo em 172.31.1.1"
    exit 0
  }
fi

ajustar_perfil_cozmo() {
  local ssid="$1" never_default route_metric autoconnect priority powersave iface_atual
  [[ -z "$ssid" ]] && return 0
  never_default="$(nmcli -g ipv4.never-default connection show "$ssid" 2>/dev/null || true)"
  route_metric="$(nmcli -g ipv4.route-metric connection show "$ssid" 2>/dev/null || true)"
  autoconnect="$(nmcli -g connection.autoconnect connection show "$ssid" 2>/dev/null || true)"
  priority="$(nmcli -g connection.autoconnect-priority connection show "$ssid" 2>/dev/null || true)"
  powersave="$(nmcli -g 802-11-wireless.powersave connection show "$ssid" 2>/dev/null || true)"
  iface_atual="$(nmcli -g connection.interface-name connection show "$ssid" 2>/dev/null || true)"
  if [[ "$never_default" == "yes" && "$route_metric" == "850" \
    && "$autoconnect" == "yes" && "$priority" == "50" \
    && ("$powersave" == "2" || "$powersave" == "disable") \
    && "$iface_atual" == "$IFACE" ]]; then
    return 0
  fi
  nmcli connection modify "$ssid" \
    ipv4.never-default yes \
    ipv4.route-metric 850 \
    connection.autoconnect yes \
    connection.autoconnect-priority 50 \
    connection.interface-name "$IFACE" \
    802-11-wireless.powersave 2 \
    >/dev/null 2>&1 || true
}

SSID="$(nmcli -t -f NAME connection show 2>/dev/null | grep -i '^Cozmo_' | head -1 || true)"
[[ -n "$SSID" ]] && ajustar_perfil_cozmo "$SSID"

# Modo seguro: só sobe o perfil quando o AP estiver visível. Não desconecte um
# perfil já ativo: na MT7921e desta máquina uma desassociação durante falha de
# ARP pode travar o firmware do rádio e derrubar o Wi-Fi inteiro.
if [[ "$SAFE" == "1" ]]; then
  nmcli dev wifi rescan >/dev/null 2>&1 || true
  sleep 1
  SSID_VIS="$(nmcli -t -f SSID dev wifi list 2>/dev/null | grep -i '^Cozmo_' | head -1 || true)"
  if [[ -z "$SSID_VIS" ]]; then
    echo "Cozmo offline — sem AP visível (modo seguro, Wi-Fi PC intacto)."
    exit 2
  else
    SSID="$SSID_VIS"
  fi
fi

if [[ -n "$SSID" ]]; then
  ajustar_perfil_cozmo "$SSID"
  nmcli radio wifi on >/dev/null 2>&1 || true
  if [[ "$SAFE" == "1" ]]; then
    nmcli connection up "$SSID" ifname "$IFACE" >/dev/null 2>&1 || true
  else
    nmcli connection up "$SSID" ifname "$IFACE" >/dev/null 2>&1 || true
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
  nmcli connection up "$SSID" ifname "$IFACE" >/dev/null 2>&1 || true
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
  nmcli connection up "$SSID" ifname "$IFACE" || exit 1
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
