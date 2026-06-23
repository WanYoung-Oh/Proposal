# 공공정보화 RFP 제안전략 수립 시스템

공공정보화 사업 RFP(제안요청서)를 입력하면, **제안 PM**과 AI가 제안전략 7단계를 단계별로 협업하여 **최종 전략 문서·제안서 스토리보드**를 생성하는 내부용 AI 서비스입니다.

---

## 주요 기능

- **RFP 자동 분석** — PDF 업로드 시 사업개요·공식 요구사항·평가항목 자동 추출 (STEP 1~3)
- **PM 협업 입력** — 비공식 요구사항(Hidden Needs, Pain Point)·경쟁력 분석을 폼으로 입력하면 LLM이 구조화 (STEP 2b, 4, 6)
- **차별화 전략 생성** — 유사 사례 RAG 참조 → 경쟁구도·핵심이슈 차별화 전략 자동 도출 (STEP 5)
- **사업수행전략 완성** — CSF·수행전략 요약·MECE 4영역 이행방안·제안서 간이 스토리보드 생성 (STEP 7)
- **슬라이드 샘플 검색** — 주제 키워드로 기존 제안서에서 유사 슬라이드 이미지 3장 + LLM 선정 사유 제공

---

## 제안전략 7단계 프로세스

```
[자동] STEP 1  사업개요 추출         ─┐
[자동] STEP 2a 공식 요구사항 추출     ├─▶ [AI] STEP 5 차별화 전략 ──┐
[자동] STEP 3  평가항목 분석          │                              │
[입력] STEP 2b 비공식 요구사항 (PM)  ─┤   [선택] STEP 6 의사결정 ──┤─▶ [AI] STEP 7 수행전략
[입력] STEP 4  경쟁력 분석 (PM)     ─┘                              │
                                                                    ▼
                                                         Markdown 최종 산출물 다운로드
```

| 단계 | 활동 | 담당 |
|------|------|------|
| 1 | 사업개요 | AI 자동 (PM 검토) |
| 2a | 공식 요구사항 | AI 자동 (PM 검토) |
| 2b | 비공식 요구사항 (Hidden Needs, Pain Point) | PM 입력 → AI 구조화 |
| 3 | 평가항목·배점 분석 | AI 자동 (PM 검토) |
| 4 | 경쟁력 분석 | PM 입력 → AI 구조화 |
| 5 | 경쟁우위 차별화 (5-1 경쟁구도 / 5-2 핵심이슈) | AI (RAG 참조) |
| 6 | 주요 의사결정 사항 | PM 입력 (건너뛰기 가능) |
| 7 | 사업수행전략 (CSF·요약·MECE 이행방안·스토리보드) | AI (누적 정보 종합) |

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| 파이프라인 | LangGraph + LangChain |
| LLM (로컬) | Qwen3.5-9B via MLX (Apple Silicon) — 추출·구조화 |
| LLM (클라우드) | Claude (Anthropic) / Solar Pro (Upstage) — 전략 생성 (STEP 5·7) |
| 설정 관리 | Hydra 1.3 + OmegaConf |
| RAG | BAAI/bge-m3 임베딩 + Qdrant 벡터 DB + BM25 + RRF 하이브리드 검색 |
| 세션 영속 | SqliteSaver (`langgraph-checkpoint-sqlite`) |
| UI (MVP) | Streamlit |
| UI (최종) | Next.js + FastAPI |

---

## 구현 현황

| Phase | 내용 | 상태 |
|-------|------|------|
| Phase 1 | 데이터 처리 파이프라인 (파서·청커·인덱서·렌더러) | ✅ 완료 |
| Phase 2 | RAG 검색 파이프라인 | ✅ 완료 |
| Phase 3 | LangGraph 파이프라인 | ✅ 완료 |
| Phase 4 | Streamlit MVP UI | ✅ 완료 |
| Phase 5 | Next.js + FastAPI 최종 UI | 미착수 |
| Phase 6 | 평가 및 최적화 | 미착수 |

**지식베이스:** 공공정보화 제안서 26건 + 제안전략 방법론 3건 — Qdrant 인덱싱 완료 (proposals 1,160 포인트 / methodology 130 포인트)

---

## 하드웨어 구성

