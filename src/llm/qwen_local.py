"""QwenLocal LLM — Qwen3.5 로컬 서버 (MLX / Ollama, OpenAI 호환 API).

mlx_lm 서버의 Qwen3.5 응답 구조:
  - reasoning: thinking 내용 (enable_thinking=true 시 존재)
  - content:   실제 답변

모든 요청에 chat_template_kwargs={"enable_thinking": False}를 전달해
서버 시작 옵션과 무관하게 thinking을 비활성화한다.
"""
import logging
import re
from typing import Iterator

from openai import OpenAI

from .base import BaseLLM

log = logging.getLogger(__name__)

_KOREAN_RE = re.compile(r'[가-힣]')


def _extract_json_from_reasoning(text: str) -> str:
    """reasoning 텍스트에서 JSON 블록을 우선 추출, 없으면 마지막 한국어 단락 반환.

    Qwen3가 max_tokens 부족으로 content 없이 reasoning만 반환할 때 사용.
    추출 우선순위:
      1. ```json ... ``` 또는 ``` ... ``` 블록
      2. 마지막으로 등장하는 {...} 또는 [...] 블록
      3. 마지막 한국어 단락 (최후 fallback)
    """
    # 1. 코드 블록 우선
    for m in re.finditer(r"```(?:json)?\s*([\s\S]+?)```", text):
        candidate = m.group(1).strip()
        if candidate.startswith(("{", "[")):
            return candidate

    # 2. 마지막 {...} 블록
    brace_match = list(re.finditer(r'\{[\s\S]+\}', text))
    if brace_match:
        return brace_match[-1].group(0).strip()

    # 3. 마지막 [...] 블록
    bracket_match = list(re.finditer(r'\[[\s\S]+\]', text))
    if bracket_match:
        return bracket_match[-1].group(0).strip()

    # 4. 마지막 한국어 단락
    paragraphs = re.split(r'\n{2,}', text)
    for para in reversed(paragraphs):
        cleaned = para.strip()
        if len(_KOREAN_RE.findall(cleaned)) >= 15:
            return cleaned

    return text.strip()


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

    # mlx_lm 서버에 thinking 비활성화 + 반복 루프 억제 파라미터를 매 요청마다 전달
    # repetition_penalty=1.1: 동일 토큰 반복에 약한 패널티 → 루프 발생률 대폭 감소
    _NO_THINKING = {
        "chat_template_kwargs": {"enable_thinking": False},
        "repetition_penalty": 1.1,
    }

    def _get_content(self, msg) -> str:
        """응답 메시지에서 실제 답변 텍스트 추출."""
        content = (msg.content or "").strip()
        if content:
            return content

        # thinking이 켜진 채로 max_tokens를 소진한 경우 fallback
        reasoning = (
            getattr(msg, "reasoning", None)
            or (getattr(msg, "model_extra", None) or {}).get("reasoning", "")
            or ""
        ).strip()

        if reasoning:
            log.warning(
                "Qwen3: content 필드 없음 — reasoning(%d자)에서 JSON/텍스트 추출 (fallback).",
                len(reasoning),
            )
            return _extract_json_from_reasoning(reasoning)

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
            extra_body=self._NO_THINKING,
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
            extra_body=self._NO_THINKING,
        )
        for chunk in resp:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                yield delta
