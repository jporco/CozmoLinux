# AGENTS.md

## Cursor Cloud specific instructions

CozmoLinux é um app Python que controla um robô Anki Cozmo por Wi-Fi/UDP
(`pycozmo`) a partir de um PC Linux: notificações no OLED, bips no alto-falante,
palavra de ativação + STT (Vosk) e chat opcional (Ollama). Alvo oficial do
`install.sh` é Arch, mas o app roda igual neste VM Ubuntu 24.04 (Python 3.12).

### Ambiente (já preparado no snapshot)
- Virtualenv em `.venv` (não use o `pip` do sistema). Ative com o prefixo
  `PYTHONPATH=src .venv/bin/python ...`, como no README.
- Dependências de sistema já instaladas via apt (persistem no snapshot):
  `libgirepository1.0-dev`, `libgirepository-2.0-dev`, `libglib2.0-dev`,
  `libdbus-1-dev`, `libcairo2-dev`, `python3-dev`, `pkg-config`,
  `portaudio19-dev`/`libportaudio2` (sounddevice), `espeak` e `espeak-ng`,
  `python3.12-venv`, `fonts-dejavu-core`.
  - `dbus-python` e `PyGObject` compilam do source; `PyGObject 3.56` exige o pc
    `girepository-2.0` (pacote `libgirepository-2.0-dev`), não só o 1.0.
- Fonte OLED: `face.py` procura TTF em caminhos do Arch e, primeiro, em
  `src/data/fonts/DejaVuSans.ttf`. Sem uma TTF Unicode, o texto acentuado (ç/ã/é)
  vira caixinhas (cai no bitmap default). Um symlink para a DejaVu do sistema já
  existe em `src/data/fonts/DejaVuSans.ttf` (recrie com
  `ln -sf /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf src/data/fonts/DejaVuSans.ttf`
  se sumir).

### Config
- `config.env` e `config.guardian.env` são criados a partir dos `*.example`
  (gitignored). Rode `sed -i "s|@INSTALL_DIR@|/workspace|g"` neles.
- Ao dar `source config.env`, a linha `GAME_PROCESSES=your-game.exe,Your Game`
  emite `Game: command not found` (valor com espaço sem aspas no exemplo). É
  cosmético e não impede o boot.

### Rodar
- Foreground: `set -a && source config.env && set +a && PYTHONPATH=src .venv/bin/python -m cozmo_companion`
- Sem o robô físico (172.31.1.1) o app entra em modo offline seguro e loga
  `Cozmo offline — aguardando ...` em backoff, sem floodar Wi-Fi. Isso é o
  comportamento esperado no VM (não há hardware).
- Não há robô nem `nmcli` no VM; funcionalidades de rede/hardware (conexão UDP,
  reconexão Wi-Fi) não podem ser exercitadas end-to-end aqui. O núcleo testável
  sem hardware inclui render OLED (`display/face.py` + `pycozmo.image_encoder`) e
  TTS→pacotes de áudio (`voice/tts.py` via `espeak`).

### Testes / lint
- Testes: `PYTHONPATH=src .venv/bin/python -m pytest src/cozmo_companion -q --import-mode=importlib`
- Não há linter configurado no repo (sem ruff/flake8/black/pyproject).
- Gotcha de teste (pré-existente, não é do ambiente):
  `test_display.py::TestDisplay::test_envia_via_anim_controller` falha quando a
  suíte roda inteira porque `test_motor_cozmo.py` seta o global
  `motor._charger_keeper_ativo = True` sem restaurar (poluição de estado). O
  teste passa isolado. Rode-o sozinho para validar OLED direto.
