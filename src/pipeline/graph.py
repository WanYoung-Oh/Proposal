"""LangGraph 파이프라인 — 제안전략 수립 7단계 DAG 조립."""
import functools
import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph
from omegaconf import DictConfig

from .state import GraphState
from .nodes import (
    parse_rfp_node,
    extract_step1_node,
    extract_step2_formal_node,
    extract_step3_node,
    pm_step2_informal_node,
    pm_step4_node,
    pm_step6_node,
    retrieve_rag_node,
    generate_step5_node,
    generate_step7_node,
    format_output_node,
)

log = logging.getLogger(__name__)


def _wrap(fn, cfg: DictConfig):
    """Hydra cfg를 클로저로 캡처하는 노드 래퍼 (LangGraph는 단일 state 인수 기대)."""
    @functools.wraps(fn)
    def wrapped(state: GraphState) -> GraphState:
        return fn(state, cfg)
    return wrapped


def build_graph(cfg: DictConfig, checkpointer=None):
    """LangGraph 컴파일 앱 반환.

    Args:
        cfg: Hydra DictConfig
        checkpointer: LangGraph checkpointer (기본 None → MemorySaver)
    Returns:
        CompiledGraph
    """
    if checkpointer is None:
        import warnings
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()
        warnings.warn(
            "build_graph(checkpointer=None): MemorySaver 사용 중. "
            "interrupt_before가 정상 동작하려면 SqliteSaver 등 영속 checkpointer가 필요합니다.",
            stacklevel=2,
        )
        log.debug("MemorySaver 사용 (개발 모드)")

    graph = StateGraph(GraphState)

    # ── 자동 단계 ─────────────────────────────────────────────────
    graph.add_node("parse_rfp",            parse_rfp_node)         # rfp_file_path → rfp_raw_text
    graph.add_node("extract_step1",        _wrap(extract_step1_node, cfg))
    graph.add_node("extract_step2_formal", _wrap(extract_step2_formal_node, cfg))
    graph.add_node("extract_step3",        _wrap(extract_step3_node, cfg))

    # ── PM 입력 단계 (interrupt_before) ────────────────────────────
    graph.add_node("pm_step2_informal",    pm_step2_informal_node)
    graph.add_node("pm_step4",             pm_step4_node)
    graph.add_node("pm_step6",             pm_step6_node)

    # ── AI 도출 단계 ───────────────────────────────────────────────
    graph.add_node("retrieve_rag",         _wrap(retrieve_rag_node, cfg))
    graph.add_node("generate_step5",       _wrap(generate_step5_node, cfg))
    graph.add_node("generate_step7",       _wrap(generate_step7_node, cfg))
    graph.add_node("format_output",        format_output_node)

    # ── 엣지 ──────────────────────────────────────────────────────
    graph.set_entry_point("parse_rfp")
    graph.add_edge("parse_rfp",            "extract_step1")
    graph.add_edge("extract_step1",        "extract_step2_formal")
    graph.add_edge("extract_step2_formal", "extract_step3")
    graph.add_edge("extract_step3",        "pm_step2_informal")
    graph.add_edge("pm_step2_informal",    "pm_step4")
    graph.add_edge("pm_step4",             "retrieve_rag")
    graph.add_edge("retrieve_rag",         "generate_step5")
    graph.add_edge("generate_step5",       "pm_step6")
    graph.add_edge("pm_step6",             "generate_step7")
    graph.add_edge("generate_step7",       "format_output")
    graph.add_edge("format_output",        END)

    app = graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["pm_step2_informal", "pm_step4", "pm_step6"],
    )
    log.info("LangGraph 파이프라인 컴파일 완료")
    return app


@contextmanager
def sqlite_checkpointer(db_path: str) -> Iterator[SqliteSaver]:
    """SqliteSaver 컨텍스트 매니저 — 연결 수명 관리."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    try:
        yield checkpointer
    finally:
        conn.close()


def get_app(cfg: DictConfig):
    """MemorySaver를 사용하는 컴파일 앱 반환 (개발·테스트 전용).

    운영 환경(Streamlit 포함)에서는 SqliteSaver를 직접 생성:

        db_path = cfg.get("sessions_db_path", "data/sessions.db")
        with sqlite_checkpointer(db_path) as cp:
            app = build_graph(cfg, checkpointer=cp)
            ...

    Streamlit에서는 streamlit_app.py의 _get_pipeline_app() 사용 권장.
    """
    return build_graph(cfg)
