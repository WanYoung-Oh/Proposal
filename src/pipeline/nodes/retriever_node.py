"""retrieve_rag 노드 — 방법론 + 제안서 병렬 Hybrid 검색."""
import logging

from omegaconf import DictConfig

from rag.embedder import Embedder, get_embedder
from rag.retriever import Retriever, normalize_domain
from rag.vectorstore import VectorStore
from ..state import GraphState

log = logging.getLogger(__name__)

_METHODOLOGY_COLLECTION = "methodology"
_PROPOSALS_COLLECTION = "proposals"

_embedder_cache: dict[str, Embedder] = {}


def _get_cached_embedder(cfg: DictConfig) -> Embedder:
    key = f"{cfg.ingestion.embedding_model}:{cfg.env.embedding_device}"
    if key not in _embedder_cache:
        _embedder_cache[key] = get_embedder(cfg)
    return _embedder_cache[key]


def _build_rag_query(state: GraphState) -> str:
    """STEP 1~3 결과를 종합하여 RAG 검색 쿼리 문자열 생성."""
    parts: list[str] = []

    overview = state.get("step1_business_overview") or {}
    if overview.get("project_name"):
        parts.append(overview["project_name"])
    if overview.get("project_scope"):
        parts.append(overview["project_scope"])
    if overview.get("domain"):
        parts.append(overview["domain"])

    informal = state.get("step2_informal_requirements") or {}
    for field in ("hidden_needs", "pain_points", "key_issues"):
        items = informal.get(field, [])
        if items:
            parts.append(" ".join(str(i) for i in items[:3]))

    eval_info = state.get("step3_eval_criteria") or {}
    high_score = eval_info.get("high_score_items", [])
    if high_score:
        parts.append(" ".join(str(i) for i in high_score[:3]))

    return " ".join(parts)[:500] if parts else "공공정보화 제안전략 차별화"


def _domain_filter(state: GraphState) -> dict | None:
    """사업개요 domain에서 Qdrant 필터 dict 생성. 매핑 없으면 None 반환."""
    overview = state.get("step1_business_overview") or {}
    domain_raw = overview.get("domain", "")
    canonical = normalize_domain(domain_raw) if domain_raw else None
    if canonical:
        return {"domain": canonical}
    return None


def retrieve_rag_node(state: GraphState, cfg: DictConfig) -> GraphState:
    """Dense + BM25 + RRF로 방법론·제안서 컬렉션 검색."""
    embedder = _get_cached_embedder(cfg)
    vs = VectorStore(cfg)
    retriever = Retriever(embedder, vs, cfg)

    query = _build_rag_query(state)
    domain_filter = _domain_filter(state)

    log.info("RAG 쿼리: %s (domain_filter=%s)", query[:60], domain_filter)

    # 방법론 검색 (domain 필터 없이 전체)
    methodology_results = retriever.search_methodology(query, collection=_METHODOLOGY_COLLECTION)

    # 제안서 검색 (domain 필터 적용)
    proposal_results = retriever.search_proposals(
        query, collection=_PROPOSALS_COLLECTION, filter_dict=domain_filter
    )

    # 검색 결과를 LLM 컨텍스트용 텍스트 목록으로 직렬화
    methodology_docs = [
        {
            "doc_id": r.doc_id,
            "slide_no": r.slide_no,
            "text": r.text[:800],
            "score": round(r.score, 4),
            "section": r.payload.get("section", ""),
        }
        for r in methodology_results
    ]
    case_docs = [
        {
            "doc_id": r.doc_id,
            "slide_no": r.slide_no,
            "text": r.text[:800],
            "score": round(r.score, 4),
            "section": r.payload.get("section", ""),
            "year": r.payload.get("year", ""),
            "agency": r.payload.get("agency", ""),
            "result": r.payload.get("result", ""),
            "strategy_summary": r.payload.get("strategy_summary", []),
            "png_path": r.payload.get("png_path", ""),
        }
        for r in proposal_results
    ]

    log.info(
        "RAG 결과: methodology=%d건, proposals=%d건",
        len(methodology_docs), len(case_docs),
    )

    meta = dict(state.get("metadata") or {})
    meta["rag_hit_counts"] = {
        "methodology": len(methodology_docs),
        "proposals": len(case_docs),
    }
    return {
        "rag_methodology_docs": methodology_docs,
        "rag_case_docs": case_docs,
        "metadata": meta,
    }
