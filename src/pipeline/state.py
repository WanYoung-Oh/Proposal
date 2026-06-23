"""GraphState — LangGraph 전체 상태 TypedDict."""
from typing import TypedDict


class GraphState(TypedDict, total=False):
    # ── 입력 ──────────────────────────────────────────────────────
    rfp_raw_text: str           # 원본 RFP 텍스트 (parse_rfp 노드 출력)
    rfp_file_path: str          # RFP PDF 경로 (parse_rfp 노드 입력)
    current_step: int           # 현재 진행 단계 (1~7)
    pm_messages: list[dict]     # PM과의 대화 이력

    # ── STEP 1~3: RFP 자동 추출 ───────────────────────────────────
    step1_business_overview: dict
    # 사업명·발주기관·사업범위·주요 경쟁사 현황

    step2_formal_requirements: list
    # [{name, detail, priority, linked_eval_item}]

    step2_informal_requirements: dict
    # {hidden_needs: [...], pain_points: [...], key_issues: [...]}

    step3_eval_criteria: dict
    # {total_score, eval_items(score 내림차순): [...], high_score_items: [{item, score, proposal_focus}], implications: str}

    # ── STEP 4: PM 입력 (경쟁력 분석) ──────────────────────────────
    step4_competitiveness: dict
    # {past_projects, key_personnel, tech_solutions, partners, vs_competitors}

    # ── STEP 5: AI 도출 (경쟁우위 차별화) ─────────────────────────
    step5_1_competitive_diff: str   # 5-1 경쟁구도 차별화
    step5_2_issue_solution: str     # 5-2 핵심이슈 차별화

    # ── STEP 6: 의사결정 사항 (선택) ──────────────────────────────
    skip_step6: bool                # True면 STEP 6 건너뜀
    step6_decisions: list           # [{item, recommendation}]

    # ── STEP 7: 사업수행전략 최종 산출물 ──────────────────────────
    step7_1_csf: list               # 핵심성공요소 5~7개
    step7_2_strategy_summary: str   # 사업수행전략 요약
    step7_3_execution_plan: str     # MECE 4영역 이행방안
    step7_4_storyboard: list        # [{title, key_message, differentiator, csf}]

    # ── RAG 검색 결과 ──────────────────────────────────────────────
    rag_methodology_docs: list      # 방법론 컬렉션 검색 결과
    rag_case_docs: list             # 유사 제안서 사례 검색 결과

    # ── 최종 산출물 ────────────────────────────────────────────────
    final_output_md: str            # 최종 Markdown 산출물

    # ── 공통 메타 ──────────────────────────────────────────────────
    metadata: dict                  # {used_llm_nodes, rag_hit_counts, ...}
