"""Resolve nome amigável do app a partir de dbus, .desktop, ícone e título."""

from __future__ import annotations

import logging
import os
import re
from functools import lru_cache
from pathlib import Path

from cozmo_companion.notifications.core.listener import Notificacao

logger = logging.getLogger("cozmo.notif.apps")

_ALIASES: dict[str, str] = {
    "org.telegram.desktop": "Telegram",
    "telegram": "Telegram",
    "org.kde.discover": "Discover",
    "org.kde.dolphin": "Arquivos",
    "org.kde.kmail2": "KMail",
    "org.kde.plasma.browser_integration": "Firefox",
    "org.kde.plasma.notifications": "",
    "org.kde.plasma.networkmanagement": "",
    "org.kde.kdeconnect": "KDE Connect",
    "org.kde.konversation": "Konversation",
    "org.kde.neochat": "NeoChat",
    "com.discordapp.Discord": "Discord",
    "discord": "Discord",
    "firefox": "Firefox",
    "librewolf": "Librewolf",
    "google-chrome": "Chrome",
    "chromium": "Chromium",
    "brave-browser": "Brave",
    "microsoft-edge": "Edge",
    "vivaldi-stable": "Vivaldi",
    "spotify": "Spotify",
    "steam": "Steam",
    "steam_runtime": "Steam",
    "thunderbird": "Thunderbird",
    "org.mozilla.thunderbird": "Thunderbird",
    "whatsapp": "WhatsApp",
    "whatsapp-for-linux": "WhatsApp",
    "signal": "Signal",
    "slack": "Slack",
    "cursor": "Cursor",
    "code": "VS Code",
    "code-oss": "VS Code",
    "com.visualstudio.code": "VS Code",
    "github": "GitHub",
    "com.github.": "GitHub",
    "element-desktop": "Element",
    "io.element.": "Element",
    "net.lutris.lutris": "Lutris",
    "com.heroicgameslauncher.hgl": "Heroic",
    "com.valvesoftware.Steam": "Steam",
    "com.obsproject.Studio": "OBS",
    "org.gnome.Evolution": "Evolution",
    "org.gnome.TelegramDesktop": "Telegram",
    "com.microsoft.Teams": "Teams",
    "zoom": "Zoom",
    "us.zoom.Zoom": "Zoom",
    "hotmail": "Outlook",
    "outlook": "Outlook",
    "evolution": "Email",
    "kmail": "KMail",
    "gw2": "GW2",
    "guild wars": "GW2",
    "super-led-mail": "Email",
}


def _desktop_dirs() -> list[Path]:
    home = Path(os.path.expanduser("~/.local/share/applications"))
    dirs = [home]
    for parte in os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":"):
        p = Path(parte.strip()) / "applications"
        if p.is_dir():
            dirs.append(p)
    flatpak = Path(os.path.expanduser("~/.local/share/flatpak/exports/share/applications"))
    if flatpak.is_dir():
        dirs.append(flatpak)
    snap = Path("/var/lib/snapd/desktop/applications")
    if snap.is_dir():
        dirs.append(snap)
    vistos: set[str] = set()
    out: list[Path] = []
    for d in dirs:
        s = str(d)
        if s not in vistos:
            vistos.add(s)
            out.append(d)
    return out


@lru_cache(maxsize=512)
def _nome_arquivo_desktop(caminho: str) -> str | None:
    try:
        p = Path(caminho)
        if not p.is_file():
            return None
        nome: str | None = None
        for linha in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if linha.startswith("Name="):
                nome = linha[5:].strip()
            elif linha.startswith("GenericName=") and not nome:
                nome = linha[12:].strip()
        if not nome:
            return None
        return re.sub(r"\s+", " ", nome).strip()
    except OSError:
        return None


