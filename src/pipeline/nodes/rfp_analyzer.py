"""RFP 분석 노드 — STEP 1~3 자동 추출 + STEP 2비공식·4·6 PM 입력 처리."""
import json
import logging
import re

from omegaconf import DictConfig

from llm.factory import get_llm, get_node_temperature
from ..state import GraphState
from ._prompt_utils import load_prompt as _load_prompt

log = logging.getLogger(__name__)


def _parse_json_response(text: str) -> dict | list:
    """LLM 응답에서 JSON 블록 추출·파싱.

    추출 시도 순서:
      1. ```json ... ``` / ``` ... ``` 블록
      2. raw JSON ({...} / [...]) 직접 파싱
      3. 텍스트 내 마지막 {...} / [...] 블록
    """
    original = text

    # 1. 코드 블록
    match = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
    if match:
        candidate = match.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # 2. 전체를 직접 파싱
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # 3. 마지막 {...} 블록
    for m in reversed(list(re.finditer(r'\{[\s\S]+\}', text))):
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            continue

    # 4. 마지막 [...] 블록
    for m in reversed(list(re.finditer(r'\[[\s\S]+\]', text))):
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            continue

    log.warning("JSON 파싱 실패 — 원문 반환\n%s", original[:300])
    return {"raw_output": original}


def extract_step1_node(state: GraphState, cfg: DictConfig) -> GraphState:
    """STEP 1 — 사업개요 구조화."""
    prompt = _load_prompt("extract_step1")
    rfp_text = state["rfp_raw_text"]

    llm = get_llm(cfg, "extract_step1")
    temp = get_node_temperature(cfg, "extract_step1")

    messages = [
        {"role": "system", "content": prompt["system"]},
        {"role": "user", "content": prompt["user"].format(rfp_text=rfp_text[:12000])},
    ]
    raw = llm.generate(messages, temperature=temp)
    result = _parse_json_response(raw)

    log.info("STEP 1 완료: %s", str(result)[:100])
    meta = dict(state.get("metadata") or {})
    meta.setdefault("used_llm_nodes", {})["extract_step1"] = type(llm).__name__
    return {"step1_business_overview": result, "current_step": 1, "metadata": meta}


def extract_step2_formal_node(state: GraphState, cfg: DictConfig) -> GraphState:
    """STEP 2 공식 — 공식 고객 요구사항 추출."""
    prompt = _load_prompt("extract_step2_formal")
    rfp_text = state["rfp_raw_text"]

    llm = get_llm(cfg, "extract_step2_formal")
    temp = get_node_temperature(cfg, "extract_step2_formal")

    messages = [
        {"role": "system", "content": prompt["system"]},
        {"role": "user", "content": prompt["user"].format(rfp_text=rfp_text[:12000])},
    ]
    raw = llm.generate(messages, temperature=temp)
    parsed = _parse_json_response(raw)
    # formal_requirements 리스트 또는 전체 dict
    requirements = parsed.get("formal_requirements", parsed) if isinstance(parsed, dict) else parsed

    log.info("STEP 2 공식 완료: %d개 요구사항", len(requirements) if isinstance(requirements, list) else 1)
    meta = dict(state.get("metadata") or {})
    meta.setdefault("used_llm_nodes", {})["extract_step2_formal"] = type(llm).__name__
    return {
        "step2_formal_requirements": requirements if isinstance(requirements, list) else [parsed],
        "current_step": 2,
        "metadata": meta,
    }


_EVAL_SECTION_PATTERNS = re.compile(
    r'(평가\s*항목|평가\s*기준|제안서\s*평가|심사\s*기준|채점\s*기준|'
    r'기술\s*평가|가격\s*평가|배점\s*기준|평가\s*방법|심사\s*방법)',
    re.IGNORECASE,
)
# 별첨 기술 평가항목 섹션 전용 패턴 — 평가/배점 컨텍스트가 있을 때만 매치
_EVAL_APPENDIX_PATTERNS = re.compile(
    r'별첨.{0,30}평가항목|'                        # "별첨 기술 평가항목 및 배점"
    r'기술\s*평가항목\s*및\s*배점|'                 # "기술 평가항목 및 배점"
    r'\[\s*\d+\s*\]\s*별첨.{0,20}(평가|배점)|'      # "[ 2] 별첨 기술 평가..." (평가/배점 필수)
    r'별첨\s*\d+\b.{0,20}(평가항목|배점)',           # "별첨 2 기술 평가항목"
    re.IGNORECASE,
)
_EVAL_SECTION_MAX = 12000  # 평가 섹션 추출 최대 글자 수 (별첨 테이블 전체 커버)


def _extract_eval_section(text: str, window: int = _EVAL_SECTION_MAX) -> str:
    """RFP 전문에서 평가항목 섹션을 찾아 반환.

    탐색 우선순위:
      1. '별첨 기술 평가항목 및 배점' 계열 전용 패턴 — 여러 개면 마지막 위치 사용
         (목차에도 동일 문자열이 나타나므로 마지막이 실제 별첨 섹션일 가능성이 높음)
      2. 일반 평가 키워드 — 마지막 등장 위치 (별첨은 문서 후반에 위치)
      3. 키워드 없음 → RFP 후반부 window 글자 반환
    """
    # 1. 별첨 전용 패턴 — 마지막 등장 위치 우선
    appendix_matches = list(_EVAL_APPENDIX_PATTERNS.finditer(text))
    if appendix_matches:
        last_m = appendix_matches[-1]
        start = max(0, last_m.start() - 200)
        extracted = text[start: start + window]
        log.info(
            "STEP 3 별첨 평가 섹션 (%d개 중 마지막, 위치 %d): 추출 %d자",
            len(appendix_matches), last_m.start(), len(extracted),
        )
        return extracted

    # 2. 일반 평가 키워드 — 마지막 등장 위치 (첫 등장은 개요/목차일 수 있음)
    all_matches = list(_EVAL_SECTION_PATTERNS.finditer(text))
    if all_matches:
        last_m = all_matches[-1]
        start = max(0, last_m.start() - 500)
        extracted = text[start: start + window]
        log.info(
            "STEP 3 평가 섹션 (마지막 위치 %d): 추출 %d자",
            last_m.start(), len(extracted),
        )
        return extracted

    log.info("STEP 3 평가 섹션 키워드 없음 → RFP 후반 %d자 사용", window)
    return text[-window:]


