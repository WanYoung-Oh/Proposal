"""format_output 노드 — 최종 산출물 Markdown 구조화."""
import json
import logging
from datetime import datetime

from ..state import GraphState

log = logging.getLogger(__name__)


def format_output_node(state: GraphState, cfg=None) -> GraphState:
    """GraphState 전체를 Markdown 최종 산출물로 직렬화."""
    overview = state.get("step1_business_overview") or {}
    project_name = overview.get("project_name", "RFP 사업")
    agency = overview.get("agency", "")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    meta = state.get("metadata") or {}

    lines: list[str] = [
        f"# 제안전략 수립 보고서: {project_name}",
        f"> 발주기관: {agency}  |  생성일시: {now}",
        "",
    ]

    # STEP 1
    lines += ["---", "## STEP 1. 사업개요", ""]
    lines.append(_json_block(overview))

    # STEP 2 공식
    lines += ["---", "## STEP 2-1. 고객 요구사항 (공식)", ""]
    formal = state.get("step2_formal_requirements") or []
    lines.append(_json_block(formal))

    # STEP 2 비공식
    lines += ["---", "## STEP 2-2. 고객 요구사항 (비공식)", ""]
    informal = state.get("step2_informal_requirements") or {}
    lines.append(_json_block(informal))

    # STEP 3
    lines += ["---", "## STEP 3. 평가항목 분석", ""]
    lines.append(_json_block(state.get("step3_eval_criteria") or {}))

    # STEP 4
    lines += ["---", "## STEP 4. 경쟁력 분석", ""]
    lines.append(_json_block(state.get("step4_competitiveness") or {}))

    # STEP 5
    lines += ["---", "## STEP 5. 경쟁우위 차별화 전략", ""]
    s51 = state.get("step5_1_competitive_diff", "")
    s52 = state.get("step5_2_issue_solution", "")
    if s51:
        lines += ["### [5-1] 경쟁구도 차별화", "", s51, ""]
    if s52:
        lines += ["### [5-2] 핵심이슈 차별화", "", s52, ""]

    # STEP 6 (옵션)
    decisions = state.get("step6_decisions") or []
    if decisions and not state.get("skip_step6", False):
        lines += ["---", "## STEP 6. 주요 의사결정 사항", ""]
        lines.append(_json_block(decisions))

    # STEP 7
    lines += ["---", "## STEP 7. 사업수행전략", ""]
    csf_list = state.get("step7_1_csf") or []
    if csf_list:
        lines += ["### [7-1] 핵심성공요소 (CSF)", "", csf_list[0], ""]
    summary = state.get("step7_2_strategy_summary", "")
    if summary:
        lines += ["### [7-2] 사업수행전략 요약", "", summary, ""]
    plan = state.get("step7_3_execution_plan", "")
    if plan:
        lines += ["### [7-3] 이행방안 (MECE 4영역)", "", plan, ""]
    storyboard_list = state.get("step7_4_storyboard") or []
    if storyboard_list:
        lines += ["### [7-4] 제안서 간이 스토리보드", "", storyboard_list[0], ""]

    # 메타 정보
    lines += ["---", "## 메타 정보", ""]
    llm_nodes = meta.get("used_llm_nodes", {})
    if llm_nodes:
        lines.append("| 노드 | 사용 LLM |")
        lines.append("|------|---------|")
        for node, llm in llm_nodes.items():
            lines.append(f"| {node.strip()} | {llm} |")
        lines.append("")
    rag_hits = meta.get("rag_hit_counts", {})
    if rag_hits:
        lines.append(f"- RAG 방법론: {rag_hits.get('methodology', 0)}건")
        lines.append(f"- RAG 제안서: {rag_hits.get('proposals', 0)}건")

    final_md = "\n".join(lines)
    log.info("최종 산출물 생성 완료: %d자", len(final_md))
    return {"final_output_md": final_md, "current_step": 7, "metadata": meta}


def _json_block(data) -> str:
    try:
        return f"```json\n{json.dumps(data, ensure_ascii=False, indent=2)}\n```"
    except Exception:
        return str(data)
