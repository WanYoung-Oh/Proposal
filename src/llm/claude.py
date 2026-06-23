"""Claude LLM — Anthropic Claude API."""
import logging
from typing import Iterator

import anthropic

from .base import BaseLLM

log = logging.getLogger(__name__)


class ClaudeLLM(BaseLLM):
    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-6",
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ):
        self.model = model
        self.default_temperature = temperature
        self.default_max_tokens = max_tokens
        self.client = anthropic.Anthropic(api_key=api_key)

    def _split_system(self, messages: list[dict]) -> tuple[str, list[dict]]:
        """messages에서 role=system을 추출해 Claude API의 system= 파라미터로 분리."""
        system = next(
            (m["content"] for m in messages if m["role"] == "system"), ""
        )
        user_msgs = [m for m in messages if m["role"] != "system"]
        return system, user_msgs

    def generate(
        self,
        messages: list[dict],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        system, msgs = self._split_system(messages)
        kwargs: dict = dict(
            model=self.model,
            messages=msgs,
            temperature=temperature if temperature is not None else self.default_temperature,
            max_tokens=max_tokens if max_tokens is not None else self.default_max_tokens,
        )
        if system:
            kwargs["system"] = system
        resp = self.client.messages.create(**kwargs)
        return resp.content[0].text

    def stream(
        self,
        messages: list[dict],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Iterator[str]:
        system, msgs = self._split_system(messages)
        kwargs: dict = dict(
            model=self.model,
            messages=msgs,
            temperature=temperature if temperature is not None else self.default_temperature,
            max_tokens=max_tokens if max_tokens is not None else self.default_max_tokens,
        )
        if system:
            kwargs["system"] = system
        with self.client.messages.stream(**kwargs) as s:
            for text in s.text_stream:
                yield text
