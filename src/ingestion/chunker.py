import json
import re
from pathlib import Path
from typing import Optional

from kiwipiepy import Kiwi

from .parsers.base import ParsedDocument, ParsedSlide
from .slide_classifier import SectionEnricher, detect_slide_type, extract_hierarchy_labels

_kiwi: Optional[Kiwi] = None
_KEEP_TAGS = {"NNG", "NNP", "VV", "VA", "SL"}


def _get_kiwi() -> Kiwi:
    global _kiwi
    if _kiwi is None:
        _kiwi = Kiwi()
    return _kiwi


def tokenize_for_bm25(text: str) -> list[str]:
    return [t.form for t in _get_kiwi().tokenize(text) if t.tag in _KEEP_TAGS]


def _load_json(path: Path) -> dict:
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def build_chunks(
    doc: ParsedDocument,
    meta: dict,
    tags: dict,
    source: str,
    min_chunk_chars: int = 100,
    data_dir: str = "data/projects",
) -> list[dict]:
    """슬라이드 단위 청크 생성. 100자 미만 슬라이드는 전후와 병합."""
    slides = doc.slides
    merged: list[ParsedSlide] = []

    i = 0
    while i < len(slides):
        slide = slides[i]
        if len(slide) < min_chunk_chars and merged:
            prev = merged[-1]
            merged[-1] = ParsedSlide(
                slide_no=prev.slide_no,
                title=prev.title,
                body=prev.body + "\n" + slide.body,
                notes=prev.notes + "\n" + slide.notes,
            )
        else:
            merged.append(slide)
        i += 1

    strategy_keywords = tags.get("strategy_keywords", [])
    evaluation_criteria = tags.get("evaluation_criteria", [])
    differentiators = tags.get("differentiators", [])
    strategy_summary = tags.get("strategy_summary", [])

    png_base = f"{data_dir}/{doc.doc_id}/slides"
    enricher = SectionEnricher(max_propagation=12)

    chunks = []
    for slide in merged:
        text = slide.text
        # 공백 정규화 후 길이 기준 (이미지 PDF 등 줄바꿈만 가득한 청크 제거)
        if len(re.sub(r"\s+", " ", text).strip()) < min_chunk_chars:
            continue

        slide_type = detect_slide_type(text)
        hierarchy_labels = extract_hierarchy_labels(text)

        # 개요·목차 슬라이드 → 섹션 컨텍스트 갱신
        if slide_type in ("overview", "toc"):
            enricher.update(text)
            section_context = ""
        else:
            # 상세·일반 슬라이드 → 이전 개요의 섹션 제목 보강
            section_context = enricher.get_context()

        # 섹션 컨텍스트가 있고 아직 텍스트에 없으면 앞에 붙임
        if section_context and section_context not in text:
            indexed_text = f"{section_context}\n{text}"
        else:
            indexed_text = text

        chunk = {
            "doc_id": doc.doc_id,
            "source": source,
            "slide_no": slide.slide_no,
            "text": indexed_text,
            "section": slide.title or "",
            "year": meta.get("year", ""),
            "agency": meta.get("agency", ""),
            "domain": meta.get("domain", ""),
            "project_type": meta.get("project_type", ""),
            "result": meta.get("result", ""),
            "has_rfp": meta.get("has_rfp", False),
            "png_path": f"{png_base}/slide_{slide.slide_no:03d}.png",
            "strategy_keywords": strategy_keywords,
            "evaluation_criteria": evaluation_criteria,
            "differentiators": differentiators,
            "strategy_summary": strategy_summary,
            "slide_type": slide_type,
            "hierarchy_labels": hierarchy_labels,
            "section_context": section_context,
            "tokenized_text": tokenize_for_bm25(indexed_text),
        }
        chunks.append(chunk)

    return chunks


def load_project_chunks(
    project_dir: Path,
    source: str = "proposals",
    min_chunk_chars: int = 100,
) -> list[dict]:
    doc_id = project_dir.name
    meta = _load_json(project_dir / "meta.json")
    tags = _load_json(project_dir / "tags.json")

    pptx_path = project_dir / "proposal.pptx"
    pdf_path = project_dir / "proposal.pdf"

    from .parsers.pptx_parser import parse_pptx
    from .parsers.pdf_parser import parse_pdf

    if pptx_path.exists():
        doc = parse_pptx(pptx_path, doc_id)
    elif pdf_path.exists():
        doc = parse_pdf(pdf_path, doc_id)
    else:
        return []

    # project_dir.parent를 data_dir로 전달 — 절대경로로 PNG 경로 생성
    data_dir = str(project_dir.parent)
    return build_chunks(doc, meta, tags, source=source, min_chunk_chars=min_chunk_chars, data_dir=data_dir)


def load_methodology_chunks(
    methodology_dir: Path,
    min_chunk_chars: int = 100,
) -> list[dict]:
    chunks = []
    for pptx_path in sorted(methodology_dir.glob("*.pptx")):
        doc_id = pptx_path.stem
        slides_dir = methodology_dir / "slides" / doc_id
        from .parsers.pptx_parser import parse_pptx
        doc = parse_pptx(pptx_path, doc_id)
        for slide in doc.slides:
            text = slide.text
            if not text.strip():
                continue
            if len(text) < min_chunk_chars and chunks:
                prev = chunks[-1]
                prev["text"] += "\n" + text
                prev["tokenized_text"] += tokenize_for_bm25(text)
                continue
            png_path = str(slides_dir / f"slide_{slide.slide_no:03d}.png")
            chunks.append({
                "doc_id": doc_id,
                "source": "methodology",
                "slide_no": slide.slide_no,
                "text": text,
                "section": slide.title or "",
                "year": "",
                "agency": "",
                "domain": "methodology",
                "project_type": "",
                "result": "",
                "has_rfp": False,
                "png_path": png_path,
                "strategy_keywords": [],
                "evaluation_criteria": [],
                "differentiators": [],
                "strategy_summary": [],
                "tokenized_text": tokenize_for_bm25(text),
            })

    return chunks
