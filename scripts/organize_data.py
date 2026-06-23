#!/usr/bin/env python3
"""
공공정보화 제안서 데이터 재정리 스크립트

Phase 1: 파일명 파싱 → data/review.csv 생성 (사람이 검토/수정)
Phase 2: review.csv 기반 → data/projects/ 구조 생성

사용법:
    python scripts/organize_data.py --phase 1             # 검토 파일 생성
    python scripts/organize_data.py --phase 2             # dry-run (실제 복사 없음)
    python scripts/organize_data.py --phase 2 --apply     # 실제 적용
"""

import re
import csv
import json
import shutil
import argparse
import unicodedata
from pathlib import Path
from collections import defaultdict, Counter

BASE_DIR = Path(__file__).parent.parent
RAW_DATA_DIR = BASE_DIR / "data" / "raw_data"
PROJECTS_DIR = BASE_DIR / "data" / "projects"
REVIEW_CSV = BASE_DIR / "data" / "review.csv"


# ─────────────────────────────────────────────────────────────────
# 파싱 규칙 정의
# ─────────────────────────────────────────────────────────────────

YEAR_PATTERNS = [
    r"(20[012]\d)년",               # 2022년  (가장 명확)
    r"(20[012]\d)\d{4}",           # 20080908 형식 → 앞 4자리
    r"(?<!\d)(20[012]\d)(?!\d)",   # 숫자 아닌 문자로 둘러싸인 4자리 연도
    r"(\d{2})년",                   # 16년 → 2016
]

# (파일명 포함 키워드) → (기관명, 기관코드)
# 우선순위: 더 구체적인 키워드를 앞에 배치
AGENCY_MAP = [
    # 건강보험
    ("건강보험경인", "건강보험공단 경인지역본부", "NHIS_GI"),
    ("국민건강보험", "국민건강보험공단",           "NHIS"),
    ("건강보험공단", "국민건강보험공단",           "NHIS"),
    # 우정사업본부 (우체국, 스마트금융 모두 KPIC)
    ("우체국",       "우정사업본부",               "KPIC"),
    ("스마트금융",   "우정사업본부",               "KPIC"),
    # 기타 금융
    ("펀드판매",     "금융위원회",                 "FSC"),
    # 연금/장학
    ("사학연금",     "사학연금공단",               "TP"),
    ("장학재단",     "한국장학재단",               "KOSAF"),
    # 세정/관세
    ("국세청",       "국세청",                     "NTS"),
    ("관세청",       "관세청",                     "CUSTOMS"),
    ("국종망",       "관세청",                     "CUSTOMS"),   # 국종망=관세청 국가관세종합정보망
    # 국가정보자원관리원 (범정부·HW자원·전산장비·정보자원 → NIRS)
    ("정보자원관리원","국가정보자원관리원",         "NIRS"),
    ("범정부",       "국가정보자원관리원",         "NIRS"),
    ("HW자원",       "국가정보자원관리원",         "NIRS"),
    ("전산장비",     "국가정보자원관리원",         "NIRS"),
    # 교육부 (나이스·에듀파인·교육정보 모두 KERIS 코드 사용)
    ("나이스",       "교육부",                     "KERIS"),
    ("에듀파인",     "교육부",                     "KERIS"),
    ("교육정보",     "교육부",                     "KERIS"),
    # 지역자치 → KLID
    ("자치단체",     "한국지역정보개발원",         "KLID"),
    # 재정
    ("국고보조금",   "기획재정부",                 "MOFE"),
    # 외교
    ("여권",         "외교부",                     "MOFA"),
    # 국토
    ("자동차관리",   "국토교통부",                 "MOLIT"),
    # 행정안전부 계열 (NIA는 행안부 산하지만 별도 코드)
    ("행정공공기관", "한국지능정보사회진흥원",     "NIA"),
    ("지능정보",     "한국지능정보사회진흥원",     "NIA"),
    ("클라우드",     "행정안전부",                 "MOIS"),
    ("행정",         "행정안전부",                 "MOIS"),
    ("콤텍",         "행정안전부",                 "MOIS"),
    # 국방 (SDDC·국방통합데이터센터 → DIDC, 일반 국방 → MND)
    ("SDDC",         "국방부",                     "DIDC"),
    ("국방통합",     "국방부",                     "DIDC"),
    ("국방",         "국방부",                     "MND"),
    # 기타
    ("체육진흥",     "국민체육진흥공단",           "KSPO"),
    ("교통안전공단", "한국교통안전공단",           "KOTSA"),
    ("석유공사",     "한국석유공사",               "KNOC"),
    ("광주",         "광주광역시",                 "GWANGJU"),
]

