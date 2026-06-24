"""Política — filtro e texto OLED para notificações KDE."""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass

from cozmo_companion.notifications.core.listener import Notificacao

OLED_APP_DESCONHECIDO = "???"

_LIXO_APP_RE = re.compile(
    r"(?i)^(notifica(ç|c)[aã]o(ões|oes)?|notifications?)"
    r"(\s+(de|from|do|da|para|to|of))?\s*"
)
_LIXO_SISTEMA_RE = re.compile(
    r"(?i)^(notifica(ç|c)[aã]o(ões|oes)?\s+)?(do|da|de)\s+sistema$|^sistema$|^system$"
)
_PALAVRAS_LIXO_OLED = frozenset(
    {
        "mensagem",
        "message",
        "notificação",
        "notificacao",
        "notification",
        "notifications",
        "alerta",
        "alert",
        "aviso",
        "warning",
        "nova",
        "new",
        "novo",
        "sistema",
        "system",
        "do",
        "da",
        "de",
        "from",
        "of",
    }
)
_GENERICO_SUBSTR = (
    "notifica",
    "notification",
)

_ALIASES: dict[str, str] = {
    "org.telegram.desktop": "Telegram",
    "telegram": "Telegram",
    "discord": "Discord",
    "firefox": "Firefox",
    "google-chrome": "Chrome",
    "chromium": "Chromium",
    "brave": "Brave",
    "spotify": "Spotify",
    "steam": "Steam",
    "thunderbird": "Email",
    "org.kde.dolphin": "Arquivos",
    "dolphin": "Arquivos",
    "whatsapp": "WhatsApp",
    "signal": "Signal",
    "slack": "Slack",
    "cursor": "Cursor",
    "code": "VS Code",
}


@dataclass(frozen=True)
class ContextoNotif:
    falando: bool
    llm_ocupado: bool
    modo_udp_leve: bool
    na_base: bool
    carregando: bool
    ultima_em: float
    agora: float
    ultima_app: str = ""
    ultima_titulo: str = ""
    rx_ok: bool = True


def _lista_env(nome: str) -> frozenset[str]:
    raw = os.environ.get(nome, "")
    if not raw.strip():
        return frozenset()
    return frozenset(x.strip().lower() for x in raw.split(",") if x.strip())


def _limpar_app_dbus(app: str) -> str:
    s = re.sub(r"\s+", " ", (app or "").strip())
    if _LIXO_SISTEMA_RE.match(s):
        return ""
    for _ in range(6):
        novo = _LIXO_APP_RE.sub("", s, count=1).strip()
        if novo == s:
            break
        s = novo
    if _LIXO_SISTEMA_RE.match(s):
        return ""
    return s


def _app_e_generico_oled(nome: str) -> bool:
    if not nome or nome in (OLED_APP_DESCONHECIDO, "?", "??"):
        return True
    chave = nome.strip().lower()
    if chave in _PALAVRAS_LIXO_OLED:
        return True
    if any(tok in chave for tok in _GENERICO_SUBSTR):
        return True
    if _LIXO_SISTEMA_RE.match(chave):
        return True
    palavras = set(re.findall(r"\w+", chave, flags=re.UNICODE))
    return bool(palavras) and palavras <= _PALAVRAS_LIXO_OLED


def _normalizar_app(app: str) -> str:
    chave = _limpar_app_dbus(app).lower()
    if not chave:
        return ""
    if chave in _ALIASES:
        return _ALIASES[chave]
    for k, v in _ALIASES.items():
        if k in chave or chave.endswith(k):
            return v
    base = chave.rsplit(".", 1)[-1]
    base = re.sub(r"[-_]+", " ", base).strip()
    if not base:
        return ""
    if base.islower() or base.isupper():
        return base.title()
    return base[:1].upper() + base[1:]


def max_oled_chars() -> int:
    try:
        return max(8, int(os.environ.get("COZMO_MAX_OLED_CHARS", "16")))
    except ValueError:
        return 16


def nome_app_oled(notif: Notificacao) -> str:
    """Uma linha OLED — só nome do app; nunca título/corpo."""
    from cozmo_companion.notifications.core.apps import resolver_nome_app

    app = resolver_nome_app(notif)
    lim = max_oled_chars()
    if len(app) > lim:
        return app[:lim]
    return app


def texto_tela(notif: Notificacao) -> str:
    """Alias — OLED de notificação = nome do app."""
    return nome_app_oled(notif)


def texto_trecho(notif: Notificacao) -> str:
    """OLED de notificação — só nome do app (sem título/corpo)."""
    return nome_app_oled(notif)


def texto_scroll(notif: Notificacao) -> str:
    """Marquee — mesmo critério que OLED: só nome do app."""
    return nome_app_oled(notif)


def deve_processar(notif: Notificacao, ctx: ContextoNotif) -> bool:
    if os.environ.get("NOTIF_ENABLED", "0") != "1":
        return False

    app_raw = (notif.app or "").strip().lower()
    titulo = (notif.titulo or "").strip()
    if not app_raw and not titulo:
        return False

    ignorar = _lista_env("NOTIF_IGNORE_APPS") | frozenset(
        ("cozmo-companion", "plasmashell", "kded6", "notify-send")
    )
    if app_raw in ignorar:
        return False
    for bloqueado in ignorar:
        if not bloqueado:
            continue
        if app_raw == bloqueado or app_raw.endswith("." + bloqueado):
            return False
        if "." not in bloqueado and bloqueado in app_raw.split("."):
            return False

    if ctx.na_base and os.environ.get("NOTIF_NA_BASE", "1") != "1":
        return False

    if os.environ.get("NOTIF_IGNORE_DURING_TTS", "1") == "1" and (
        ctx.falando or ctx.llm_ocupado
    ):
        return False

    if ctx.modo_udp_leve and os.environ.get("NOTIF_BLOCK_UDP_LEVE", "1") == "1":
        return False

    if (
        ctx.na_base
        and os.environ.get("NOTIF_BLOCK_RX_STALL", "1") == "1"
        and not ctx.rx_ok
    ):
        return False

    if ctx.na_base:
        cooldown = float(
            os.environ.get(
                "NOTIF_BASE_COOLDOWN_S",
                os.environ.get("NOTIF_COOLDOWN_S", "0.4"),
            )
        )
    else:
        cooldown = float(os.environ.get("NOTIF_COOLDOWN_S", "0.4"))
    if ctx.ultima_em > 0 and ctx.agora - ctx.ultima_em < cooldown:
        app_ant = (ctx.ultima_app or "").strip().lower()
        tit_ant = (ctx.ultima_titulo or "").strip()
        if app_raw == app_ant and titulo == tit_ant:
            return False

    permitidos = _lista_env("NOTIF_APPS")
    if permitidos:
        alvo = app_raw or titulo.lower()
        if not any(p in alvo for p in permitidos):
            return False

    return True
