import logging
from pathlib import Path

import fitz  # pymupdf

log = logging.getLogger(__name__)

_DPI_SCALE = 2.0  # 144dpi (72 × 2)


def render_pdf_to_png(pdf_path: Path, output_dir: Path) -> list[Path]:
    """PDF 페이지별 → PNG (pymupdf, 144dpi)."""
    output_dir.mkdir(parents=True, exist_ok=True)

    pngs = []
    mat = fitz.Matrix(_DPI_SCALE, _DPI_SCALE)

    with fitz.open(str(pdf_path)) as doc:
        for i, page in enumerate(doc, 1):
            pix = page.get_pixmap(matrix=mat)
            target = output_dir / f"slide_{i:03d}.png"
            pix.save(str(target))
            pngs.append(target)

    return pngs


def render_all_projects(data_dir: Path) -> None:
    """data/projects 전체 순회하며 proposal.pdf → slides/*.png 생성 (멱등)."""
    project_dirs = sorted(p for p in data_dir.iterdir() if p.is_dir())
    for project_dir in project_dirs:
        pdf_path = project_dir / "proposal.pdf"
        if not pdf_path.exists():
            log.debug("proposal.pdf 없음, 스킵: %s", project_dir.name)
            continue

        slides_dir = project_dir / "slides"
        existing = list(slides_dir.glob("slide_*.png")) if slides_dir.exists() else []
        if existing:
            log.info("이미 렌더링 완료, 스킵: %s (%d장)", project_dir.name, len(existing))
            continue

        log.info("렌더링 시작: %s", project_dir.name)
        try:
            pngs = render_pdf_to_png(pdf_path, slides_dir)
            log.info("  → %d장 생성", len(pngs))
        except Exception as e:
            log.error("  렌더링 실패 (%s): %s", project_dir.name, e)
