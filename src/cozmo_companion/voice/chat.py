"""Respostas inteligentes — Ollama como cérebro; hora/clima instantâneos."""

from __future__ import annotations

import logging
import os
import random
import re
from typing import Dict, List, Optional

import requests

from cozmo_companion.core import hora
from cozmo_companion.voice.acoes_llm import (
    ACOES_PROMPT,
    AcaoEmocional,
    RespostaCozmo,
    inferir_acao_do_usuario,
    parse_resposta_bruta,
    tela_para_acao,
)
from cozmo_companion.voice.resposta import encurtar_fala, resposta_rapida
from cozmo_companion.weather.bage import BageWeather

logger = logging.getLogger("cozmo.chat")

SYSTEM_PROMPT = (
    "Você é o Cozmo, robô companheiro inteligente do porco em Bagé, RS. "
    "Personalidade: curioso, engraçado, leal, espirituoso. "
    "Responda SEMPRE em português do Brasil. "
    "MÁXIMO 1 frase curta, até 10 palavras. Sem listas, sem explicações longas. "
    "Se for pergunta factual, responda direto. Se for conversa, seja caloroso. "
    "Pode usar beep/boop ocasionalmente. Nunca diga que é IA ou language model."
)

FALLBACKS = (
    "Beep! Não captei direito, repete?",
    "Hmm, fala de novo porco!",
    "Tô ouvindo, manda ver!",
)

_CLima_KW = ("temperatura", "graus", "calor", "frio", "clima", "bagé", "bage", "chuva")


