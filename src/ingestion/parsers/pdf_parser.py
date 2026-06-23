from pathlib import Path

import pdfplumber

from .base import ParsedDocument, ParsedSlide


def parse_pdf(path: Path, doc_id: str) -> ParsedDocument:
    slides = []
    with pdfplumber.open(str(path)) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            text = text.strip()

            lines = [l.strip() for l in text.splitlines() if l.strip()]
            title = lines[0] if lines else ""
            body = "\n".join(lines[1:]) if len(lines) > 1 else ""

            slides.append(ParsedSlide(
                slide_no=i,
                title=title,
                body=body,
                notes="",
            ))

    return ParsedDocument(
        doc_id=doc_id,
        source_path=str(path),
        file_type="pdf",
        slides=slides,
    )