| 장비 | 역할 | 사용 시점 |
|------|------|----------|
| Mac Mini M5 Pro (24GB) | UI·LLM·Qdrant·RAG 쿼리 **상시 운영** | 항상 |
| GeForce RTX 3090 (24GB VRAM) | bge-m3 CUDA 임베딩·PNG 렌더링·초기 인덱싱 | 초기 빌드·신규 데이터 추가 시 |

---

## 빠른 시작

### 1. 환경 설정

```bash
# Python 가상환경 생성
python3.11 -m venv .venv
source .venv/bin/activate

# 의존성 설치
pip install -r requirements.txt

# Apple Silicon 전용 (MLX)
pip install mlx-lm>=0.19.0
```

### 2. 환경 변수 설정

```bash
cp .env.template .env
```

`.env` 파일 편집:

```dotenv
ANTHROPIC_API_KEY=sk-ant-...     # Claude 사용 시
UPSTAGE_API_KEY=up_...           # Solar Pro 사용 시
LOCAL_LLM_BASE_URL=http://localhost:11434
QDRANT_HOST=localhost
QDRANT_PORT=6333
SESSIONS_DB_PATH=data/sessions.db
```

### 3. Qdrant 기동

```bash
docker run -d \
  --name qdrant \
  --restart unless-stopped \
  -p 6333:6333 \
  -v $(pwd)/data/qdrant_storage:/qdrant/storage \
  qdrant/qdrant:latest
```

### 4. 로컬 LLM 서버 기동 (Apple Silicon)

```bash
mlx_lm.server \
  --model mlx-community/Qwen3.5-9B-4bit \
  --port 11434 \
  --chat-template-args '{"enable_thinking": false}'
```

> Claude/Solar API만 사용할 경우 이 단계 생략 가능

### 5. 데이터 인덱싱

```bash
python scripts/reindex.py
```

### 6. Streamlit 앱 실행

```bash
export $(grep -v '^#' .env | xargs)
streamlit run src/app/streamlit_app.py --server.port 8501
```

브라우저에서 `http://localhost:8501` 접속

---

## 프로젝트 구조

```
.
├── configs/            # Hydra 설정 (LLM·RAG·파이프라인 파라미터)
├── data/
│   ├── projects/       # 과거 제안서 (meta.json, tags.json, slides/)
│   ├── methodology/    # 제안전략 방법론 PPTX 3종
│   └── qdrant_storage/ # Qdrant 벡터 DB 영속 데이터
├── docs/
│   ├── PRD.md          # 제품 요구사항 정의서
│   ├── PLAN.md         # 기술 구현 계획
│   ├── OPERATION.md    # 운영 가이드
│   └── ref/            # 제안전략 방법론 PDF
├── scripts/
│   ├── reindex.py      # 전체 인덱싱 (임베딩 → Qdrant 업로드)
│   ├── organize_data.py
│   ├── extract_tags.py
│   └── verify_phase*.py
└── src/
    ├── app/            # Streamlit UI
    ├── ingestion/      # 파서·청커·인덱서·슬라이드 분류기
    ├── llm/            # LLM 클라이언트 (Claude·Solar·Qwen3.5·팩토리)
    ├── pipeline/       # LangGraph DAG (state, graph)
    └── rag/            # 임베더·벡터스토어·리트리버
```

---

## LLM 역할 분담

| LangGraph 노드 | 권장 LLM | 역할 |
|----------------|---------|------|
| `extract_step1~3` | Qwen3.5 (로컬) | RFP 사실 추출·JSON 구조화 (temp 0.1) |
| `pm_step2b·4·6` | Qwen3.5 (로컬) | PM 입력 구조화 (temp 0.1~0.2) |
| `generate_step5` | Claude / Solar | 경쟁구도·핵심이슈 차별화 전략 (temp 0.6) |
| `generate_step7` | Claude / Solar | MECE 수행전략·이행방안 (temp 0.65) |
| `slide_explainer` | Qwen3.5 (로컬) | 슬라이드 선정 사유 2~3문장 (temp 0.3) |

> Hydra `configs/config.yaml`에서 기본 LLM을 선택하고, `node_llm`으로 노드별 override 가능

---

## 관련 문서

- [PRD.md](docs/PRD.md) — 제품 요구사항·기능 정의·KPI·릴리스 로드맵
- [PLAN.md](docs/PLAN.md) — 기술 구현 명세·아키텍처·일정
- [OPERATION.md](docs/OPERATION.md) — 운영 가이드·문제 해결
