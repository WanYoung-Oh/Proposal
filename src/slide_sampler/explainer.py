"""SlideExplainer — LLM으로 슬라이드 선정 사유 생성 (temp=0.3)."""
import logging

from omegaconf import DictConfig

from llm.factory import get_llm, get_node_temperature

log = logging.getLogger(__name__)

_SYSTEM_PROMPT = """공공정보화 제안전략 전문가로서, 슬라이드 선정 사유를 2~3문장으로 즉시 작성하세요.
반드시 한국어로, 차별화 포인트와 참고할 표현·구성에 집중하세요. 분석 설명 없이 결과만 출력합니다."""

_USER_TEMPLATE = """주제: {topic}
프로젝트: {project_name} ({year}, {result}) | 섹션: {section}
내용: {slide_text}

위 슬라이드가 "{topic}" 우수 사례인 이유 (2~3문장):"""


def generate_reason(
    topic: str,
    slide_text: str,
    project_name: str,
    year: str,
    result: str,
    section: str,
    cfg: DictConfig,
) -> str:
    """슬라이드 선정 사유 생성.

    Args:
        topic: 검색 주제
        slide_text: 슬라이드 본문 텍스트
        project_name: 프로젝트 ID/이름
        year: 연도
        result: 수주 여부 (수주/실주)
        section: 슬라이드 섹션명
        cfg: Hydra DictConfig

    Returns:
        2~3문장 선정 사유 문자열
    """
    try:
        llm = get_llm(cfg, "slide_explainer")
        temp = get_node_temperature(cfg, "slide_explainer")

        user_content = _USER_TEMPLATE.format(
            topic=topic,
            project_name=project_name,
            year=year,
            result=result,
            section=section or "(없음)",
            slide_text=slide_text[:600],
        )

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        return llm.generate(messages, temperature=temp, max_tokens=4096) or "(빈 응답)"
    except Exception as e:
        log.warning("선정 사유 생성 실패: %s", e)
        return f"(선정 사유 생성 실패: {e})"
