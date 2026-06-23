"""전략 생성 노드 — STEP 5 경쟁우위 차별화 + STEP 7 사업수행전략."""
import json
import logging
import re

from omegaconf import DictConfig

from llm.factory import get_llm, get_node_temperature
from ..state import GraphState
from ._prompt_utils import load_prompt as _load_prompt

log = logging.getLogger(__name__)

# LLM 반복 루프 감지: 10~80자 구절이 5회 이상 연속 등장
_REPEAT_RE = re.compile(r'(.{10,80})\1{4,}', re.DOTALL)


def _truncate_repetition(text: str) -> str:
    """LLM 반복 루프(동일 구절 5회+ 연속) 감지 → 첫 1회 후 잘라냄."""
    m = _REPEAT_RE.search(text)
    if not m:
        return text
    cut_at = m.start() + len(m.group(1))
    log.warning(
        "LLM 반복 루프 감지: %r × N회 (위치 %d) → %d자에서 잘라냄",
        m.group(1)[:30], m.start(), cut_at,
    )
    return (
        text[:cut_at].rstrip()
        + "\n\n> ⚠️ LLM 반복 오류로 해당 내용이 잘렸습니다. "
        "이 항목을 직접 보완하거나 [재생성] 버튼을 사용하세요."
    )


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
    raw = _truncate_repetition(raw)

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


def _json_to_markdown(text: str) -> str:
    """JSON으로 출력된 전략 텍스트를 마크다운으로 변환 (Qwen3 fallback).

    JSON 최상위 키를 ### 헤더로, 문자열 값을 본문으로, 리스트 항목을 - 불릿으로 변환.
    JSON이 아니면 원문 그대로 반환.
    """
    stripped = text.strip()
    if not stripped.startswith("{"):
        return text

    try:
        data = json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        return text

    lines: list[str] = []
    for key, val in data.items():
        lines.append(f"### {key}")
        if isinstance(val, list):
            for item in val:
                lines.append(f"- {item}" if isinstance(item, str) else f"- {json.dumps(item, ensure_ascii=False)}")
        elif isinstance(val, dict):
            for k2, v2 in val.items():
                lines.append(f"**{k2}**: {v2}")
        else:
            lines.append(str(val))
        lines.append("")

    log.warning("STEP 5/7: JSON 출력 감지 → 마크다운 변환 적용 (Qwen3 fallback)")
    return "\n".join(lines).strip()


def _split_step5(text: str) -> tuple[str, str]:
    """[5-1], [5-2] 섹션 분리. 실패 시 전체를 5-1에 담음."""
    text = _json_to_markdown(text)
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


def _compress_step1(step1: dict) -> str:
    """STEP 7 입력용 step1 요약 (full JSON 대신 핵심만)."""
    return (
        f"사업명: {step1.get('project_name', '')}\n"
        f"발주기관: {step1.get('agency', '')}\n"
        f"도메인: {step1.get('domain', '')}\n"
        f"사업 범위: {step1.get('project_scope', '')}"
    )


def _compress_step3_high(eval_criteria: dict) -> str:
    """STEP 3에서 배점 상위 항목만 추출."""
    high = eval_criteria.get("high_score_items", [])
    if not high:
        return eval_criteria.get("implications", "(평가항목 정보 없음)")
    lines: list[str] = []
    for h in high:
        if isinstance(h, dict):
            name = h.get("item", "")
            score = h.get("score", "")
            focus = h.get("proposal_focus", "")
            lines.append(f"- {name}({score}점): {focus}")
        else:
            lines.append(f"- {h}")
    if imp := eval_criteria.get("implications", ""):
        lines.append(f"\n시사점: {imp}")
    return "\n".join(lines)


def _compress_step4(comp: dict) -> str:
    """STEP 4 경쟁력에서 강점/약점만 추출."""
    vs = comp.get("vs_competitors", {})
    strengths = vs.get("strengths", [])
    weaknesses = vs.get("weaknesses", [])
    parts: list[str] = []
    if strengths:
        parts.append("강점: " + " / ".join(strengths))
    if weaknesses:
        parts.append("약점(만회 필요): " + " / ".join(weaknesses))
    return "\n".join(parts) or "(없음)"