DOMAIN_MAP = [
    # 인프라 — 가장 먼저: 명시적 키워드
    ("인프라",    "인프라"),
    ("HW자원",    "인프라"),
    ("정보자원",  "인프라"),
    ("전산장비",  "인프라"),
    ("장비",      "인프라"),   # 자치단체장비, 노후장비 등
    ("노후장비",  "인프라"),
    ("SDDC",      "인프라"),
    # 물적기반 인프라 (교육정보시스템 물적기반 등)
    ("물적기반",  "인프라"),
    # DR
    ("재해복구",  "DR"),
    # 클라우드전환 (project_type과 별도로 domain도 구분)
    # → 클라우드 전환 사업은 실제 domain=인프라로 분류되므로 제거
    # 교육행정
    ("나이스",    "교육행정시스템"),
    ("에듀파인",  "교육행정시스템"),
    ("교육정보",  "교육행정시스템"),
    # 보건/의료
    ("건강보험",  "보건의료시스템"),
    ("민원",      "보건의료시스템"),   # 건강보험공단 민원처리 → 보건의료
    # 금융
    ("스마트금융","스마트금융시스템"),
    ("자산운용",  "자산운용시스템"),
    ("인터넷뱅킹","금융시스템"),
    ("전자금융",  "금융시스템"),
    ("금융",      "금융시스템"),
    ("펀드",      "금융시스템"),
    # 재정/세정
    ("보조금",    "재정시스템"),
    ("엔티스",    "세정시스템"),
    # 여권/외교
    ("여권",      "여권정보시스템"),
    # 장학
    ("장학",      "장학대출시스템"),
    # 스포츠
    ("투표권",    "스포츠토토"),
    # 기타 행정
    ("자동차",    "행정시스템"),
    ("연금",      "연금시스템"),
    ("국방",      "국방IT"),
    ("국종망",    "국방IT"),
    ("컨설팅",    "컨설팅"),
    # 주의: "정보시스템" 키워드는 너무 일반적이어서 제거 (오분류 유발)
    # → IT시스템운영은 review.csv 검토 시 수동 분류
]

PROJECT_TYPE_MAP = [
    # ITO (운영·유지관리) — 가장 먼저
    ("운영 및 유지보수", "ITO"),
    ("운영 유지관리",    "ITO"),
    ("유지 및 보수",     "ITO"),
    ("유지관리",         "ITO"),
    ("유지보수",         "ITO"),
    ("운영",             "ITO"),
    # 클라우드전환
    ("클라우드 전환",    "클라우드전환"),
    ("클라우드전환",     "클라우드전환"),
    # 컨설팅
    ("ISP",              "컨설팅"),
    ("컨설팅",           "컨설팅"),
    # 고도화
    ("고도화",           "고도화"),
    # 구축 — 차세대보다 먼저 (차세대+구축 혼재 시 구축 우선)
    ("통합구축",         "구축"),
    ("구축",             "구축"),
    ("교체",             "구축"),
    ("개발",             "구축"),
    ("확대",             "구축"),
    # 차세대 — 파일명에 차세대 단독으로 있을 때
    ("차세대",           "차세대"),
]

# 사업명 정제 시 제거할 패턴
NOISE_PATTERNS = [
    r"^\[.+?\]\s*",                          # [발표자료], [편집본]
    r"^\d+\s*인쇄본\s*_?\s*",               # 02 인쇄본
    r"[-_\s]*(v\d+[\.\d]*)\s*",             # v0.7, v1.9.7
    r"[-_\s]*(Ver\.?\s*\d+[\.\d]*)\s*",     # Ver.12
    r"\b20[012]\d{5}\b",                    # 20080908 날짜
    r"\b\d{6}\b",                           # 160809
    r"[-_\s]*(최종|완료|인쇄용|인쇄본|발표본|발표용|출력용|수정금지|프리징.*|편집본)"
    r"\s*(디자인완료|완료)?",               # 접미사 노이즈
    r"[-_\s]*(PT|GD|QA|Q&A포함|웹제출|new|simple fact|Add On)\s*",
    r"[-_\s]*\d+차$",                       # 2차, 3차 끝에 오는 것
    r"[★\[\]()]",
    r"[-_\s]+$",
    r"^[-_\s]+",
]


