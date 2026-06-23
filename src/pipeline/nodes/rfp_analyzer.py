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
    """LLM 응답에서 JSON 블록 추출·파싱."""
    # ```json ... ``` 블록 우선 추출
    match = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
    if match:
        text = match.group(1)
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        # JSON 파싱 실패 시 원문 dict로 감싸서 반환
        log.warning("JSON 파싱 실패 — 원문 반환\n%s", text[:200])
        return {"raw_output": text}


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


def extract_step3_node(state: GraphState, cfg: DictConfig) -> GraphState:
    """STEP 3 — 평가항목 분석."""
    prompt = _load_prompt("extract_step3")
    rfp_text = state["rfp_raw_text"]

    llm = get_llm(cfg, "extract_step3")
    temp = get_node_temperature(cfg, "extract_step3")

    messages = [
        {"role": "system", "content": prompt["system"]},
        {"role": "user", "content": prompt["user"].format(rfp_text=rfp_text[:12000])},
    ]
    raw = llm.generate(messages, temperature=temp)
    result = _parse_json_response(raw)

    log.info("STEP 3 완료: %d개 평가항목", len(result.get("eval_items", [])) if isinstance(result, dict) else 0)
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
