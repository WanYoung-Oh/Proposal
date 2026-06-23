"""SlideClassifier — 슬라이드 유형 분류 및 계층 구조 키워드 추출.

공공 제안서의 전형적인 구조:
  개요(overview): "전략 01 / 전략 02 / 전략 03" 나열, "실행방안 XX" 참조
  상세(detail):   "실행방안 05" 단독, 구체적 구현 내용
  목차(toc):      "목차", "INDEX", "agenda" 등
  일반(general):  나머지
"""
import re

# ── 패턴 정의 ──────────────────────────────────────────────────────

# 전략/실행방안 레이블 (개요 감지용)
_HIER_LABEL = re.compile(
    r'(?:전략|추진전략|핵심전략|실행방안|추진과제|이행과제|세부방안|Action\s*Item)'
    r'\s*(?:\d{1,2}|[①-⑩])',
    re.IGNORECASE,
)

# 목차 키워드
_TOC_KW = re.compile(r'(?:목\s*차|INDEX|Table\s+of\s+Contents|Agenda)', re.IGNORECASE)

# 번호 나열 인덱스 페이지: "1 2 3 4 5 6 7 8 9" 형태 9개 이상 (KERIS slide41 유형)
# 8개 이하는 본문 특징 나열일 수 있어 제외; 9개 이상은 명백한 목차 인덱스
_SEQUENTIAL_NUMS = re.compile(r'(?<!\w)[1-9](?:\s+[1-9]){8,}(?!\w)')

# 공공 제안서 표준 순번 항목: "01. 항목명" ~ "09. 항목명" (0-padded 한 자리)
# "12. 데이터 이관" 같은 슬라이드 자체 번호나 "304." 같은 큰 번호는 제외
_NUMBERED_ITEMS = re.compile(r'\b0[1-9]\.\s+[가-힣]')

# 섹션 제목 추출: "03. 사업수행에 적합한 조직구성" 또는 "III. 제목"
_SECTION_TITLE = re.compile(
    r'(?:^|\n)\s*(?:\d{1,2}|[IVX]+)\.?\s+([가-힣][가-힣·\s]{2,25})(?:\n|$)',
    re.MULTILINE,
)

# 레이블 + 키워드 쌍: "전략 03: 사업수행조직 구성" → "사업수행조직 구성"
_LABEL_KEYWORD = re.compile(
    r'(?:전략|추진전략|실행방안|추진과제|Action\s*Item)\s*\d{1,2}'
    r'\s*[:\.\s]\s*([가-힣][가-힣·\s]{2,30})',
    re.IGNORECASE,
)


def detect_slide_type(text: str) -> str:
    """슬라이드 유형 반환: 'toc' | 'overview' | 'detail' | 'general'"""
    if _TOC_KW.search(text):
        return "toc"

    # 번호 나열 인덱스 페이지: "1 2 3 4 5 6" → toc
    if _SEQUENTIAL_NUMS.search(text):
        return "toc"

    # "01. 항목명" 형태가 2개 이상 → 개요 (전략별 상세실행방안 목록 등)
    numbered = _NUMBERED_ITEMS.findall(text)
    if len(numbered) >= 2:
        return "overview"

    matches = _HIER_LABEL.findall(text)
    if len(matches) >= 3:
        return "overview"   # 3개 이상 나열 → 개요 (2개는 섹션헤더+본문 혼재일 수 있음)
    if len(matches) == 1:
        return "detail"     # 1개만 → 해당 슬라이드 자신의 실행방안
    return "general"


def extract_section_title(overview_text: str) -> str:
    """개요 슬라이드 텍스트에서 섹션 제목 추출.

    예) "03. 사업수행에 적합한 조직구성" → "사업수행에 적합한 조직구성"
    """
    m = _SECTION_TITLE.search(overview_text)
    if m:
        return m.group(1).strip()
    return ""


def extract_hierarchy_labels(text: str) -> list[str]:
    """전략·실행방안 레이블에 붙은 키워드 추출.

    예) "전략 03: 사업수행조직 구성" → ["사업수행조직 구성"]
    """
    labels = []
    for m in _LABEL_KEYWORD.finditer(text):
        kw = m.group(1).strip()
        if kw:
            labels.append(kw[:30])
    return labels


class SectionEnricher:
    """개요 슬라이드에서 추출한 섹션 제목을 이후 슬라이드에 전파.

    개요 슬라이드를 만나면 섹션 제목을 갱신하고,
    이후 최대 `max_propagation`장의 상세 슬라이드에 섹션 제목을 보강 텍스트로 제공.
    다음 개요/목차 슬라이드가 나타나면 자동 갱신.
    """

    def __init__(self, max_propagation: int = 12):
        self._context = ""
        self._count = 0
        self._max = max_propagation

    def update(self, overview_text: str) -> None:
        """개요 슬라이드 도달 시 호출 — 섹션 제목 갱신."""
        title = extract_section_title(overview_text)
        if title:
            self._context = title
        self._count = 0

    def get_context(self) -> str:
        """현재 섹션 컨텍스트 반환. max_propagation 초과 시 빈 문자열."""
        if self._count >= self._max:
            return ""
        self._count += 1
        return self._context

    def reset(self) -> None:
        self._context = ""
        self._count = 0
