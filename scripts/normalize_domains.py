"""meta.json의 domain 값을 4대 canonical 분류로 정규화.

분류 기준:
  - project_type == 'ITO'          → 'ITO'
  - project_type == '컨설팅'        → '컨설팅'
  - project_type 구축/차세대 등 + domain 인프라 계열 → '인프라'
  - project_type 구축/차세대 등 + domain 응용 계열   → '응용시스템'

실행: python scripts/normalize_domains.py [--dry-run]
"""
import argparse
import json
import sys
from pathlib import Path

from omegaconf import OmegaConf

DOMAIN_MAP_PATH = Path(__file__).parent.parent / "configs/rag/domain_map.yaml"
PROJECTS_DIR = Path(__file__).parent.parent / "data/projects"

# project_type → canonical 직접 매핑 (domain 값 무관하게 우선 적용)
TYPE_TO_CANONICAL: dict[str, str] = {
    "ITO": "ITO",
    "컨설팅": "컨설팅",
}

# 구축/차세대 등에서 domain 값으로 인프라 vs 응용시스템 판별
INFRA_DOMAIN_KEYWORDS = {
    "인프라", "dr", "하드웨어", "hw인프라", "데이터센터", "dc",
    "sddc", "클라우드", "장비", "서버", "스토리지", "네트워크",
    "재해복구", "통합구축",
}


def build_lookup(domain_aliases: dict) -> dict[str, str]:
    """alias → canonical 역방향 맵."""
    lookup = {}
    for canonical, aliases in domain_aliases.items():
        lookup[canonical.lower()] = canonical
        for alias in aliases:
            lookup[alias.strip().lower()] = canonical
    return lookup


def classify(meta: dict, lookup: dict[str, str]) -> tuple[str, str]:
    """(canonical_domain, reason) 반환."""
    project_type = meta.get("project_type", "").strip()
    old_domain = meta.get("domain", "").strip()

    # 1. project_type으로 직접 판별 가능한 경우
    if project_type in TYPE_TO_CANONICAL:
        return TYPE_TO_CANONICAL[project_type], f"project_type={project_type!r}"

    # 2. 구축/차세대 계열 → domain 값으로 인프라 vs 응용시스템 판별
    domain_lower = old_domain.lower()
    if any(kw in domain_lower for kw in INFRA_DOMAIN_KEYWORDS):
        return "인프라", f"project_type={project_type!r}, domain={old_domain!r} → 인프라 키워드"

    # 3. domain alias 맵으로 폴백
    canonical = lookup.get(domain_lower)
    if canonical:
        return canonical, f"domain alias: {old_domain!r} → {canonical!r}"

    return "", f"분류 불가 (project_type={project_type!r}, domain={old_domain!r})"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="변경 없이 예상 결과만 출력")
    args = parser.parse_args()

    cfg = OmegaConf.load(DOMAIN_MAP_PATH)
    lookup = build_lookup(OmegaConf.to_container(cfg.domain_aliases, resolve=True))

    changed, same, unknown = [], [], []

    for meta_path in sorted(PROJECTS_DIR.glob("*/meta.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        old = meta.get("domain", "")
        canonical, reason = classify(meta, lookup)

        if not canonical:
            unknown.append((meta_path.parent.name, old, reason))
            continue

        if old == canonical:
            same.append((meta_path.parent.name, canonical))
            continue

        changed.append((meta_path.parent.name, old, canonical, reason))
        if not args.dry_run:
            meta["domain"] = canonical
            meta_path.write_text(
                json.dumps(meta, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    # ── 결과 출력 ─────────────────────────────────────────────────────────
    mode = "[DRY-RUN] " if args.dry_run else ""
    print(f"\n{mode}domain 정규화 결과")
    print("=" * 70)

    if changed:
        print(f"\n변경됨 ({len(changed)}건):")
        for name, old, new, reason in changed:
            print(f"  {name[:55]}")
            print(f"    {old!r:25} → {new!r}  ({reason})")

    if same:
        print(f"\n변경 불필요 ({len(same)}건, 이미 canonical):")
        for name, val in same:
            print(f"  {val:12} {name[:55]}")

    if unknown:
        print(f"\n⚠️  분류 불가 ({len(unknown)}건):")
        for name, old, reason in unknown:
            print(f"  {name[:55]:57} {reason}")

    # 카테고리별 통계
    all_results = (
        [(n, new) for n, _, new, _ in changed]
        + [(n, v) for n, v in same]
    )
    from collections import Counter
    stats = Counter(v for _, v in all_results)
    print(f"\n카테고리별 분포:")
    for cat, cnt in sorted(stats.items(), key=lambda x: -x[1]):
        print(f"  {cat:12} {cnt}건")

    print(f"\n{'✅ 변경 완료' if not args.dry_run else '(dry-run — 파일 수정 없음)'}")
    if not args.dry_run and changed:
        print("  재인덱싱 필요: python src/main.py env=rtx3090 +task=ingest")


if __name__ == "__main__":
    main()