_SCORE_IN_TEXT_RE = re.compile(r'(\d+)\s*점')


def _verify_scores(result: dict, eval_text: str) -> dict:
    """LLM이 추출한 배점이 실제 텍스트에 존재하는지 검증.

    텍스트에서 'N점' 형태의 숫자 집합을 추출한 뒤,
    각 eval_item의 score가 그 집합에 없으면 score_unverified=True 플래그를 달고
    경고 로그를 출력한다. score를 제거하거나 변조하지 않는다.
    """
    text_scores: set[int] = {int(m) for m in _SCORE_IN_TEXT_RE.findall(eval_text)}
    items = result.get("eval_items", [])
    flagged: list[str] = []

    for item in items:
        score = item.get("score")
        if score is None:
            continue
        try:
            score_int = int(score)
        except (TypeError, ValueError):
            continue
        if score_int not in text_scores:
            item["score_unverified"] = True
            flagged.append(f"{item.get('item', '?')}({score_int}점)")

    if flagged:
        log.warning(
            "STEP 3 배점 검증 실패 — 텍스트에서 확인 안 된 배점: %s  |  텍스트 내 실제 배점: %s",
            ", ".join(flagged),
            sorted(text_scores, reverse=True),
        )
    return result


def extract_step3_node(state: GraphState, cfg: DictConfig) -> GraphState:
    """STEP 3 — 평가항목 분석."""
    prompt = _load_prompt("extract_step3")
    rfp_text = state["rfp_raw_text"]
    eval_section = _extract_eval_section(rfp_text)

    llm = get_llm(cfg, "extract_step3")
    temp = get_node_temperature(cfg, "extract_step3")

    messages = [
        {"role": "system", "content": prompt["system"]},
        {"role": "user", "content": prompt["user"].format(rfp_text=eval_section)},
    ]
    raw = llm.generate(messages, temperature=temp)
    result = _parse_json_response(raw)

    if isinstance(result, dict):
        result = _verify_scores(result, eval_section)

    n_items = len(result.get("eval_items", [])) if isinstance(result, dict) else 0
    n_unverified = sum(1 for it in result.get("eval_items", []) if it.get("score_unverified"))
    log.info("STEP 3 완료: %d개 평가항목 (미검증 배점 %d개)", n_items, n_unverified)

    meta = dict(state.get("metadata") or {})
    meta.setdefault("used_llm_nodes", {})["extract_step3"] = type(llm).__name__
    return {"step3_eval_criteria": result, "current_step": 3, "metadata": meta}


# ── PM 입력 노드 (Human-in-the-Loop) ─────────────────────────────────────────
# interrupt_before로 실행이 중단되므로 노드 자체는 no-op 패스스루.
# PM이 app.update_state()로 값을 주입한 뒤 Command(resume=None)으로 재개.

def pm_step2_informal_node(state: GraphState, cfg: DictConfig | None = None) -> GraphState:
    """STEP 2 비공식 — PM 비공식 요구사항 입력 대기 (interrupt_before).

    PM이 update_state()로 step2_informal_requirements를 주입한 경우 그대로 통과.
    주입이 없으면 빈 dict로 초기화 (이후 단계에서 생략 처리).
    """
    informal = state.get("step2_informal_requirements") or {
        "hidden_needs": [],
        "pain_points": [],
        "key_issues": [],
    }
    return {"step2_informal_requirements": informal, "current_step": 2}


def pm_step4_node(state: GraphState, cfg: DictConfig | None = None) -> GraphState:
    """STEP 4 — PM 경쟁력 분석 입력 대기 (interrupt_before).

    PM이 update_state()로 step4_competitiveness를 주입한 경우 그대로 통과.
    주입이 없으면 빈 dict로 초기화 (이후 단계에서 생략 처리).
    """
    competitiveness = state.get("step4_competitiveness") or {
        "past_projects": [],
        "key_personnel": [],
        "tech_solutions": [],
        "partners": [],
        "vs_competitors": {"strengths": [], "weaknesses": []},
    }
    return {"step4_competitiveness": competitiveness, "current_step": 4}


def pm_step6_node(state: GraphState, cfg: DictConfig | None = None) -> GraphState:
    """STEP 6 — 주요 의사결정 사항 (Optional, interrupt_before).

    skip_step6=True면 no-op 통과.
    PM이 step6_decisions를 주입하면 그대로 사용.
    """
    if state.get("skip_step6", False):
        log.info("STEP 6 건너뜀 (skip_step6=True)")
        return {"step6_decisions": [], "current_step": 6}

    decisions = state.get("step6_decisions") or []
    return {"step6_decisions": decisions, "current_step": 6}
