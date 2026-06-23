# 운영 가이드 — 공공정보화 RFP 제안전략 수립 시스템

> 대상 환경: **Mac Mini M5 Pro** (Apple Silicon, macOS)  
> 최초 작성: 2026-06-19 · 최종 수정: 2026-06-22

---

## 목차

1. [사전 요구사항](#1-사전-요구사항)
2. [초기 환경 설정](#2-초기-환경-설정)
3. [서비스 기동](#3-서비스-기동)
4. [초기 데이터 인덱싱](#4-초기-데이터-인덱싱)
5. [Streamlit 앱 실행 및 기능 테스트](#5-streamlit-앱-실행-및-기능-테스트)
6. [신규 제안서·RFP 추가 절차](#6-신규-제안서rfp-추가-절차)
7. [일상 운영](#7-일상-운영)
8. [문제 해결](#8-문제-해결)

---

## 1. 사전 요구사항

### 1-1. 소프트웨어

| 항목 | 버전 | 설치 방법 |
|------|------|----------|
| Python | 3.11 이상 | `brew install python@3.11` |
| Docker Desktop | 최신 | https://www.docker.com/products/docker-desktop/ |
| Git | 최신 | `brew install git` |
| Homebrew | 최신 | https://brew.sh |

### 1-2. API 키 (선택적 — 하나 이상 필요)

| 서비스 | 용도 | 발급처 |
|--------|------|--------|
| Anthropic API | Claude LLM (전략 생성 권장) | https://console.anthropic.com |
| Upstage API | Solar Pro LLM | https://console.upstage.ai |
| Qwen3.5-9B (로컬) | 추출·구조화 LLM (API 키 불필요) | mlx_lm으로 로컬 서빙 |

> **권장 조합**: 추출(STEP 1~3) = Qwen 로컬, 전략 생성(STEP 5·7) = Claude API

### 1-3. 리소스 요구사항

- RAM: 16GB 이상 (Qwen3.5 9B + bge-m3 동시 로드 시 ~12GB)
- 디스크: 20GB 이상 (모델 + 데이터)
- 네트워크: 초기 모델 다운로드 시 필요

---

## 2. 초기 환경 설정

### 2-1. 코드 클론

```bash
git clone <repository-url> proposal
cd proposal
```

### 2-2. Python 가상환경 생성 및 의존성 설치

```bash
python3.11 -m venv .venv
source .venv/bin/activate

# 기본 패키지 설치
pip install -r requirements.txt
```

> **Apple Silicon 전용**: `requirements.txt`의 mlx-lm 주석을 해제하고 설치
> ```bash
> pip install mlx-lm>=0.19.0
> ```

### 2-3. 환경 변수 설정

```bash
cp .env.template .env   # 없으면 아래 내용으로 직접 생성
```

`.env` 파일을 편집합니다:

```dotenv
# ── API 키 ────────────────────────────────────────────────────────
ANTHROPIC_API_KEY=sk-ant-...          # Claude 사용 시
UPSTAGE_API_KEY=up_...                # Solar Pro 사용 시

# ── 로컬 LLM 서버 ─────────────────────────────────────────────────
LOCAL_LLM_BASE_URL=http://localhost:11434

# ── Qdrant 벡터 DB ────────────────────────────────────────────────
QDRANT_HOST=localhost
QDRANT_PORT=6333

# ── 세션 DB ───────────────────────────────────────────────────────
SESSIONS_DB_PATH=data/sessions.db
```

### 2-4. 데이터 디렉토리 확인

```bash
ls data/projects/    # 제안서 디렉토리 목록 확인
ls data/methodology/ # 방법론 PPTX 파일 확인
```

예상 구조:
```
data/
├── projects/
│   ├── 2022_NIA_행정공공기관_.../
│   │   ├── meta.json        # 메타데이터
│   │   ├── tags.json        # AI 추출 태그
│   │   ├── proposal.pptx    # 제안서 파일
│   │   └── slides/          # PNG 슬라이드 이미지
│   │       ├── slide_001.png
│   │       └── ...
│   └── ...
└── methodology/
    ├── 제안전략수립 교재-V2.0(최종본_Add On).pptx
    └── Case Study_Add On(대외비).pptx
```

---

## 3. 서비스 기동

### 3-1. Qdrant 벡터 DB (Docker)

```bash
docker run -d \
  --name qdrant \
  --restart unless-stopped \
  -p 6333:6333 \
  -v $(pwd)/data/qdrant_storage:/qdrant/storage \
  qdrant/qdrant:latest
```

기동 확인:

```bash
curl -s http://localhost:6333/collections | python3 -m json.tool
# {"result":{"collections":[...]},"status":"ok",...} 이 나오면 정상
```

> **재시작 후**: `docker start qdrant`

### 3-2. 로컬 LLM 서버 (Qwen3.5-9B, Apple Silicon 전용)

새 터미널에서 실행:

```bash
source .venv/bin/activate

mlx_lm.server \
  --model mlx-community/Qwen3.5-9B-4bit \
  --port 11434
  --chat-template-args '{"enable_thinking": false}'
```

최초 실행 시 모델 다운로드(약 5~6GB). 이후에는 로컬 캐시 사용.

서버 확인:

```bash
curl -s http://localhost:11434/v1/models | python3 -m json.tool
# models 목록에 Qwen 모델이 보이면 정상
```

> Claude/Solar API만 사용한다면 이 단계 생략 가능.

---

## 4. 초기 데이터 인덱싱

### 4-1. 슬라이드 PNG 렌더링 확인

각 프로젝트에 `slides/` 폴더가 있는지 확인합니다. 없다면 렌더링 스크립트를 실행합니다:

```bash
source .venv/bin/activate

python3 - <<'EOF'
import sys
sys.path.insert(0, "src")
from pathlib import Path
from slide_sampler.renderer import render_pptx_to_png

for proj in sorted(Path("data/projects").iterdir()):
    slides_dir = proj / "slides"
    pptx = proj / "proposal.pptx"
    if pptx.exists() and not slides_dir.exists():
        print(f"렌더링: {proj.name}")
        render_pptx_to_png(pptx, slides_dir)
print("완료")
EOF
```

### 4-2. 전체 인덱싱 실행

```bash
source .venv/bin/activate
python scripts/reindex.py
```

**예상 소요 시간**: 30~60분 (제안서 26건 + 방법론 3종, bge-m3 임베딩 포함)

> **인덱싱 시 각 슬라이드에 자동 부여되는 메타데이터:**
> - `slide_type`: `toc` / `overview` / `detail` / `general` — 검색 시 개요·목차 슬라이드 패널티 기준
> - `section_context`: 개요 슬라이드에서 이후 상세 슬라이드로 전파되는 섹션 제목 (BM25 색인 보강)
> - `hierarchy_labels`: 전략·실행방안 레이블에서 추출한 키워드

진행 상황이 로그로 출력됩니다:
```
09:00:00  INFO     제안서 26건 처리 (컬렉션: proposals)
09:00:05  INFO       2022_NIA_행정공공기관_...  61 청크
...
09:45:00  INFO     방법론 130 청크 처리 (컬렉션: methodology)
09:46:00  INFO     총 소요 시간: 2820.3s

==================================================
  재인덱싱 결과
==================================================
  proposals           : 1160 포인트
  methodology         :  130 포인트
==================================================
```

### 4-3. 인덱싱 결과 확인

```bash
source .venv/bin/activate
python scripts/verify_phase1.py
```

`=== 3. Qdrant 벡터스토어 검증 ===` 섹션에서 포인트 수가 위와 일치하면 정상입니다.

---

## 5. Streamlit 앱 실행 및 기능 테스트

### 5-1. 앱 실행

```bash
source .venv/bin/activate
export $(grep -v '^#' .env | xargs)

streamlit run src/app/streamlit_app.py --server.port 8501

# MacBook에서 Macmini의 Streamlit 앱에 접속하기 위해 사용
streamlit run src/app/streamlit_app.py --server.port 8501 --server.address 192.168.35.6
```

브라우저에서 `http://localhost:8501` 접속.

---

### 5-2. 기능 테스트: 슬라이드 샘플 검색 탭

**먼저 이 탭을 테스트합니다** (LLM 없이 검색만 동작하므로 빠르게 확인 가능).

1. **"🖼️ 슬라이드 샘플 검색"** 탭 클릭
2. 검색 주제 입력: `재해복구 전략`
3. **🔍 검색** 버튼 클릭
4. 슬라이드 이미지 카드 3개가 나타나는지 확인

**확인 항목:**

| 항목 | 정상 | 이상 |
|------|------|------|
| 슬라이드 이미지 | 이미지 표시 | "이미지 없음" → PNG 경로 문제 |
| Rerank 점수 | 0.0 ~ 10.0 범위 | 모두 0 → reranker 오류 |
| 필터 동작 | 도메인/사업유형/수주 여부 필터 적용 | 필터 무시 |
| 슬라이드 유형 | 상세(detail) 슬라이드 위주 반환 | 개요·목차만 반환 → 재인덱싱 후 확인 |

> **슬라이드 필터링 동작**: 개요(overview)·목차(toc)로 분류된 슬라이드는 reranker 점수에 0.3× 패널티가 적용되어 자동으로 하위 순위가 됩니다. 상세 내용을 담은 슬라이드가 우선 반환됩니다.

**추가 검색 주제 예시:**
- `핵심인력 구성 방안`
- `클라우드 전환 아키텍처`
- `보안 3Tier 구성`

---

### 5-3. 기능 테스트: 제안전략 수립 탭 (전체 파이프라인)

#### STEP A — RFP 업로드 및 자동 추출

1. **"📋 제안전략 수립"** 탭 클릭
2. 사이드바에서 LLM 선택:
   - 기본 LLM: `🏠 Qwen3.5 (로컬)` 또는 `☀️ Solar Pro`
   - 전략 생성 LLM: `🤖 Claude` (권장) 또는 `☀️ Solar Pro`
3. RFP PDF 파일 업로드 (테스트용: 나라장터에서 공공 RFP 1건 다운로드)
4. **🚀 자동 분석 시작 (STEP 1~3)** 클릭
5. 각 단계 expander에서 결과 확인:

| 단계 | 확인 내용 |
|------|-----------|
| 📄 RFP 텍스트 추출 | 텍스트 앞부분 500자 표시 |
| 🏢 STEP 1: 사업개요 | JSON 구조 (project_name, domain, budget 등) |
| 📋 STEP 2-1: 공식 요구사항 | 요구사항 목록 JSON |
| ⚖️ STEP 3: 평가항목 | 평가항목 JSON |

> ⚠️ JSON 파싱 실패 시 노란색 경고 배너 표시됨 → LLM 응답 품질 문제, 다른 LLM으로 재시도

#### STEP B — PM 비공식 요구사항 입력

자동 추출 완료 후 `비공식 고객 요구사항 입력` 화면으로 전환됩니다.

1. **Hidden Needs**: 발주처가 명시 못한 요구사항 입력
   ```
   예: 담당자가 클라우드 전환을 원하지만 예산상 명시 불가
   ```
2. **Pain Points**: 발주처 우려 이슈 입력
   ```
   예: 기존 시스템 이전 시 데이터 손실 우려
   ```
3. **핵심 쟁점**: 영업을 통해 파악한 핵심 이슈
4. **✅ 입력 완료 → 경쟁력 분석으로** 클릭

#### STEP C — 경쟁력 분석 입력

1. 과거 유사 실적, 핵심 인력, 기술 솔루션, 협력사 입력
2. 경쟁사 대비 강점/약점 입력
3. **✅ 입력 완료 → 전략 생성 시작** 클릭
4. RAG 검색 및 STEP 5·7 생성 대기 (3~5분)

#### STEP D — STEP 5·7 결과 확인

- **STEP 5**: 경쟁우위 차별화 전략 (경쟁구도 차별화 + 핵심이슈 차별화)
- (선택) **STEP 6**: 의사결정 사항 입력 또는 건너뛰기
- **STEP 7**: 사업수행전략 (CSF + 전략 요약 + 이행방안 + 스토리보드)

#### STEP E — 산출물 다운로드

완료 화면에서 **📥 최종 산출물 다운로드 (Markdown)** 클릭.

---

### 5-4. 품질 판단 기준

| 목표 | 기준 |
|------|------|
| RFP 추출 정확도 (G2) | PM이 수정한 필드 < 30% |
| 전략 초안 채택률 (G3) | 편집 후 실제 사용 ≥ 70% |
| 슬라이드 관련성 | 검색 결과 3장 중 2장 이상 주제 관련 |

---

## 6. 신규 제안서·RFP 추가 절차

새 제안서/RFP를 수집해 RAG를 업데이트하는 전체 흐름입니다.

### 6-1. 파일 준비

```
data/projects/YYYY_기관코드_사업명/
├── proposal.pptx   (또는 proposal.pdf)
└── meta.json
```

**meta.json 형식:**

```json
{
  "project_id": "2024_NIA_차세대행정망구축",
  "year": "2024",
  "agency": "한국지능정보사회진흥원",
  "agency_code": "NIA",
  "project_name": "차세대행정망구축",
  "domain": "인프라",
  "project_type": "구축",
  "result": "수주",
  "scale": "대형",
  "has_rfp": false,
  "has_proposal": true,
  "files": {
    "proposal": "proposal.pptx",
    "rfp": null,
    "extras": []
  },
  "note": ""
}
```

**domain 값 (4종):** `인프라` / `ITO` / `응용시스템` / `컨설팅`  
**project_type 값 (4종):** `구축` / `운영·유지보수` / `컨설팅` / `기타`  
**result 값:** `수주` / `실주`

### 6-2. 도메인 정규화 (필요 시)

meta.json의 domain 값이 alias인 경우 canonical 값으로 정규화합니다:

```bash
source .venv/bin/activate

# 변경될 내용 미리 확인
python scripts/normalize_domains.py --dry-run

# 실제 적용
python scripts/normalize_domains.py
```

### 6-3. 슬라이드 PNG 렌더링

```bash
source .venv/bin/activate

python3 - <<'EOF'
import sys
sys.path.insert(0, "src")
from pathlib import Path
from slide_sampler.renderer import render_pptx_to_png

proj = Path("data/projects/YYYY_기관코드_사업명")  # ← 실제 경로로 변경
slides_dir = proj / "slides"
pptx = proj / "proposal.pptx"

if pptx.exists():
    render_pptx_to_png(pptx, slides_dir)
    print(f"렌더링 완료: {len(list(slides_dir.glob('*.png')))}장")
EOF
```

### 6-4. AI 태그 추출 (선택 — Claude API 필요)

전략 키워드, 차별화 포인트, 요약을 자동 추출해 `tags.json`으로 저장합니다.

```bash
source .venv/bin/activate
export $(grep -v '^#' .env | xargs)

# 특정 프로젝트만
python scripts/extract_tags.py --project YYYY_기관코드_사업명

# 전체 (tags.json 없는 프로젝트만)
python scripts/extract_tags.py
```

> tags.json이 없어도 인덱싱·검색은 동작합니다. 단, 슬라이드 카드의 `strategy_summary`가 비어있게 됩니다.

### 6-5. 재인덱싱

```bash
source .venv/bin/activate

# 제안서만 업데이트 (방법론은 변경 없는 경우)
python scripts/reindex.py --proposals-only

# 방법론도 함께 업데이트
python scripts/reindex.py
```

### 6-6. 결과 확인

```bash
python scripts/verify_phase1.py
```

proposals 포인트 수가 추가된 청크 수만큼 증가했는지 확인합니다.

---

## 7. 일상 운영

### 7-1. 서비스 시작 순서

```bash
# 1. Qdrant 시작 (Docker)
docker start qdrant

# 2. 로컬 LLM 서버 시작 (새 터미널)
source .venv/bin/activate
mlx_lm.server --model mlx-community/Qwen3.5-9B-4bit --port 11434

# 3. Streamlit 앱 시작 (새 터미널)
source .venv/bin/activate
export $(grep -v '^#' .env | xargs)
streamlit run src/app/streamlit_app.py --server.port 8501
```

### 7-2. 서비스 종료

```bash
# Streamlit: Ctrl+C
# mlx_lm: Ctrl+C
# Qdrant: docker stop qdrant
```

### 7-3. 세션 초기화

동일 RFP를 처음부터 다시 분석하려면 Streamlit 사이드바의 **🔄 새 세션 시작** 클릭.  
모든 중간 결과와 체크포인트가 초기화됩니다.

### 7-4. 로그 확인

```bash
# Streamlit 앱 로그는 터미널에 직접 출력됨
# 파일로 저장하려면:
streamlit run src/app/streamlit_app.py --server.port 8501 2>&1 | tee logs/app.log
```

---

## 8. 문제 해결

### Qdrant 연결 실패

```
ConnectionRefusedError / timed out
```

```bash
docker ps | grep qdrant   # 컨테이너 실행 확인
docker start qdrant        # 재시작
curl http://localhost:6333/healthz  # 헬스 체크
```

### 로컬 LLM 응답 없음

```
Connection refused (http://localhost:11434)
```

```bash
# mlx_lm 서버가 실행 중인지 확인
curl http://localhost:11434/v1/models
# 실행 중이 아니면 §3-2 참고해 재기동
```

### JSON 파싱 실패 경고 (노란 배너)

LLM이 JSON 대신 마크다운이나 자연어로 응답한 경우입니다.

1. **다른 LLM으로 전환**: 사이드바에서 Solar Pro 또는 Claude로 변경 후 새 세션 시작
2. **새 세션 재시도**: 같은 LLM으로 재시도 (비결정적 응답이라 두 번째에 성공하기도 함)

### 슬라이드 이미지가 표시되지 않음 ("이미지 없음")

PNG 파일이 없거나 경로가 잘못된 경우입니다.

```bash
# 해당 프로젝트의 slides/ 존재 확인
ls data/projects/YYYY_기관코드_사업명/slides/ | head -3

# 없으면 §6-3 렌더링 후 재인덱싱 (§6-5)
```

### 인덱싱 중 특정 프로젝트 스킵

```
스킵 (청크 없음): 2021_KERIS_...
```

해당 프로젝트의 `proposal.pptx/pdf`가 이미지 기반 PDF이거나 파일이 없는 경우입니다.  
텍스트 추출이 불가능한 파일은 RAG에서 제외됩니다.

### bge-m3 임베딩 모델 다운로드 실패

```bash
# Hugging Face 캐시 경로 확인
python3 -c "from pathlib import Path; print(Path.home() / '.cache/huggingface')"

# 수동 다운로드
source .venv/bin/activate
python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3')"
```

### `data/sessions.db` 초기화

세션 DB가 손상되거나 오래된 경우:

```bash
rm data/sessions.db
# 앱 재시작 시 자동 재생성됨
```

### 슬라이드 검색에서 개요·목차만 반환됨

`slide_type` 메타데이터가 없는 구버전 인덱스입니다.

```bash
# 재인덱싱으로 slide_type, section_context 메타 갱신
source .venv/bin/activate
python scripts/reindex.py --proposals-only
```

재인덱싱 후에도 개요 슬라이드가 상위에 오면 `slide_type` 분류 패턴 문제입니다:

```bash
# 특정 슬라이드의 분류 확인
source .venv/bin/activate
python3 - <<'EOF'
import sys; sys.path.insert(0, "src")
from ingestion.slide_classifier import detect_slide_type
text = "확인할 슬라이드 텍스트"
print(detect_slide_type(text))
EOF
```

### 슬라이드 검색 결과에 특정 상세 슬라이드가 포함되지 않음

해당 슬라이드의 Dense 유사도가 낮고 BM25 점수도 낮은 경우입니다.  
`section_context` 전파가 제대로 됐는지 확인합니다:

```bash
# Qdrant에서 해당 슬라이드 페이로드 확인
source .venv/bin/activate
python3 - <<'EOF'
import sys; sys.path.insert(0, "src")
from rag.vectorstore import VectorStore
import hydra, omegaconf

# Qdrant에서 특정 슬라이드 검색
# vs.client.scroll(collection_name="proposals", scroll_filter=...) 활용
EOF
```
