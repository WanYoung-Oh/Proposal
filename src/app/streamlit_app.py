"""공공정보화 RFP 제안전략 수립 시스템 — Streamlit MVP UI.

실행:
    cd /data/ephemeral/home/proposal
    source .venv/bin/activate
    export $(grep -v '^#' .env | xargs)
    streamlit run src/app/streamlit_app.py --server.port 8501
"""
import json
import logging
import os
import sys
import tempfile
import uuid
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from omegaconf import OmegaConf

# src/ 경로 추가
_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_ROOT / "src"))

load_dotenv(_ROOT / ".env")

log = logging.getLogger(__name__)

# ── 페이지 설정 ──────────────────────────────────────────────────
st.set_page_config(
    page_title="RFP 제안전략 수립 시스템",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 상수 ─────────────────────────────────────────────────────────
_DOMAINS = ["(전체)", "인프라", "ITO", "응용시스템", "컨설팅"]
_PROJECT_TYPES = ["(전체)", "구축", "운영·유지보수", "컨설팅", "기타"]
_RESULTS = ["(전체)", "수주", "실주"]
_STEPS = [
    "STEP 1: 사업개요",
    "STEP 2-1: 공식 요구사항",
    "STEP 2-2: 비공식 요구사항",
    "STEP 3: 평가항목 분석",
    "STEP 4: 경쟁력 분석",
    "STEP 5: 경쟁우위 차별화",
    "STEP 6: 의사결정 사항",
    "STEP 7: 사업수행전략",
]

_STAGE_LABEL = {
    "idle": "대기",
    "extracting": "STEP 1~3 자동 추출 중…",
    "wait_step2": "PM 입력 필요: 비공식 요구사항",
    "wait_step4": "PM 입력 필요: 경쟁력 분석",
    "wait_step6": "PM 입력 필요: 의사결정 사항",
    "generating": "STEP 5~7 전략 생성 중…",
    "done": "완료",
}


# ── Hydra cfg 빌더 ────────────────────────────────────────────────

def _build_cfg(
    default_llm: str,
    step5_llm: str,
    step7_llm: str,
    embedding_device: str = "cpu",
    reranker_device: str = "cpu",
) -> OmegaConf:
    """UI 선택값 + 환경변수로 Hydra-호환 cfg 생성."""
    base_url = os.environ.get("LOCAL_LLM_BASE_URL", "http://localhost:11434")
    qdrant_host = os.environ.get("QDRANT_HOST", "localhost")
    qdrant_port = int(os.environ.get("QDRANT_PORT", "6333"))
    sessions_db = os.environ.get("SESSIONS_DB_PATH", "data/sessions.db")
    data_dir = os.environ.get("DATA_DIR", "data/projects")
    vectorstore_path = os.environ.get("VECTORSTORE_PATH", "data/vectorstore")

    llm_targets = {
        "solar": "src.llm.solar.SolarProLLM",
        "claude": "src.llm.claude.ClaudeLLM",
        "qwen_local": "src.llm.qwen_local.QwenLocalLLM",
    }
    llm_models = {
        "solar": "solar-pro",
        "claude": "claude-sonnet-4-6",
        "qwen_local": "mlx-community/Qwen3.5-9B-4bit",
    }

    cfg = OmegaConf.create({
        "llm": {
            "_target_": llm_targets[default_llm],
            "model": llm_models[default_llm],
            "temperature": 0.3,
            "max_tokens": 4096,
            "base_url": base_url,
            "api_key": "",
        },
        "env": {
            "qdrant_host": qdrant_host,
            "qdrant_port": qdrant_port,
            "embedding_device": embedding_device,
            "embedding_batch_size": 16,
            "reranker_device": reranker_device,
        },
        "rag": {
            "top_k": 10,
            "methodology_top_k": 5,
            "hybrid_alpha": 0.80,
            "min_score_threshold": 0.50,
        },
        "pipeline": {
            "node_llm": {
                "extract_step1": "qwen_local",
                "extract_step2_formal": "qwen_local",
                "extract_step3": "qwen_local",
                "generate_step5": step5_llm,
                "generate_step7": step7_llm,
                "slide_explainer": default_llm,
            },
            "node_temperature": {
                "extract_step1": 0.1,
                "extract_step2_formal": 0.1,
                "extract_step3": 0.1,
                "pm_step2_informal": 0.2,
                "pm_step4": 0.2,
                "pm_step6": 0.3,
                "generate_step5": 0.6,
                "generate_step7": 0.65,
                "slide_explainer": 0.3,
            },
        },
        "ingestion": {
            "embedding_model": "BAAI/bge-m3",
        },
        "project": {
            "data_dir": data_dir,
            "methodology_dir": "data/methodology",
            "vectorstore_path": vectorstore_path,
        },
        "sessions_db_path": sessions_db,
    })
    return cfg


# ── 세션 초기화 ────────────────────────────────────────────────────

def _init_session():
    defaults = {
        "stage": "idle",
        "thread_id": str(uuid.uuid4()),
        "app": None,
        "checkpointer_conn": None,
        "step_outputs": {},
        "final_md": "",
        "rfp_filename": "",
        "error_msg": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ── LangGraph 앱 생성 ──────────────────────────────────────────────

def _get_pipeline_app(cfg):
    """세션당 1회 생성. LLM 선택이 바뀌면 재생성."""
    from pipeline.graph import build_graph
    import sqlite3

    # LLM 선택 변경 여부 감지 — node_llm 설정 문자열을 키로 사용
    cfg_key = str(dict(cfg.pipeline.node_llm))
    if st.session_state.app is not None and st.session_state.get("_cfg_key") == cfg_key:
        return st.session_state.app

    # 기존 연결 종료
    if old_conn := st.session_state.get("checkpointer_conn"):
        try:
            old_conn.close()
        except Exception:
            pass

    db_path = cfg.get("sessions_db_path", "data/sessions.db")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)

    from langgraph.checkpoint.sqlite import SqliteSaver
    cp = SqliteSaver(conn)
    app = build_graph(cfg, checkpointer=cp)

    st.session_state.app = app
    st.session_state.checkpointer_conn = conn
    st.session_state["_cfg_key"] = cfg_key
    return app


# ── 파이프라인 실행 헬퍼 ──────────────────────────────────────────

def _run_until_interrupt(app, input_or_command, config: dict, step_container):
    """스트림 이벤트를 소비하며 단계별 결과를 UI에 표시.

    interrupt 또는 END까지 실행. 최종 상태 dict 반환.
    """
    from langgraph.types import Command

    outputs: dict = {}
    with step_container:
        for event in app.stream(input_or_command, config=config, stream_mode="updates"):
            for node_name, node_output in event.items():
                if node_name.startswith("__"):
                    continue
                outputs.update(node_output)
                _show_node_result(node_name, node_output)
    return outputs


def _warn_if_parse_failed(data, step_label: str):
    """JSON 파싱 실패(raw_output 키 존재) 시 경고 표시."""
    if isinstance(data, dict) and "raw_output" in data:
        st.warning(
            f"⚠️ {step_label} — LLM이 JSON 형식으로 응답하지 않았습니다. "
            "이후 단계에서 오류가 발생할 수 있습니다. LLM 응답을 로그에서 확인하세요."
        )


def _show_node_result(node_name: str, output: dict):
    """노드 실행 결과를 expander로 표시."""
    labels = {
        "parse_rfp": "📄 RFP 텍스트 추출",
        "extract_step1": "🏢 STEP 1: 사업개요 구조화",
        "extract_step2_formal": "📋 STEP 2-1: 공식 요구사항 추출",
        "extract_step3": "⚖️ STEP 3: 평가항목 분석",
        "retrieve_rag": "🔍 RAG: 유사 사례 검색",
        "generate_step5": "⚡ STEP 5: 경쟁우위 차별화 전략",
        "generate_step7": "🎯 STEP 7: 사업수행전략",
        "format_output": "📝 최종 산출물 생성",
    }
    label = labels.get(node_name, f"🔄 {node_name}")

    with st.expander(label, expanded=True):
        if node_name == "parse_rfp":
            text = output.get("rfp_raw_text", "")
            st.text(text[:500] + ("…" if len(text) > 500 else ""))

        elif node_name == "extract_step1":
            data = output.get("step1_business_overview", {})
            _warn_if_parse_failed(data, "STEP 1")
            st.json(data)

        elif node_name == "extract_step2_formal":
            data = output.get("step2_formal_requirements", [])
            _warn_if_parse_failed(data, "STEP 2-1")
            st.json(data)

        elif node_name == "extract_step3":
            data = output.get("step3_eval_criteria", {})
            _warn_if_parse_failed(data, "STEP 3")
            st.json(data)

        elif node_name == "retrieve_rag":
            meta = output.get("metadata", {})
            hits = meta.get("rag_hit_counts", {})
            st.write(f"방법론 {hits.get('methodology', 0)}건 | 제안서 사례 {hits.get('proposals', 0)}건")

        elif node_name in ("generate_step5", "generate_step7"):
            for key, val in output.items():
                if key.startswith("step5_") or key.startswith("step7_"):
                    st.markdown(str(val))

        elif node_name == "format_output":
            md = output.get("final_output_md", "")
            st.markdown(md[:300] + "…" if len(md) > 300 else md)


def _current_graph_state(app, config: dict) -> dict:
    """현재 스냅샷 상태 조회."""
    try:
        snapshot = app.get_state(config)
        return dict(snapshot.values) if snapshot else {}
    except Exception:
        return {}


# ── 사이드바 ─────────────────────────────────────────────────────

def _render_sidebar() -> tuple[str, str, str]:
    with st.sidebar:
        st.title("⚙️ LLM 설정")

        st.markdown("**기본 LLM (추출·구조화)**")
        default_llm = st.selectbox(
            "기본 LLM",
            ["qwen_local", "solar", "claude"],
            format_func=lambda x: {"qwen_local": "🏠 Qwen3.5 (로컬)", "solar": "☀️ Solar Pro", "claude": "🤖 Claude"}[x],
            label_visibility="collapsed",
        )

        st.markdown("**전략 생성 LLM (STEP 5·7 권장)**")
        strategy_llm = st.selectbox(
            "전략 LLM",
            ["claude", "solar", "qwen_local"],
            format_func=lambda x: {"qwen_local": "🏠 Qwen3.5 (로컬)", "solar": "☀️ Solar Pro", "claude": "🤖 Claude"}[x],
            label_visibility="collapsed",
        )

        st.divider()
        st.markdown("**세션**")
        tid = st.session_state.get("thread_id", "—")
        st.caption(f"`{tid[:16]}…`")

        if st.button("🔄 새 세션 시작", width="stretch"):
            if old_conn := st.session_state.get("checkpointer_conn"):
                try:
                    old_conn.close()
                except Exception:
                    pass
            for k in ["stage", "thread_id", "app", "checkpointer_conn", "_cfg_key",
                       "step_outputs", "final_md", "rfp_filename", "error_msg"]:
                st.session_state.pop(k, None)
            st.rerun()

        stage = st.session_state.get("stage", "idle")
        st.divider()
        st.markdown("**진행 상태**")
        st.info(_STAGE_LABEL.get(stage, stage))

        return default_llm, strategy_llm, strategy_llm


# ── 탭 1: 제안전략 수립 ───────────────────────────────────────────

def _render_tab_strategy(cfg):
    st.header("📋 제안전략 수립")
    stage = st.session_state.stage

    # ── 진행 표시 바 ──────────────────────────────────────────────
    _render_progress_bar(stage)

    # ── RFP 업로드 (idle 상태에서만) ─────────────────────────────
    if stage == "idle":
        st.subheader("1. RFP PDF 업로드")
        uploaded = st.file_uploader(
            "RFP PDF 파일 선택 (50MB 이하)",
            type=["pdf"],
            accept_multiple_files=False,
        )
        if uploaded:
            size_mb = len(uploaded.getvalue()) / 1024 / 1024
            if size_mb > 50:
                st.error(f"파일 크기가 50MB를 초과합니다 ({size_mb:.1f}MB). 다른 파일을 선택하세요.")
                return

            st.success(f"파일 선택됨: {uploaded.name} ({size_mb:.1f}MB)")
            if st.button("🚀 자동 분석 시작 (STEP 1~3)", type="primary", width="stretch"):
                _start_extraction(uploaded, cfg)

    # ── STEP 2 비공식 요구사항 입력 ───────────────────────────────
    elif stage == "wait_step2":
        st.subheader("2. 비공식 고객 요구사항 입력")
        st.info("영업·인터뷰를 통해 파악한 고객의 실제 요구사항을 입력하세요.")
        _show_previous_results()
        _render_step2_form(cfg)

    # ── STEP 4 경쟁력 분석 입력 ───────────────────────────────────
    elif stage == "wait_step4":
        st.subheader("4. 경쟁력 분석 입력")
        st.info("우리 회사의 강점·약점 및 경쟁사 대비 분석 내용을 입력하세요.")
        _show_previous_results()
        _render_step4_form(cfg)

    # ── STEP 6 의사결정 사항 입력 ─────────────────────────────────
    elif stage == "wait_step6":
        st.subheader("6. 주요 의사결정 사항 (선택)")
        _show_previous_results()
        _render_step6_form(cfg)

    # ── 처리 중 ───────────────────────────────────────────────────
    elif stage in ("extracting", "generating"):
        st.info(f"⏳ {_STAGE_LABEL[stage]}")
        st.progress(0.5 if stage == "extracting" else 0.85)

    # ── 완료 ──────────────────────────────────────────────────────
    elif stage == "done":
        _render_done_screen()

    # ── 에러 ──────────────────────────────────────────────────────
    if st.session_state.error_msg:
        st.error(f"오류: {st.session_state.error_msg}")


def _render_progress_bar(stage: str):
    step_icons = {
        "idle": 0, "extracting": 3, "wait_step2": 3,
        "wait_step4": 4, "generating": 6, "wait_step6": 6, "done": 8,
    }
    current = step_icons.get(stage, 0)
    cols = st.columns(len(_STEPS))
    for i, (col, label) in enumerate(zip(cols, _STEPS)):
        parts = label.split(":", 1)
        step_num = parts[0].strip()
        step_name = parts[1].strip() if len(parts) > 1 else ""
        display = f"{step_num}<br><small>{step_name}</small>"
        with col:
            if i < current:
                st.markdown(f"<div style='text-align:center;color:green;font-size:0.75em'>✅<br>{display}</div>", unsafe_allow_html=True)
            elif i == current:
                st.markdown(f"<div style='text-align:center;color:blue;font-size:0.75em'>▶️<br>{display}</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='text-align:center;color:gray;font-size:0.75em'>⏳<br>{display}</div>", unsafe_allow_html=True)
    st.divider()


def _show_previous_results():
    """이전 단계 결과를 축소된 expander로 표시."""
    outputs = st.session_state.step_outputs
    if not outputs:
        return
    with st.expander("이전 단계 결과 보기", expanded=False):
        if "step1_business_overview" in outputs:
            st.markdown("**STEP 1: 사업개요**")
            st.json(outputs["step1_business_overview"])
        if "step2_formal_requirements" in outputs:
            st.markdown("**STEP 2-1: 공식 요구사항**")
            st.json(outputs.get("step2_formal_requirements", []))
        if "step3_eval_criteria" in outputs:
            st.markdown("**STEP 3: 평가항목 분석**")
            st.json(outputs["step3_eval_criteria"])


def _start_extraction(uploaded_file, cfg):
    """RFP 파일 임시 저장 → LangGraph 스트림 시작 (STEP 1~3)."""
    import traceback

    st.session_state.stage = "extracting"
    st.session_state.rfp_filename = uploaded_file.name
    st.session_state.error_msg = ""

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(uploaded_file.getvalue())
        tmp_path = tmp.name

    try:
        from llm.factory import clear_cache
        clear_cache()

        app = _get_pipeline_app(cfg)
        config = {"configurable": {"thread_id": st.session_state.thread_id}}
        init_input = {"rfp_file_path": tmp_path}

        result_container = st.container()
        with st.spinner("STEP 1~3 자동 추출 중…"):
            outputs = _run_until_interrupt(app, init_input, config, result_container)

        st.session_state.step_outputs.update(outputs)

        # 다음 interrupt 확인
        snapshot = app.get_state(config)
        next_nodes = list(snapshot.next) if snapshot.next else []

        if "pm_step2_informal" in next_nodes:
            st.session_state.stage = "wait_step2"
        elif "pm_step4" in next_nodes:
            st.session_state.stage = "wait_step4"
        else:
            st.session_state.stage = "done"

    except Exception as e:
        st.session_state.stage = "idle"
        st.session_state.error_msg = str(e)
        log.exception("STEP 1~3 추출 오류")
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    st.rerun()


def _render_step2_form(cfg):
    """비공식 요구사항 폼."""
    with st.form("step2_form"):
        st.markdown("#### Hidden Needs (발주처의 명시되지 않은 요구)")
        hidden = st.text_area(
            "Hidden Needs",
            placeholder="예: 담당자가 클라우드 전환을 강력히 원하나 예산상 명시 못함",
            height=100, label_visibility="collapsed",
        )
        st.markdown("#### Pain Points (발주처가 가장 우려하는 이슈)")
        pain = st.text_area(
            "Pain Points",
            placeholder="예: 기존 시스템 이전 시 데이터 손실 우려, 운영 중단 불가",
            height=100, label_visibility="collapsed",
        )
        st.markdown("#### 핵심 쟁점사항 (영업·인터뷰에서 파악된 핵심 이슈)")
        issues = st.text_area(
            "핵심 쟁점",
            placeholder="예: 전임 사업자 대비 인력 규모 비교가 핵심 평가 기준",
            height=80, label_visibility="collapsed",
        )

        submitted = st.form_submit_button("✅ 입력 완료 → 경쟁력 분석으로", type="primary", width="stretch")

    if submitted:
        _parse_and_set(
            "step2_informal_requirements",
            {
                "hidden_needs": [l.strip() for l in hidden.split("\n") if l.strip()],
                "pain_points": [l.strip() for l in pain.split("\n") if l.strip()],
                "key_issues": [l.strip() for l in issues.split("\n") if l.strip()],
            },
            next_stage="wait_step4",
            cfg=cfg,
        )


def _render_step4_form(cfg):
    """경쟁력 분석 폼."""
    with st.form("step4_form"):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 과거 유사 실적")
            past = st.text_area("과거실적", placeholder="예: 2023 국가정보자원관리원 HW통합구축 (120억)", height=100, label_visibility="collapsed")
            st.markdown("#### 핵심 인력")
            personnel = st.text_area("핵심인력", placeholder="예: PM 홍길동 - 20년 공공정보화 경력, PMP", height=100, label_visibility="collapsed")
        with col2:
            st.markdown("#### 기술 솔루션·차별화 기술")
            tech = st.text_area("기술솔루션", placeholder="예: 자체 개발 AI 기반 인프라 모니터링 플랫폼", height=100, label_visibility="collapsed")
            st.markdown("#### 협력사")
            partners = st.text_area("협력사", placeholder="예: (주)ABC - DB 전문업체, SLA 보증", height=80, label_visibility="collapsed")

        st.markdown("#### 경쟁사 대비 강점 / 약점")
        col3, col4 = st.columns(2)
        with col3:
            strengths = st.text_area("강점", placeholder="예: 동일 기관 레퍼런스 보유", height=80, label_visibility="collapsed")
        with col4:
            weaknesses = st.text_area("약점", placeholder="예: 가격 경쟁력이 2위 업체 대비 5% 높음", height=80, label_visibility="collapsed")

        submitted = st.form_submit_button("✅ 입력 완료 → 전략 생성 시작", type="primary", width="stretch")

    if submitted:
        _parse_and_set(
            "step4_competitiveness",
            {
                "past_projects": [l.strip() for l in past.split("\n") if l.strip()],
                "key_personnel": [l.strip() for l in personnel.split("\n") if l.strip()],
                "tech_solutions": [l.strip() for l in tech.split("\n") if l.strip()],
                "partners": [l.strip() for l in partners.split("\n") if l.strip()],
                "vs_competitors": {
                    "strengths": [l.strip() for l in strengths.split("\n") if l.strip()],
                    "weaknesses": [l.strip() for l in weaknesses.split("\n") if l.strip()],
                },
            },
            next_stage="generating",
            cfg=cfg,
        )


def _render_step6_form(cfg):
    """STEP 6 의사결정 폼 (선택)."""
    st.markdown("STEP 5 전략 생성 결과를 확인 후, 주요 의사결정이 필요한 항목을 입력하거나 건너뜁니다.")

    # STEP 5 결과 표시
    outputs = st.session_state.step_outputs
    s51 = outputs.get("step5_1_competitive_diff", "")
    s52 = outputs.get("step5_2_issue_solution", "")
    if s51 or s52:
        with st.expander("STEP 5 전략 결과 확인", expanded=True):
            if s51:
                st.markdown("**[5-1] 경쟁구도 차별화**")
                st.markdown(s51)
            if s52:
                st.markdown("**[5-2] 핵심이슈 차별화**")
                st.markdown(s52)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("⏭️ STEP 6 건너뛰고 STEP 7 생성", width="stretch"):
            _resume_after_pm(
                {"skip_step6": True, "step6_decisions": []},
                next_stage="generating",
                cfg=cfg,
            )

    with col2:
        if st.button("📝 의사결정 사항 입력하기", width="stretch"):
            st.session_state["show_step6_form"] = True
            st.rerun()

    if st.session_state.get("show_step6_form"):
        with st.form("step6_form"):
            decisions_text = st.text_area(
                "주요 의사결정 필요 항목",
                placeholder="예:\n- 컨소시엄 구성 여부 결정 필요 (주관사 vs 단독)\n- 가격 전략: 최저가 vs 기술가산점 우선",
                height=150,
            )
            submitted = st.form_submit_button("✅ 입력 완료 → STEP 7 생성", type="primary", width="stretch")

        if submitted:
            decisions = [
                {"item": l.strip().lstrip("-").strip()}
                for l in decisions_text.split("\n")
                if l.strip()
            ]
            _resume_after_pm(
                {"skip_step6": False, "step6_decisions": decisions},
                next_stage="generating",
                cfg=cfg,
            )


def _parse_and_set(key: str, value: dict, next_stage: str, cfg):
    """PM 입력값을 LangGraph 상태에 주입하고 다음 interrupt까지 실행."""
    st.session_state.step_outputs[key] = value
    _resume_after_pm({key: value}, next_stage, cfg)


def _resume_after_pm(state_update: dict, next_stage: str, cfg):
    """update_state + Command(resume=None) → 다음 interrupt 또는 END."""
    from langgraph.types import Command

    try:
        from llm.factory import clear_cache
        clear_cache()

        app = _get_pipeline_app(cfg)
        config = {"configurable": {"thread_id": st.session_state.thread_id}}

        app.update_state(config, state_update)
        st.session_state.stage = next_stage

        result_container = st.container()
        with st.spinner("처리 중…"):
            outputs = _run_until_interrupt(app, Command(resume=None), config, result_container)

        st.session_state.step_outputs.update(outputs)

        # 다음 interrupt 확인
        snapshot = app.get_state(config)
        next_nodes = list(snapshot.next) if snapshot.next else []

        if "pm_step4" in next_nodes:
            st.session_state.stage = "wait_step4"
        elif "pm_step6" in next_nodes:
            st.session_state.stage = "wait_step6"
        elif next_nodes:
            # 알 수 없는 interrupt 노드 — 사용자에게 알리고 idle로 복귀
            log.warning("알 수 없는 interrupt 노드: %s", next_nodes)
            st.session_state.error_msg = f"예상치 못한 중단점: {next_nodes}. 개발자에게 문의하세요."
            st.session_state.stage = "idle"
        else:
            # END 도달 — 최종 산출물 추출
            final_md = st.session_state.step_outputs.get("final_output_md", "")
            if not final_md:
                state = _current_graph_state(app, config)
                final_md = state.get("final_output_md", "")
            st.session_state.final_md = final_md
            st.session_state.stage = "done"

    except Exception as e:
        st.session_state.error_msg = str(e)
        log.exception("파이프라인 재개 오류")

    st.rerun()


def _render_done_screen():
    """완료 화면 — 각 단계 결과 + Markdown 다운로드."""
    st.success("✅ 제안전략 수립 완료!")

    outputs = st.session_state.step_outputs
    final_md = st.session_state.final_md

    # 다운로드 버튼
    if final_md:
        st.download_button(
            label="📥 최종 산출물 다운로드 (Markdown)",
            data=final_md.encode("utf-8"),
            file_name=f"제안전략_{st.session_state.rfp_filename.replace('.pdf', '')}.md",
            mime="text/markdown",
            type="primary",
            width="stretch",
        )

    st.divider()

    # 단계별 결과 표시
    with st.expander("STEP 1: 사업개요", expanded=True):
        st.json(outputs.get("step1_business_overview", {}))

    with st.expander("STEP 2-1: 공식 요구사항"):
        st.json(outputs.get("step2_formal_requirements", []))

    with st.expander("STEP 2-2: 비공식 요구사항"):
        st.json(outputs.get("step2_informal_requirements", {}))

    with st.expander("STEP 3: 평가항목 분석"):
        st.json(outputs.get("step3_eval_criteria", {}))

    with st.expander("STEP 4: 경쟁력 분석"):
        st.json(outputs.get("step4_competitiveness", {}))

    with st.expander("STEP 5: 경쟁우위 차별화 전략", expanded=True):
        s51 = outputs.get("step5_1_competitive_diff", "")
        s52 = outputs.get("step5_2_issue_solution", "")
        if s51:
            st.markdown("**[5-1] 경쟁구도 차별화**")
            st.markdown(s51)
        if s52:
            st.markdown("**[5-2] 핵심이슈 차별화**")
            st.markdown(s52)

    decisions = outputs.get("step6_decisions", [])
    if decisions:
        with st.expander("STEP 6: 의사결정 사항"):
            st.json(decisions)

    with st.expander("STEP 7: 사업수행전략", expanded=True):
        csf = outputs.get("step7_1_csf", [])
        summary = outputs.get("step7_2_strategy_summary", "")
        plan = outputs.get("step7_3_execution_plan", "")
        storyboard = outputs.get("step7_4_storyboard", [])
        if csf:
            st.markdown("**[7-1] 핵심성공요소**")
            st.markdown(csf[0])
        if summary:
            st.markdown("**[7-2] 전략 요약**")
            st.markdown(summary)
        if plan:
            st.markdown("**[7-3] MECE 이행방안**")
            st.markdown(plan)
        if storyboard:
            st.markdown("**[7-4] 스토리보드**")
            st.markdown(storyboard[0])

    if final_md:
        with st.expander("전체 Markdown 미리보기"):
            st.markdown(final_md)


# ── 탭 2: 슬라이드 샘플 검색 ─────────────────────────────────────

@st.dialog("🖼️ 슬라이드 미리보기", width="large")
def _image_popup(png_path: str, file_name: str):
    st.image(png_path, width="stretch")
    with open(png_path, "rb") as img_file:
        st.download_button(
            "📥 이미지 다운로드",
            data=img_file.read(),
            file_name=file_name,
            mime="image/png",
            type="primary",
            width="stretch",
        )


def _render_tab_slides(cfg):
    st.header("🖼️ 슬라이드 샘플 검색")
    st.caption("기존 26건 제안서에서 주제 관련 슬라이드를 검색합니다.")

    col1, col2 = st.columns([3, 1])
    with col1:
        topic = st.text_input(
            "검색 주제",
            placeholder="예: 재해복구 전략, 핵심인력 구성, 클라우드 전환 아키텍처",
            key="slide_topic",
        )
    with col2:
        final_k = st.slider("표시 개수", min_value=3, max_value=10, value=10, key="slide_final_k")

    # 필터 옵션
    with st.expander("🔎 필터 옵션"):
        fcol1, fcol2, fcol3 = st.columns(3)
        with fcol1:
            domain_filter = st.selectbox("도메인", _DOMAINS, key="slide_domain")
        with fcol2:
            project_type_filter = st.selectbox("사업유형", _PROJECT_TYPES, key="slide_project_type")
        with fcol3:
            result_filter = st.selectbox("수주 여부", _RESULTS, key="slide_result")

    if st.button("🔍 검색", type="primary", disabled=not topic):
        if not topic:
            st.warning("검색 주제를 입력하세요.")
            return

        filter_dict: dict = {}
        if domain_filter != "(전체)":
            filter_dict["domain"] = domain_filter
        if project_type_filter != "(전체)":
            filter_dict["project_type"] = project_type_filter
        if result_filter != "(전체)":
            filter_dict["result"] = result_filter

        # 이전 검색 결과 및 선정 사유 캐시 초기화
        for k in list(st.session_state.keys()):
            if k.startswith("reason_"):
                del st.session_state[k]
        st.session_state["slide_results"] = None

        _run_slide_search(topic, final_k, filter_dict or None, cfg)

    # 세션 상태에서 결과 표시 (rerun 후에도 유지)
    results = st.session_state.get("slide_results")
    search_topic = st.session_state.get("slide_search_topic", "")
    if results is not None:
        if results:
            st.caption(f"{len(results)}개 슬라이드")
            n_cols = min(3, len(results))
            cols = st.columns(n_cols)
            for i, r in enumerate(results):
                with cols[i % n_cols]:
                    _render_slide_card(i + 1, r, search_topic, cfg)
        else:
            st.info("검색 결과가 없습니다. 주제를 변경하거나 필터를 조정해 보세요.")


def _run_slide_search(topic: str, final_k: int, filter_dict, cfg):
    from slide_sampler.searcher import search_slides

    with st.spinner(f"슬라이드 검색 중 (주제: {topic!r})…"):
        try:
            results = search_slides(topic, cfg=cfg, final_k=final_k, filter_dict=filter_dict)
        except Exception as e:
            st.error(f"검색 오류: {e}")
            log.exception("슬라이드 검색 오류")
            st.session_state["slide_results"] = []
            return

    st.session_state["slide_results"] = results or []
    st.session_state["slide_search_topic"] = topic


def _render_slide_card(rank: int, r, topic: str, cfg):
    from slide_sampler.explainer import generate_reason

    st.markdown(f"**#{rank}** `Rerank: {r.rerank_score:.3f}`")

    # 이미지 표시
    png_path = Path(r.png_path) if r.png_path else None
    if png_path and png_path.exists():
        st.image(str(png_path), width="stretch")
        file_name = f"{r.doc_id}_slide{r.slide_no or rank}.png"
        if st.button("🔍 크게 보기 / 다운로드", key=f"zoom_{rank}_{r.doc_id}_{r.slide_no}"):
            _image_popup(str(png_path), file_name)
    else:
        st.info("이미지 없음")
        st.caption(r.slide_text[:200])

    st.caption(
        f"📁 {r.doc_id}  \n"
        f"📅 {r.year}  |  🏢 {r.agency}  |  "
        f"{'🏆 수주' if r.result == '수주' else '❌ 실주' if r.result == '실주' else r.result}"
        + (f"  |  슬라이드 {r.slide_no}" if r.slide_no else "")
    )
    if r.section:
        st.caption(f"섹션: {r.section}")

    # LLM 선정 사유 (on-demand)
    reason_key = f"reason_{r.doc_id}_{r.slide_no}"
    if reason_key not in st.session_state:
        if st.button("💬 선정 사유 보기", key=f"btn_{rank}_{r.doc_id}_{r.slide_no}"):
            with st.spinner("선정 사유 생성 중…"):
                try:
                    reason = generate_reason(
                        topic=topic,
                        slide_text=r.slide_text,
                        project_name=r.doc_id,
                        year=r.year,
                        result=r.result,
                        section=r.section,
                        cfg=cfg,
                    )
                except Exception as e:
                    log.warning("선정 사유 UI 오류: %s", e)
                    reason = f"(선정 사유 생성 실패: {e})"
            st.session_state[reason_key] = reason or "(응답 없음)"
            st.markdown(st.session_state[reason_key])
    else:
        st.markdown(st.session_state[reason_key])


# ── 메인 ─────────────────────────────────────────────────────────

def main():
    _init_session()

    default_llm, step5_llm, step7_llm = _render_sidebar()
    cfg = _build_cfg(
        default_llm=default_llm,
        step5_llm=step5_llm,
        step7_llm=step7_llm,
    )

    tab1, tab2 = st.tabs(["📋 제안전략 수립", "🖼️ 슬라이드 샘플 검색"])

    with tab1:
        _render_tab_strategy(cfg)

    with tab2:
        _render_tab_slides(cfg)


if __name__ == "__main__":
    main()
