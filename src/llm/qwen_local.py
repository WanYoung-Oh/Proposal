"""QwenLocal LLM — Qwen3.5 로컬 서버 (MLX / Ollama, OpenAI 호환 API).

mlx_lm 서버의 Qwen3.5 응답 구조:
  - reasoning: thinking 내용 (항상 존재, enable_thinking=false 무시됨)
  - content:   실제 답변 (reasoning 완료 후 token 여유가 있을 때만 존재)

thinking 토큰이 max_tokens를 다 소모하면 content가 비어,
reasoning에서 마지막 한국어 단락을 추출해 fallback으로 사용.
"""
import logging
import re
from typing import Iterator

from openai import OpenAI

from .base import BaseLLM

log = logging.getLogger(__name__)

# reasoning 단락 레이블 제거용 (Draft 1:, Revised:, Final Version: 등)
_LABEL_RE = re.compile(r'^[A-Za-z][A-Za-z0-9\s(),./\-]*:\s*', re.MULTILINE)
_KOREAN_RE = re.compile(r'[가-힣]')


def _extract_last_korean_block(text: str) -> str:
    """reasoning 텍스트에서 마지막 한국어 단락을 추출.

    Qwen3가 content 없이 reasoning만 반환할 때,
    reasoning 안에 포함된 최종 초안(한국어)을 꺼낸다.
    """
    paragraphs = re.split(r'\n{2,}', text)
    best = ""
    for para in paragraphs:
        cleaned = _LABEL_RE.sub("", para.strip()).strip()
        if len(_KOREAN_RE.findall(cleaned)) >= 15:  # 한국어 15자 이상인 단락만
            best = cleaned
    return best or text.strip()


class QwenLocalLLM(BaseLLM):
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "mlx-community/Qwen3.5-9B-4bit",
        temperature: float = 0.3,
        max_tokens: int = 4096,
        context_window: int = 32768,
    ):
        self.model = model
        self.default_temperature = temperature
        self.default_max_tokens = max_tokens
        self.context_window = context_window
        self.client = OpenAI(api_key="local", base_url=f"{base_url}/v1")

    def _get_content(self, msg) -> str:
        """응답 메시지에서 실제 답변 텍스트 추출.

        우선순위:
          1. msg.content — thinking 완료 후 생성된 실제 답변
          2. reasoning 필드 파싱 — max_tokens 부족으로 content가 없을 때 fallback
        """
        content = (msg.content or "").strip()
        if content:
            return content

        # content 없음 → reasoning 필드에서 최종 한국어 단락 추출
        reasoning = (
            getattr(msg, "reasoning", None)
            or (getattr(msg, "model_extra", None) or {}).get("reasoning", "")
            or ""
        ).strip()

        if reasoning:
            log.warning(
                "Qwen3: content 필드 없음 — reasoning(%d자)에서 마지막 한국어 단락 추출. "
                "근본 해결: mlx_lm.server를 --enable-thinking false 옵션으로 재시작하세요.",
                len(reasoning),
            )
            return _extract_last_korean_block(reasoning)

        return ""

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
        result = self._get_content(resp.choices[0].message)
        log.debug(
            "Qwen3 generate: finish=%s content_len=%d",
            resp.choices[0].finish_reason,
            len(result),
        )
        return result

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
            delta = chunk.choices[0].delta.content or ""
            if delta:
                yield delta