def generate_step7_node(state: GraphState, cfg: DictConfig) -> GraphState:
    """STEP 7 — 사업수행전략 생성 (LLM API 권장).

    호출 1: [7-1] CSF + [7-2] 전략요약 + [7-3] MECE 이행방안
    호출 2: [7-4] 제안서 간이 스토리보드 (별도 호출 — 토큰 초과 방지)
    """
    llm = get_llm(cfg, "generate_step7")
    temp = get_node_temperature(cfg, "generate_step7")
    meta = dict(state.get("metadata") or {})

    # ── 입력 압축 ──────────────────────────────────────────────────
    step1 = state.get("step1_business_overview") or {}
    step3 = state.get("step3_eval_criteria") or {}
    step4 = state.get("step4_competitiveness") or {}
    decisions = state.get("step6_decisions") or []
    step6_section = (
        "## STEP 6 의사결정 사항\n" + _format_dict_pretty(decisions)
        if decisions and not state.get("skip_step6", False)
        else ""
    )

    # ── 호출 1: [7-1] + [7-2] + [7-3] ───────────────────────────
    prompt_main = _load_prompt("generate_step7")
    user_main = prompt_main["user"].format(
        step1_summary=_compress_step1(step1),
        step3_high_score=_compress_step3_high(step3),
        step4_summary=_compress_step4(step4),
        step6_section=step6_section,
        step5_1_competitive_diff=state.get("step5_1_competitive_diff", "(없음)"),
        step5_2_issue_solution=state.get("step5_2_issue_solution", "(없음)"),
    )
    raw_main = llm.generate(
        [{"role": "system", "content": prompt_main["system"]},
         {"role": "user", "content": user_main}],
        temperature=temp,
    )
    csf, summary, plan = _split_step7_main(_json_to_markdown(_truncate_repetition(raw_main)))
    log.info("STEP 7 호출1 완료: CSF=%d자, 요약=%d자, 이행방안=%d자", len(csf), len(summary), len(plan))

    # ── 호출 2: [7-4] 스토리보드 ─────────────────────────────────
    prompt_sb = _load_prompt("generate_step7_storyboard")
    # plan 요약: 각 영역 제목만 추출 (스토리보드 컨텍스트용)
    plan_summary = "\n".join(
        line for line in plan.splitlines()
        if line.strip().startswith(("####", "###", "**A.", "**B.", "**C.", "**D."))
    ) or plan[:1000]
    user_sb = prompt_sb["user"].format(
        csf_text=csf,
        plan_summary=plan_summary,
        step3_high_score=_compress_step3_high(step3),
    )
    raw_sb = llm.generate(
        [{"role": "system", "content": prompt_sb["system"]},
         {"role": "user", "content": user_sb}],
        temperature=temp,
    )
    storyboard = _truncate_repetition(raw_sb).strip()
    log.info("STEP 7 호출2 완료: 스토리보드=%d자", len(storyboard))

    meta.setdefault("used_llm_nodes", {})["generate_step7"] = type(llm).__name__
    return {
        "step7_1_csf": [csf],
        "step7_2_strategy_summary": summary,
        "step7_3_execution_plan": plan,
        "step7_4_storyboard": [storyboard],
        "current_step": 7,
        "metadata": meta,
    }


def _split_step7_main(text: str) -> tuple[str, str, str]:
    """[7-1]~[7-3] 분리 (스토리보드 제외)."""
    headers = [r"###\s*\[7-2\]", r"###\s*\[7-3\]"]
    positions: list[int] = []
    for h in headers:
        m = re.search(h, text)
        positions.append(m.start() if m else len(text))

    p0, p1 = positions
    csf = text[0:p0].strip()
    summary = text[p0:p1].strip() if p0 < len(text) else ""
    plan = text[p1:].strip() if p1 < len(text) else ""
    return csf, summary, plan
