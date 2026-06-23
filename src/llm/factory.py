"""LLM Factory — Hydra cfg + node_llm 라우팅 → BaseLLM 인스턴스 반환.

노드별 라우팅 우선순위:
  1. pipeline.node_llm.<node_name> 값 (solar | claude | qwen_local)
  2. 없으면 cfg.llm._target_ 기반 기본 LLM
"""
import logging
import os
from pathlib import Path

from omegaconf import DictConfig, OmegaConf

from .base import BaseLLM

log = logging.getLogger(__name__)

_LLM_CACHE: dict[str, BaseLLM] = {}

_CONFIGS_LLM_DIR = Path(__file__).parent.parent.parent / "configs" / "llm"


def _build_llm(llm_type: str, cfg: DictConfig) -> BaseLLM:
    """llm_type 문자열(solar|claude|qwen_local)로 LLM 인스턴스 생성."""
    if llm_type == "solar":
        from .solar import SolarProLLM
        llm_cfg = cfg.llm if cfg.llm._target_.endswith("SolarProLLM") else OmegaConf.load(
            str(_CONFIGS_LLM_DIR / "solar.yaml")
        )
        return SolarProLLM(
            api_key=os.environ.get("SOLAR_API_KEY", ""),
            model=OmegaConf.select(llm_cfg, "model", default="solar-pro"),
            temperature=OmegaConf.select(llm_cfg, "temperature", default=0.3),
            max_tokens=OmegaConf.select(llm_cfg, "max_tokens", default=4096),
        )
    elif llm_type == "claude":
        from .claude import ClaudeLLM
        llm_cfg = cfg.llm if cfg.llm._target_.endswith("ClaudeLLM") else OmegaConf.load(
            str(_CONFIGS_LLM_DIR / "claude.yaml")
        )
        return ClaudeLLM(
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            model=OmegaConf.select(llm_cfg, "model", default="claude-sonnet-4-6"),
            temperature=OmegaConf.select(llm_cfg, "temperature", default=0.3),
            max_tokens=OmegaConf.select(llm_cfg, "max_tokens", default=4096),
        )
    elif llm_type == "qwen_local":
        from .qwen_local import QwenLocalLLM
        llm_cfg = cfg.llm if cfg.llm._target_.endswith("QwenLocalLLM") else OmegaConf.load(
            str(_CONFIGS_LLM_DIR / "qwen_local.yaml")
        )
        base_url = os.environ.get(
            "LOCAL_LLM_BASE_URL",
            OmegaConf.select(llm_cfg, "base_url", default="http://localhost:11434"),
        )
        return QwenLocalLLM(
            base_url=base_url,
            model=OmegaConf.select(llm_cfg, "model", default="mlx-community/Qwen3.5-9B-4bit"),
            temperature=OmegaConf.select(llm_cfg, "temperature", default=0.3),
            max_tokens=OmegaConf.select(llm_cfg, "max_tokens", default=4096),
            context_window=OmegaConf.select(llm_cfg, "context_window", default=32768),
        )
    else:
        raise ValueError(f"알 수 없는 llm_type: {llm_type!r}. solar | claude | qwen_local 중 하나")


def _default_llm_type(cfg: DictConfig) -> str:
    """cfg.llm._target_ 에서 llm 타입 문자열 추출."""
    target: str = cfg.llm._target_
    if "Solar" in target:
        return "solar"
    elif "Claude" in target:
        return "claude"
    elif "Qwen" in target:
        return "qwen_local"
    raise ValueError(f"cfg.llm._target_ 에서 LLM 타입을 식별할 수 없습니다: {target}")


def get_llm(cfg: DictConfig, node_name: str | None = None) -> BaseLLM:
    """노드 이름에 맞는 LLM 인스턴스를 반환 (캐시 적용).

    node_name이 pipeline.node_llm에 등록된 경우 해당 타입 사용,
    아니면 cfg.llm 기본값 사용.
    """
    # node_llm 라우팅 확인
    node_llm_type: str | None = None
    if node_name:
        node_llm_type = OmegaConf.select(
            cfg, f"pipeline.node_llm.{node_name}", default=None
        )

    llm_type = node_llm_type if node_llm_type else _default_llm_type(cfg)

    if llm_type not in _LLM_CACHE:
        log.debug("LLM 초기화: type=%s (node=%s)", llm_type, node_name)
        _LLM_CACHE[llm_type] = _build_llm(llm_type, cfg)

    return _LLM_CACHE[llm_type]


def get_node_temperature(cfg: DictConfig, node_name: str) -> float:
    """pipeline.node_temperature.<node_name> 값 반환 (없으면 cfg.llm.temperature 기본값)."""
    temp = OmegaConf.select(cfg, f"pipeline.node_temperature.{node_name}", default=None)
    if temp is not None:
        return float(temp)
    return float(OmegaConf.select(cfg, "llm.temperature", default=0.3))


def clear_cache() -> None:
    """테스트 시 캐시 초기화용."""
    _LLM_CACHE.clear()
