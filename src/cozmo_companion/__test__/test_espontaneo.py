import random
import time

from cozmo_companion.perception.events import PerceptionEvent, PerceptionEventKind
from cozmo_companion.voice.espontaneo import FalaEspontanea, frase_eco_valida


def test_filtra_eco_ruido_e_comando(monkeypatch):
    monkeypatch.setenv("ECO_MIN_WORDS", "2")
    assert frase_eco_valida("qual o tempo") is None
    assert frase_eco_valida("cozmo vem aqui") is None
    assert frase_eco_valida("olha isso") == "olha isso"


def test_face_respeita_cooldown(monkeypatch):
    monkeypatch.setenv("ESPONTANEO_FACE_FALA", "1")
    monkeypatch.setenv("ESPONTANEO_FACE_CHANCE", "1")
    monkeypatch.setenv("ESPONTANEO_FACE_MIN_GAP_S", "0")
    monkeypatch.setenv("ESPONTANEO_FACE_COOLDOWN_S", "60")
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    fala = FalaEspontanea()
    evento = PerceptionEvent(kind=PerceptionEventKind.FACE_SEEN)

    assert fala.fala_rosto(evento) == "Oi!"
    assert fala.fala_rosto(evento) is None


def test_eco_no_modo_sinal_retorna_sinal_e_tela(monkeypatch):
    monkeypatch.setenv("ECO_FRASES_ENABLED", "1")
    monkeypatch.setenv("ECO_CHANCE", "1")
    monkeypatch.setenv("ECO_COOLDOWN_S", "0")
    monkeypatch.setenv("TTS_MODO", "sinal")
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    fala = FalaEspontanea()

    assert fala.fala_eco("olha isso") == ("Eco", "olha isso")


def test_eco_cooldown(monkeypatch):
    monkeypatch.setenv("ECO_CHANCE", "1")
    monkeypatch.setenv("ECO_COOLDOWN_S", "120")
    fala = FalaEspontanea()
    fala.ultimo_eco = time.monotonic()

    assert fala.fala_eco("olha isso") is None
