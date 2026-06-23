import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from kiwipiepy import Kiwi
from omegaconf import DictConfig, OmegaConf
from rank_bm25 import BM25Okapi

from .embedder import Embedder
from .vectorstore import VectorStore

log = logging.getLogger(__name__)

_kiwi: Optional[Kiwi] = None
_KEEP_TAGS = {"NNG", "NNP", "VV", "VA", "SL"}


def _get_kiwi() -> Kiwi:
    global _kiwi
    if _kiwi is None:
        _kiwi = Kiwi()
    return _kiwi

_RRF_K = 60           # RRF 상수 (낮을수록 상위 랭크 강조)
_DENSE_CANDIDATES = 200  # Dense 1차 후보 수 — BM25 후보 풀로 사용

_DOMAIN_MAP_PATH = Path(__file__).parent.parent.parent / "configs/rag/domain_map.yaml"
_domain_lookup: dict[str, str] | None = None


def _get_domain_lookup() -> dict[str, str]:
    global _domain_lookup
    if _domain_lookup is None:
        cfg = OmegaConf.load(_DOMAIN_MAP_PATH)
        aliases = OmegaConf.to_container(cfg.domain_aliases, resolve=True)
        lookup = {}
        for canonical, alias_list in aliases.items():
            lookup[canonical.lower()] = canonical
            for alias in alias_list:
                lookup[alias.strip().lower()] = canonical
        _domain_lookup = lookup
    return _domain_lookup


def normalize_domain(value: str) -> str | None:
    """alias/동의어를 canonical domain 이름으로 변환. 매핑 없으면 None 반환."""
    return _get_domain_lookup().get(value.strip().lower())


@dataclass
class SearchResult:
    doc_id: str
    slide_no: int
    text: str
    score: float      # RRF 병합 점수
    payload: dict = field(default_factory=dict)


def korean_tokenize(text: str) -> list[str]:
    return [t.form for t in _get_kiwi().tokenize(text) if t.tag in _KEEP_TAGS]


def _rrf_merge(
    dense: list,
    bm25: list,
    top_k: int,
    dense_weight: float,
) -> list[SearchResult]:
    """Reciprocal Rank Fusion: 두 랭킹 리스트를 dense_weight 가중치로 병합."""
    bm25_weight = 1.0 - dense_weight
    scores: dict[str, float] = {}
    points: dict[str, object] = {}

    for rank, pt in enumerate(dense):
        pid = str(pt.id)
        scores[pid] = scores.get(pid, 0.0) + dense_weight / (_RRF_K + rank + 1)
        points[pid] = pt

    for rank, pt in enumerate(bm25):
        pid = str(pt.id)
        scores[pid] = scores.get(pid, 0.0) + bm25_weight / (_RRF_K + rank + 1)
        points[pid] = pt

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    results = []
    for pid, rrf_score in ranked[:top_k]:
        pt = points[pid]
        results.append(SearchResult(
            doc_id=pt.payload.get("doc_id", ""),
            slide_no=pt.payload.get("slide_no", 0),
            text=pt.payload.get("text", ""),
            score=rrf_score,
            payload=pt.payload,
        ))
    return results


class Retriever:
    def __init__(self, embedder: Embedder, vectorstore: VectorStore, cfg: DictConfig):
        self.embedder = embedder
        self.vs = vectorstore
        self.top_k = cfg.rag.top_k
        self.methodology_top_k = cfg.rag.methodology_top_k
        self.hybrid_alpha = cfg.rag.hybrid_alpha
        self.min_score = cfg.rag.min_score_threshold

    def search(
        self,
        query: str,
        collection: str,
        top_k: int | None = None,
        filter_dict: dict | None = None,
    ) -> list[SearchResult]:
        """Dense(Qdrant) + BM25(kiwipiepy) Hybrid 검색 후 RRF 병합."""
        if top_k is None:
            top_k = self.top_k

        # 1단계: 쿼리 임베딩
        query_vec = self.embedder.encode_single(query)

        # 2단계: Dense 검색 — 의미 유사도 기반 200개 후보 확보
        dense_pts = self.vs.search(
            collection=collection,
            vector=query_vec,
            limit=_DENSE_CANDIDATES,
            filter_dict=filter_dict,
        )

        if not dense_pts:
            return []

        # 최소 품질 가드: 완전히 무관한 후보만 조기 제거 (낮은 임계값 적용)
        # BM25가 Dense 점수 낮은 키워드 매칭 슬라이드를 구제할 수 있으므로
        # 최종 필터는 RRF 이후에 적용
        _DENSE_PREFILTER = 0.35
        dense_pts = [p for p in dense_pts if p.score >= _DENSE_PREFILTER]
        if not dense_pts:
            return []

        # 3단계: BM25 — Dense 후보 내 형태소 기반 키워드 재순위
        # tokenized_text는 인덱싱 시 사전 계산된 값 사용 → kiwipiepy 재실행 없음
        token_corpus = [p.payload.get("tokenized_text") or [] for p in dense_pts]
        query_tokens = korean_tokenize(query)

        bm25_top_n = min(top_k * 2, len(dense_pts))
        if any(token_corpus):
            bm25 = BM25Okapi(token_corpus)
            bm25_scores = bm25.get_scores(query_tokens)
            bm25_ranked_idx = bm25_scores.argsort()[::-1][:bm25_top_n]
            bm25_pts = [dense_pts[i] for i in bm25_ranked_idx]
        else:
            log.warning("BM25 skip: tokenized_text 없는 문서 %d건 — Dense 결과로 대체", len(dense_pts))
            bm25_pts = dense_pts[:bm25_top_n]

        # 4단계: Dense 상위 + BM25 상위 합집합 → RRF 점수 부여 후 반환
        # Dense top-N과 BM25 top-N을 union하여 reranker 후보 풀을 구성.
        # RRF로만 top_k를 자르면 BM25 고순위이지만 Dense 낮은 슬라이드가 탈락하므로
        # 두 랭킹의 상위 후보를 모두 포함시켜 reranker가 최종 판단하게 함.
        dense_top_n = top_k        # Dense 상위 N개
        bm25_top_n2 = top_k        # BM25 상위 N개
        dense_top = dense_pts[:dense_top_n]
        bm25_top = bm25_pts[:bm25_top_n2]

        # 합집합: RRF 점수 계산 후 union 포인트 전체 반환 (상한 없음)
        results = _rrf_merge(dense_top, bm25_top, top_k=top_k * 4, dense_weight=self.hybrid_alpha)

        log.debug("검색 '%s' → %d건 (dense_top=%d, bm25_top=%d, collection=%s)",
                  query[:30], len(results), dense_top_n, bm25_top_n2, collection)
        return results

    def search_proposals(
        self,
        query: str,
        collection: str,
        filter_dict: dict | None = None,
    ) -> list[SearchResult]:
        return self.search(query, collection=collection, top_k=self.top_k, filter_dict=filter_dict)

    def search_methodology(
        self,
        query: str,
        collection: str,
    ) -> list[SearchResult]:
        return self.search(query, collection=collection, top_k=self.methodology_top_k)
