"""BaseLLM — 공통 추상 인터페이스."""
from abc import ABC, abstractmethod
from typing import Iterator


class BaseLLM(ABC):
    @abstractmethod
    def generate(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        """동기 생성 — 완성된 응답 문자열 반환."""
        ...

    @abstractmethod
    def stream(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> Iterator[str]:
        """스트리밍 생성 — 토큰 청크를 순서대로 yield."""
        ...
