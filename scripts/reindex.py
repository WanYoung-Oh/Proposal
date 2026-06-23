"""재인덱싱 스크립트 — 기존 컬렉션 삭제 후 전체 재구축.

pptx_parser 제목 파싱 수정, PNG 경로 절대화, tokenized_text 증분 수정 반영.

실행:
    cd /path/to/proposal
    source .venv/bin/activate
    python scripts/reindex.py                  # 전체 (proposals + methodology)
    python scripts/reindex.py --proposals-only
    python scripts/reindex.py --methodology-only
    python scripts/reindex.py --dry-run        # 삭제·업로드 없이 청크 수만 확인
"""
import argparse
import logging
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from omegaconf import OmegaConf
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from sentence_transformers import SentenceTransformer

from ingestion.chunker import load_methodology_chunks, load_project_chunks
from ingestion.indexer import VECTOR_DIM, _embed_chunks, _get_client, _upsert

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def _load_cfg() -> OmegaConf:
    """config.yaml + defaults 서브 설정을 수동 병합."""
    cfg_dir = _ROOT / "configs"
    main = OmegaConf.load(cfg_dir / "config.yaml")

    merged = OmegaConf.create({})
    for item in OmegaConf.to_container(main, resolve=False).get("defaults", []):
        if not isinstance(item, dict):
            continue
        for section, name in item.items():
            if section.startswith("_"):
                continue
            sub_path = cfg_dir / section / f"{name}.yaml"
            if sub_path.exists():
                sub = OmegaConf.load(sub_path)
                merged = OmegaConf.merge(merged, {section: sub})

    # _self_ (project 등 main 본문) 마지막에 병합
    self_keys = {k: v for k, v in OmegaConf.to_container(main, resolve=False).items()
                 if k not in ("defaults", "hydra")}
    return OmegaConf.merge(merged, self_keys)


def _drop_and_recreate(client: QdrantClient, name: str, dry_run: bool) -> None:
    existing = {c.name for c in client.get_collections().collections}
    if name in existing:
        if dry_run:
            log.info("[DRY-RUN] 삭제 예정: %s", name)
        else:
            client.delete_collection(name)
            log.info("컬렉션 삭제: %s", name)
    if dry_run:
        log.info("[DRY-RUN] 생성 예정: %s", name)
    else:
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
        )
        log.info("컬렉션 생성: %s", name)


def reindex_proposals(client, model, cfg, dry_run: bool) -> int:
    col = cfg.ingestion.proposals_collection
    data_dir = Path(cfg.project.data_dir)
    min_chars = cfg.ingestion.min_chunk_chars

    _drop_and_recreate(client, col, dry_run)

    project_dirs = sorted(p for p in data_dir.iterdir() if p.is_dir())
    log.info("제안서 %d건 처리 (컬렉션: %s)", len(project_dirs), col)

    total, skipped = 0, []
    for project_dir in project_dirs:
        chunks = load_project_chunks(project_dir, source="proposals", min_chunk_chars=min_chars)
        if not chunks:
            skipped.append(project_dir.name)
            log.warning("  스킵 (청크 없음): %s", project_dir.name)
            continue
        log.info("  %-45s %3d 청크", project_dir.name, len(chunks))
        if not dry_run:
            vectors = _embed_chunks(chunks, model, cfg.env.embedding_batch_size)
            _upsert(client, col, chunks, vectors)
        total += len(chunks)

    if skipped:
        log.warning("스킵 %d건: %s", len(skipped), ", ".join(skipped))
    log.info("제안서 완료: 총 %d 청크", total)
    return total


def reindex_methodology(client, model, cfg, dry_run: bool) -> int:
    col = cfg.ingestion.methodology_collection
    methodology_dir = Path(cfg.project.methodology_dir)
    min_chars = cfg.ingestion.min_chunk_chars

    _drop_and_recreate(client, col, dry_run)

    chunks = load_methodology_chunks(methodology_dir, min_chunk_chars=min_chars)
    log.info("방법론 %d 청크 처리 (컬렉션: %s)", len(chunks), col)

    if not chunks:
        log.warning("방법론 청크 없음 — %s 경로 확인 필요", methodology_dir)
        return 0

    if not dry_run:
        vectors = _embed_chunks(chunks, model, cfg.env.embedding_batch_size)
        _upsert(client, col, chunks, vectors)

    log.info("방법론 완료: %d 청크", len(chunks))
    return len(chunks)


def print_summary(client: QdrantClient, cfg) -> None:
    print("\n" + "=" * 50)
    print("  재인덱싱 결과")
    print("=" * 50)
    for col in [cfg.ingestion.proposals_collection, cfg.ingestion.methodology_collection]:
        try:
            info = client.get_collection(col)
            print(f"  {col:20s}: {info.points_count:>5d} 포인트")
        except Exception as e:
            print(f"  {col:20s}: 조회 실패 ({e})")
    print("=" * 50)


def main():
    parser = argparse.ArgumentParser(description="Qdrant 재인덱싱")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--proposals-only", action="store_true", help="제안서만 재인덱싱")
    group.add_argument("--methodology-only", action="store_true", help="방법론만 재인덱싱")
    parser.add_argument("--dry-run", action="store_true", help="청크 수 확인만 (변경 없음)")
    args = parser.parse_args()

    cfg = _load_cfg()

    if args.dry_run:
        log.info("=" * 40)
        log.info("DRY-RUN 모드 — 실제 변경 없음")
        log.info("=" * 40)

    client = _get_client(cfg)

    if not args.dry_run:
        log.info("임베딩 모델 로드: %s (device=%s)",
                 cfg.ingestion.embedding_model, cfg.env.embedding_device)
        model = SentenceTransformer(
            cfg.ingestion.embedding_model,
            device=cfg.env.embedding_device,
        )
    else:
        model = None

    t0 = time.time()

    if args.methodology_only:
        reindex_methodology(client, model, cfg, args.dry_run)
    elif args.proposals_only:
        reindex_proposals(client, model, cfg, args.dry_run)
    else:
        reindex_proposals(client, model, cfg, args.dry_run)
        reindex_methodology(client, model, cfg, args.dry_run)

    log.info("총 소요 시간: %.1fs", time.time() - t0)

    if not args.dry_run:
        print_summary(client, cfg)


if __name__ == "__main__":
    main()