# ─────────────────────────────────────────────────────────────────
# 파싱 함수
# ─────────────────────────────────────────────────────────────────

def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def extract_year(filename: str) -> str:
    filename = nfc(filename)
    for pattern in YEAR_PATTERNS:
        m = re.search(pattern, filename)
        if m:
            y = m.group(1)
            if len(y) == 2:
                return str(2000 + int(y))
            return y[:4]
    return "XXXX"


def extract_agency(filename: str) -> tuple[str, str]:
    filename = nfc(filename)
    for keyword, agency_name, agency_code in AGENCY_MAP:
        if keyword in filename:
            return agency_name, agency_code
    return "미상", "UNKNOWN"


def extract_domain(filename: str) -> str:
    filename = nfc(filename)
    for keyword, domain in DOMAIN_MAP:
        if keyword in filename:
            return domain
    return "기타"


def extract_project_type(filename: str) -> str:
    filename = nfc(filename)
    for keyword, ptype in PROJECT_TYPE_MAP:
        if keyword in filename:
            return ptype
    return "기타"


def clean_project_name(filename: str) -> str:
    name = nfc(re.sub(r"\.[a-zA-Z]+$", "", filename))
    for pattern in NOISE_PATTERNS:
        name = re.sub(pattern, " ", name, flags=re.IGNORECASE)
    name = re.sub(r"[-_\s]+", " ", name).strip()
    return name


def make_project_id(year: str, agency_code: str, project_name: str) -> str:
    slug = re.sub(r"[^가-힣a-zA-Z0-9]", "_", project_name)
    slug = re.sub(r"_+", "_", slug).strip("_")[:28]
    return f"{year}_{agency_code}_{slug}"


# ─────────────────────────────────────────────────────────────────
# Phase 1: review.csv 생성
# ─────────────────────────────────────────────────────────────────

CSV_FIELDS = [
    "original_filename",
    "suggested_project_id",
    "year",
    "agency",
    "agency_code",
    "project_name",
    "domain",
    "project_type",
    "is_duplicate",
    "action",   # keep | merge:<target_project_id> | skip
    "note",
]


