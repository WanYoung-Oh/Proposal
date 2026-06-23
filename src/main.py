"""Hydra entry point — 공공정보화 RFP 제안전략 수립 시스템."""
import logging
from pathlib import Path

import hydra
from omegaconf import DictConfig, OmegaConf

log = logging.getLogger(__name__)


@hydra.main(version_base=None, config_path="../configs", config_name="config")
def main(cfg: DictConfig) -> None:
    log.info("설정:\n%s", OmegaConf.to_yaml(cfg))

    task_name = OmegaConf.select(cfg, "task.name", default=None)

    if task_name in ("ingest", "ingest_with_render", None):
        if OmegaConf.select(cfg, "task.render_slides", default=False):
            _run_render(cfg)
        if OmegaConf.select(cfg, "task.index_qdrant", default=True):
            _run_ingest(cfg)
        if task_name is None:
            log.info("task 미지정 — 인덱싱만 실행. UI 실행은 'streamlit run src/app/streamlit_app.py'")

    elif task_name == "render_slides":
        _run_render(cfg)

    elif task_name == "pipeline":
        _run_pipeline(cfg)

    else:
        log.error("알 수 없는 task: %s", task_name)


def _run_render(cfg: DictConfig) -> None:
    from slide_sampler.renderer import render_all_projects
    data_dir = Path(cfg.project.data_dir)
    log.info("슬라이드 PNG 렌더링 시작 (data_dir=%s)", data_dir)
    render_all_projects(data_dir)
    log.info("렌더링 완료")


def _run_ingest(cfg: DictConfig) -> None:
    from ingestion.indexer import run_indexing, verify_indexing
    log.info("Qdrant 인덱싱 시작 (host=%s:%s)", cfg.env.qdrant_host, cfg.env.qdrant_port)
    run_indexing(cfg)
    verify_indexing(cfg)


def _run_pipeline(cfg: DictConfig) -> None:
    """파이프라인 연결 확인용 드라이런 — 그래프 컴파일만 수행."""
    from pipeline.graph import build_graph
    app = build_graph(cfg)
    log.info("파이프라인 컴파일 성공: 노드 수=%d", len(app.get_graph().nodes))
    log.info("실제 RFP 처리: 'streamlit run src/app/streamlit_app.py'")


if __name__ == "__main__":
    main()
