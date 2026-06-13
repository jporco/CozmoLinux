# CozmoLinux

Run an **Anki Cozmo** robot from a Linux PC — no phone required. CozmoLinux connects over Wi-Fi, keeps the robot on the charger, shows notifications on the OLED, plays short beeps on Cozmo's speaker, and supports voice wake word + optional local LLM chat (Ollama).

> **Arch Linux only** — this project is developed and tested on **Arch-based** distributions: Arch Linux, CachyOS, Manjaro, EndeavourOS, Garuda, Artix, and similar (`ID=arch` or `ID_LIKE=arch` in `/etc/os-release`). Other distros are not supported by the installer.

## Requirements

| Item | Notes |
|------|--------|
| **OS** | Arch-based Linux with **NetworkManager** (`nmcli`) |
| **Desktop** | KDE Plasma recommended (DBus notifications); X11 or Wayland |
| **Hardware** | Anki Cozmo (2016–2018), USB Wi-Fi or onboard Wi-Fi for robot AP |
| **Python** | 3.11+ (3.14 tested) |
| **Optional** | [Ollama](https://ollama.com) for conversational replies |
| **Optional** | USB microphone for voice commands |

Cozmo creates a Wi-Fi access point (`Cozmo_XXXX`) when awake on the charger. Your PC connects to that AP; the robot is always at **`172.31.1.1`**.

## Quick install

```bash
git clone https://github.com/jporco/CozmoLinux.git
cd CozmoLinux
chmod +x install.sh
./install.sh
```

Then edit `config.env` and set **`COZMO_WIFI_SENHA`** to the password printed on Cozmo's Wi-Fi label (or under the robot).

## Configuration

Copy is created automatically as `config.env`. Important keys:

| Variable | Description |
|----------|-------------|
| `COZMO_WIFI_SENHA` | Cozmo Wi-Fi password (**required**) |
| `COZMO_VOLUME` | Speaker volume 0–65535 |
| `WEATHER_CITY` / `WEATHER_LAT` / `WEATHER_LON` | Weather for voice/OLED |
| `MIC_DEVICE` | Microphone name (empty = system default) |
| `OLLAMA_URL` / `OLLAMA_MODEL` | Local LLM (optional) |
| `NOTIF_PC_AUDIO` | `0` = notification sound **only on Cozmo** (default) |

Never commit `config.env` — it contains your Wi-Fi password.

## Usage

**Connect Wi-Fi (first time or after reboot):**

```bash
./conectar-cozmo.sh
```

**Run in foreground (debugging):**

```bash
cd CozmoLinux
set -a && source config.env && set +a
PYTHONPATH=src .venv/bin/python -m cozmo_companion
```

**Systemd user service (auto-start with your session):**

```bash
systemctl --user enable --now cozmo-companion.service
systemctl --user enable --now cozmo-guardian.service
journalctl --user -u cozmo-companion.service -f
```

**Volume:**

```bash
cozmo      # show volume
cozmo +    # louder
cozmo -    # quieter
```

## Features

- **No phone** — direct UDP via [pycozmo](https://github.com/zaydman/pycozmo)
- **Charger / base mode** — wheels disabled while docked; head button toggles base vs free intent
- **KDE notifications** — short beep + app name on OLED (no PC speaker by default)
- **Voice** — wake word + Vosk STT (Portuguese model installed by `install.sh`)
- **Stability** — UDP governor, COZMO 01 recovery, guardian watchdog
- **Safe Wi-Fi** — does not break your main internet when Cozmo is offline (`COZMO_WIFI_SAFE=1`)

## Project layout

```
CozmoLinux/
├── install.sh           # Arch installer
├── config.env.example   # template (no secrets)
├── conectar-cozmo.sh    # Wi-Fi connect helper
├── src/cozmo_companion/ # application
├── scripts/             # diagnostics & helpers
├── systemd/             # user units (paths filled by install.sh)
└── data/                # runtime (Vosk model, volume, logs)
```

## Tests

```bash
PYTHONPATH=src .venv/bin/python -m pytest src/cozmo_companion -q --import-mode=importlib
```

## Troubleshooting

| Problem | Check |
|---------|--------|
| `COZMO 01` on screen | Wait for guardian recovery; see `cozmo-companion.log` |
| No ping to `172.31.1.1` | Cozmo on charger, arm up, `./conectar-cozmo.sh` |
| No voice | `MIC_DEVICE`, PipeWire/PulseAudio, `VOSK_MODEL` path |
| Notifications silent | `NOTIF_SOM=1`, volume `cozmo +`, robot not in sleep |
| Wrong Wi-Fi route | `ip route get 172.31.1.1` must **not** go `via` home gateway |

Hardware diagnostic:

```bash
PYTHONPATH=src .venv/bin/python scripts/diagnostico-hardware.py
```

## License

MIT — see [LICENSE](LICENSE). Not affiliated with Anki or Digital Dream Labs.

---

## Português (Brasil)

# CozmoLinux

Controle um **Anki Cozmo** pelo Linux — **sem celular**. O CozmoLinux conecta via Wi-Fi, mantém o robô na base carregando, mostra notificações no OLED, toca bips curtos no **alto-falante do Cozmo** e aceita palavra de ativação + chat opcional com LLM local (Ollama).

> **Somente Arch Linux** — projeto feito para distros **baseadas em Arch**: Arch Linux, CachyOS, Manjaro, EndeavourOS, Garuda, Artix etc. (`ID=arch` ou `ID_LIKE=arch` em `/etc/os-release`). O instalador **não** suporta Ubuntu, Fedora ou Debian.

## Requisitos

| Item | Detalhe |
|------|---------|
| **SO** | Linux baseado em Arch com **NetworkManager** (`nmcli`) |
| **Ambiente** | KDE Plasma recomendado (notificações DBus) |
| **Hardware** | Anki Cozmo, Wi-Fi no PC para o AP do robô |
| **Python** | 3.11+ |
| **Opcional** | Ollama, microfone USB |

Com o Cozmo na base e o braço levantado, ele cria o Wi-Fi `Cozmo_XXXX`. O IP do robô é **`172.31.1.1`**.

## Instalação rápida

```bash
git clone https://github.com/jporco/CozmoLinux.git
cd CozmoLinux
chmod +x install.sh
./install.sh
```

Edite `config.env` e defina **`COZMO_WIFI_SENHA`** (senha na etiqueta Wi-Fi do Cozmo).

## Configuração

| Variável | Descrição |
|----------|-----------|
| `COZMO_WIFI_SENHA` | Senha do Wi-Fi do Cozmo (**obrigatório**) |
| `COZMO_VOLUME` | Volume do alto-falante (0–65535) |
| `WEATHER_CITY` / `WEATHER_LAT` / `WEATHER_LON` | Clima na voz/OLED |
| `MIC_DEVICE` | Nome do microfone (vazio = padrão do sistema) |
| `NOTIF_PC_AUDIO` | `0` = som de notificação **só no Cozmo** (padrão) |

**Nunca** envie `config.env` para o Git — contém senha Wi-Fi.

## Uso

```bash
./conectar-cozmo.sh                    # conectar Wi-Fi
PYTHONPATH=src .venv/bin/python -m cozmo_companion   # foreground
systemctl --user enable --now cozmo-companion.service   # serviço
cozmo +                                # volume
```

## Recursos

- Sem celular (pycozmo / UDP)
- Modo base (sem rodas na base) e modo livre (fora da base)
- Notificações KDE → OLED + bip no Cozmo
- Voz em português (modelo Vosk instalado pelo `install.sh`)
- Recuperação COZMO 01 e guardian de estabilidade
- Wi-Fi seguro quando o Cozmo está desligado

## Testes

```bash
PYTHONPATH=src .venv/bin/python -m pytest src/cozmo_companion -q --import-mode=importlib
```

## Problemas comuns

| Sintoma | O que fazer |
|---------|-------------|
| Tela `COZMO 01` | Ver `cozmo-companion.log`; aguardar recuperação |
| Sem ping | Base + braço levantado → `./conectar-cozmo.sh` |
| Sem voz | `MIC_DEVICE`, PipeWire, caminho `VOSK_MODEL` |
| Sem som de notif | `NOTIF_SOM=1`, `cozmo +`, robô acordado |

## Licença

MIT — veja [LICENSE](LICENSE). Projeto independente; não afiliado à Anki ou Digital Dream Labs.