def phase1_generate_csv():
    files = sorted(f for f in RAW_DATA_DIR.iterdir() if not f.name.startswith("."))

    rows = []
    for f in files:
        year = extract_year(f.name)
        agency, agency_code = extract_agency(f.name)
        domain = extract_domain(f.name)
        ptype = extract_project_type(f.name)
        project_name = clean_project_name(f.name)
        project_id = make_project_id(year, agency_code, project_name)

        rows.append({
            "original_filename": f.name,
            "suggested_project_id": project_id,
            "year": year,
            "agency": agency,
            "agency_code": agency_code,
            "project_name": project_name,
            "domain": domain,
            "project_type": ptype,
            "is_duplicate": "",
            "action": "keep",
            "note": "",
        })

    # 동일 project_id 중복 탐지
    id_counter = Counter(r["suggested_project_id"] for r in rows)
    for r in rows:
        if id_counter[r["suggested_project_id"]] > 1:
            r["is_duplicate"] = "YES"
            r["action"] = "review"  # 사람이 keep/merge/skip 결정

    REVIEW_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(REVIEW_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    total = len(rows)
    dups = sum(1 for r in rows if r["is_duplicate"] == "YES")
    unknown_year = sum(1 for r in rows if r["year"] == "XXXX")

    print(f"✅  review.csv 생성 완료: {REVIEW_CSV}")
    print(f"    총 파일: {total}개")
    print(f"    중복 의심: {dups}개  ← action='review' 항목 검토 필요")
    print(f"    연도 미상: {unknown_year}개  ← year='XXXX' 항목 직접 입력 필요")
    print()
    print("📝 다음 단계:")
    print("   1. data/review.csv 열어 각 행 검토/수정")
    print("      - action: keep | merge:<target_id> | skip")
    print("      - 연도 미상 항목 year 컬럼 직접 수정")
    print("      - suggested_project_id 필요 시 수정")
    print("   2. python scripts/organize_data.py --phase 2")
    print("   3. 확인 후 --apply 추가하여 실제 적용")


# ─────────────────────────────────────────────────────────────────
# Phase 2: data/projects/ 구조 생성
# ─────────────────────────────────────────────────────────────────

def phase2_create_structure(apply: bool):
    if not REVIEW_CSV.exists():
        print("❌ review.csv 없음. --phase 1 을 먼저 실행하세요.")
        return

    with open(REVIEW_CSV, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    # merge 타겟 수집: merge:<id> 인 파일을 해당 프로젝트에 함께 복사
    merge_map: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        action = r["action"].strip()
        if action.lower().startswith("merge:"):
            target_id = action.split(":", 1)[1].strip()
            merge_map[target_id].append(r["original_filename"])

    ops = []
    for r in rows:
        action = r["action"].strip().lower()
        if action == "skip":
            continue
        if action.startswith("merge:"):
            continue  # 타겟 행에서 처리

        src = RAW_DATA_DIR / r["original_filename"]
        if not src.exists():
            print(f"⚠️  파일 없음: {src.name}")
            continue

        ext = src.suffix
        project_id = r["suggested_project_id"].strip()
        ops.append({
            "src": src,
            "ext": ext,
            "project_id": project_id,
            "meta_row": r,
            "extra_files": merge_map.get(project_id, []),
        })

    mode_label = "🔵 [DRY-RUN]" if not apply else "🟢 [APPLY]"
    print(f"\n{mode_label} {len(ops)}개 프로젝트 디렉토리\n")

    created = 0
    for op in ops:
        dst_dir = PROJECTS_DIR / op["project_id"]
        proposal_name = f"proposal{op['ext']}"
        print(f"  📁 {op['project_id']}/")
        print(f"       proposal{op['ext']}  ←  {op['src'].name}")
        for i, extra_name in enumerate(op["extra_files"], 1):
            extra_ext = Path(extra_name).suffix
            print(f"       extra_{i}{extra_ext}          ←  {extra_name}")
        print(f"       meta.json")

        if apply:
            dst_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(op["src"], dst_dir / proposal_name)

            for i, extra_name in enumerate(op["extra_files"], 1):
                extra_src = RAW_DATA_DIR / extra_name
                extra_ext = Path(extra_name).suffix
                if extra_src.exists():
                    shutil.copy2(extra_src, dst_dir / f"extra_{i}{extra_ext}")

            r = op["meta_row"]
            meta = {
                "project_id":   r["suggested_project_id"].strip(),
                "year":         r["year"],
                "agency":       r["agency"],
                "agency_code":  r["agency_code"],
                "project_name": r["project_name"],
                "domain":       r["domain"],
                "project_type": r["project_type"],
                "result":       "미확인",   # 수주/미수주 직접 입력
                "scale":        "미확인",   # 대형/중형/소형 직접 입력
                "has_rfp":      False,
                "has_proposal": True,
                "files": {
                    "proposal": proposal_name,
                    "rfp":      None,
                    "extras":   [f"extra_{i}{Path(n).suffix}" for i, n in enumerate(op["extra_files"], 1)],
                },
                "note": r.get("note", ""),
            }
            with open(dst_dir / "meta.json", "w", encoding="utf-8") as mf:
                json.dump(meta, mf, ensure_ascii=False, indent=2)
            created += 1

    print()
    if apply:
        print(f"✅ 완료: {created}개 프로젝트 디렉토리 생성 → {PROJECTS_DIR}")
    else:
        print("💡 실제 적용: python scripts/organize_data.py --phase 2 --apply")


# ─────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="공공정보화 제안서 데이터 재정리")
    parser.add_argument("--phase", type=int, required=True, choices=[1, 2],
                        help="1: review.csv 생성  |  2: 디렉토리 구조 생성")
    parser.add_argument("--apply", action="store_true",
                        help="Phase 2: 실제로 파일 복사/생성 (기본: dry-run)")
    args = parser.parse_args()

    if args.phase == 1:
        phase1_generate_csv()
    else:
        phase2_create_structure(apply=args.apply)
