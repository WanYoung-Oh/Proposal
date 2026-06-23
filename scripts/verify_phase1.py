"""Phase 1 결과 검증 스크립트.

실행:
    python scripts/verify_phase1.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import logging
logging.basicConfig(level=logging.WARNING)


def check_parsing() -> None:
    print("\n=== 1. 파서 검증 ===")
    from src.ingestion.parsers.pptx_parser import parse_pptx
    from src.ingestion.parsers.pdf_parser import parse_pdf

    data_dir = Path("data/projects")
    pptx_count = pdf_count = skip = 0

    for proj in sorted(data_dir.iterdir()):
        if not proj.is_dir():
            continue
        pptx = proj / "proposal.pptx"
        pdf = proj / "proposal.pdf"
        if pptx.exists():
            doc = parse_pptx(pptx, proj.name)
            pptx_count += 1
            print(f"  [PPTX] {proj.name}: {doc.total_slides}슬라이드")
        elif pdf.exists():
            doc = parse_pdf(pdf, proj.name)
            pdf_count += 1
            print(f"  [PDF ] {proj.name}: {doc.total_slides}페이지")
        else:
            skip += 1
            print(f"  [SKIP] {proj.name}: proposal 없음")

    print(f"  → PPTX {pptx_count}건, PDF {pdf_count}건, 스킵 {skip}건")


def check_chunking() -> None:
    print("\n=== 2. 청킹 검증 ===")
    from src.ingestion.chunker import load_project_chunks, load_methodology_chunks

    data_dir = Path("data/projects")
    methodology_dir = Path("data/methodology")

    total_chunks = 0
    for proj in sorted(data_dir.iterdir()):
        if not proj.is_dir():
            continue
        chunks = load_project_chunks(proj)
        total_chunks += len(chunks)
        if chunks:
            c = chunks[0]
            print(f"  {proj.name}: {len(chunks)}청크 | 첫청크={len(c['text'])}자 | "
                  f"bm25={len(c['tokenized_text'])}토큰 | result={c['result']}")

    method_chunks = load_methodology_chunks(methodology_dir)
    print(f"\n  방법론 청크: {len(method_chunks)}건")
    print(f"  제안서 총 청크: {total_chunks}건 (예상 ~1,040)")


def check_vectorstore() -> None:
    print("\n=== 3. Qdrant 벡터스토어 검증 ===")
    from qdrant_client import QdrantClient
    import socket

    def _tcp_reachable(host: str, port: int) -> bool:
        try:
            with socket.create_connection((host, port), timeout=3):
                return True
        except OSError:
            return False

    try:
        if _tcp_reachable("localhost", 6333):
            client = QdrantClient(host="localhost", port=6333)
            print("  (서버 모드: localhost:6333)")
        else:
            client = QdrantClient(path="data/vectorstore")
            print("  (파일 모드: data/vectorstore)")

        for col in ["proposals", "methodology"]:
            try:
                info = client.get_collection(col)
                print(f"  컬렉션 '{col}': {info.points_count} 포인트")
            except Exception as e:
                print(f"  컬렉션 '{col}': 오류 — {e}")
    except Exception as e:
        print(f"  Qdrant 연결 오류: {e}")


def check_png_rendering() -> None:
    print("\n=== 4. PNG 렌더링 검증 ===")
    data_dir = Path("data/projects")
    rendered = no_render = no_pptx = 0

    for proj in sorted(data_dir.iterdir()):
        if not proj.is_dir():
            continue
        pptx = proj / "proposal.pptx"
        slides_dir = proj / "slides"
        pngs = list(slides_dir.glob("slide_*.png")) if slides_dir.exists() else []

        if pngs:
            rendered += 1
            total_mb = sum(p.stat().st_size for p in pngs) / 1024 / 1024
            print(f"  ✅ {proj.name}: {len(pngs)}장 ({total_mb:.1f}MB)")
        elif pptx.exists():
            no_render += 1
            print(f"  ⚠️  {proj.name}: PPTX 있으나 PNG 없음 (렌더링 필요)")
        else:
            no_pptx += 1

    print(f"\n  → 렌더링 완료 {rendered}건, 미렌더링 {no_render}건, PPTX없음 {no_pptx}건")


def check_metadata() -> None:
    print("\n=== 5. 메타데이터 검증 ===")
    data_dir = Path("data/projects")
    issues = []

    for proj in sorted(data_dir.iterdir()):
        if not proj.is_dir():
            continue
        meta_path = proj / "meta.json"
        tags_path = proj / "tags.json"

        if not meta_path.exists():
            issues.append(f"meta.json 없음: {proj.name}")
            continue
        if not tags_path.exists():
            issues.append(f"tags.json 없음: {proj.name}")
            continue

        with open(meta_path) as f:
            meta = json.load(f)
        with open(tags_path) as f:
            tags = json.load(f)

        has_summary = bool(tags.get("strategy_summary"))
        has_keywords = bool(tags.get("strategy_keywords"))
        print(f"  {proj.name[:40]:40s} | result={meta.get('result','?'):2s} | "
              f"keywords={'✅' if has_keywords else '❌'} | summary={'✅' if has_summary else '❌'}")

    if issues:
        print("\n  이슈:")
        for i in issues:
            print(f"  ❌ {i}")


if __name__ == "__main__":
    print("=" * 60)
    print("Phase 1 검증")
    print("=" * 60)
    check_metadata()
    check_parsing()
    check_chunking()
    check_vectorstore()
    check_png_rendering()
    print("\n검증 완료")
