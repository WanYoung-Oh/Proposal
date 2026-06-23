import logging
import socket

from omegaconf import DictConfig, OmegaConf
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

log = logging.getLogger(__name__)


def _tcp_reachable(host: str, port: int, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def get_client(cfg: DictConfig) -> QdrantClient:
    qdrant_path = OmegaConf.select(cfg, "project.vectorstore_path", default=None)
    host = cfg.env.qdrant_host
    port = cfg.env.qdrant_port

    if host not in ("localhost", "127.0.0.1") or _tcp_reachable(host, port):
        try:
            client = QdrantClient(host=host, port=port, timeout=5)
            client.get_collections()
            log.info("Qdrant 원격 연결 성공: %s:%s", host, port)
            return client
        except Exception as e:
            log.warning("Qdrant 원격 연결 실패 (%s) — 로컬 파일 모드로 폴백", e)

    local_path = qdrant_path or "data/vectorstore"
    log.info("Qdrant 로컬 파일 모드: %s", local_path)
    return QdrantClient(path=local_path)


def _build_filter(filter_dict: dict) -> Filter | None:
    conditions = [
        FieldCondition(key=k, match=MatchValue(value=v))
        for k, v in filter_dict.items()
        if v  # 빈 문자열·None 무시
    ]
    return Filter(must=conditions) if conditions else None


class VectorStore:
    def __init__(self, cfg: DictConfig):
        self.client = get_client(cfg)

    def search(
        self,
        collection: str,
        vector: list[float],
        limit: int,
        filter_dict: dict | None = None,
    ) -> list:
        """Dense vector 검색. qdrant-client 1.18.0+ query_points API 사용."""
        qfilter = _build_filter(filter_dict) if filter_dict else None
        result = self.client.query_points(
            collection_name=collection,
            query=vector,
            limit=limit,
            with_payload=True,
            query_filter=qfilter,
        )
        return result.points  # list[ScoredPoint]: .id, .score, .payload
