"""SlideSearcher — 주제 기반 슬라이드 샘플 검색 (Dense + BM25 + RRF + Reranker)."""
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path

from omegaconf import DictConfig
from sentence_transformers import CrossEncoder

from ingestion.slide_classifier import detect_slide_type
from rag.embedder import Embedder, get_embedder
from rag.retriever import Retriever, normalize_domain
from rag.vectorstore import VectorStore

log = logging.getLogger(__name__)

_PROPOSALS_COLLECTION = "proposals"
_RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"

_embedder_cache: dict[str, Embedder] = {}


def _get_cached_embedder(cfg: DictConfig) -> Embedder:
    key = f"{cfg.ingestion.embedding_model}:{cfg.env.embedding_device}"
    if key not in _embedder_cache:
        _embedder_cache[key] = get_embedder(cfg)
    return _embedder_cache[key]

_reranker: CrossEncoder | None = None
_reranker_lock = threading.Lock()


def get_reranker(device: str = "cpu") -> CrossEncoder:
    global _reranker
    if _reranker is None:
        with _reranker_lock:
            if _reranker is None:
                log.info("Reranker 모델 로드: %s (device=%s)", _RERANKER_MODEL, device)
                _reranker = CrossEncoder(_RERANKER_MODEL, device=device)
    return _reranker


@dataclass
class SlideResult:
    doc_id: str
    slide_no: int
    slide_text: str
    rrf_score: float
    rerank_score: float = 0.0
    png_path: str = ""
    project_name: str = ""
    year: str = ""
    agency: str = ""
    result: str = ""
    domain: str = ""
    section: str = ""
    strategy_summary: list = field(default_factory=list)
    meta: dict = field(default_factory=dict)


def _deduplicate_by_project(
    candidates: list, max_per_project: int = 2
) -> list:
    """동일 프로젝트의 슬라이드를 최대 max_per_project개로 제한."""
    counts: dict[str, int] = {}
    result = []
    for c in candidates:
        pid = c.doc_id
        if counts.get(pid, 0) < max_per_project:
            counts[pid] = counts.get(pid, 0) + 1
            result.append(c)
    return result


_OVERVIEW_PENALTY = 0.3
_MIN_RERANK_SCORE = 0.05


def _search_collection(
    topic: str,
    cfg: DictConfig,
    collection: str,
    final_k: int,
    filter_dict: dict | None = None,
    apply_type_penalty: bool = True,
) -> list[SlideResult]:
    """단일 컬렉션 검색 → Reranker → 정렬 → final_k 반환.

    Args:
        apply_type_penalty: False이면 overview/toc 패널티 및 실시간 재분류 생략.
                            방법론처럼 이론 자료라 개요 형식이 많은 경우에 사용.
    """
    embedder = _get_cached_embedder(cfg)
    vs = VectorStore(cfg)
    retriever = Retriever(embedder, vs, cfg)

    candidates_raw = retriever.search(
        query=topic,
        collection=collection,
        top_k=20,
        filter_dict=filter_dict,
    )

    if not candidates_raw:
        return []

    candidates = [
        SlideResult(
            doc_id=r.doc_id,
            slide_no=r.slide_no,
            slide_text=r.text,
            rrf_score=r.score,
            png_path=r.payload.get("png_path", ""),
            project_name=r.doc_id,
            year=r.payload.get("year", ""),
            agency=r.payload.get("agency", ""),
            result=r.payload.get("result", ""),
            domain=r.payload.get("domain", ""),
            section=r.payload.get("section", ""),
            strategy_summary=r.payload.get("strategy_summary", []),
            meta=r.payload,
        )
        for r in candidates_raw
    ]

    # 슬라이드 유형 실시간 재분류 (proposals만 적용 — 방법론은 개요 형식이 많아 패널티 불필요)
    if apply_type_penalty:
        for c in candidates:
            stored_type = c.meta.get("slide_type", "general")
            if stored_type in ("general", "detail"):
                live_type = detect_slide_type(c.slide_text)
                if live_type in ("overview", "toc"):
                    c.meta["slide_type"] = live_type
                    log.debug("slide_type 재분류: %s slide%03d  %s → %s",
                              c.doc_id[-20:], c.slide_no, stored_type, live_type)

    # Reranker
    reranker = get_reranker(device=cfg.env.reranker_device)
    pairs = [(topic, c.slide_text) for c in candidates]
    scores = reranker.predict(pairs, batch_size=1)
    for c, s in zip(candidates, scores):
        c.rerank_score = float(s)

    # overview/toc 패널티 (proposals만 적용)
    if apply_type_penalty:
        for c in candidates:
            if c.meta.get("slide_type") in ("overview", "toc"):
                c.rerank_score *= _OVERVIEW_PENALTY

    ranked = sorted(candidates, key=lambda c: c.rerank_score, reverse=True)
    ranked = [c for c in ranked if c.rerank_score >= _MIN_RERANK_SCORE]
    ranked = _deduplicate_by_project(ranked, max_per_project=2)
    return ranked[:final_k]


def search_slides(
    topic: str,
    cfg: DictConfig,
    final_k: int = 10,
    filter_dict: dict | None = None,
) -> list[SlideResult]:
    """제안서 컬렉션에서 슬라이드 검색 (overview/toc 패널티 적용)."""
    results = _search_collection(
        topic, cfg,
        collection=_PROPOSALS_COLLECTION,
        final_k=final_k,
        filter_dict=filter_dict,
        apply_type_penalty=True,
    )
    log.info("제안서 검색 완료: topic='%s', 최종=%d", topic, len(results))
    return results


