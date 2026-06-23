"""공통 프롬프트 로더 — rfp_analyzer, strategy_generator 공유."""
from pathlib import Path

from omegaconf import OmegaConf

_PROMPTS_DIR = Path(__file__).parent.parent.parent.parent / "configs" / "prompts"


def load_prompt(name: str) -> dict:
    """configs/prompts/<name>.yaml 로드 + 페르소나 치환."""
    path = _PROMPTS_DIR / f"{name}.yaml"
    cfg = OmegaConf.load(str(path))
    persona = OmegaConf.load(str(_PROMPTS_DIR / "expert_persona.yaml")).persona
    return {
        "system": cfg.system.replace("{persona}", persona),
        "user": cfg.user,
    }