def _candidatos_desktop(app_id: str) -> list[Path]:
    raw = (app_id or "").strip()
    if not raw:
        return []
    base = raw if raw.endswith(".desktop") else f"{raw}.desktop"
    stem = Path(base).stem
    nomes = {base, stem, stem.replace("_", "-"), f"{stem.replace('_', '-')}.desktop"}
    out: list[Path] = []
    for d in _desktop_dirs():
        for nome in nomes:
            p = d / nome
            if p.is_file():
                out.append(p)
    return out


def nome_de_desktop(app_id: str) -> str:
    for p in _candidatos_desktop(app_id):
        nome = _nome_arquivo_desktop(str(p))
        if nome:
            return nome
    return ""


def _token_icone(icone: str) -> str:
    raw = (icone or "").strip()
    if not raw:
        return ""
    if raw.startswith("/"):
        stem = Path(raw).stem
    else:
        stem = raw.rsplit("/", 1)[-1]
    stem = re.sub(r"[-_]?(?:icon|logo)?[-_]?\d+$", "", stem, flags=re.I)
    stem = re.sub(r"[-_]+", " ", stem).strip()
    return stem


def _alias_de_chave(chave: str) -> str:
    k = re.sub(r"\s+", " ", (chave or "").strip().lower())
    if not k:
        return ""
    if k in _ALIASES:
        return _ALIASES[k]
    for pref, nome in _ALIASES.items():
        if pref.endswith(".") and k.startswith(pref):
            return nome
    for pref, nome in sorted(_ALIASES.items(), key=lambda x: len(x[0]), reverse=True):
        if len(pref) >= 3 and pref in k:
            return nome
    return ""


def _formatar_token(token: str) -> str:
    t = re.sub(r"[-_]+", " ", (token or "").strip())
    if not t:
        return ""
    if t.islower() or t.isupper():
        return t.title()
    return t[:1].upper() + t[1:]


def _nome_de_titulo(titulo: str) -> str:
    t = re.sub(r"\s+", " ", (titulo or "").strip())
    if not t:
        return ""
    for sep in (" — ", " – ", " - ", " | ", ": "):
        if sep in t:
            for parte in (t.split(sep, 1)[0].strip(), t.split(sep, 1)[-1].strip()):
                hit = _alias_de_chave(parte)
                if hit:
                    return hit
                fmt = _formatar_token(parte)
                if fmt and len(fmt) <= 16:
                    return fmt
    hit = _alias_de_chave(t)
    if hit:
        return hit
    for pref, nome in sorted(_ALIASES.items(), key=lambda x: len(x[0]), reverse=True):
        if len(pref) >= 4 and pref in t.lower():
            return nome
    return ""


def _app_e_generico(nome: str) -> bool:
    from cozmo_companion.notifications.core.policy import _app_e_generico_oled

    return _app_e_generico_oled(nome)


def resolver_nome_app(notif: Notificacao) -> str:
    """Melhor nome para OLED — app dbus, .desktop, ícone, título."""
    candidatos: list[str] = []

    app_raw = (notif.app or "").strip()
    if app_raw:
        candidatos.append(_alias_de_chave(app_raw))
        candidatos.append(nome_de_desktop(app_raw))
        candidatos.append(_formatar_token(app_raw.rsplit(".", 1)[-1]))

    icone = _token_icone(notif.icone)
    if icone:
        candidatos.append(_alias_de_chave(icone))
        candidatos.append(_formatar_token(icone))

    candidatos.append(_nome_de_titulo(notif.titulo))

    for nome in candidatos:
        nome = re.sub(r"\s+", " ", (nome or "").strip())
        if nome and not _app_e_generico(nome):
            logger.info(
                "Notif app → OLED %r (dbus=%r icone=%r)",
                nome,
                app_raw[:40],
                (notif.icone or "")[:40],
            )
            return nome

    logger.info(
        "Notif app desconhecido (dbus=%r icone=%r titulo=%r)",
        app_raw[:40],
        (notif.icone or "")[:40],
        (notif.titulo or "")[:40],
    )
    return "???"
