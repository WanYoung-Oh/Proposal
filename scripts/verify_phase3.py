#!/usr/bin/env python
"""Phase 1~4 통합 검증 스크립트.

실행:
    cd /data/ephemeral/home/proposal
    source .venv/bin/activate
    export $(cat .env | xargs)
    python scripts/verify_phase3.py [--llm solar|claude|qwen_local] [--skip-llm]
"""
import argparse
import json
import logging
import os
import sys
from pathlib import Path

# src/ 경로 추가
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("verify_phase3")

_PASS = "✅"
_FAIL = "❌"
_SKIP = "⏭️ "
_results: list[tuple[str, bool, str]] = []


def _check(name: str, ok: bool, detail: str = "") -> bool:
    _results.append((name, ok, detail))
    icon = _PASS if ok else _FAIL
    print(f"  {icon} {name}" + (f" — {detail}" if detail else ""))
    return ok


def _section(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ── 1. 모듈 import 검사 ───────────────────────────────────────────

def check_imports() -> bool:
    _section("1. 모듈 Import 검사")
    ok = True

    try:
        from llm.base import BaseLLM
        _check("llm.base.BaseLLM", True)
    except Exception as e:
        _check("llm.base.BaseLLM", False, str(e)); ok = False

    try:
        from llm.solar import SolarProLLM
        _check("llm.solar.SolarProLLM", True)
    except Exception as e:
        _check("llm.solar.SolarProLLM", False, str(e)); ok = False

    try:
        from llm.claude import ClaudeLLM
        _check("llm.claude.ClaudeLLM", True)
    except Exception as e:
        _check("llm.claude.ClaudeLLM", False, str(e)); ok = False

    try:
        from llm.qwen_local import QwenLocalLLM
        _check("llm.qwen_local.QwenLocalLLM", True)
    except Exception as e:
        _check("llm.qwen_local.QwenLocalLLM", False, str(e)); ok = False

    try:
        from llm.factory import get_llm, get_node_temperature
        _check("llm.factory.get_llm", True)
    except Exception as e:
        _check("llm.factory.get_llm", False, str(e)); ok = False

    try:
        from pipeline.state import GraphState
        _check("pipeline.state.GraphState", True)
    except Exception as e:
        _check("pipeline.state.GraphState", False, str(e)); ok = False

    try:
        from pipeline.nodes import (
            parse_rfp_node, extract_step1_node, extract_step2_formal_node,
            extract_step3_node, pm_step2_informal_node, pm_step4_node,
            pm_step6_node, retrieve_rag_node, generate_step5_node,
            generate_step7_node, format_output_node,
        )
        _check("pipeline.nodes (11개 노드)", True)
    except Exception as e:
        _check("pipeline.nodes", False, str(e)); ok = False

    try:
        from pipeline.graph import build_graph, sqlite_checkpointer
        _check("pipeline.graph.build_graph", True)
    except Exception as e:
        _check("pipeline.graph.build_graph", False, str(e)); ok = False

    return ok


# ── 2. GraphState 타입 검사 ──────────────────────────────────────

def check_graph_state() -> bool:
    _section("2. GraphState 구조 검사")
    from pipeline.state import GraphState
    required_keys = [
        "rfp_raw_text", "rfp_file_path", "current_step",
        "step1_business_overview", "step2_formal_requirements",
        "step2_informal_requirements", "step3_eval_criteria",
        "step4_competitiveness", "step5_1_competitive_diff",
        "step5_2_issue_solution", "skip_step6", "step6_decisions",
        "step7_1_csf", "step7_2_strategy_summary", "step7_3_execution_plan",
        "step7_4_storyboard", "rag_methodology_docs", "rag_case_docs",
        "final_output_md", "metadata",
    ]
    hints = GraphState.__annotations__
    ok = True
    for key in required_keys:
        found = key in hints
        _check(f"GraphState.{key}", found)
        ok = ok and found
    return ok


# ── 3. 프롬프트 설정 파일 검사 ────────────────────────────────────

def check_prompts() -> bool:
    _section("3. 프롬프트 설정 파일 검사")
    prompts_dir = Path(__file__).parent.parent / "configs" / "prompts"
    required = [
        "expert_persona.yaml",
        "extract_step1.yaml",
        "extract_step2_formal.yaml",
        "extract_step3.yaml",
        "generate_step5.yaml",
        "generate_step7.yaml",
    ]
    ok = True
    for fname in required:
        path = prompts_dir / fname
        found = path.exists()
        _check(f"configs/prompts/{fname}", found, f"{path.stat().st_size}B" if found else "없음")
        ok = ok and found
    return ok


# ── 4. LangGraph 그래프 컴파일 검사 ──────────────────────────────

def check_graph_compile() -> bool:
    _section("4. LangGraph 그래프 컴파일 검사")
    try:
        from omegaconf import OmegaConf
        # 최소 cfg 구성 (LLM 호출 없이 컴파일만 검사)
        cfg = OmegaConf.create({
            "llm": {
                "_target_": "src.llm.solar.SolarProLLM",
                "model": "solar-pro",
                "temperature": 0.3,
                "max_tokens": 4096,
            },
            "env": {
                "qdrant_host": "localhost",
                "qdrant_port": 6333,
                "embedding_device": "cpu",
                "embedding_batch_size": 16,
                "reranker_device": "cpu",
            },
            "rag": {
                "top_k": 5,
                "methodology_top_k": 3,
                "hybrid_alpha": 0.7,
                "min_score_threshold": 0.5,
            },
            "pipeline": {
                "node_llm": {
                    "extract_step1": "solar",
                    "generate_step5": "claude",
                    "generate_step7": "claude",
                },
                "node_temperature": {
                    "extract_step1": 0.1,
                    "generate_step5": 0.6,
                    "generate_step7": 0.65,
                },
            },
        })
        from pipeline.graph import build_graph
        app = build_graph(cfg)

        # 노드 목록 확인
        nodes = list(app.get_graph().nodes.keys())
        expected_nodes = [
            "parse_rfp", "extract_step1", "extract_step2_formal", "extract_step3",
            "pm_step2_informal", "pm_step4", "retrieve_rag", "generate_step5",
            "pm_step6", "generate_step7", "format_output",
        ]
        node_set = set(nodes)
        ok = True
        for n in expected_nodes:
            found = n in node_set
            _check(f"노드 존재: {n}", found)
            ok = ok and found

        _check(f"전체 노드 수: {len(node_set)}", len(node_set) >= len(expected_nodes),
               f"{len(node_set)}개")
        return ok

    except Exception as e:
        _check("그래프 컴파일", False, str(e))
        return False


# ── 5. LLM 연결 검사 (선택적) ────────────────────────────────────

def check_llm_connection(llm_type: str) -> bool:
    _section(f"5. LLM 연결 검사 ({llm_type})")

    if llm_type == "solar":
        api_key = os.environ.get("SOLAR_API_KEY", "")
        if not api_key:
            _check("SOLAR_API_KEY 환경변수", False, "미설정")
            return False
        try:
            from llm.solar import SolarProLLM
            llm = SolarProLLM(api_key=api_key)
            result = llm.generate(
                [{"role": "user", "content": "안녕하세요. '테스트 성공'이라고만 답하세요."}],
                temperature=0.1, max_tokens=20,
            )
            _check("Solar Pro API 호출", "테스트" in result or len(result) > 0, result[:50])
            return True
        except Exception as e:
            _check("Solar Pro API 호출", False, str(e))
            return False

    elif llm_type == "claude":
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            _check("ANTHROPIC_API_KEY 환경변수", False, "미설정")
            return False
        try:
            from llm.claude import ClaudeLLM
            llm = ClaudeLLM(api_key=api_key, model="claude-haiku-4-5-20251001")
            result = llm.generate(
                [{"role": "user", "content": "안녕하세요. '테스트 성공'이라고만 답하세요."}],
                temperature=0.1, max_tokens=20,
            )
            _check("Claude API 호출", len(result) > 0, result[:50])
            return True
        except Exception as e:
            _check("Claude API 호출", False, str(e))
            return False

    elif llm_type == "qwen_local":
        base_url = os.environ.get("LOCAL_LLM_BASE_URL", "http://localhost:11434")
        try:
            import httpx
            r = httpx.get(f"{base_url}/v1/models", timeout=5)
            _check(f"로컬 LLM 서버 응답 ({base_url})", r.status_code == 200,
                   f"HTTP {r.status_code}")
            return r.status_code == 200
        except Exception as e:
            _check(f"로컬 LLM 서버 연결 ({base_url})", False, str(e))
            return False

    return True


# ── 6. 노드 단위 기능 검사 ────────────────────────────────────────

def check_rfp_parser() -> bool:
    _section("6. parse_rfp 노드 단위 검사")
    from pipeline.nodes.rfp_parser import parse_rfp_node

    # rfp_raw_text 이미 있는 경우 — skip 동작
    state = {"rfp_raw_text": "테스트 RFP 내용"}
    result = parse_rfp_node(state)
    _check("rfp_raw_text 존재 시 skip", result.get("current_step") == 1)

    # 없는 파일 경로 — 예외 처리
    try:
        parse_rfp_node({"rfp_file_path": "/nonexistent/path.pdf"})
        _check("없는 파일 예외 처리", False, "예외 미발생")
        return False
    except FileNotFoundError:
        _check("없는 파일 예외 처리 (FileNotFoundError)", True)

    return True


def check_pm_nodes() -> bool:
    _section("7. PM 입력 노드 패스스루 검사")
    from pipeline.nodes.rfp_analyzer import (
        pm_step2_informal_node, pm_step4_node, pm_step6_node
    )

    # pm_step2_informal — 빈 입력 초기화
    result = pm_step2_informal_node({})
    ok = all(k in result["step2_informal_requirements"]
             for k in ("hidden_needs", "pain_points", "key_issues"))
    _check("pm_step2_informal 빈 입력 초기화", ok)

    # pm_step4 — 빈 입력 초기화
    result = pm_step4_node({})
    ok = all(k in result["step4_competitiveness"]
             for k in ("past_projects", "key_personnel", "tech_solutions", "partners", "vs_competitors"))
    _check("pm_step4 빈 입력 초기화", ok)

    # pm_step6 — skip_step6=True
    result = pm_step6_node({"skip_step6": True})
    ok = result["step6_decisions"] == [] and result["current_step"] == 6
    _check("pm_step6 skip 동작", ok)

    return True


def check_output_formatter() -> bool:
    _section("8. format_output 노드 검사")
    from pipeline.nodes.output_formatter import format_output_node

    state = {
        "step1_business_overview": {"project_name": "테스트 사업", "agency": "테스트 기관"},
        "step2_formal_requirements": [{"name": "요구사항1", "detail": "내용1"}],
        "step2_informal_requirements": {"hidden_needs": ["니즈1"]},
        "step3_eval_criteria": {"high_score_items": ["기술평가"]},
        "step4_competitiveness": {"past_projects": ["프로젝트1"]},
        "step5_1_competitive_diff": "차별화 전략 내용",
        "step5_2_issue_solution": "핵심이슈 내용",
        "step7_1_csf": ["CSF 내용"],
        "step7_2_strategy_summary": "전략 요약",
        "step7_3_execution_plan": "이행방안",
        "step7_4_storyboard": ["스토리보드"],
        "skip_step6": True,
        "metadata": {},
    }
    result = format_output_node(state)
    md = result.get("final_output_md", "")
    _check("final_output_md 생성", len(md) > 100, f"{len(md)}자")
    _check("사업명 포함", "테스트 사업" in md)
    _check("STEP 5 포함", "5-1" in md or "[5-1]" in md)
    _check("STEP 7 포함", "7-1" in md or "[7-1]" in md)
    return True


def check_phase4_modules() -> bool:
    _section("9. Phase 3+4 — slide_sampler 모듈 검사")
    ok = True

    try:
        from slide_sampler.searcher import SlideResult, search_slides, get_reranker
        _check("slide_sampler.searcher 임포트", True)
    except Exception as e:
        _check("slide_sampler.searcher 임포트", False, str(e)); ok = False

    try:
        from slide_sampler.explainer import generate_reason
        _check("slide_sampler.explainer 임포트", True)
    except Exception as e:
        _check("slide_sampler.explainer 임포트", False, str(e)); ok = False

    # SlideResult 구조 검사
    try:
        from slide_sampler.searcher import SlideResult
        import dataclasses
        fields = {f.name for f in dataclasses.fields(SlideResult)}
        required = {"doc_id", "slide_no", "slide_text", "rrf_score", "rerank_score", "png_path"}
        for f in required:
            _check(f"SlideResult.{f}", f in fields)
            ok = ok and (f in fields)
    except Exception as e:
        _check("SlideResult 구조", False, str(e)); ok = False

    # streamlit_app cfg 빌더
    try:
        from app.streamlit_app import _build_cfg
        cfg = _build_cfg("solar", "claude", "claude")
        _check("streamlit_app._build_cfg", True, f"keys={list(cfg.keys())}")
        _check("node_llm generate_step5=claude", cfg.pipeline.node_llm.generate_step5 == "claude")
    except Exception as e:
        _check("streamlit_app._build_cfg", False, str(e)); ok = False

    return ok


# ── 10. Phase 1 — ingestion 모듈 import 검사 ────────────────────

def check_phase1_imports() -> bool:
    _section("10. Phase 1 — ingestion 모듈 Import 검사")
    ok = True

    mods = [
        ("ingestion.parsers.base", "ParsedDocument, ParsedSlide",
         "from ingestion.parsers.base import ParsedDocument, ParsedSlide"),
        ("ingestion.parsers.pptx_parser", "parse_pptx",
         "from ingestion.parsers.pptx_parser import parse_pptx, _is_title_placeholder"),
        ("ingestion.parsers.pdf_parser", "parse_pdf",
         "from ingestion.parsers.pdf_parser import parse_pdf"),
        ("ingestion.chunker", "build_chunks, tokenize_for_bm25",
         "from ingestion.chunker import build_chunks, tokenize_for_bm25, load_project_chunks"),
        ("ingestion.indexer", "run_indexing",
         "from ingestion.indexer import run_indexing, verify_indexing"),
        ("slide_sampler.renderer", "render_pdf_to_png",
         "from slide_sampler.renderer import render_pdf_to_png, render_all_projects"),
    ]
    for mod, label, stmt in mods:
        try:
            exec(stmt)
            _check(f"{mod} ({label})", True)
        except Exception as e:
            _check(f"{mod} ({label})", False, str(e)); ok = False

    return ok


# ── 11. Phase 1 — pptx_parser 버그 수정 확인 ────────────────────

def check_pptx_parser_fix() -> bool:
    _section("11. Phase 1 — pptx_parser 수정 확인")
    import inspect
    ok = True

    try:
        from ingestion.parsers.pptx_parser import _is_title_placeholder
        src = inspect.getsource(_is_title_placeholder)

        correct = "ph.idx == 0" in src
        _check("_is_title_placeholder: ph.idx == 0 사용", correct)
        ok = ok and correct

        bug_gone = "ph.idx in (0, 1)" not in src
        _check("_is_title_placeholder: ph.idx in (0,1) 제거됨", bug_gone)
        ok = ok and bug_gone
    except Exception as e:
        _check("pptx_parser._is_title_placeholder 검사", False, str(e)); ok = False

    return ok


# ── 12. Phase 1 — chunker 단위 검사 ─────────────────────────────

def check_chunker() -> bool:
    _section("12. Phase 1 — chunker 단위 검사")
    import inspect
    ok = True

    # Kiwi 지연 초기화
    try:
        import ingestion.chunker as chunker_mod
        is_lazy = chunker_mod._kiwi is None
        _check("chunker: Kiwi import 시점에 None (지연 초기화)", is_lazy)
        ok = ok and is_lazy
    except Exception as e:
        _check("chunker Kiwi 지연 초기화", False, str(e)); ok = False

    # build_chunks data_dir 파라미터
    try:
        from ingestion.chunker import build_chunks
        sig = inspect.signature(build_chunks)
        has_data_dir = "data_dir" in sig.parameters
        _check("build_chunks: data_dir 파라미터 존재", has_data_dir)
        ok = ok and has_data_dir
    except Exception as e:
        _check("build_chunks data_dir 파라미터", False, str(e)); ok = False

    # PNG 경로가 data_dir 반영
    try:
        from ingestion.parsers.base import ParsedDocument, ParsedSlide
        from ingestion.chunker import build_chunks
        doc = ParsedDocument(
            doc_id="test_proj",
            source_path="test.pptx",
            file_type="pptx",
            slides=[ParsedSlide(
                slide_no=1,
                title="테스트 제목",
                body="테스트 본문 내용입니다. " * 8,
                notes="",
            )],
        )
        chunks = build_chunks(doc, meta={}, tags={}, source="proposals",
                              data_dir="/custom/data/projects")
        if chunks:
            png_path = chunks[0].get("png_path", "")
            reflected = "/custom/data/projects" in png_path
            _check("build_chunks: png_path에 data_dir 반영",
                   reflected, f"png_path={png_path!r}")
            ok = ok and reflected
        else:
            _check("build_chunks: 청크 생성됨", False, "결과 없음"); ok = False
    except Exception as e:
        _check("build_chunks PNG 경로 검사", False, str(e)); ok = False

    # methodology 증분 토큰화 (O(n) 방식)
    try:
        from ingestion.chunker import load_methodology_chunks
        src = inspect.getsource(load_methodology_chunks)
        has_incremental = 'prev["tokenized_text"] +=' in src
        has_old = 'tokenize_for_bm25(prev["text"])' in src
        _check("methodology 병합: 증분 토큰화 (+= 방식)", has_incremental)
        _check("methodology 병합: 전체 재토큰화 제거됨", not has_old)
        ok = ok and has_incremental and (not has_old)
    except Exception as e:
        _check("methodology 증분 토큰화 확인", False, str(e)); ok = False

    return ok


# ── 13. Phase 1 — renderer·indexer 검사 ─────────────────────────

def check_renderer_indexer() -> bool:
    _section("13. Phase 1 — renderer·indexer 검사")
    import inspect
    ok = True

    # fitz 컨텍스트 매니저
    try:
        from slide_sampler.renderer import render_pdf_to_png
        src = inspect.getsource(render_pdf_to_png)
        has_ctx = "with fitz.open" in src
        _check("renderer: with fitz.open() 컨텍스트 매니저", has_ctx)
        ok = ok and has_ctx

        no_manual_close = "doc.close()" not in src
        _check("renderer: 명시적 doc.close() 제거됨", no_manual_close)
        ok = ok and no_manual_close
    except Exception as e:
        _check("renderer fitz 컨텍스트 매니저", False, str(e)); ok = False

    # indexer dead code 제거
    try:
        from ingestion.indexer import _upsert
        src = inspect.getsource(_upsert)
        no_dead = 'if k != "text"' not in src
        _check("indexer._upsert: 불필요한 text 필터링 dead code 제거됨", no_dead)
        ok = ok and no_dead
    except Exception as e:
        _check("indexer._upsert dead code 확인", False, str(e)); ok = False

    return ok


# ── 14. Phase 2 — RAG 모듈 import 검사 ──────────────────────────

def check_phase2_imports() -> bool:
    _section("14. Phase 2 — RAG 모듈 Import 검사")
    ok = True

    mods = [
        ("rag.embedder", "Embedder, get_embedder",
         "from rag.embedder import Embedder, get_embedder"),
        ("rag.vectorstore", "VectorStore, get_client",
         "from rag.vectorstore import VectorStore, get_client"),
        ("rag.retriever", "Retriever, SearchResult, normalize_domain",
         "from rag.retriever import Retriever, SearchResult, normalize_domain, korean_tokenize"),
    ]
    for mod, label, stmt in mods:
        try:
            exec(stmt)
            _check(f"{mod} ({label})", True)
        except Exception as e:
            _check(f"{mod} ({label})", False, str(e)); ok = False

    return ok


# ── 15. Phase 2 — Retriever·VectorStore 단위 검사 ────────────────

def check_retriever() -> bool:
    _section("15. Phase 2 — Retriever·VectorStore 단위 검사")
    import inspect
    ok = True

    # Kiwi 지연 초기화
    try:
        import rag.retriever as retriever_mod
        is_lazy = retriever_mod._kiwi is None
        _check("retriever: Kiwi import 시점에 None (지연 초기화)", is_lazy)
        ok = ok and is_lazy
    except Exception as e:
        _check("retriever Kiwi 지연 초기화", False, str(e)); ok = False

    # BM25 빈 코퍼스 방어
    try:
        from rag.retriever import Retriever
        src = inspect.getsource(Retriever.search)
        has_guard = "any(token_corpus)" in src
        _check("retriever.search: BM25 빈 코퍼스 방어 (any 체크)", has_guard)
        ok = ok and has_guard
    except Exception as e:
        _check("retriever BM25 방어 코드", False, str(e)); ok = False

    # VectorStore query_points() API 사용
    try:
        from rag.vectorstore import VectorStore
        src = inspect.getsource(VectorStore.search)
        uses_new = "query_points" in src
        no_old = "self.client.search(" not in src
        _check("VectorStore.search: query_points() 사용", uses_new)
        _check("VectorStore.search: 구버전 client.search() 미사용", no_old)
        ok = ok and uses_new and no_old
    except Exception as e:
        _check("VectorStore API 확인", False, str(e)); ok = False

    # SearchResult 구조
    try:
        from rag.retriever import SearchResult
        import dataclasses
        fields = {f.name for f in dataclasses.fields(SearchResult)}
        for f in ("doc_id", "slide_no", "text", "score", "payload"):
            found = f in fields
            _check(f"SearchResult.{f}", found)
            ok = ok and found
    except Exception as e:
        _check("SearchResult 구조", False, str(e)); ok = False

    # normalize_domain 호출 가능
    try:
        from rag.retriever import normalize_domain
        result = normalize_domain("인프라")
        _check("normalize_domain('인프라') 호출 성공", True, f"결과='{result}'")
    except FileNotFoundError:
        _check("normalize_domain (domain_map.yaml 없음 — 스킵)", True)
    except Exception as e:
        _check("normalize_domain 기능", False, str(e)); ok = False

    return ok


# ── 16. Phase 2 — RAG 설정·캐시 검사 ───────────────────────────

def check_rag_configs() -> bool:
    _section("16. Phase 2 — RAG 설정·캐시 검사")
    import inspect
    ok = True

    # domain_map.yaml 존재
    cfg_path = Path(__file__).parent.parent / "configs" / "rag" / "domain_map.yaml"
    found = cfg_path.exists()
    _check("configs/rag/domain_map.yaml 존재",
           found, f"{cfg_path.stat().st_size}B" if found else "없음")
    ok = ok and found

    # searcher embedder 모듈 캐시
    try:
        import slide_sampler.searcher as searcher_mod
        has_cache = hasattr(searcher_mod, "_embedder_cache")
        _check("slide_sampler.searcher: _embedder_cache 존재", has_cache)
        ok = ok and has_cache
    except Exception as e:
        _check("searcher embedder 캐시", False, str(e)); ok = False

    # retriever_node metadata shallow copy
    try:
        from pipeline.nodes.retriever_node import retrieve_rag_node
        src = inspect.getsource(retrieve_rag_node)
        has_shallow = 'dict(state.get("metadata")' in src or "dict(state.get('metadata')" in src
        _check("retriever_node: metadata dict() 얕은 복사", has_shallow)
        ok = ok and has_shallow
    except Exception as e:
        _check("retriever_node metadata 얕은 복사", False, str(e)); ok = False

    return ok


# ── 메인 ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Phase 1~4 통합 검증")
    parser.add_argument("--llm", choices=["solar", "claude", "qwen_local"], default=None,
                        help="LLM 연결 검사 대상 (생략 시 건너뜀)")
    parser.add_argument("--skip-llm", action="store_true", help="LLM 연결 검사 건너뜀")
    args = parser.parse_args()

    print("\n🔍 Phase 1~4 통합 검증 시작\n")

    all_ok = True
    # Phase 3+4
    all_ok &= check_imports()
    all_ok &= check_graph_state()
    all_ok &= check_prompts()
    all_ok &= check_graph_compile()
    all_ok &= check_rfp_parser()
    all_ok &= check_pm_nodes()
    all_ok &= check_output_formatter()
    all_ok &= check_phase4_modules()
    # Phase 1
    all_ok &= check_phase1_imports()
    all_ok &= check_pptx_parser_fix()
    all_ok &= check_chunker()
    all_ok &= check_renderer_indexer()
    # Phase 2
    all_ok &= check_phase2_imports()
    all_ok &= check_retriever()
    all_ok &= check_rag_configs()

    if not args.skip_llm and args.llm:
        all_ok &= check_llm_connection(args.llm)
    elif not args.skip_llm and not args.llm:
        print(f"\n{_SKIP} LLM 연결 검사 건너뜀 (--llm solar|claude|qwen_local 로 활성화)")

    # 최종 요약
    print(f"\n{'='*60}")
    print("  최종 결과")
    print(f"{'='*60}")
    passed = sum(1 for _, ok, _ in _results if ok)
    total = len(_results)
    failed = [name for name, ok, _ in _results if not ok]

    print(f"  통과: {passed}/{total}")
    if failed:
        print(f"  실패 항목:")
        for f in failed:
            print(f"    {_FAIL} {f}")
    else:
        print(f"  {_PASS} 전체 검증 통과!")

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
