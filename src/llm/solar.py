"""Solar Pro LLM — Upstage Solar Pro REST API (OpenAI 호환)."""
import logging
from typing import Iterator

from openai import OpenAI

from .base import BaseLLM

log = logging.getLogger(__name__)

_SOLAR_BASE_URL = "https://api.upstage.ai/v1/solar"


class SolarProLLM(BaseLLM):
    def __init__(
        self,
        api_key: str,
        model: str = "solar-pro",
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ):
        self.model = model
        self.default_temperature = temperature
        self.default_max_tokens = max_tokens
        self.client = OpenAI(api_key=api_key, base_url=_SOLAR_BASE_URL)

    def generate(
        self,
        messages: list[dict],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature if temperature is not None else self.default_temperature,
            max_tokens=max_tokens if max_tokens is not None else self.default_max_tokens,
        )
        return resp.choices[0].message.content or ""

    def stream(
        self,
        messages: list[dict],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Iterator[str]:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature if temperature is not None else self.default_temperature,
            max_tokens=max_tokens if max_tokens is not None else self.default_max_tokens,
            stream=True,
        )
        for chunk in resp:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
