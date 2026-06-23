import logging
import uuid
from pathlib import Path

from omegaconf import DictConfig, OmegaConf
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    VectorParams,
)
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from .chunker import load_methodology_chunks, load_project_chunks

log = logging.getLogger(__name__)

VECTOR_DIM = 1024  # bge-m3 output dimension


def _get_client(cfg: DictConfig) -> QdrantClient:
    qdrant_path = OmegaConf.select(cfg, "project.vectorstore_path", default=None)
    host = cfg.env.qdrant_host
    port = cfg.env.qdrant_port

    # 원격 Qdrant에 먼저 연결 시도; 실패하면 로컬 파일 모드로 폴백
    if host not in ("localhost", "127.0.0.1") or _tcp_reachable(host, port):
        try:
            client = QdrantClient(host=host, port=port, timeout=5)
            client.get_collections()  # 연결 확인
            log.info("Qdrant 원격 연결 성공: %s:%s", host, port)
            return client
        except Exception as e:
            log.warning("Qdrant 원격 연결 실패 (%s) — 로컬 파일 모드로 폴백", e)

    local_path = qdrant_path or "data/vectorstore"
    log.info("Qdrant 로컬 파일 모드: %s", local_path)
    return QdrantClient(path=local_path)


def _tcp_reachable(host: str, port: int, timeout: float = 3.0) -> bool:
    import socket
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _ensure_collection(client: QdrantClient, name: str) -> None:
    existing = {c.name for c in client.get_collections().collections}
    if name not in existing:
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
        )
        log.info("컬렉션 생성: %s", name)
    else:
        log.info("컬렉션 이미 존재: %s", name)


def _embed_chunks(
    chunks: list[dict],
    model: SentenceTransformer,
    batch_size: int,
) -> list[list[float]]:
    texts = [c["text"] for c in chunks]
    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        batch_size=batch_size,
        convert_to_numpy=True,
        show_progress_bar=True,
    )
    return embeddings.astype("float32").tolist()


def _make_point_id(chunk: dict) -> str:
    # 결정론적 UUID — 동일 청크 재인덱싱 시 기존 포인트 업데이트(중복 방지)
    key = f"{chunk['source']}:{chunk['doc_id']}:{chunk['slide_no']}"
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, key))


def _upsert(client: QdrantClient, collection: str, chunks: list[dict], vectors: list) -> None:
    points = []
    for chunk, vec in zip(chunks, vectors):
        payload = dict(chunk)
        points.append(PointStruct(
            id=_make_point_id(chunk),
            vector=vec,
            payload=payload,
        ))

    batch = 128
    for start in range(0, len(points), batch):
        client.upsert(
            collection_name=collection,
            points=points[start:start + batch],
        )
    log.info("  → %d 포인트 업로드 완료 (컬렉션: %s)", len(points), collection)


def run_indexing(cfg: DictConfig) -> None:
    device = cfg.env.embedding_device
    batch_size = cfg.env.embedding_batch_size
    proposals_col = cfg.ingestion.proposals_collection
    methodology_col = cfg.ingestion.methodology_collection
    min_chars = cfg.ingestion.min_chunk_chars

    data_dir = Path(cfg.project.data_dir)
    methodology_dir = Path(cfg.project.methodology_dir)

    log.info("임베딩 모델 로드: %s (device=%s)", cfg.ingestion.embedding_model, device)
    model = SentenceTransformer(cfg.ingestion.embedding_model, device=device)

    client = _get_client(cfg)
    _ensure_collection(client, proposals_col)
    _ensure_collection(client, methodology_col)

    # ── 제안서 인덱싱 ──────────────────────────────────────────────
    project_dirs = sorted(p for p in data_dir.iterdir() if p.is_dir())
    log.info("제안서 %d건 인덱싱 시작", len(project_dirs))

    for project_dir in project_dirs:
        log.info("처리 중: %s", project_dir.name)
        chunks = load_project_chunks(project_dir, source="proposals", min_chunk_chars=min_chars)
        if not chunks:
            log.warning("  스킵 (청크 없음 — 파일 부재 또는 이미지PDF): %s", project_dir.name)
            continue
        log.info("  청크 수: %d", len(chunks))
        vectors = _embed_chunks(chunks, model, batch_size)
        _upsert(client, proposals_col, chunks, vectors)

    # ── 방법론 인덱싱 ──────────────────────────────────────────────
    log.info("방법론 인덱싱 시작: %s", methodology_dir)
    method_chunks = load_methodology_chunks(methodology_dir, min_chunk_chars=min_chars)
    log.info("방법론 청크 수: %d", len(method_chunks))
    if method_chunks:
        method_vectors = _embed_chunks(method_chunks, model, batch_size)
        _upsert(client, methodology_col, method_chunks, method_vectors)

    log.info("인덱싱 완료")


def verify_indexing(cfg: DictConfig) -> None:
    client = _get_client(cfg)
    for col in [cfg.ingestion.proposals_collection, cfg.ingestion.methodology_collection]:
        info = client.get_collection(col)
        log.info("컬렉션 '%s': %d 포인트", col, info.points_count)
