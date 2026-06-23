"""전략 생성 노드 — STEP 5 경쟁우위 차별화 + STEP 7 사업수행전략."""
import json
import logging
import re

from omegaconf import DictConfig

from llm.factory import get_llm, get_node_temperature
from ..state import GraphState
from ._prompt_utils import load_prompt as _load_prompt

log = logging.getLogger(__name__)


def _format_list(items: list | None, indent: str = "- ") -> str:
    if not items:
        return "(없음)"
    return "\n".join(f"{indent}{item}" for item in items)


def _format_dict_pretty(d: dict | list | None) -> str:
    if d is None:
        return "(없음)"
    return json.dumps(d, ensure_ascii=False, indent=2)


def _format_rag_docs(docs: list | None) -> str:
    if not docs:
        return "(검색 결과 없음)"
    parts: list[str] = []
    for i, doc in enumerate(docs, 1):
        agency = doc.get("agency", "")
        year = doc.get("year", "")
        result = doc.get("result", "")
        section = doc.get("section", "")
        text = doc.get("text", "")
        summary = doc.get("strategy_summary", [])
        header = f"[{i}] {doc.get('doc_id', '')} (슬라이드 {doc.get('slide_no', '')})"
        if agency or year:
            header += f" — {agency} {year} {result}"
        parts.append(header)
        if section:
            parts.append(f"  섹션: {section}")
        if summary:
            parts.append(f"  전략 방향: {', '.join(str(s) for s in summary[:3])}")
        parts.append(f"  내용: {text[:400]}")
    return "\n".join(parts)


def generate_step5_node(state: GraphState, cfg: DictConfig) -> GraphState:
    """STEP 5 — 경쟁우위 차별화 전략 생성 (LLM API 권장)."""
    prompt = _load_prompt("generate_step5")

    user_content = prompt["user"].format(
        step1_business_overview=_format_dict_pretty(state.get("step1_business_overview")),
        step2_formal_requirements=_format_dict_pretty(state.get("step2_formal_requirements")),
        step2_informal_requirements=_format_dict_pretty(state.get("step2_informal_requirements")),
        step3_eval_criteria=_format_dict_pretty(state.get("step3_eval_criteria")),
        step4_competitiveness=_format_dict_pretty(state.get("step4_competitiveness")),
        rag_case_docs=_format_rag_docs(state.get("rag_case_docs")),
        rag_methodology_docs=_format_rag_docs(state.get("rag_methodology_docs")),
    )

    llm = get_llm(cfg, "generate_step5")
    temp = get_node_temperature(cfg, "generate_step5")

    messages = [
        {"role": "system", "content": prompt["system"]},
        {"role": "user", "content": user_content},
    ]
    raw = llm.generate(messages, temperature=temp)

    # [5-1]과 [5-2] 섹션 분리
    step5_1, step5_2 = _split_step5(raw)

    log.info("STEP 5 완료: 5-1=%d자, 5-2=%d자", len(step5_1), len(step5_2))
    meta = dict(state.get("metadata") or {})
    meta.setdefault("used_llm_nodes", {})["generate_step5"] = type(llm).__name__
    return {
        "step5_1_competitive_diff": step5_1,
        "step5_2_issue_solution": step5_2,
        "current_step": 5,
        "metadata": meta,
    }


def _split_step5(text: str) -> tuple[str, str]:
    """[5-1], [5-2] 섹션 분리. 실패 시 전체를 5-1에 담음."""
    pattern = r"###\s*\[5-2\]"
    match = re.search(pattern, text)
    if match:
        return text[: match.start()].strip(), text[match.start():].strip()
    # 헤더 없이 5-2 키워드로 분리 시도
    pattern2 = r"\[5-2\]"
    match2 = re.search(pattern2, text)
    if match2:
        return text[: match2.start()].strip(), text[match2.start():].strip()
    return text.strip(), ""


def generate_step7_node(state: GraphState, cfg: DictConfig) -> GraphState:
    """STEP 7 — 사업수행전략 + MECE 이행방안 생성 (LLM API 권장)."""
    prompt = _load_prompt("generate_step7")

    # STEP 6 의사결정 사항 (있을 경우 포함)
    decisions = state.get("step6_decisions") or []
    if decisions and not state.get("skip_step6", False):
        step6_section = "## STEP 6 의사결정 사항\n" + _format_dict_pretty(decisions)
    else:
        step6_section = ""

    user_content = prompt["user"].format(
        step1_business_overview=_format_dict_pretty(state.get("step1_business_overview")),
        step2_formal_requirements=_format_dict_pretty(state.get("step2_formal_requirements")),
        step2_informal_requirements=_format_dict_pretty(state.get("step2_informal_requirements")),
        step3_eval_criteria=_format_dict_pretty(state.get("step3_eval_criteria")),
        step4_competitiveness=_format_dict_pretty(state.get("step4_competitiveness")),
        step6_section=step6_section,
        step5_1_competitive_diff=state.get("step5_1_competitive_diff", "(없음)"),
        step5_2_issue_solution=state.get("step5_2_issue_solution", "(없음)"),
    )

    llm = get_llm(cfg, "generate_step7")
    temp = get_node_temperature(cfg, "generate_step7")

    messages = [
        {"role": "system", "content": prompt["system"]},
        {"role": "user", "content": user_content},
    ]
    raw = llm.generate(messages, temperature=temp)

    csf, summary, plan, storyboard = _split_step7(raw)

    log.info("STEP 7 완료: CSF=%d자, 요약=%d자, 이행방안=%d자", len(csf), len(summary), len(plan))
    meta = dict(state.get("metadata") or {})
    meta.setdefault("used_llm_nodes", {})["generate_step7"] = type(llm).__name__
    return {
        "step7_1_csf": [csf],          # 원문 그대로 저장 (파싱은 UI에서 처리)
        "step7_2_strategy_summary": summary,
        "step7_3_execution_plan": plan,
        "step7_4_storyboard": [storyboard],
        "current_step": 7,
        "metadata": meta,
    }


def _split_step7(text: str) -> tuple[str, str, str, str]:
    """[7-1]~[7-4] 섹션 분리. 실패 시 전체를 csf에 담음."""
    headers = [r"###\s*\[7-2\]", r"###\s*\[7-3\]", r"###\s*\[7-4\]"]
    # 미발견 헤더는 len(text)로 설정 → text[a:len(text)] = text[a:] (마지막 문자 유실 없음)
    positions: list[int] = []
    for h in headers:
        m = re.search(h, text)
        positions.append(m.start() if m else len(text))

    p0, p1, p2 = positions
    csf = text[0:p0].strip()
    summary = text[p0:p1].strip() if p0 < len(text) else ""
    plan = text[p1:p2].strip() if p1 < len(text) else ""
    storyboard = text[p2:].strip() if p2 < len(text) else ""

    return csf, summary, plan, storyboard
