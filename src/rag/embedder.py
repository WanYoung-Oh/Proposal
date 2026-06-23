import logging

import numpy as np
from omegaconf import DictConfig
from sentence_transformers import SentenceTransformer

log = logging.getLogger(__name__)


class Embedder:
    def __init__(self, model_name: str, device: str, batch_size: int = 32):
        log.info("임베딩 모델 로드: %s (device=%s)", model_name, device)
        self.model = SentenceTransformer(model_name, device=device)
        self.batch_size = batch_size

    def encode(self, texts: list[str]) -> list[list[float]]:
        embeddings = self.model.encode(
            texts,
            normalize_embeddings=True,
            batch_size=self.batch_size,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return embeddings.astype("float32").tolist()

    def encode_single(self, text: str) -> list[float]:
        return self.encode([text])[0]


def get_embedder(cfg: DictConfig) -> Embedder:
    return Embedder(
        model_name=cfg.ingestion.embedding_model,
        device=cfg.env.embedding_device,
        batch_size=cfg.env.embedding_batch_size,
    )