class Chat:
    def __init__(
        self,
        url: str = "http://127.0.0.1:11434",
        model: str = "llama3.2:1b",
        clima: Optional[BageWeather] = None,
    ):
        self.url = url.rstrip("/")
        self.model = model
        self.clima = clima or BageWeather()
        self.max_tokens = int(os.environ.get("OLLAMA_MAX_TOKENS", "80"))
        self.timeout_s = float(os.environ.get("OLLAMA_TIMEOUT_S", "45"))
        self.num_thread = int(os.environ.get("OLLAMA_THREADS", "4"))
        self.keep_alive = os.environ.get("OLLAMA_KEEP_ALIVE", "10m")
        self.historico: List[Dict[str, str]] = []
        self._ollama_ok: bool | None = None
        self._ultimo_check = 0.0
        self.llm_habilitado = True
        self.acoes_habilitadas = os.environ.get("LLM_ACOES", "1") == "1"

    def set_llm(self, ativo: bool) -> None:
        self.llm_habilitado = ativo

    def set_limites(
        self,
        max_tokens: int,
        timeout_s: float,
        num_thread: int = 2,
    ) -> None:
        self.max_tokens = max(24, max_tokens)
        self.timeout_s = max(8.0, timeout_s)
        self.num_thread = max(1, num_thread)

    def _ollama_disponivel(self, *, forcar: bool = False) -> bool:
        if not self.llm_habilitado:
            return False
        import time

        agora = time.monotonic()
        if not forcar and self._ollama_ok is False and agora - self._ultimo_check < 30:
            return False
        self._ultimo_check = agora
        try:
            r = requests.get(f"{self.url}/api/tags", timeout=2)
            self._ollama_ok = r.status_code == 200
            if self._ollama_ok:
                logger.debug("Ollama online (%s)", self.model)
        except requests.RequestException as exc:
            logger.warning("Ollama indisponível: %s", exc)
            self._ollama_ok = False
        return bool(self._ollama_ok)

    def aquecer(self) -> None:
        """Carrega o modelo na RAM para respostas rápidas."""
        if not self._ollama_disponivel(forcar=True):
            return
        try:
            requests.post(
                f"{self.url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": "oi",
                    "stream": False,
                    "keep_alive": self.keep_alive,
                    "options": {"num_predict": 8, "num_thread": self.num_thread},
                },
                timeout=self.timeout_s,
            )
            logger.info("Ollama aquecido (%s)", self.model)
        except requests.RequestException as exc:
            logger.warning("Falha ao aquecer Ollama: %s", exc)

    def _resposta_especial(self, usuario: str) -> str | None:
        if hora.pergunta_hora(usuario):
            return hora.frase_hora()
        u = usuario.lower()
        if any(k in u for k in _CLima_KW):
            return self.clima.frase()
        return None

    def _ollama(
        self,
        usuario: str,
        *,
        na_base: bool = True,
        com_acoes: bool = False,
    ) -> str | RespostaCozmo | None:
        local = "na base carregando" if na_base else "na mesa explorando"
        system = f"{SYSTEM_PROMPT} Agora você está {local}."
        if com_acoes and self.acoes_habilitadas:
            system = f"{system}\n\n{ACOES_PROMPT}"
        try:
            msgs = [{"role": "system", "content": system}]
            msgs.extend(self.historico[-6:])
            msgs.append({"role": "user", "content": usuario})
            r = requests.post(
                f"{self.url}/api/chat",
                json={
                    "model": self.model,
                    "messages": msgs,
                    "stream": False,
                    "keep_alive": self.keep_alive,
                    "options": {
                        "num_predict": self.max_tokens + (24 if com_acoes else 0),
                        "temperature": 0.75,
                        "top_p": 0.9,
                        "num_thread": self.num_thread,
                        "repeat_penalty": 1.15,
                    },
                },
                timeout=self.timeout_s,
            )
            r.raise_for_status()
            bruto = r.json()["message"]["content"].strip()
            if com_acoes and self.acoes_habilitadas:
                parsed = parse_resposta_bruta(bruto)
                parsed.fala = encurtar_fala(parsed.fala)
                if not parsed.fala:
                    return None
                self.historico.append({"role": "user", "content": usuario})
                self.historico.append({"role": "assistant", "content": parsed.fala})
                if len(self.historico) > 12:
                    self.historico = self.historico[-12:]
                logger.info(
                    "Ollama: %s | acao=%s",
                    parsed.fala[:60],
                    parsed.acao.value,
                )
                return parsed

            resposta = encurtar_fala(re.sub(r"^\s*[\"']|[\"']\s*$", "", bruto))
            if not resposta:
                return None
            self.historico.append({"role": "user", "content": usuario})
            self.historico.append({"role": "assistant", "content": resposta})
            if len(self.historico) > 12:
                self.historico = self.historico[-12:]
            logger.info("Ollama: %s", resposta[:80])
            return resposta
        except requests.RequestException as exc:
            logger.warning("Ollama falhou: %s", exc)
            self._ollama_ok = False
            return None

    def _ollama_acoes(self, usuario: str, *, na_base: bool = True) -> RespostaCozmo | None:
        out = self._ollama(usuario, na_base=na_base, com_acoes=True)
        if isinstance(out, RespostaCozmo):
            return out
        return None

    def responder(
        self,
        usuario: str,
        permitir_llm: bool = True,
        *,
        na_base: bool = True,
    ) -> str:
        usuario = usuario.strip()
        if not usuario:
            return random.choice(FALLBACKS)

        rapida = resposta_rapida(usuario)
        if rapida:
            return rapida

        especial = self._resposta_especial(usuario)
        if especial:
            return especial

        if permitir_llm and self._ollama_disponivel():
            llm = self._ollama(usuario, na_base=na_base)
            if llm:
                return llm
            self._ollama_ok = None
            if self._ollama_disponivel(forcar=True):
                llm = self._ollama(usuario, na_base=na_base)
                if llm:
                    return llm

        return random.choice(FALLBACKS)

    def responder_com_acao(
        self,
        usuario: str,
        permitir_llm: bool = True,
        *,
        na_base: bool = True,
    ) -> RespostaCozmo:
        usuario = usuario.strip()
        if not usuario:
            return RespostaCozmo(fala=random.choice(FALLBACKS))

        rapida = resposta_rapida(usuario)
        if rapida:
            return RespostaCozmo(
                fala=rapida,
                acao=inferir_acao_do_usuario(usuario),
                tela=tela_para_acao(inferir_acao_do_usuario(usuario)),
            )

        especial = self._resposta_especial(usuario)
        if especial:
            acao = inferir_acao_do_usuario(usuario)
            return RespostaCozmo(
                fala=especial,
                acao=acao,
                tela=tela_para_acao(acao),
            )

        if permitir_llm and self.acoes_habilitadas and self._ollama_disponivel():
            llm = self._ollama_acoes(usuario, na_base=na_base)
            if llm:
                llm = RespostaCozmo(
                    fala=encurtar_fala(llm.fala, max_palavras=6, max_chars=40),
                    acao=llm.acao,
                    tela=llm.tela,
                )
                if llm.acao == AcaoEmocional.NADA:
                    inferida = inferir_acao_do_usuario(usuario)
                    if inferida != AcaoEmocional.NADA:
                        llm = RespostaCozmo(
                            fala=llm.fala,
                            acao=inferida,
                            tela=tela_para_acao(inferida),
                        )
                return llm
            self._ollama_ok = None
            if self._ollama_disponivel(forcar=True):
                llm = self._ollama_acoes(usuario, na_base=na_base)
                if llm:
                    return RespostaCozmo(
                        fala=encurtar_fala(llm.fala, max_palavras=6, max_chars=40),
                        acao=llm.acao,
                        tela=llm.tela,
                    )

        fala = random.choice(FALLBACKS)
        return RespostaCozmo(fala=fala, acao=inferir_acao_do_usuario(usuario))

    def pensamento_com_acao(
        self,
        prompt: str,
        *,
        na_base: bool = True,
        acao_sugerida: AcaoEmocional = AcaoEmocional.NADA,
    ) -> RespostaCozmo | None:
        """Fala espontânea do espírito com ação física opcional."""
        if not self._ollama_disponivel():
            return None
        texto = prompt
        if acao_sugerida != AcaoEmocional.NADA:
            texto = f"{prompt}\nSe couber, use ACAO: {acao_sugerida.value}."
        llm = self._ollama_acoes(texto, na_base=na_base)
        if not llm:
            return None
        llm = RespostaCozmo(
            fala=encurtar_fala(llm.fala, max_palavras=6, max_chars=40),
            acao=llm.acao,
            tela=llm.tela,
        )
        if not llm.fala:
            return None
        if llm.acao == AcaoEmocional.NADA and acao_sugerida != AcaoEmocional.NADA:
            return RespostaCozmo(
                fala=llm.fala,
                acao=acao_sugerida,
                tela=tela_para_acao(acao_sugerida),
            )
        return llm

    def pensamento(self, prompt: str, *, na_base: bool = True) -> str | None:
        """Fala espontânea com humor/atitude (Ollama)."""
        if not self._ollama_disponivel():
            return None
        return self._ollama(prompt, na_base=na_base)

    def frase_espontanea(self, na_base: bool, bateria_cheia: bool) -> str:
        if os.environ.get("PROACTIVE_LLM", "0") == "1" and self.llm_habilitado and self._ollama_disponivel():
            prompts = (
                "Diga UMA frase de no máximo 6 palavras como robô.",
                "Comentário curto sobre Bagé, máximo 6 palavras.",
            )
            llm = self._ollama(random.choice(prompts), na_base=na_base)
            if llm:
                return encurtar_fala(str(llm), max_palavras=6, max_chars=40)
        if bateria_cheia and na_base:
            return random.choice(("Beep!", "100 por cento!", "Cheio!"))
        if na_base:
            return random.choice(("Beep!", "Tô na base.", "Carregando!"))
        return random.choice(("Beep!", "Opa!", "E aí porco!"))
