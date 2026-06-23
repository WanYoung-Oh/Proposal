"""Phase 2 RAG 검색 파이프라인 검증 스크립트.

실행: python scripts/verify_phase2.py [env=m5pro|rtx3090]
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import hydra
from omegaconf import DictConfig

from src.rag.embedder import get_embedder
from src.rag.vectorstore import VectorStore
from src.rag.retriever import Retriever, normalize_domain

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s - %(message)s",
)
log = logging.getLogger(__name__)


TEST_QUERIES = [
    ("재해복구 시스템 구축 전략", None),
    ("클라우드 전환 마이그레이션", None),
    ("핵심인력 구성 PM 역량", None),
    ("HW 인프라 통합 운영", {"domain": "인프라"}),       # canonical
    ("시스템 유지보수 운영 관리", {"domain": "ITO"}),     # canonical
    ("보안 취약점 점검 대응", None),
    ("사업수행 일정 관리 WBS", None),
]


def _bar(score: float, width: int = 20) -> str:
    filled = int(score * width)
    return "[" + "█" * filled + "░" * (width - filled) + f"] {score:.4f}"


@hydra.main(config_path="../configs", config_name="config", version_base=None)
def main(cfg: DictConfig) -> None:
    proposals_col = cfg.ingestion.proposals_collection
    methodology_col = cfg.ingestion.methodology_collection

    log.info("임베딩 모델 초기화 중…")
    embedder = get_embedder(cfg)

    log.info("Qdrant 연결 중…")
    vs = VectorStore(cfg)
    retriever = Retriever(embedder, vs, cfg)

    # ── 컬렉션 포인트 수 확인 ──────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  Phase 2 — RAG 검색 파이프라인 검증")
    print("=" * 60)
    for col in [proposals_col, methodology_col]:
        info = vs.client.get_collection(col)
        print(f"  [{col}] 포인트 수: {info.points_count}")
    print()

    # ── 제안서 검색 테스트 ─────────────────────────────────────────────────
    print("━" * 60)
    print("  [1] proposals 검색 테스트")
    print("━" * 60)

    for query, filt in TEST_QUERIES:
        print(f"\n  쿼리: '{query}'", end="")
        if filt:
            print(f"  (필터: {filt})", end="")
        print()

        results = retriever.search(query, collection=proposals_col, filter_dict=filt)
        if not results:
            print("    ⚠️  결과 없음 (min_score_threshold 또는 필터 확인 필요)")
            continue

        for i, r in enumerate(results[:3], 1):
            meta = r.payload
            project = f"{meta.get('year', '?')} {meta.get('agency', '?')}"
            result_mark = "✅" if meta.get("result") == "수주" else "❌"
            print(f"  #{i} {_bar(r.score)}  slide {r.slide_no:03d}  {result_mark} {project}")
            print(f"     {r.text[:80].replace(chr(10), ' ')}")

    # ── 방법론 검색 테스트 ─────────────────────────────────────────────────
    print("\n" + "━" * 60)
    print("  [2] methodology 검색 테스트")
    print("━" * 60)

    method_queries = ["제안전략 수립 방법론", "차별화 전략 핵심이슈"]
    for query in method_queries:
        print(f"\n  쿼리: '{query}'")
        results = retriever.search_methodology(query, collection=methodology_col)
        if not results:
            print("    ⚠️  결과 없음")
            continue
        for i, r in enumerate(results[:3], 1):
            print(f"  #{i} {_bar(r.score)}  {r.doc_id} slide {r.slide_no}")
            print(f"     {r.text[:80].replace(chr(10), ' ')}")

    # ── 메타 필터 검증 ─────────────────────────────────────────────────────
    print("\n" + "━" * 60)
    print("  [3] 메타 필터 검증 — alias → canonical 자동 변환")
    print("━" * 60)
    # alias 입력 → normalize_domain() → canonical → Qdrant 필터
    alias_tests = [
        ("시스템 운영 유지보수", "HW인프라"),    # → 인프라
        ("금융 전자금융 시스템 구축", "금융"),    # → 응용시스템
        ("장비 유지관리 운영", "유지보수"),       # → ITO
        ("ISP 정보화전략", "ISP"),              # → 컨설팅
    ]
    for query, alias in alias_tests:
        canonical = normalize_domain(alias)
        filt = {"domain": canonical} if canonical else None
        print(f"\n  쿼리: '{query}'  alias='{alias}' → canonical={canonical!r}")
        if not canonical:
            print("    ⚠️  alias 매핑 없음 — domain_map.yaml 업데이트 필요")
            continue
        results = retriever.search(query, collection=proposals_col, filter_dict=filt)
        domains = {r.payload.get("domain", "?") for r in results}
        filter_ok = all(r.payload.get("domain") == canonical for r in results)
        status = "✅ 정상" if filter_ok else "⚠️  오작동"
        print(f"  → {len(results)}건  domain={domains}  {status}")

    print("\n" + "=" * 60)
    print("  검증 완료")
    print("=" * 60)


if __name__ == "__main__":
    main()
