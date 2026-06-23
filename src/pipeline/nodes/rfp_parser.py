"""parse_rfp 노드 — RFP PDF 파일을 텍스트로 추출."""
import logging
from pathlib import Path

from ..state import GraphState

log = logging.getLogger(__name__)

_MAX_BYTES = 50 * 1024 * 1024  # 50MB


def parse_rfp_node(state: GraphState) -> GraphState:
    """RFP PDF → 텍스트 추출. rfp_file_path 또는 rfp_raw_text 중 하나 필요."""
    if state.get("rfp_raw_text"):
        log.info("rfp_raw_text 이미 존재 — parse_rfp 스킵")
        return {"current_step": 1}

    file_path = state.get("rfp_file_path", "")
    if not file_path:
        raise ValueError("rfp_file_path 또는 rfp_raw_text 중 하나를 입력해야 합니다.")

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"RFP 파일을 찾을 수 없습니다: {path}")

    size = path.stat().st_size
    if size > _MAX_BYTES:
        raise ValueError(f"RFP 파일이 50MB를 초과합니다: {size / 1024 / 1024:.1f}MB")

    suffix = path.suffix.lower()
    if suffix == ".pdf":
        text = _extract_pdf(path)
    else:
        raise ValueError(f"RFP는 PDF만 지원합니다 (입력: {suffix})")

    log.info("RFP 텍스트 추출 완료: %d자 (%s)", len(text), path.name)
    return {
        "rfp_raw_text": text,
        "current_step": 1,
        "metadata": {**(state.get("metadata") or {}), "rfp_file": path.name},
    }


def _extract_pdf(path: Path) -> str:
    """pdfplumber로 텍스트 추출 (이미지 PDF는 pymupdf 폴백)."""
    import pdfplumber

    pages: list[str] = []
    with pdfplumber.open(str(path)) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            pages.append(f"[페이지 {i}]\n{text}")

    full_text = "\n\n".join(pages)
    if len(full_text.strip()) < 200:
        log.warning("pdfplumber 추출 텍스트 부족 (%d자) — pymupdf 폴백", len(full_text))
        full_text = _extract_pdf_pymupdf(path)

    return full_text


def _extract_pdf_pymupdf(path: Path) -> str:
    import fitz

    doc = fitz.open(str(path))
    pages: list[str] = []
    for i, page in enumerate(doc, 1):
        text = page.get_text("text") or ""
        pages.append(f"[페이지 {i}]\n{text}")
    doc.close()
    return "\n\n".join(pages)
