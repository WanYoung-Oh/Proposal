# 공공정보화 RFP 제안전략 수립 시스템 — 구현 계획

> 최종 수정: 2026-06-22 (슬라이드 분류·검색 품질 개선 — slide_classifier.py 신규, 검색 파이프라인 재설계, 1,160청크 재인덱싱)
>
> **관련 문서:** [PRD.md](./PRD.md) — 제품 요구사항·FR·KPI (본 문서는 기술 구현 명세)

### 구현 진행 상태

| Phase | 내용 | 상태 |
|-------|------|------|
| Phase 1 | 데이터 처리 파이프라인 (파서·청커·인덱서·렌더러) | ✅ **완료** (2026-06-18) · 코드 리뷰+버그 수정 (2026-06-19) |
| Phase 2 | RAG 검색 파이프라인 | ✅ **완료** (2026-06-18) · 코드 리뷰+버그 수정 (2026-06-19) |
| Phase 3 | LangGraph 파이프라인 | ✅ **완료** (2026-06-19) · 코드 리뷰+버그 수정 (2026-06-19) |
| Phase 4 | Streamlit MVP UI | ✅ **완료** (2026-06-19) · 코드 리뷰+버그 수정 (2026-06-19) |
| Phase 5 | Next.js + FastAPI 최종 UI | ⏳ 미착수 |
| Phase 6 | 평가 및 최적화 | ⏳ 미착수 |

### 문서 역할

| 문서 | 역할 | 독자 |
|------|------|------|
| **PRD.md** | 무엇을·왜 만드는가 (기능·KPI·범위) | PM·기획·경영 |
| **PLAN.md** | 어떻게 만드는가 (아키텍처·코드·일정) | 개발·AI 엔지니어 |

---

## 1. 프로젝트 개요

공공정보화 사업 RFP를 입력받아 **PM(제안 담당자)과 단계별 상호작용**을 통해 제안전략 수립 7단계 프로세스를 완주하는 LLM 기반 서비스.

- **RFP 자동 분석**: 사업개요·고객 요구사항(공식)·평가항목을 RFP PDF에서 자동 추출
- **PM 입력 보조**: 고객 요구사항(비공식, 인터뷰 기반) 및 경쟁력 분석 항목을 PM이 입력하면 LLM이 구조화·보완
- **차별화 전략 도출**: 경쟁구도 차별화(약점 만회·강점 부각) + 핵심이슈 차별화(고배점·Hidden Needs·Pain Point)를 유사 사례 RAG 참조 하에 자동 생성
- **사업수행전략 완성**: 핵심성공요소 → 수행전략 요약 → 이행방안 → 제안서 간이 스토리보드 순서로 최종 산출물 생성
- **슬라이드 샘플 검색**: 주제 입력 시 기존 제안서에서 유사 슬라이드를 추출·이미지로 제시하고, LLM이 선정 사유 설명

공공정보화 제안서 **26건(현재 확정, 목표 43건)** + 제안전략 방법론 3건을 RAG 지식베이스로 구축하고,
유사 수주 사례를 실시간 참조하면서 PM과 **협업**하여 전략을 완성한다.

---

## 2. 제안전략 수립 7단계 프로세스

> ref: `docs/ref/process.pdf`, `docs/ref/process_detail.pdf`

```
① 고객 요구사항 분석
  1 사업개요 ──────────────────────────────────┐
  2 고객 요구사항 분석 (공식/비공식) ──────────┤──▶ 5 경쟁우위 제안
  3 평가항목 분석 ─────────────────────────────┤     차별화 방향 ──────┐
                                               │                       │
② 경쟁 포지션 분석                             │  6 제안관련 주요       ├──▶ 7 사업수행전략
  4 경쟁력 분석 ──────────────────────────────┘     의사결정 사항 ───┘     정리
                                                                            │
                                                                        제안서 간이 스토리보드
                                                                            │
                                                                        ▼
                                                                    제안 스토리보드
```

### 단계별 상세

| # | 활동 | 담당 | 데이터 소스 | 시스템 역할 | 필수 |
|---|------|------|------------|------------|------|
| 1 | **사업개요** | 제안PM | RFP (자동추출) | 사업명·발주기관·사업범위·주요 경쟁사 현황 자동 구조화 | M |
| 2 | **고객 요구사항 분석 (공식)** | 제안PM | RFP (자동추출) | RFP 제안요청사항 추출 및 차별화 포인트 도출 보조 | M |
| 2 | **고객 요구사항 분석 (비공식)** | 제안PM + 영업대표 | PM 직접 입력 | Hidden Needs·Pain Point·핵심 쟁점사항을 PM 인터뷰 내용 기반으로 LLM이 구조화 | M |
| 3 | **평가항목 분석** | 제안PM | RFP (자동추출) | 배점 분포·특징·**high_score_items**(STEP 5 입력) | M |
| 4 | **경쟁력 분석** | 제안PM | PM 직접 입력 | 과거실적·핵심인력·기술솔루션·협력업체 등 경쟁사 대비 장단점 비교표 생성 | M |
| 5 | **경쟁우위 차별화 방향** | 제안PM | 2+3+4+RAG | 5-1 경쟁구도(약점 만회·강점 부각) + 5-2 핵심이슈(고배점·Hidden·Pain) 차별화 | M |
| 6 | **제안관련 주요 의사결정 사항** | 제안PM + 사업부장/영업대표 | PM 입력 + LLM 보조 | 의사결정 필요 항목 정리 및 권고안 제시 | O |
| 7 | **사업수행전략 도출** | 제안PM | 1~6 종합 | 7-1 CSF / 7-2 요약 / 7-3 MECE 4영역 이행방안 / 7-4 스토리보드 | M |

### PM 상호작용 방식

- **자동 단계** (1·2공식·3): RFP 업로드 후 LLM이 자동 추출 → PM이 검토·수정
- **PM 입력 단계** (2비공식·4·6): **MVP는 폼 입력** → LLM 구조화 (추후 대화형 Q&A 확장 가능)
- **AI 도출 단계** (5·7): 앞 단계 누적 정보 + RAG 유사 사례 참조 → 차별화 전략·수행전략 자동 생성

---

## 3. 핵심 요구사항 (기술 스택)

| 항목 | 내용 |
|------|------|
| 파이프라인 | LangGraph 기반 DAG 관리 |
| LLM (클라우드) | Solar Pro / Claude — **LLM API** (STEP 5·7 권장) |
| LLM (로컬) | Qwen3.5 — **sLLM** via MLX / Ollama (추출·구조화·슬라이드 사유) |
| 설정 관리 | Hydra 1.3 + OmegaConf |
| RAG | BAAI/bge-m3 임베딩 + Qdrant 벡터 DB + Dense(Qdrant) + BM25(앱) + RRF |
| UI (MVP)        | Streamlit |
| UI (최종)       | Next.js + FastAPI |

### 3.1 sLLM vs LLM API — 역할 정의

본 시스템에서 LLM은 **두 계층**으로 구분한다.

| 구분 | 해당 모델 | 별칭 | 특성 |
|------|----------|------|------|
| **sLLM** | Qwen3.5-9B (MLX / Ollama, Mac Mini 로컬) | Small / Local LLM | 빠른 응답, 데이터 외부 유출 없음, 구조화·추출·짧은 설명에 적합 |
| **LLM API** | Solar Pro (Upstage) / Claude (Anthropic) | Cloud LLM | 복잡한 추론·창의적 전략 도출·장문 생성에 적합 |

> Hydra `llm=` 설정은 **기본 LLM**을 지정한다. 노드별로 sLLM·API를 **혼합 사용**할 수 있도록 `configs/pipeline/default.yaml`의 `node_llm`으로 개별 override한다 (§9).

#### 역할 분담 원칙

```
┌─────────────────────────────────────────────────────────────────────────┐
│  sLLM (Qwen3.5 로컬) — "정확·빠름·폐쇄"                                  │
│  ✅ RFP 사실 추출 (STEP 1~3)          temp 0.1                          │
│  ✅ PM 입력 구조화 (STEP 2b·4·6)      temp 0.1~0.2                      │
│  ✅ 슬라이드 선정 사유 (2~3문장)       temp 0.3                          │
│  ⚠️ STEP 5·7 전략 생성 — 가능하나 품질·MECE 논리는 LLM API 권장         │
├─────────────────────────────────────────────────────────────────────────┤
│  LLM API (Solar Pro / Claude) — "추론·창의·전략"                         │
│  ✅ 경쟁구도·핵심이슈 차별화 (STEP 5)  temp 0.6  ← **권장**              │
│  ✅ MECE 사업수행전략·이행방안 (STEP 7) temp 0.65 ← **권장**             │
│  ✅ 복잡·장문 RFP 추출 (STEP 1~3)      temp 0.1  — sLLM 대비 정확도↑ 선택 │
└─────────────────────────────────────────────────────────────────────────┘
```

#### 노드별 LLM 라우팅 (권장 기본값)

| LangGraph 노드 | 권장 LLM | temp | 근거 |
|----------------|---------|------|------|
| `extract_step1` ~ `extract_step3` | **sLLM** | 0.1 | RFP 사실 추출, JSON 구조화 |
| `pm_step2_informal` | **sLLM** | 0.2 | PM 자유 입력 → 필드 구조화 |
| `pm_step4` | **sLLM** | 0.2 | 경쟁력 표 구조화 |
| `pm_step6` | **sLLM** 또는 API | 0.3 | 의사결정 항목·권고안 (복잡 시 API) |
| `generate_step5` | **LLM API** ⭐ | 0.6 | 경쟁구도·핵심이슈 **전략 추론** |
| `generate_step7` | **LLM API** ⭐ | 0.65 | MECE **수행전략·이행방안** |
| `slide_explainer` | **sLLM** | 0.3 | 짧은 선정 사유 |

**운영 권장 조합:**
- **일상 (비용·보안):** `llm=qwen_local` — STEP 5·7만 `node_llm`으로 Claude/Solar override
- **중요 RFP (품질 우선):** `llm=claude` 또는 `llm=solar` — 전 노드 API
- **PM UI:** 사이드바에서 "전략 생성 LLM"과 "추출·보조 LLM" 분리 선택 (Phase 4)

#### 전문가 페르소나 (공통)

STEP 5·7 및 RFP 분석 노드의 system prompt 공통 역할:

> **당신은 20년 이상 공공정보화 사업 제안전략을 수립해 온 제안전략 수립 전문가입니다.**
> RFP·평가항목·경쟁구도·고객 Hidden Needs를 종합하여 **수주 가능한 차별화 전략**과 **MECE한 사업수행전략**을 도출합니다.
> 추측은 `[가정]`으로 표시하고, RFP·PM 입력·RAG 사례에 근거한 내용만 사실로 서술합니다.

---

## 4. 하드웨어 환경 및 역할 분담

> **핵심 원칙:** 일상 운영은 **Mac Mini M5 Pro 단독**으로 수행한다. RTX 3090은 **최초 RAG 빌드·신규 데이터 추가·(미래) 파인튜닝** 등 GPU가 필요한 작업에만 가동한다. 빌드가 끝나면 RTX 3090을 꺼도 서비스는 정상 동작한다.

### 보유 장비 스펙

| 구분 | 장비 | 주요 스펙 | OS | 사용 시점 |
|------|------|-----------|-----|----------|
| **운영 서버** | Mac Mini M5 Pro | 통합 메모리 24GB, Apple Silicon | macOS | **상시** — UI·LLM·Qdrant·RAG 쿼리 |
| **GPU 빌드 서버** | GeForce RTX 3090 | VRAM 24GB (GDDR6X), CUDA | Linux (Ubuntu) | **초기 빌드·재인덱싱·학습 시에만** |

### 운영 vs 초기 빌드

```
┌─ [초기 빌드] RTX 3090 — Week 0~1, 신규 제안서 추가 시 ─────────────────┐
│  ✅ bge-m3 CUDA 배치 임베딩 (3~5× 빠름)                                  │
│  ✅ 슬라이드 PNG 사전 렌더링 (LibreOffice + pymupdf)                     │
│  ✅ (미래) QLoRA Qwen3.5-9B 파인튜닝                                    │
│  📡 벡터 업로드 대상 → Mac Mini Qdrant (QDRANT_HOST=Mac IP)             │
│  📁 data/ 접근 → NAS·동기화·공유 마운트 (projects·methodology)           │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼  인덱싱 1회 완료
┌─ [일상 운영] Mac Mini M5 Pro — 상시 ─────────────────────────────────────┐
│  ✅ LangGraph 파이프라인 + Streamlit / Next.js+FastAPI                  │
│  ✅ Qdrant 벡터 DB (Docker, 유일한 DB)                                   │
│  ✅ LLM: MLX Qwen3.5-9B (1순위) / Solar Pro / Claude                    │
│  ✅ RAG 쿼리: bge-m3(CPU) + BM25 + reranker(CPU)                        │
│  ✅ SqliteSaver 세션 (data/sessions.db)                                  │
└──────────────────────────────────────────────────────────────────────────┘
```

### Mac Mini M5 Pro 24GB 메모리 예산 (동시 구동)

| 구성요소 | 예상 메모리 | 비고 |
|---------|------------|------|
| Qwen3.5-9B (MLX 4-bit) | ~6GB | 운영 LLM |
| Qdrant Docker | ~0.5–2GB | 26건→43건 확장 시 증가 |
| bge-reranker-v2-m3 | ~0.5–1.5GB | `reranker_device: cpu`, batch=1 |
| bge-m3 쿼리 임베딩 | ~0.5–1GB | `embedding_device: cpu` |
| Streamlit + OS | ~2–4GB | |
| **합계** | **~10–15GB** | 24GB 내 여유 확보 |

### Qwen3.5 모델 라인업 (HuggingFace 공식 컬렉션)

> **Qwen3.5는 실재하는 공식 모델 계열입니다.** 전 모델이 멀티모달(Image-Text-to-Text)을 지원합니다.

| 모델 | 파라미터 | 구조 | 비고 |
|------|---------|------|------|
| Qwen3.5-0.8B | 0.9B | Dense | 초경량 |
| Qwen3.5-2B | 2B | Dense | |
| Qwen3.5-4B | 5B | Dense | |
| **Qwen3.5-9B** | 10B | Dense | ✅ **운영(M5 Pro) + 빌드(RTX) 공통 권장** |
| Qwen3.5-28B | 28B | Dense | 메모리 24GB 환경에서 제약 가능성 (사용 비권장) |
| Qwen3.5-35B-A3B | 36B (활성 3B) | **MoE** | 빠른 추론, 메모리는 전체 로드 필요 |
| Qwen3.5-122B-A10B | 125B (활성 10B) | MoE | |
| Qwen3.5-397B-A17B | 403B (활성 17B) | MoE | |

> MoE 모델(35B-A3B 등): 추론 속도는 빠르지만 weights 전체를 메모리에 올려야 하므로
> 24GB 환경에서는 양자화(GPTQ-Int4) 필수.

### 환경별 Qwen3.5 추론 성능 예상

| 환경 | 모델 | 양자화 | 메모리 사용 | 토큰/초 (추정) |
|------|------|--------|------------|--------------|
| M5 Pro 24GB (MLX) | **Qwen3.5-9B** | **4-bit** | **~6GB** | **50~70 tok/s** ← **운영 권장** |
| M5 Pro 24GB (MLX) | Qwen3.5-28B | 4-bit | ~15GB | 20~35 tok/s (메모리 압박, 비권장) |
| RTX 3090 24GB | **Qwen3.5-9B** | **GPTQ-Int4** | **~6GB** | **80~120 tok/s** ← 빌드·테스트용 (선택) |
| RTX 3090 24GB | Qwen3.5-28B | GPTQ-Int4 | ~14GB | 50~80 tok/s (빌드·실험용) |

> **운영은 Mac Mini M5 Pro + Qwen3.5-9B(MLX 4-bit) 단일 구성.** RTX 3090은 임베딩·렌더링·학습 등 GPU 배치 작업 후 전원 OFF 가능.
> 향후 비전 기능 활용 시 슬라이드 이미지 직접 이해 가능 (차트·표 포함).

---

## 5. Ollama vs vLLM 비교 검토

### 비교표

| 항목 | Ollama | vLLM |
|------|--------|------|
| Apple Silicon 지원 | ✅ Metal 백엔드 완전 지원 | ❌ **CUDA 전용, 미지원** |
| CUDA (RTX 3090) 지원 | ✅ CUDA 백엔드 지원 | ✅ 최적화됨 |
| 설치 난이도 | 매우 쉬움 (1 command) | 복잡 (CUDA 드라이버, pip 의존성) |
| 추론 처리량 | 보통 (단일 요청 최적화) | 높음 (PagedAttention, 연속 배치) |
| 스트리밍 지원 | ✅ | ✅ |
| OpenAI 호환 API | ✅ `/v1/chat/completions` | ✅ |
| 운영-빌드 LLM 일치 | MLX(운영) / Ollama(빌드·선택) — OpenAI API로 통일 | ❌ (운영에서 vLLM 사용 불가) |
| 동시 사용자 처리 | 제한적 | 우수 |
| 적합 상황 | 단일 사용자 인터랙티브 | 다중 사용자 고처리량 |

### 결정: **Ollama 채택 (운영 LLM은 MLX 1순위)**

**핵심 이유:** 운영 환경이 Mac Mini M5 Pro(Apple Silicon)이므로 vLLM 자체가 실행 불가.

- vLLM은 CUDA 전용으로 Apple Silicon MPS/Metal 미지원 (공식 문서 명시)
- **운영 LLM:** MLX(mlx-lm) 1순위 — Qwen3.5 즉시 사용, Metal 네이티브
- **Ollama:** Qwen3.5 공식 레지스트리·버전(0.17.1+) 확인 후 전환 검토. 호환 이슈 시 Qwen2.5-7B fallback
- RTX 3090 Ollama(CUDA)는 **빌드·실험·파인튜닝 검증용** (일상 운영 불필요)
- 제안전략 시스템은 1인 인터랙티브 사용 → vLLM의 고처리량 장점 불필요

> **vLLM이 유리한 시나리오:** 다중 사용자 API 서버, RTX 3090 Linux만 상시 가동하는 경우.
> 본 프로젝트는 Mac Mini 단독 운영이므로 해당 없음.

### 로컬 서빙: Ollama vs MLX (M5 Pro 전용 대안)

Qwen3.5는 최신 모델이므로 Ollama 레지스트리 등록까지 시간이 걸릴 수 있습니다.
M5 Pro에는 **MLX (mlx-lm)**가 더 빠른 대안입니다.

| | Ollama | MLX (mlx-lm) |
|--|--------|--------------|
| M5 Pro 지원 | ✅ Metal 백엔드 | ✅ Apple Silicon 네이티브 (더 빠름) |
| RTX 3090 지원 | ✅ CUDA | ❌ Apple Silicon 전용 |
| Qwen3.5 가용성 | 레지스트리 등록 대기 가능 | HuggingFace 직접 로드 가능 |
| OpenAI 호환 API | ✅ | ✅ (`mlx_lm.server`) |
| 설치 | `brew install ollama` | `pip install mlx-lm` |

**전략:**
- **M5 Pro (운영):** MLX 1순위 → Ollama Metal은 Qwen3.5 공식 지원 확인 후 전환
- **RTX 3090 (빌드):** CUDA 임베딩·PNG 렌더링·(미래) QLoRA. LLM Ollama는 선택(실험용)
- 코드는 OpenAI 호환 API(`/v1/chat/completions`)로 추상화 — MLX·Ollama·클라우드 동일 인터페이스

```bash
# M5 Pro — MLX 서버 실행 (운영, OpenAI 호환)
mlx_lm.server --model mlx-community/Qwen3.5-9B-4bit --port 11434

# RTX 3090 — Ollama (빌드·실험용, Qwen3.5 버전 확인 필수)
ollama pull qwen3.5:9b    # 실패 시: ollama -v 0.17.1+ 확인 또는 Qwen2.5 fallback
ollama serve
```

---

## 6. 시스템 아키텍처

```
[PM] ──RFP 업로드──▶ [Streamlit / Next.js UI]
                              │
                              ▼
              ┌───────────────────────────────────────┐
              │         LangGraph 파이프라인            │
              │                                       │
              │  ① STEP 1~3: RFP 자동 분석 (배치)      │
              │    parse_rfp                          │
              │    → extract_business_overview (S1)   │
              │    → extract_formal_requirements (S2) │
              │    → extract_eval_criteria (S3)       │
              │                  ↓                    │
              │  ② PM 입력: STEP 2비공식·4            │
              │    pm_step2_informal / pm_step4        │
              │                  ↓                    │
              │  ③ STEP 5: 경쟁우위 차별화 (RAG+AI)     │
              │    retrieve_rag → generate_step5     │
              │                  ↓                    │
              │  ②' STEP 6: 의사결정 (Optional)        │
              │    pm_step6 — interrupt, skip 가능    │
              │                  ↓                    │
              │  ④ STEP 7: 사업수행전략 도출            │
              └───────────────────────────────────────┘
                              │
                              ▼
              [최종 산출물: Markdown 다운로드 (PDF는 향후 릴리스에서 검토)]

[LLM 추상화 레이어 — Mac Mini 운영]
  Solar Pro API  /  Claude API  /  Qwen3.5 via MLX (Ollama fallback)
  ↑ python src/main.py llm=solar | llm=claude | llm=qwen_local env=m5pro

[RAG 지식베이스 — Mac Mini Qdrant]          [초기 빌드 — RTX 3090, 1회성]
  ┌──────────────┐  ┌──────────────┐         bge-m3 CUDA 배치 임베딩
  │ methodology  │  │  proposals   │         슬라이드 PNG 렌더링
  │  (방법론 3건) │  │  (제안서 26건)│  ──▶   → Mac Qdrant 원격 업로드
  └──────────────┘  └──────────────┘         (QDRANT_HOST=Mac IP)
     Qdrant (Mac Mini Docker, 상시)
```


---

### 시스템 상호작용 다이어그램

#### LangGraph 노드 플로우

```mermaid
flowchart TD
    START([RFP 업로드]) --> parse_rfp

    subgraph AUTO ["① 자동 분석 — STEP 1~3"]
        parse_rfp["parse_rfp
PDF 텍스트 추출"]
        s1["extract_step1
사업개요 구조화
temp=0.1"]
        s2["extract_step2_formal
공식 요구사항 추출
temp=0.1"]
        s3["extract_step3
평가항목 분석
temp=0.1"]
        parse_rfp --> s1 --> s2 --> s3
    end

    subgraph HITL ["② PM 입력 — Human-in-the-Loop"]
        p2["⏸ pm_step2_informal
비공식 요구사항 입력
interrupt_before"]
        p4["⏸ pm_step4
경쟁력 분석 입력
interrupt_before"]
        p2 --> p4
    end

    subgraph AI ["③ AI 도출 — STEP 5~7"]
        rag["retrieve_rag
방법론 + 제안서 병렬 검색
Dense(Qdrant) + BM25 + RRF"]
        s5["generate_step5
경쟁우위 차별화 전략
temp=0.6"]
        p6["⏸ pm_step6
의사결정 사항
Optional · interrupt_before"]
        s7["generate_step7
사업수행전략
temp=0.65"]
        rag --> s5 --> p6 --> s7
    end

    fmt["format_output
최종 산출물 Markdown"]
    END([산출물 다운로드])

    s3 --> p2
    p4 --> rag
    s7 --> fmt --> END

    LLM(["LLM
Solar Pro · Claude · Qwen3.5-9B"])
    DB[("Qdrant
Mac Mini Docker")]
    CP[("SqliteSaver
data/sessions.db")]

    s1 & s2 & s3 -.->|"temp=0.1 추출"| LLM
    s5 -.->|"temp=0.6 창의"| LLM
    s7 -.->|"temp=0.65 창의"| LLM
    rag -.->|"벡터 + BM25 검색"| DB
    parse_rfp & p2 & p4 & p6 -.->|"상태 저장/복구"| CP
```

#### PM-시스템 상호작용 (Sequence)

```mermaid
sequenceDiagram
    actor PM
    participant UI as UI (Streamlit/Next.js)
    participant LG as LangGraph App
    participant CP as SqliteSaver
    participant LLM as LLM
    participant QD as Qdrant

    PM->>UI: RFP PDF 업로드
    UI->>LG: stream(rfp_text, thread_id)
    LG->>CP: 초기 상태 저장

    rect rgb(230, 240, 255)
        Note over LG,LLM: ① 자동 분석 STEP 1~3
        LG->>LLM: extract_step1~3 (temp=0.1)
        LLM-->>LG: 사업개요 · 요구사항 · 평가항목
        LG->>CP: 상태 저장
    end

    LG-->>UI: interrupt — pm_step2_informal
    UI-->>PM: 비공식 요구사항 입력 요청
    PM->>UI: Hidden Needs · Pain Point 입력
    UI->>LG: update_state + Command(resume)
    LG->>CP: 상태 저장

    LG-->>UI: interrupt — pm_step4
    UI-->>PM: 경쟁력 분석 입력 요청
    PM->>UI: 과거실적 · 인력 · 솔루션 입력
    UI->>LG: update_state + Command(resume)
    LG->>CP: 상태 저장

    rect rgb(230, 255, 230)
        Note over LG,QD: ③ 차별화 전략 STEP 5
        LG->>QD: retrieve_rag (방법론+제안서 병렬)
        QD-->>LG: 유사 슬라이드 청크 top-k
        LG->>LLM: generate_step5 (temp=0.6)
        LLM-->>LG: 경쟁구도 · 핵심이슈 차별화
    end

    alt STEP 6 진행 (기본)
        LG-->>UI: interrupt — pm_step6
        UI-->>PM: 의사결정 사항 입력 요청
        PM->>UI: 의사결정 입력
        UI->>LG: update_state(step6_decisions) + Command(resume)
    else STEP 6 건너뛰기
        LG-->>UI: interrupt — pm_step6
        PM->>UI: "건너뛰기" 선택
        UI->>LG: update_state(skip_step6=True) + Command(resume)
    end

    rect rgb(255, 245, 220)
        Note over LG,LLM: ④ 사업수행전략 STEP 7
        LG->>LLM: generate_step7 (temp=0.65)
        LLM-->>LG: CSF · 전략요약 · 이행방안 · 스토리보드
        LG->>CP: 최종 상태 저장
    end

    LG-->>UI: 최종 산출물 Markdown
    UI-->>PM: 다운로드 제공
```

#### 슬라이드 샘플 검색 흐름

```mermaid
sequenceDiagram
    actor PM
    participant UI as UI
    participant SR as SlideSearcher
    participant QD as Qdrant
    participant CL as slide_classifier
    participant RR as bge-reranker-v2-m3
    participant LLM as LLM (temp=0.3)

    PM->>UI: 주제 입력 (예: "재해복구 전략")
    UI->>SR: search_slides(topic, final_k=10)

    SR->>QD: Dense 검색 (200개 후보, prefilter≥0.35)
    QD-->>SR: dense_pts
    Note over SR: BM25 재순위 → Dense top20 ∪ BM25 top20<br/>RRF 점수 부여 → 최대 top_k*4 반환

    SR->>CL: detect_slide_type(slide_text) — 실시간 재분류
    CL-->>SR: slide_type 보정 (general/detail → overview/toc 가능)

    SR->>RR: CrossEncoder.predict(topic, slide_text × 전체 후보)
    RR-->>SR: rerank_score

    Note over SR: overview/toc → rerank_score × 0.3 패널티<br/>정렬 → MIN_SCORE(0.05) 필터 → 중복 제거(max 2/project) → final_k

    loop final_k 슬라이드 각각
        SR->>LLM: 선정 사유 생성 (temp=0.3)
        LLM-->>SR: 2~3문장 사유
    end

    SR-->>UI: SlideResult × final_k (png_path, rerank_score, slide_type, reason)
    UI-->>PM: 슬라이드 이미지 + 순위 + 선정 사유 카드
```

---

## 7. 기술 스택

```
언어            Python 3.11+
파이프라인      LangGraph 0.2+
LLM 클라우드    Solar Pro API (upstage-solar-pro) / Claude API (anthropic)
                  — 사용자 선택, Hydra config 전환
LLM 로컬        Qwen3.5-9B
                  └── Mac Mini M5 Pro (운영): MLX (mlx-lm) 1순위
                      Ollama Metal — Qwen3.5 공식 지원 확인 후 전환
                  └── RTX 3090 (빌드·실험): Ollama CUDA — 선택, 일상 운영 불필요
멀티모달 (향후) Qwen3.5 비전: 슬라이드 이미지 → 차트·표 직접 이해
임베딩          BAAI/bge-m3 (sentence-transformers)
                  ├── 인덱싱(초기 빌드): RTX 3090 CUDA → Mac Qdrant 업로드
                  └── 쿼리(운영):     M5 Pro CPU
벡터 DB         Qdrant (Mac Mini Docker, 상시 운영 — 유일한 DB)
하이브리드 검색  Qdrant Dense + BM25(kiwipiepy, 앱 레벨) + RRF 병합
                  ※ Qdrant sparse vector 미사용 — 26~43건 규모에 적합
설정 관리       Hydra 1.3 + OmegaConf
파일 파싱       python-pptx, pdfplumber, pymupdf
                  RFP 입력: PDF만 (parse_rfp, **50MB 이하**). PPTX는 기존 제안서 코퍼스용
슬라이드 렌더링 LibreOffice headless (PPTX → PDF → PNG, 초기 빌드 시 1회 생성)
슬라이드 랭킹  BAAI/bge-reranker-v2-m3 (CrossEncoder, 운영 시 M5 Pro CPU)
UI (MVP)        Streamlit
UI (최종)       Next.js + FastAPI
패키지 관리     uv (또는 pip + venv)
```

---

## 8. 디렉토리 구조 (목표 상태)

```
Proposal/
├── data/
│   ├── raw_data/                   (선택) 원본 보관 — P0 정리 완료, 운영은 projects/ 사용
│   ├── methodology/                제안전략 방법론 3건 ✅ 업로드 완료
│   ├── review_reviewed.csv         재정리 검토 파일 (scripts/organize_data.py 출력)
│   └── projects/                   26건 생성 완료 (목표 43건)
│       └── {project_id}/
│           ├── rfp.pdf             제안요청서 (별도 수집)
│           ├── proposal.pdf        제안설명회 자료 (원본 pptx/pdf → 모두 PDF로 통일 완료)
│           ├── proposal.pptx       원본 보존 (pptx 출처인 경우)
│           ├── extra_1.pptx        중복 파일 (있을 경우)
│           ├── meta.json           사업 메타데이터
│           ├── tags.json           전략 키워드·평가항목 태그 (P2 라벨링 산출물)
│           └── slides/             슬라이드 PNG 캐시 (인덱싱 시 자동 생성)
│               ├── slide_001.png
│               ├── slide_002.png
│               └── ...
│
├── configs/                        Hydra 설정
│   ├── config.yaml                 기본 설정 (entry point)
│   ├── llm/
│   │   ├── solar.yaml              Solar Pro API 설정
│   │   ├── claude.yaml             Claude API 설정 (Anthropic)
│   │   └── qwen_local.yaml         Qwen3.5 로컬 설정 (OpenAI 호환 API)
│   ├── env/
│   │   ├── m5pro.yaml              Mac Mini M5 Pro — **운영** 환경
│   │   └── rtx3090.yaml            RTX 3090 Linux — **초기 빌드** 환경
│   ├── rag/
│   │   └── default.yaml            RAG 파라미터
│   ├── pipeline/
│   │   └── default.yaml            LangGraph 파이프라인·node_llm·node_temperature
│   ├── prompts/                    노드별 system/user 프롬프트 (§10 명세)
│   │   ├── expert_persona.yaml     공통 전문가 페르소나
│   │   ├── extract_step3.yaml
│   │   ├── generate_step5.yaml
│   │   └── generate_step7.yaml
│   ├── ingestion/
│   │   └── default.yaml            데이터 처리 설정
│   └── task/
│       ├── ingest.yaml             인덱싱만
│       ├── ingest_with_render.yaml 인덱싱 + PNG 렌더링
│       └── render_slides.yaml      PNG 렌더링만
│
├── src/
│   ├── ingestion/                  Phase 1 — 데이터 처리
│   │   ├── parsers/
│   │   │   ├── pptx_parser.py
│   │   │   ├── pdf_parser.py
│   │   │   └── base.py
│   │   ├── slide_classifier.py     슬라이드 유형 분류 (toc/overview/detail/general) + 계층 키워드 추출 + SectionEnricher
│   │   ├── chunker.py
│   │   └── indexer.py              Qdrant 인덱싱
│   │
│   ├── rag/                        Phase 2 — 검색
│   │   ├── embedder.py
│   │   ├── vectorstore.py
│   │   └── retriever.py            Hybrid retrieval
│   │
│   ├── llm/                        LLM 추상화
│   │   ├── base.py                 BaseLLM 인터페이스
│   │   ├── solar.py                Solar Pro API 클라이언트
│   │   ├── claude.py               Claude API 클라이언트 (Anthropic)
│   │   ├── qwen_local.py           Qwen3.5 로컬 클라이언트 (OpenAI 호환 API)
│   │   └── factory.py              Hydra cfg → LLM 인스턴스 생성
│   │
│   ├── pipeline/                   Phase 3 — LangGraph
│   │   ├── state.py                GraphState TypedDict
│   │   ├── nodes/
│   │   │   ├── rfp_parser.py
│   │   │   ├── rfp_analyzer.py
│   │   │   ├── retriever_node.py
│   │   │   ├── strategy_generator.py
│   │   │   └── output_formatter.py
│   │   └── graph.py                LangGraph 그래프 조립
│   │
│   ├── slide_sampler/              슬라이드 샘플 검색 기능
│   │   ├── renderer.py             PPTX → PDF (LibreOffice) → PNG (pymupdf)
│   │   ├── searcher.py             주제 기반 Qdrant 검색 + 슬라이드 매핑
│   │   └── explainer.py            LLM: 슬라이드 선정 사유 생성
│   │
│   ├── app/                        Phase 4 — UI
│   │   └── streamlit_app.py
│   │
│   └── main.py                     Hydra entry point
│
├── scripts/
│   ├── organize_data.py            데이터 재정리 (완료)
│   └── convert_to_pdf.py           proposal.pptx → PDF 일괄 변환 (완료)
│
├── docs/
│   └── PLAN.md                     이 파일
│
├── .env.template                   환경변수 템플릿 (cp .env.template .env 후 값 입력)
└── requirements.txt
```

---

## 9. Hydra 설정 구조

### configs/config.yaml
```yaml
defaults:
  - llm: solar          # solar | claude | qwen_local
  - env: m5pro          # m5pro(운영) | rtx3090(초기빌드)
  - rag: default
  - pipeline: default
  - ingestion: default
  - _self_

project:
  data_dir: data/projects
  methodology_dir: data/methodology
  vectorstore_path: data/vectorstore

hydra:
  run:
    dir: outputs/${now:%Y-%m-%d}/${now:%H-%M-%S}
```

### configs/llm/solar.yaml
```yaml
_target_: src.llm.solar.SolarProLLM
api_key: ${oc.env:SOLAR_API_KEY}
model: solar-pro
temperature: 0.3      # 기본값 — 노드별 override는 configs/pipeline/default.yaml 참고
max_tokens: 4096
```

### configs/llm/claude.yaml
```yaml
_target_: src.llm.claude.ClaudeLLM
api_key: ${oc.env:ANTHROPIC_API_KEY}
model: claude-sonnet-4-6   # claude-opus-4-8 | claude-sonnet-4-6 | claude-haiku-4-5-20251001
temperature: 0.3      # 기본값 — 노드별 override는 configs/pipeline/default.yaml 참고
max_tokens: 4096
```

### configs/llm/qwen_local.yaml
```yaml
_target_: src.llm.qwen_local.QwenLocalLLM
# LOCAL_LLM_BASE_URL 환경변수로 백엔드 전환 (MLX · Ollama 중 하나만 실행, 동시 기동 금지):
#   M5 Pro MLX:     http://localhost:11434  (mlx_lm.server, 기본값)
#   M5 Pro Ollama:  http://localhost:11434  (동일 포트 — Ollama로 전환 시 MLX 서버 중지 후 기동)
#   RTX 3090 원격:  http://192.168.x.x:11434
base_url: ${oc.env:LOCAL_LLM_BASE_URL,http://localhost:11434}
model: mlx-community/Qwen3.5-9B-4bit    # MLX 기준; Ollama 전환 시 qwen3.5:9b
temperature: 0.3      # 기본값 — 노드별 override는 configs/pipeline/default.yaml 참고
max_tokens: 4096
context_window: 32768
```

### configs/pipeline/default.yaml
```yaml
# 노드별 temperature — 역할에 따라 정확성/창의성 분리
node_temperature:
  extract_step1: 0.1
  extract_step2_formal: 0.1
  extract_step3: 0.1
  pm_step2_informal: 0.2
  pm_step4: 0.2
  pm_step6: 0.3
  generate_step5: 0.6       # 경쟁우위 차별화 — LLM API 권장
  generate_step7: 0.65      # MECE 수행전략 — LLM API 권장
  slide_explainer: 0.3

# 노드별 LLM 라우팅 — null이면 configs/config.yaml의 llm 기본값 사용
# 값: solar | claude | qwen_local
node_llm:
  extract_step1: qwen_local
  extract_step2_formal: qwen_local
  extract_step3: qwen_local
  pm_step2_informal: qwen_local
  pm_step4: qwen_local
  pm_step6: qwen_local
  generate_step5: claude        # ⭐ 전략 추론 — LLM API 권장 (solar 가능)
  generate_step7: claude        # ⭐ MECE 이행방안 — LLM API 권장
  slide_explainer: qwen_local
```

### configs/env/m5pro.yaml
```yaml
# Mac Mini M5 Pro — 운영 환경 (상시)
role: production
device: mps                        # Apple Silicon Metal
embedding_device: cpu              # bge-m3 MPS 지원 불안정 — cpu 고정 권장 (안정화 확인 후 mps로 변경 가능)
embedding_batch_size: 16
reranker_device: cpu               # bge-reranker-v2-m3 (운영)
llm_backend: mlx                   # mlx | ollama (Qwen3.5 Ollama 확인 후 전환)
llm_base_url: http://localhost:11434
qdrant_host: localhost             # Qdrant Docker (동일 Mac)
qdrant_port: 6333
```

### configs/env/rtx3090.yaml
```yaml
# RTX 3090 Linux — 초기 빌드·재인덱싱 환경 (GPU 작업 시에만 가동)
role: build
device: cuda
embedding_device: cuda             # bge-m3 CUDA 가속 (M5 Pro CPU 대비 3~5배)
embedding_batch_size: 64
reranker_device: cuda              # 빌드·검증 시에만 (운영 reranker는 M5 Pro)
llm_backend: ollama                # 선택 — LLM 실험·파인튜닝 검증용
llm_base_url: http://localhost:11434
qdrant_host: ${oc.env:QDRANT_HOST}   # Mac Mini IP (빌드 결과 업로드 대상)
qdrant_port: ${oc.env:QDRANT_PORT,6333}
```

### configs/task/ingest_with_render.yaml
```yaml
# @package _global_
# Hydra: python src/main.py env=rtx3090 +task=ingest_with_render
task:
  name: ingest_with_render
  render_slides: true
  index_qdrant: true
```

### 실행 예시
```bash
# ── [운영] Mac Mini M5 Pro — 일상 사용 ──────────────────────────────────
python src/main.py llm=solar env=m5pro
python src/main.py llm=claude env=m5pro
python src/main.py llm=qwen_local env=m5pro

# ── [초기 빌드] RTX 3090 — Mac Qdrant에 업로드 (Mac에서 Qdrant Docker 선행 기동) ──
export QDRANT_HOST=192.168.x.x      # Mac Mini IP
python src/main.py env=rtx3090 +task=ingest_with_render

# PNG 렌더링만 재실행
python src/main.py env=rtx3090 +task=render_slides

# 인덱싱만 (PNG 이미 존재 시)
python src/main.py env=rtx3090 +task=ingest

# ── [운영] RAG 파라미터 오버라이드 ─────────────────────────────────────
python src/main.py llm=solar env=m5pro rag.top_k=10 rag.hybrid_alpha=0.7

# ── [운영] sLLM 기본 + STEP 5·7만 Claude API (권장 조합) ───────────────
python src/main.py llm=qwen_local env=m5pro \
  pipeline.node_llm.generate_step5=claude \
  pipeline.node_llm.generate_step7=claude
```

---

## 10. LangGraph 파이프라인 설계

### GraphState 정의
```python
class GraphState(TypedDict):
    # 입력
    rfp_raw_text: str               # 원본 RFP 텍스트
    current_step: int               # 현재 진행 단계 (1~7)
    pm_messages: list[dict]         # PM과의 대화 이력 (Human-in-the-Loop)

    # STEP 1~3: RFP 자동 추출 결과
    step1_business_overview: dict   # 사업개요 (사업명·발주기관·사업범위·경쟁사)
    step2_formal_requirements: list # 고객 요구사항 (공식, RFP 추출)
    step2_informal_requirements: dict  # 고객 요구사항 (비공식, PM 입력: Hidden Needs·Pain Point)
    step3_eval_criteria: dict       # 평가항목 (eval_items, high_score_items, implications)

    # STEP 4: PM 입력 (경쟁력 분석)
    step4_competitiveness: dict     # 경쟁력 분석 (과거실적·핵심인력·기술솔루션·협력업체·장단점)

    # STEP 5: AI 도출 (경쟁우위 차별화)
    step5_1_competitive_diff: str   # 5-1 경쟁구도 차별화
    step5_2_issue_solution: str     # 5-2 핵심이슈 차별화

    # STEP 6: 의사결정 사항 (선택)
    skip_step6: bool                 # True 시 STEP 6 건너뜀 (PM 선택)
    step6_decisions: list           # 주요 의사결정 필요 항목 + LLM 권고안

    # STEP 7: 사업수행전략 최종 산출물
    step7_1_csf: list               # 핵심성공요소
    step7_2_strategy_summary: str   # 사업수행전략 요약
    step7_3_execution_plan: str     # 사업수행전략 (이행방안)
    step7_4_storyboard: list        # 제안서 간이 스토리보드 (목차별 차별화 포인트)

    # 공통
    rag_methodology_docs: list      # RAG: 방법론 검색 결과
    rag_case_docs: list             # RAG: 유사 사례 검색 결과
    metadata: dict                  # 처리 메타정보 (사용 LLM, 검색 수 등)
```

### 노드별 역할
```
[자동 단계] RFP 업로드 → 순차 실행
parse_rfp               RFP PDF → 텍스트 추출 (pdfplumber/pymupdf, **50MB 이하**)
    ↓
extract_step1           LLM: 사업개요 구조화 (사업명·발주기관·범위·경쟁사 현황)
    ↓
extract_step2_formal    LLM: 공식 요구사항 추출 (RFP 제안요청사항 목록화)
    ↓
extract_step3           LLM: 평가항목 분석 (배점 분포·특징·시사점)
    ↓
[PM 입력 단계] Human-in-the-Loop — MVP: 폼 입력
pm_step2_informal       PM: 비공식 요구사항 입력 (Hidden Needs, Pain Point, 핵심 쟁점)
    ↓
pm_step4                PM: 경쟁력 정보 입력 (과거실적·인력·솔루션·협력사·경쟁사 장단점)
    ↓
[AI 도출 단계] RAG 참조 → 전략 생성
retrieve_rag            방법론 컬렉션 + 제안서 컬렉션 Hybrid 검색  ← 병렬
    ↓
generate_step5          LLM: [5-1] 경쟁구도(약점만회·강점부각) + [5-2] 핵심이슈(고배점·Hidden·Pain)  ← **LLM API 권장**
    ↓
pm_step6                PM: 주요 의사결정 사항 확인 (Optional — interrupt에서 skip 가능)
    ↓
generate_step7          LLM: CSF → 요약 → MECE 4영역 이행방안 → 스토리보드  ← **LLM API 권장**
    ↓                      ※ STEP 7은 STEP 5 RAG 결과 재활용 (MVP). 스토리보드 품질 개선 시
format_output           최종 산출물 Markdown 구조화 + 다운로드 생성   retrieve_rag 추가 검토 (Phase 6)
```

### LangGraph 그래프 구조
```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver  # 영속 체크포인트 (W5)

graph = StateGraph(GraphState)

# 자동 단계
graph.add_node("parse_rfp",            parse_rfp_node)       # PDF → 텍스트
graph.add_node("extract_step1",        extract_step1_node)
graph.add_node("extract_step2_formal", extract_step2_formal_node)
graph.add_node("extract_step3",        extract_step3_node)

# PM 입력 단계 (Human-in-the-Loop: interrupt_before)
graph.add_node("pm_step2_informal",    pm_step2_informal_node)
graph.add_node("pm_step4",             pm_step4_node)
graph.add_node("pm_step6",             pm_step6_node)       # Optional — interrupt에서 skip

# AI 도출 단계
graph.add_node("retrieve_rag",         retrieve_rag_node)
graph.add_node("generate_step5",       generate_step5_node)
graph.add_node("generate_step7",       generate_step7_node)
graph.add_node("format_output",        format_output_node)

# 엣지
graph.set_entry_point("parse_rfp")
graph.add_edge("parse_rfp",            "extract_step1")
graph.add_edge("extract_step1",        "extract_step2_formal")
graph.add_edge("extract_step2_formal", "extract_step3")
graph.add_edge("extract_step3",        "pm_step2_informal")
graph.add_edge("pm_step2_informal",    "pm_step4")
graph.add_edge("pm_step4",             "retrieve_rag")
graph.add_edge("retrieve_rag",         "generate_step5")
graph.add_edge("generate_step5",       "pm_step6")          # STEP 6: 항상 interrupt
graph.add_edge("pm_step6",             "generate_step7")
graph.add_edge("generate_step7",       "format_output")
graph.add_edge("format_output",        END)

# W5: SqliteSaver — 프로세스 재시작 후에도 thread_id로 세션 복구
checkpointer = SqliteSaver.from_conn_string("data/sessions.db")
app = graph.compile(
    checkpointer=checkpointer,
    interrupt_before=["pm_step2_informal", "pm_step4", "pm_step6"],
)
```

**pm_step6_node 동작:** `skip_step6=True`이면 no-op 통과, `False`(기본)이면 LLM 권고안 생성 후 PM 입력과 병합.
```

### PM 입력 주입 및 interrupt 재개 패턴 (W5)

> **버전 노트 (LangGraph 0.2+):** `Command(resume=None)` 패턴 사용.
> 버전에 따라 `Command(resume="")` 또는 `app.stream(None, config=config)`가 필요할 수 있음.
> 실제 설치 버전에서 동작 확인 필수.

```python
import uuid
from langgraph.types import Command

# ── 세션 시작 ──────────────────────────────────────────────────────────────
thread_id = str(uuid.uuid4())   # 세션별 고유 ID (Streamlit: session_state, FastAPI: 쿠키)
config = {"configurable": {"thread_id": thread_id}}

# ── 1. 자동 단계 실행 (STEP 1~3) — pm_step2_informal 직전에 interrupt ──────
for event in app.stream({"rfp_raw_text": rfp_text}, config=config):
    yield event  # 단계별 결과 UI에 스트리밍

# ── 2. PM 비공식 요구사항 입력 후 재개 (STEP 2 비공식) ──────────────────────
pm_input_step2 = {
    "step2_informal_requirements": {
        "hidden_needs": ["...", "..."],
        "pain_points": ["...", "..."],
        "key_issues": ["...", "..."]
    }
}
app.update_state(config, pm_input_step2)
for event in app.stream(Command(resume=None), config=config):
    yield event  # pm_step4 interrupt까지 실행

# ── 3. PM 경쟁력 분석 입력 후 재개 (STEP 4) ─────────────────────────────────
pm_input_step4 = {
    "step4_competitiveness": {
        "past_projects": ["...", "..."],
        "key_personnel": ["...", "..."],
        "tech_solutions": ["...", "..."],
        "partners": ["...", "..."],
        "vs_competitors": {"strengths": [...], "weaknesses": [...]}
    }
}
app.update_state(config, pm_input_step4)
for event in app.stream(Command(resume=None), config=config):
    yield event  # generate_step5 → pm_step6 interrupt까지 실행

# ── 4. STEP 6 — 의사결정 입력 또는 건너뛰기 (pm_step6 interrupt) ─────────────
# PM이 "의사결정 사항 건너뛰기" 선택 시:
app.update_state(config, {"skip_step6": True, "step6_decisions": []})
# PM이 진행 선택 시 (기본):
# app.update_state(config, {
#     "skip_step6": False,
#     "step6_decisions": [{"item": "...", "recommendation": "..."}, ...]
# })
for event in app.stream(Command(resume=None), config=config):
    yield event  # pm_step6 → generate_step7 → format_output → END
```

### 체크포인트 전략 (W5)

| 체크포인터 | 영속성 | 적합 상황 |
|-----------|--------|----------|
| `MemorySaver` | 인메모리 — 프로세스 재시작 시 소실 | 개발·테스트 전용 |
| `SqliteSaver` | SQLite 파일 영속 | **MVP 운영 (권장)** |
| `PostgresSaver` | DB 영속, 다중 인스턴스 | 추후 다중 사용자 확장 시 |

```python
# 개발 시 MemorySaver로 빠르게 테스트
from langgraph.checkpoint.memory import MemorySaver
checkpointer = MemorySaver()

# 운영 시 SqliteSaver로 교체 (코드 변경 없이 전환 가능)
from langgraph.checkpoint.sqlite import SqliteSaver
checkpointer = SqliteSaver.from_conn_string("data/sessions.db")
```

### 핵심 프롬프트 설계

> 프롬프트 파일 목표 위치: `configs/prompts/` (Hydra로 노드별 로드). 아래는 **내용 명세**.

**extract_step3 노드 (평가항목 분석 — STEP 5 입력 준비):**
```
시스템: {EXPERT_PERSONA}  ← §3.1 전문가 페르소나

사용자: 아래 RFP 평가항목을 분석하고 JSON으로 출력하세요.
- eval_items: [{item, score, weight_pct, description}]  # 배점·가중치
- high_score_items: [배점 상위 요구사항 — STEP 5 핵심이슈 차별화의 1순위 입력]
- eval_characteristics: 평가 구조 특징 (기술:가격 비율, 필수/가점 구분 등)
- implications: 제안 전략 수립 시사점

RFP 내용: {rfp_text}
```

**extract_step2_formal 노드 (공식 요구사항 추출):**
```
시스템: {EXPERT_PERSONA}

사용자: 아래 RFP에서 다음 항목을 JSON으로 추출하세요.
- formal_requirements: [{name, detail, priority, linked_eval_item}]  # 평가항목 연결
- key_differentiable_items: [차별화 전략 수립에 활용할 핵심 제안요청사항]
- constraint_items: [필수 준수 항목 (법령, 표준, 보안요건 등)]

RFP 내용: {rfp_text}
```

**generate_step5 노드 (경쟁우위 차별화 전략) — LLM API 권장:**
```
시스템: {EXPERT_PERSONA}

당신의 임무는 아래 입력을 종합하여 [5-1] 경쟁구도 차별화와 [5-2] 핵심이슈 차별화 전략을
**구체적·실행 가능한 제안 전략**으로 도출하는 것입니다.
유사 수주 사례(RAG)와 방법론을 참고하되, 본 사업 RFP·PM 입력에 **직접 근거**해야 합니다.

사용자:
## 사업개요
{step1_business_overview}

## 고객 요구사항 (공식 — RFP)
{step2_formal_requirements}

## 고객 요구사항 (비공식 — 인터뷰·Hidden Needs·Pain Point)
{step2_informal_requirements}

## 평가항목 분석 (high_score_items = 배점 상위 요구사항)
{step3_eval_criteria}

## 경쟁력 분석 (우리 vs 경쟁사)
{step4_competitiveness}

## 유사 수주 사례 (RAG)
{rag_case_docs}

## 제안전략 방법론 (RAG)
{rag_methodology_docs}

---
다음 두 섹션을 **지시에 따라** 작성하세요.

### [5-1] 경쟁구도 차별화 전략
경쟁사 대비 우리의 포지셔닝을 다음 관점에서 **분리**하여 작성:
1. **약점 만회 전략**: 경쟁사 대비 우리의 상대적 약점·리스크 → 만회·보완 방안
   (인력·실적·가격·기술·레퍼런스 등 영역별)
2. **강점 부각 전략**: 경쟁사 대비 우리의 차별 강점 → 평가항목·RFP 요구와 **연결**하여
   부각할 포인트·메시지·근거

### [5-2] 핵심이슈 차별화 전략
아래 **세 축**을 모두 다루되, 요구사항별로 **우리 솔루션·차별화 방안**을 매핑:
1. **고배점 평가 요구사항**: step3 `high_score_items` 중심 — 배점이 높은 항목에 대한
   제안 차별화 방안 (무엇을·어떻게·왜 우리가 유리한지)
2. **비공식 요구사항 (Hidden Needs)**: 인터뷰·영업을 통해 파악된 고객의 unstated needs에
   대한 제안 차별화 방안
3. **Pain Point·핵심 쟁점**: 고객이 가장 우려·중시하는 이슈에 대한 솔루션 차별화
   (재해복구·보안·일정·조직·예산 등)

각 항목: `{이슈/요구} → {우리 차별화 방안} → {기대 효과·근거}`
```

**generate_step7 노드 (사업수행전략·MECE 이행방안) — LLM API 권장:**
```
시스템: {EXPERT_PERSONA}

당신의 임무는 STEP 5 차별화 전략을 **실행 가능한 사업수행전략**으로 구체화하는 것입니다.
[7-3] 이행방안은 **MECE**(Mutually Exclusive, Collectively Exhaustive) 원칙을 따라
아래 **4개 영역**을 빠짐없이·중복 없이 작성합니다.

사용자:
## 앞 단계 누적 정보
{step1~step5, step6(있을 경우) 전체}

## STEP 5 차별화 전략 (필수 입력)
[5-1] {step5_1_competitive_diff}
[5-2] {step5_2_issue_solution}

---
다음 4가지 산출물을 **순서대로** 작성하세요.

### [7-1] 핵심성공요소 (CSF)
본 사업 수주·성공에 필수적인 핵심 요소 5~7개.
각 CSF는 STEP 5 차별화 전략과 **직접 연결**.

### [7-2] 사업수행전략 요약
CSF 달성을 위한 전략 요약 (경영진 보고용, 1페이지 분량).
핵심 메시지 3~5개 + CSF 매핑.

### [7-3] 사업수행전략 (이행방안) — MECE 4영역
STEP 5 [5-1][5-2]를 실행으로 옮긴 **구체적 추진 전략**. 반드시 아래 4영역으로 구분:

| 영역 | 작성 내용 |
|------|----------|
| **A. 경쟁구도·사업 포지셔닝** | [5-1] 기반 — 수주 전략·가격·실적·브랜딩·파트너십 등 |
| **B. 기술·솔루션** | [5-2] 기반 — 아키텍처·SW/HW·보안·표준·혁신 기술 등 |
| **C. 프로젝트 관리·수행** | 일정·WBS·품질·리스크·커뮤니케이션·인력·거버넌스 등 |
| **D. 고객·이해관계자 대응** | Hidden Needs·Pain Point 대응·변경관리·교육·운영 이관 등 |

각 영역: `{전략 방향} → {세부 이행 과제 3~5개} → {산출물·일정·담당}`

### [7-4] 제안서 간이 스토리보드
제안서 목차별: `{목차명, 핵심메시지, 차별화요소, 연결 CSF}`
[7-3] MECE 4영역이 목차에 **반영**되도록 구성.
```

---
## 11. 슬라이드 샘플 검색 기능

### 개요

주제 키워드를 입력하면 기존 제안서 26건(현재 확정)에서 관련 슬라이드를 검색하여
렌더링된 이미지와 LLM 선정 사유를 함께 제시하는 기능.

```
[PM] 주제 입력 (예: "재해복구 전략", "핵심인력 구성", "클라우드 전환")
        │
        ▼
  1단계: Dense(Qdrant) + BM25 → Dense∪BM25 합집합 (최대 top_k*4) — RRF 점수 부여
        │
        ▼
  2단계: 슬라이드 유형 실시간 재분류
         Qdrant payload의 slide_type이 "general/detail"이면 live 재검증
         → overview/toc로 확인되면 즉시 업데이트
        │
        ▼
  3단계: bge-reranker-v2-m3 (CrossEncoder) — 전 후보 재순위
         (운영: M5 Pro CPU / 빌드 검증: RTX CUDA)
        │
        ▼
  4단계: overview/toc 패널티 (rerank_score × 0.3) 적용
         → 개요·목차 슬라이드 하위 순위 처리
        │
        ▼
  5단계: 정렬 → 최소점수 필터(0.05) → 프로젝트 중복 제거(max 2장) → final_k 선별
        │
        ▼
  6단계: PNG 캐시에서 이미지 로드
         (data/projects/{id}/slides/slide_{n}.png)
        │
        ▼
  7단계: LLM → 선정된 장표 각각의 선정 사유 생성 (temperature=0.3)
        │
        ▼
  [UI] 슬라이드 이미지 3장+ 순위·선정 사유 카드 표시
```

### 슬라이드 PNG 사전 렌더링 (인덱싱 단계)

인덱싱 시 PPTX를 LibreOffice로 PDF 변환 후 pymupdf로 페이지별 PNG를 생성하여 캐시 저장.
검색 시에는 저장된 PNG를 즉시 로드하므로 응답 속도 영향 없음.

```bash
# LibreOffice 설치
# macOS
brew install libreoffice

# Ubuntu/Linux
apt-get install libreoffice

# 렌더링 실행 (초기 빌드 — RTX 3090, Mac Qdrant 선행 기동)
export QDRANT_HOST=192.168.x.x    # Mac Mini IP
python src/main.py env=rtx3090 +task=ingest_with_render
```

```python
# src/slide_sampler/renderer.py 핵심 로직 ✅ 구현 완료
# LibreOffice --convert-to png 는 첫 슬라이드만 출력하므로
# PPTX → PDF (LibreOffice) → 페이지별 PNG (pymupdf) 경로 사용
import subprocess, fitz  # pymupdf
from pathlib import Path

def render_pptx_to_png(pptx_path: Path, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1단계: PPTX → PDF (LibreOffice headless)
    pdf_path = output_dir / (pptx_path.stem + ".pdf")
    subprocess.run([
        "libreoffice", "--headless", "--convert-to", "pdf",
        "--outdir", str(output_dir), str(pptx_path)
    ], check=True, capture_output=True, timeout=300)  # ⚠️ 대형 PPTX 대응: 300초 (기존 120초에서 상향)

    # 2단계: PDF 페이지별 → PNG (pymupdf, 144dpi)
    doc = fitz.open(pdf_path)
    pngs = []
    for i, page in enumerate(doc, 1):
        mat = fitz.Matrix(2.0, 2.0)          # 144dpi (72 × 2)
        pix = page.get_pixmap(matrix=mat)
        target = output_dir / f"slide_{i:03d}.png"
        pix.save(str(target))
        pngs.append(target)
    doc.close()
    pdf_path.unlink()                         # 중간 PDF 정리
    return pngs
```

### 검색 및 사유 생성

```python
# src/slide_sampler/searcher.py (2026-06-22 개선)
from ingestion.slide_classifier import detect_slide_type
from sentence_transformers import CrossEncoder

_reranker: CrossEncoder | None = None
_reranker_lock = threading.Lock()

def get_reranker(device: str = "cpu") -> CrossEncoder:
    global _reranker
    if _reranker is None:
        with _reranker_lock:
            if _reranker is None:
                _reranker = CrossEncoder("BAAI/bge-reranker-v2-m3", device=device)
    return _reranker

_OVERVIEW_PENALTY = 0.3   # overview/toc 슬라이드 rerank_score 감쇄율
_MIN_RERANK_SCORE = 0.05  # 최소 점수 미달 시 결과에서 제외

def search_slides(topic: str, cfg, final_k: int = 10) -> list[SlideResult]:
    # 1단계: Dense ∪ BM25 합집합 후보 (Retriever → 최대 top_k*4)
    candidates_raw = retriever.search(topic, collection="proposals", top_k=20)
    candidates = [SlideResult(...) for r in candidates_raw]

    # 2단계: 슬라이드 유형 실시간 재분류 — 인덱싱 시점 분류 오류 보정
    for c in candidates:
        stored_type = c.meta.get("slide_type", "general")
        if stored_type in ("general", "detail"):
            live_type = detect_slide_type(c.slide_text)
            if live_type in ("overview", "toc"):
                c.meta["slide_type"] = live_type

    # 3단계: bge-reranker-v2-m3 재순위 — dedup 전에 실행 (관련도 높은 슬라이드 먼저 선별)
    # ※ 핵심: dedup을 reranker 이후로 이동해야 개요 슬라이드가 상세 슬라이드보다 먼저
    #   프로젝트 슬롯을 차지하는 문제를 방지
    reranker = get_reranker(device=cfg.env.reranker_device)
    pairs = [(topic, c.slide_text) for c in candidates]
    scores = reranker.predict(pairs, batch_size=1)
    for c, s in zip(candidates, scores):
        c.rerank_score = float(s)

    # 4단계: overview/toc 패널티 — 개요·목차 슬라이드 하위 순위 처리
    for c in candidates:
        if c.meta.get("slide_type") in ("overview", "toc"):
            c.rerank_score *= _OVERVIEW_PENALTY

    # 5단계: 정렬 → 최소점수 필터 → 중복 제거 → final_k
    ranked = sorted(candidates, key=lambda c: c.rerank_score, reverse=True)
    ranked = [c for c in ranked if c.rerank_score >= _MIN_RERANK_SCORE]
    ranked = _deduplicate_by_project(ranked, max_per_project=2)
    return ranked[:final_k]
```

```python
# src/slide_sampler/explainer.py
def generate_reason(topic: str, slide_text: str, project_meta: dict) -> str:
    prompt = f"""
주제: {topic}
프로젝트: {project_meta['project_name']} ({project_meta['year']}, {project_meta['result']})
슬라이드 내용: {slide_text}

이 슬라이드가 "{topic}" 주제의 우수 사례인 이유를 2~3문장으로 설명하세요.
차별화 포인트와 참고할 만한 표현·구성 방식을 중심으로 작성하세요.
"""
    return llm.generate(prompt)
```

### UI 표시 (Streamlit MVP 기준)

```python
# 슬라이드 샘플 검색 탭
topic = st.text_input("슬라이드 주제 검색", placeholder="예: 재해복구 전략, 핵심인력 구성")
final_k = st.slider("표시 개수", min_value=3, max_value=10, value=10)

if st.button("검색"):
    with st.spinner(f"bge-reranker로 최적 슬라이드 {final_k}장 선별 중..."):
        results = search_slides(topic, final_k=final_k)

    cols = st.columns(min(final_k, 3))   # 기본 3열; 4장 이상은 행 추가 또는 st.columns(final_k)
    for i, r in enumerate(results):
        with cols[i]:
            st.image(r.png_path, caption=f"#{i+1}  {r.project_name} - Slide {r.slide_no}")
            st.caption(f"Rerank score: {r.rerank_score:.3f}")
            reason = generate_reason(topic, r.slide_text, r.meta)
            st.info(f"**선정 사유**: {reason}")
```

### 저장 공간 예상

| 구분 | 계산 | 예상 용량 |
|------|------|----------|
| 평균 슬라이드 수/건 | ~40장 | — |
| PNG 파일 크기 (1280×720) | ~150~300KB | — |
| 전체 (26건 × 40장 × 200KB) | — | **~208MB** (목표 43건 시 ~344MB) |

> SSD 여유 공간 1GB 이상이면 충분. 인덱싱 시 1회 생성 후 재사용.

---


## 12. 선행 작업 목록 (사용자 수행)

> 구현 착수 전에 아래 작업을 완료해야 RAG 품질이 보장됩니다.

---

### P0 — 데이터 정리 ✅ 완료 (2026-06-11)

#### P0-1. review.csv 검토 및 수정 ✅

- `data/review_reviewed.csv` 로 원천 파일 직접 정리 (26건 확정)
- `suggested_project_id` 형식: `{연도}_{기관코드}_{사업명}`
- `scripts/organize_data.py` Phase 1/2 설계 완료 (향후 신규 데이터 추가 시 재사용 가능)

#### P0-2. 디렉토리 구조 생성 ✅

- `data/projects/` 하위 26개 프로젝트 폴더 생성 완료
- 파일 표준화: `proposal.pdf` (전체 PDF 통일 완료)
- `meta.json` 전 프로젝트 생성 완료

```
data/projects/
└── {project_id}/
    ├── proposal.pdf    제안서 (PDF 통일본 — RAG 파싱 기준 파일)
    ├── proposal.pptx   원본 보존 (pptx 출처인 경우에만 존재)
    ├── rfp.pdf         (수집된 경우)
    ├── meta.json
    └── tags.json
```

- `data/raw_data/` 원본 → `data/projects/` 26건 이전 완료 (raw_data는 선택적 보관)

#### P0-2-1. proposal PDF 통일 변환 ✅

26건 원본 파일(pptx 22건 + pdf 4건)을 모두 `proposal.pdf`로 통일 완료.

| 원본 형식 | 건수 | 변환 방법 |
|---------|------|---------|
| `.pptx` | 22건 | **스크립트 자동화** — `scripts/convert_to_pdf.py` (Microsoft PowerPoint 앱 osascript 자동화, 수동 변환과 동일 품질) |
| `.pdf` | 4건 | 이미 PDF — 변환 없이 그대로 사용 |

> 원본 `.pptx` 파일은 삭제하지 않고 각 프로젝트 디렉토리에 보존.

#### P0-3. meta.json 보완 ✅

- `data/meta_fill.csv` 작성 → 26개 전 프로젝트 `result` / `scale` 입력 완료
- `scripts/organize_data.py` Phase 2에서 자동 반영

| 필드 | 값 예시 | 현황 |
|------|---------|------|
| result | 수주 / 실주 | 26개 완료 |
| scale | 대형 / 중형 / 소형 | 26개 완료 |

#### P0-4. 방법론 문서 ✅

- `data/methodology/` 제안전략 방법론 **3건** 업로드 완료
- RAG `methodology` 컬렉션 인덱싱 대상

---

### P1 — RFP 수집 ⚠️ 부분 완료 (9/26)

#### P1-1. 나라장터(G2B)에서 RFP 수집

- HWP 원본 수집 후 PDF 변환 (`rfp.pdf`) 저장 — **HWP → PDF 변환은 사용자가 직접 수행** (한글 앱에서 수동 변환)
- `meta.json`의 `has_rfp` 자동 업데이트 완료

**수집 완료 (9건):**

| 프로젝트 | 연도 |
|---------|------|
| 2008_KPIC_우체국_전자금융_AML_IFDS_ISP | 2008 |
| 2016_CUSTOMS_4세대_국종망_재해복구시스템_구축 | 2016 |
| 2016_KERIS_2016년_교육정보시스템_물적기반_유지관리 | 2016 |
| 2016_KLID_2016년_자치단체장비_유지관리 | 2016 |
| 2016_MOFE_국고보조금통합관리시스템_구축 | 2016 |
| 2016_NTS_2016년_국세청엔티스_NTIS_운영_및_유지보수 | 2016 |
| 2017_KERIS_2017년_에듀파인시스템_응용SW_유지관리 | 2017 |
| 2017_KLID_2017년_자치단체장비_유지관리 | 2017 |
| 2024_KSPO_체육진흥투표권_차세대시스템_구축 | 2024 |

**미수집 (17건):** 나라장터 추가 수집 필요

---

### P2 — 라벨링 ✅ 완료 (2026-06-11)

#### P2-1. 평가 기준 및 전략 키워드 태깅 ✅

- `scripts/extract_tags.py` 구현 (Claude Haiku API 사용)
- 26개 전 프로젝트 `tags.json` 생성 완료

**추출 항목:**

| 항목 | 소스 | 내용 |
|------|------|------|
| `evaluation_criteria` | rfp.pdf | 평가 항목명 + 배점 |
| `strategy_keywords` | proposal.* | 핵심 전략 키워드 (최대 15개) |
| `differentiators` | proposal.* | 경쟁사 대비 차별화 포인트 (최대 10개) |
| `strategy_summary` | proposal.* | 핵심 제안전략 방향 3~5개 (완성된 문장, STEP 5 RAG 컨텍스트 주입용) |

```json
{
  "evaluation_criteria": [
    {"item": "기술평가", "score": 90},
    {"item": "가격평가", "score": 10}
  ],
  "strategy_keywords": ["재해복구시스템 구축", "무중단 전환", ...],
  "differentiators": ["최근 3년간 920억 규모 DR구축 경험", ...],
  "strategy_summary": [
    "이중화 DR 아키텍처를 통해 RPO=0·RTO≒0을 실현하여 무중단 서비스를 보장한다",
    "..."
  ]
}
```

**재실행 방법 (신규 프로젝트 추가 시):**
```bash
source .venv/bin/activate
export $(cat .env | xargs)
# 특정 프로젝트만
python scripts/extract_tags.py "{project_id}"
# 전체 (기존 tags.json 있으면 스킵)
python scripts/extract_tags.py
```

---

### P3 — 환경 준비 (필수, 반나절)

#### P3-1. Mac Mini M5 Pro 환경 설정 (운영, 상시)

```bash
# ── 방법 A: MLX (권장 — Qwen3.5 즉시 사용 가능) ──────────────────────
pip install mlx-lm

# Qwen3.5-9B 다운로드 (HuggingFace, MLX 4-bit 버전)
# mlx-community 에서 양자화 버전 제공
python -c "from mlx_lm import load; load('mlx-community/Qwen3.5-9B-4bit')"

# OpenAI 호환 서버 실행 (포트 11434)
mlx_lm.server --model mlx-community/Qwen3.5-9B-4bit --port 11434

# ── 방법 B: Ollama (Qwen3.5 레지스트리 등록 후) ───────────────────────
brew install ollama
ollama serve
ollama pull qwen3.5:9b    # 등록 확인: https://ollama.com/library

# ── Qdrant Docker ─────────────────────────────────────────────────────
docker run -d --name qdrant \
  -p 6333:6333 \
  -v $(pwd)/data/vectorstore:/qdrant/storage \
  qdrant/qdrant
```

#### P3-2. RTX 3090 Linux 환경 설정 (초기 빌드, GPU 작업 시에만)

> Mac Mini에서 Qdrant Docker를 먼저 기동한 뒤, RTX 3090에서 `QDRANT_HOST=Mac IP`로 인덱싱 실행.
> `data/` 폴더는 NAS·rsync·공유 마운트 등으로 RTX 3090에서 접근 가능해야 함.

```bash
# CUDA 버전 확인 (12.x 권장)
nvidia-smi

# Python 가상환경 (임베딩·렌더링 배치 처리용)
python -m venv .venv && source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cu121
pip install sentence-transformers

# LibreOffice (슬라이드 PNG 렌더링)
apt-get install -y libreoffice

# (선택) Ollama — LLM 실험·파인튜닝 검증용, 일상 운영 불필요
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen3.5:9b    # Ollama 0.17.1+ 및 Qwen3.5 호환 확인

# 초기 빌드 실행 예
export QDRANT_HOST=192.168.x.x    # Mac Mini IP
python src/main.py env=rtx3090 +task=ingest_with_render
```

#### P3-3. 클라우드 LLM API 키 발급

**Solar Pro (Upstage):**
1. Upstage 콘솔 가입 및 API Key 발급

**Claude (Anthropic):**
1. console.anthropic.com 가입 및 API Key 발급
2. Pro 구독과 별개 과금 (사용량 기반)

```bash
# .env (Mac Mini 기준 — 운영, .env.template 참고)
SOLAR_API_KEY=up_xxxxxxxxxxxxxxxxxxxx
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxx
LOCAL_LLM_BASE_URL=http://localhost:11434          # MLX 또는 Ollama

# Qdrant (Mac Mini 로컬)
QDRANT_HOST=localhost
QDRANT_PORT=6333

# 세션 체크포인트
SESSIONS_DB_PATH=data/sessions.db

# RTX 3090 초기 빌드 시에만 (.env 또는 셸 export)
# QDRANT_HOST=192.168.x.x                          # Mac Mini IP
```

---

## 13. 구현 계획 (Phase별)

---

### Phase 1 — 데이터 처리 파이프라인 (Week 1) ✅ 구현 + 코드 리뷰 완료 (2026-06-19)

**목표:** 모든 PPTX/PDF에서 구조화된 청크 추출 → Qdrant 인덱싱 + 슬라이드 PNG 사전 렌더링

**RTX 3090에서 실행 (초기 빌드):** bge-m3 CUDA 배치 임베딩 + PDF→PNG 렌더링. 빌드 완료 후 RTX 불필요.

---

#### 구현 산출물 (2026-06-18 완료)

```
src/ingestion/
├── parsers/
│   ├── base.py          ParsedSlide / ParsedDocument dataclass ✅
│   ├── pptx_parser.py   python-pptx: placeholder[0]=title만 (idx==0), 나머지=body, notes 추출 ✅
│   └── pdf_parser.py    pdfplumber: 첫줄=title, 나머지=body (이미지PDF 폴백 포함) ✅
├── slide_classifier.py  슬라이드 유형 분류 + 계층 키워드 추출 + SectionEnricher ✅ (2026-06-22 추가)
├── chunker.py           슬라이드 단위 청킹 + slide_type/hierarchy_labels/section_context + BM25 사전 토크나이즈 ✅
└── indexer.py           BAAI/bge-m3 → Qdrant upsert (batch=128, normalize_embeddings=True) ✅

src/slide_sampler/
└── renderer.py          proposal.pdf → pymupdf → slide_NNN.png (144dpi) ✅
                         ※ LibreOffice 미사용 — 26건 전부 proposal.pdf 보유

src/main.py              Hydra entry point (config_path="../configs") ✅
scripts/verify_phase1.py Phase 1 결과 검증 스크립트 ✅

configs/
├── config.yaml          defaults: llm=solar, env=m5pro, rag, pipeline, ingestion ✅
├── llm/
│   ├── solar.yaml       _target_: src.llm.solar.SolarProLLM, model: solar-pro ✅
│   ├── claude.yaml      _target_: src.llm.claude.ClaudeLLM, model: claude-sonnet-4-6 ✅
│   └── qwen_local.yaml  base_url: ${oc.env:LOCAL_LLM_BASE_URL,...} ✅
├── env/
│   ├── m5pro.yaml       embedding_device: cpu, qdrant_host: localhost ✅
│   └── rtx3090.yaml     embedding_device: cuda, embedding_batch_size: 64 ✅
├── rag/default.yaml     top_k: 10, hybrid_alpha: 0.7, min_score_threshold: 0.5 ✅
├── pipeline/default.yaml node_llm / node_temperature 라우팅 테이블 ✅
├── ingestion/default.yaml min_chunk_chars: 100, embedding_model: BAAI/bge-m3 ✅
└── task/
    ├── ingest.yaml              render_slides: false, index_qdrant: true ✅
    ├── ingest_with_render.yaml  render_slides: true, index_qdrant: true ✅
    └── render_slides.yaml       render only ✅
```

---

#### 검증 결과 (2026-06-18 기준)

| 항목 | 결과 |
|------|------|
| **파서** | PPTX 22건 / PDF 폴백 4건 (2008·2009·2013·2021 KERIS — PPTX 없음) |
| **총 청크** | proposals 1,160건 + methodology 130건 = **1,290건** |
| **Qdrant proposals** | **1,160 포인트** |
| **Qdrant methodology** | **130 포인트** |
| **임베딩 dim** | 1,024 / Cosine |
| **PNG 렌더링** | 26/26 완료, **2,011장**, 총 1,116MB |
| **PDF↔PNG 페이지 수** | 26건 전부 일치 확인 |
| **meta.json 완전성** | 26/26 (year·agency·domain·project_type·result 전 필드) |
| **tags.json strategy_keywords** | 26/26 ✅ |
| **tags.json strategy_summary** | 26/26 ✅ |
| **tags.json evaluation_criteria** | 9/26 ✅ (RFP 보유 9건만 생성; 나머지는 RFP 미수집) |

---

#### 청킹 전략 (실제 구현)

- **파서 우선순위**: `proposal.pptx` 존재 시 PPTX 파서 우선 → 없으면 `proposal.pdf` 폴백
- **슬라이드 단위** (1 슬라이드 = 1 청크 기본)
- **100자 미만** 슬라이드는 이전 청크와 병합 (공백 정규화 기준: `re.sub(r"\s+", " ", text).strip()`)
  - 이미지 PDF(OCR 불가) 대응: 공백 정규화 후 100자 미만이면 청크 제외 (2021_KERIS 이미지PDF → 0청크)
- **methodology / proposals** 컬렉션 분리 저장

```python
# src/ingestion/chunker.py — 핵심 필터 로직
import re

for slide in merged:
    text = slide.text
    # 공백 정규화 후 길이 기준 — 이미지PDF 등 줄바꿈만 가득한 청크 제거
    if len(re.sub(r"\s+", " ", text).strip()) < min_chunk_chars:
        continue
    # ... 청크 dict 생성
```

---

#### 청크 메타데이터 스키마

```python
{
    # 식별
    "doc_id":   "2022_NIRS_2022년_제1차_HW자원_통합구축_사업7",  # 프로젝트 디렉토리명
    "source":   "proposals",   # "proposals" | "methodology"
    "slide_no": 5,

    # 본문
    "text":    "슬라이드 제목\n본문\n노트 (title+body+notes 합산)",
    "section": "수행 전략",    # 슬라이드 title (없으면 "")

    # meta.json 연동
    "year":         "2022",
    "agency":       "국가정보자원관리원",
    "domain":       "HW인프라",
    "project_type": "구축",
    "result":       "실주",
    "has_rfp":      False,

    # PNG 경로 (슬라이드 샘플 검색 UI 표시용)
    "png_path": "data/projects/2022_NIRS_.../slides/slide_005.png",

    # tags.json 연동 (RAG 메타 필터·STEP 5 프롬프트 보강)
    "strategy_keywords":   ["HW 통합구축", "운영 효율화", ...],
    "evaluation_criteria": [{"item": "기술평가", "score": 90}, ...],
    "differentiators":     ["서버 가상화 통합 경험 최다", ...],
    "strategy_summary":    ["공공 HW인프라 통합 운영 경험 최다 보유", ...],
                           # STEP 5 프롬프트에 프로젝트 수준 전략 방향 직접 주입

    # 슬라이드 유형 분류 (slide_classifier.py — 2026-06-22 추가)
    "slide_type": "detail",             # "toc" | "overview" | "detail" | "general"
    "hierarchy_labels": ["사업수행조직 구성"],  # 전략·실행방안 레이블에서 추출한 키워드 (overview/detail)
    "section_context": "사업수행에 적합한 조직구성",  # 직전 overview의 섹션 제목 (detail에만 전파, max 12장)

    # BM25 사전 토크나이즈 (인덱싱 시 1회 계산 → 쿼리 시 재실행 불필요)
    # section_context가 있으면 "{section_context}\n{text}" 합산 색인
    "tokenized_text": ["HW", "통합", "구축", "운영", "효율화", ...],
                      # kiwipiepy: NNG·NNP·VV·VA·SL 품사만 유지
}
```

---

#### 슬라이드 렌더링 (실제 구현 — LibreOffice 미사용)

계획 단계에서는 LibreOffice(PPTX→PDF→PNG)를 사용하려 했으나, 대형 PPTX에서 타임아웃이 반복되었고 26건 전부 `proposal.pdf`가 이미 존재함을 확인 → **pymupdf 직접 PDF→PNG 방식으로 전환**.

```python
# src/slide_sampler/renderer.py — 실제 구현
import fitz  # pymupdf

_DPI_SCALE = 2.0  # 144dpi (72 × 2)

def render_pdf_to_png(pdf_path: Path, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(str(pdf_path))
    mat = fitz.Matrix(_DPI_SCALE, _DPI_SCALE)
    pngs = []
    for i, page in enumerate(doc, 1):
        pix = page.get_pixmap(matrix=mat)
        target = output_dir / f"slide_{i:03d}.png"
        pix.save(str(target))
        pngs.append(target)
    doc.close()
    return pngs

def render_all_projects(data_dir: Path) -> None:
    for project_dir in sorted(p for p in data_dir.iterdir() if p.is_dir()):
        pdf_path = project_dir / "proposal.pdf"
        if not pdf_path.exists():
            continue
        slides_dir = project_dir / "slides"
        if list(slides_dir.glob("slide_*.png")) if slides_dir.exists() else []:
            continue  # 이미 렌더링 완료 — 멱등성 보장
        render_pdf_to_png(pdf_path, slides_dir)
```

**렌더링 흐름:**
```
proposal.pdf 발견
    → pymupdf (fitz): PDF 페이지별 → slide_NNN.png (144dpi, 2× 스케일)
    → data/projects/{id}/slides/ 저장
    → 이미 PNG 존재하면 스킵 (멱등성 보장)
    → 청크 메타데이터에 png_path 기록
```

---

#### 인덱싱 실행 명령

```bash
# 인덱싱 + PNG 렌더링 동시
python src/main.py env=rtx3090 +task=ingest_with_render

# PNG 렌더링만 (재실행)
python src/main.py env=rtx3090 +task=render_slides

# 인덱싱만 (PNG 이미 존재 시)
python src/main.py env=rtx3090 +task=ingest

# 결과 검증
python scripts/verify_phase1.py

# Mac Mini Qdrant 업로드 시 (Docker 선행 기동)
export QDRANT_HOST=192.168.x.x   # Mac Mini IP
python src/main.py env=rtx3090 +task=ingest
```

---

#### 구현 중 확인된 기술 결정사항

| 항목 | 계획 | 실제 결정 | 이유 |
|------|------|----------|------|
| **슬라이드 렌더링** | LibreOffice PPTX→PDF→PNG | **pymupdf PDF→PNG 직접** | 26건 모두 proposal.pdf 보유; LibreOffice 타임아웃 반복 |
| **Qdrant API** | `client.search()` | **`client.query_points()`** | qdrant-client 1.18.0에서 `search()` 제거. 반환값: `result.points` (Phase 2 구현 시 동일 API 사용) |
| **Qdrant 접속** | Docker TCP | **TCP probe → 로컬 파일 자동 폴백** | `_get_client()`에서 소켓 체크 실패 시 `QdrantClient(path="data/vectorstore")`. 단일 프로세스만 허용(portalocker) |
| **이미지 PDF 필터** | `if not text.strip(): continue` | **`if len(re.sub(r"\s+", " ", text).strip()) < min_chunk_chars: continue`** | 2021_KERIS: 이미지 PDF로 pdfplumber가 줄바꿈만 추출 → 공백 정규화 기준으로 저품질 청크 제거 |
| **torch / GPU** | CUDA 임베딩 | **torch 2.5.1+cu121 + transformers 4.47.1** | Driver 535 = CUDA 12.2. torch 2.12.1은 CUDA 13.0 필요. transformers 5.x는 CVE-2025-32434 패치로 torch<2.6에서 torch.load 차단 → 4.47.1로 고정 |
| **청크 텍스트 구성** | title + body | **title + body + notes** | PPTX notes slide에 발표자 메모(전략 근거)가 포함된 경우 많음 → 청킹 품질 향상 |
| **PPTX/PDF 우선순위** | PDF 기준 | **PPTX 우선, PDF 폴백** | PPTX: title placeholder·body shapes·notes 구조 보존. PDF: 평문 추출만 가능 |

---

#### GPU 환경 설정 (RTX 3090 — CUDA 12.2)

```bash
# torch: cu121 빌드 (CUDA 12.2 드라이버와 호환되는 최신)
pip install torch==2.5.1 torchvision==0.20.1 \
    --index-url https://download.pytorch.org/whl/cu121

# transformers: CVE-2025-32434 보안 체크 이전 버전 고정
# (BAAI/bge-m3은 safetensors 미제공 → torch.load 경로 사용 → 5.x에서 차단됨)
pip install "transformers==4.47.1"

# 나머지 의존성
pip install -r requirements.txt
```

> **드라이버 550+ 업그레이드 시:** torch 2.6.0+cu124 + transformers 최신 버전 사용 가능.

---

#### 📋 완료 체크리스트

| # | 작업 | 상태 | 비고 |
|---|------|------|------|
| 1 | RTX 3090 CUDA 환경 설정 (torch 2.5.1+cu121 + transformers 4.47.1) | ✅ 완료 | GPU 인식 확인 (RTX 3090, 23GB) |
| 2 | Qdrant 로컬 파일 모드 자동 폴백 구현 | ✅ 완료 | `data/vectorstore/` 로컬 저장 |
| 3 | 26건 proposal.pdf/pptx 파일 배치 확인 | ✅ 완료 | PPTX 22건 / PDF-only 4건 |
| 4 | PDF→PNG 렌더링 (26건) | ✅ 완료 | 2,011장, 1,116MB, PDF↔PNG 페이지 수 전부 일치 |
| 5 | 인덱싱 실행 (GPU, env=rtx3090) | ✅ 완료 | proposals 1,160 / methodology 130 포인트 (결정론적 UUID, 중복 방지) |
| 6 | verify_phase1.py 검증 통과 | ✅ 완료 | 파서·청커·Qdrant·PNG 전 항목 정상 |
| 7 | 이미지PDF 청크 품질 버그 수정 | ✅ 완료 | 공백 정규화 기준 필터 추가 (2021_KERIS → 0청크) |
| 8 | (계속) 나라장터 RFP 추가 수집 — 미수집 17건 | ⚠️ 진행 중 | 우선순위 RFP 먼저 수집 |
| 9 | **코드 리뷰 + 버그 수정** (2026-06-19) | ✅ 완료 | 아래 §코드 리뷰 섹션 참고 |
| 10 | **슬라이드 유형 분류기 추가 + 재인덱싱** (2026-06-22) | ✅ 완료 | `slide_classifier.py` 신규 — toc/overview/detail/general 분류, SectionEnricher(section_context 전파), 1,160청크 재인덱싱 완료 |

---

### Phase 2 — RAG 검색 파이프라인 (Week 1 후반) ✅ 구현 + 코드 리뷰 완료 (2026-06-19)

**목표:** RFP 분석 결과 → Dense(Qdrant) + BM25 + RRF 검색

---

#### 구현 산출물 (2026-06-18 완료)

```
src/rag/
├── embedder.py      Embedder 클래스 — BAAI/bge-m3, normalize+float32, env별 device 자동 선택 ✅
├── vectorstore.py   VectorStore 클래스 — Qdrant query_points() 래퍼, 메타 필터 지원 ✅
├── retriever.py     Retriever — Dense(200) + BM25 + RRF(k=60), normalize_domain() ✅
└── __init__.py      모듈 exports ✅

configs/rag/
├── default.yaml     top_k: 10, hybrid_alpha: 0.8, methodology_top_k: 5, min_score_threshold: 0.35
└── domain_map.yaml  4대 domain canonical → alias 맵 (인프라/ITO/응용시스템/컨설팅) ✅

scripts/
├── normalize_domains.py  meta.json domain 26건 정규화 (project_type 기반 분류) ✅
└── verify_phase2.py      쿼리 9개 + alias 필터 4개 검증 스크립트 ✅
```

---

#### 검증 결과 (2026-06-18)

| 항목 | 결과 |
|------|------|
| **proposals 검색** | 1,160 포인트, 7개 쿼리 전부 관련 결과 반환 ✅ |
| **methodology 검색** | 130 포인트, 2개 쿼리 정상 ✅ |
| **메타 필터 (alias→canonical)** | HW인프라→인프라, 금융→응용시스템, 유지보수→ITO, ISP→컨설팅 전부 ✅ |
| **RRF 병합** | Dense top-200 → BM25 재순위 → RRF(k=60) 정상 동작 ✅ |

---

#### domain 4대 분류 (신규 도입)

계획 단계에서는 세분화된 업무 도메인(금융시스템, 교육행정시스템 등)을 그대로 사용하려 했으나,
RFP 추출 결과와 저장 값 불일치 문제(alias 미매핑)가 발생 → **4대 canonical 분류**로 정규화.

| 분류 | 건수 | 설명 |
|------|------|------|
| **인프라** | 8건 | HW 신규 구축, 데이터센터, DR, 클라우드 인프라 구축 |
| **ITO** | 7건 | HW/SW 운영·유지보수·유지관리 (상주 운영 포함) |
| **응용시스템** | 9건 | 업무 앱 신규 구축·차세대·고도화 (금융·행정·교육·보건의료 등) |
| **컨설팅** | 2건 | ISP·ISMP·BPR·EA 등 전략 수립·계획 수립 |

```python
# src/rag/retriever.py — normalize_domain(): alias → canonical 변환 (lazy-loaded singleton)
# Phase 3 retrieve_rag 노드에서 RFP 추출 domain 값 정규화에 사용
normalize_domain("HW인프라")  # → "인프라"
normalize_domain("금융")      # → "응용시스템"
normalize_domain("유지보수")   # → "ITO"
normalize_domain("ISP")       # → "컨설팅"
```

> alias 맵: `configs/rag/domain_map.yaml` (canonical별 20~30개 alias)
> `scripts/normalize_domains.py`로 meta.json domain 26건 정규화 후 재인덱싱 완료 (2026-06-18)

---

#### 실제 검색 파이프라인 (구현 기준)

```python
# 1. 쿼리 임베딩 (normalize_embeddings=True, float32 강제 — CUDA/CPU 일관성)
query_vec = embedder.encode_single(query)

# 2. Dense 검색 — 의미 유사도 기반 200개 후보 (Qdrant query_points API)
dense_pts = vs.search(collection, vector=query_vec, limit=200, filter_dict=filter)

# 3. 최소 품질 가드(0.35) 후 BM25 재순위 — 극단적 저품질만 사전 제거
#    0.50 하드컷 제거: Dense 점수 낮아도 BM25 고순위 슬라이드를 구제하기 위해 임계값 완화
#    payload["tokenized_text"] 사전 계산값 사용 — kiwipiepy 재실행 없음
dense_pts = [p for p in dense_pts if p.score >= 0.35]
bm25 = BM25Okapi([p.payload["tokenized_text"] for p in dense_pts])
bm25_top_n = min(top_k * 2, len(dense_pts))
bm25_pts = [dense_pts[i] for i in bm25.get_scores(korean_tokenize(query)).argsort()[::-1][:bm25_top_n]]

# 4. Dense 상위 top_k ∪ BM25 상위 top_k 합집합 → RRF 점수 부여 → 최대 top_k*4 반환
# RRF 반환 수를 top_k로 제한하지 않음 — reranker가 최종 판단하도록 전 후보 전달
dense_top = dense_pts[:top_k]
bm25_top = bm25_pts[:top_k]
results = _rrf_merge(dense_top, bm25_top, top_k=top_k * 4, dense_weight=hybrid_alpha)
```

---

#### 구현 중 확인된 기술 결정사항

| 항목 | 계획 | 실제 결정 | 이유 |
|------|------|----------|------|
| **Qdrant API** | `client.search()` | **`client.query_points()`** | qdrant-client 1.18.0+ `search()` 제거 (Phase 1과 동일) |
| **BM25 범위** | 전체 코퍼스 | **Dense 200개 후보 내** | 메모리 효율 + `tokenized_text` payload 재사용 |
| **domain 필터** | 세분화 도메인 값 직접 사용 | **4대 canonical + alias 정규화** | RFP 추출 값과 저장 값 불일치 방지 |
| **RRF 상수 k** | 계획 없음 | **60** (표준값) | 상위 랭크 강조 균형 |
| **Dense 사전 필터** (2026-06-22) | min_score 0.50 하드컷 | **0.35 최소 가드** | Dense 점수 낮아도 BM25 고순위 슬라이드 구제 (NHIS slide36: Dense=0.44 → BM25 13위로 구제) |
| **RRF 반환 수** (2026-06-22) | `top_k` 제한 | **`top_k * 4`** (union 전체) | reranker 전에 후보를 truncate하지 않고 전체를 reranker에 전달 |
| **hybrid_alpha** (2026-06-22) | 0.7 | **0.8** | Dense 가중치 상향 — 의미 유사도 우선, BM25는 보완 역할 |

---

#### 📋 완료 체크리스트

| # | 작업 | 상태 | 비고 |
|---|------|------|------|
| 1 | Embedder — normalize+float32, env별 device 자동 선택 | ✅ 완료 | |
| 2 | VectorStore — query_points() API, 메타 필터 | ✅ 완료 | |
| 3 | Retriever — Dense+BM25+RRF, normalize_domain() | ✅ 완료 | |
| 4 | domain 4대 분류 및 alias 맵 (`domain_map.yaml`) | ✅ 완료 | 인프라/ITO/응용시스템/컨설팅 |
| 5 | meta.json domain 26건 정규화 (project_type 기반) | ✅ 완료 | 19건 변경, 7건 이미 canonical |
| 6 | verify_phase2.py — 쿼리·필터·alias 변환 검증 | ✅ 완료 | |
| 7 | 재인덱싱 (새 domain 값 Qdrant payload 반영) | ✅ 완료 | proposals 1,160 / methodology 130 |
| 8 | Mac Mini Qdrant 재인덱싱 | ✅ 완료 | Phase 4 운영 중 Mac Mini에서 직접 인덱싱 |
| 9 | **코드 리뷰 + 버그 수정** (2026-06-19) | ✅ 완료 | 아래 §코드 리뷰 섹션 참고 |
| 10 | **검색 파이프라인 개선** (2026-06-22) | ✅ 완료 | Dense 필터 0.5→0.35, RRF union(top_k*4), hybrid_alpha 0.8, slide_type 패널티·dedup 순서 변경 |

---

### Phase 3 — LLM 추상화 및 LangGraph 파이프라인 (Week 2) ✅ 구현 + 코드 리뷰 완료 (2026-06-19)

**목표:** LangGraph DAG 구현, sLLM·LLM API **노드별 혼합 라우팅** (`node_llm`), Solar / Claude / Qwen3.5 전환

#### 구현 산출물 (2026-06-19 완료)

```
src/llm/
├── base.py           BaseLLM 추상 인터페이스 (generate / stream ABC) ✅
├── solar.py          Solar Pro REST API (OpenAI 호환) ✅
├── claude.py         Claude API — _split_system()으로 system 파라미터 분리 ✅
├── qwen_local.py     sLLM — OpenAI 호환 API (MLX / Ollama) ✅
└── factory.py        Hydra cfg + node_llm → 노드별 LLM 캐시 (_LLM_CACHE) ✅

src/pipeline/
├── state.py          GraphState TypedDict (20개 필드, total=False) ✅
├── nodes/
│   ├── _prompt_utils.py     공통 프롬프트 로더 (load_prompt) ✅
│   ├── rfp_parser.py        PDF 파싱 (pdfplumber→pymupdf 폴백, 50MB 제한) ✅
│   ├── rfp_analyzer.py      STEP 1~3 자동 추출 + PM 패스스루 노드 ✅
│   ├── retriever_node.py    Dense+BM25+RRF 검색 (embedder 모듈 캐시) ✅
│   ├── strategy_generator.py generate_step5/7 — LLM API 권장 노드 ✅
│   └── output_formatter.py  GraphState → Markdown 직렬화 ✅
└── graph.py          build_graph() + sqlite_checkpointer() + _wrap() 클로저 ✅

configs/prompts/
├── expert_persona.yaml, extract_step1/2/3.yaml, generate_step5/7.yaml ✅
```

**W1 — BaseLLM 인터페이스 명세:**
```python
# src/llm/base.py
from abc import ABC, abstractmethod
from typing import Iterator

class BaseLLM(ABC):
    @abstractmethod
    def generate(
        self,
        messages: list[dict],   # [{"role": "system"|"user"|"assistant", "content": str}]
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str: ...

    @abstractmethod
    def stream(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> Iterator[str]: ...
```

**system 프롬프트 처리 규칙 (3종 백엔드 통일):**

| 백엔드 | system 처리 방식 |
|--------|----------------|
| Solar (OpenAI 호환) | `messages[0] = {"role": "system", ...}` 그대로 전달 |
| Claude SDK | `messages`에서 `role=system` 추출 → `system=` 별도 파라미터로 분리 |
| Ollama / MLX (OpenAI 호환) | `messages[0] = {"role": "system", ...}` 그대로 전달 |

```python
# src/llm/claude.py — system 분리 및 generate / stream 구현
def _split_system(self, messages: list[dict]) -> tuple[str, list[dict]]:
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    user_msgs = [m for m in messages if m["role"] != "system"]
    return system, user_msgs

def generate(self, messages, temperature=0.3, max_tokens=4096) -> str:
    system, msgs = self._split_system(messages)
    resp = self.client.messages.create(
        model=self.model, system=system,
        messages=msgs, temperature=temperature, max_tokens=max_tokens,
    )
    return resp.content[0].text

def stream(self, messages, temperature=0.3, max_tokens=4096) -> Iterator[str]:
    # FR-27: 단계별 결과 실시간 스트리밍 — Streamlit st.write_stream / FastAPI SSE
    system, msgs = self._split_system(messages)
    with self.client.messages.stream(
        model=self.model, system=system,
        messages=msgs, temperature=temperature, max_tokens=max_tokens,
    ) as s:
        for text in s.text_stream:
            yield text
```

#### 📋 완료 체크리스트

| # | 작업 | 상태 | 비고 |
|---|------|------|------|
| 1 | BaseLLM ABC + Solar / Claude / Qwen3.5 구현 | ✅ 완료 | Claude: _split_system()으로 system 파라미터 분리 |
| 2 | factory.py — node_llm 라우팅 + _LLM_CACHE 싱글턴 | ✅ 완료 | |
| 3 | GraphState TypedDict (20개 필드) | ✅ 완료 | |
| 4 | LangGraph 7단계 DAG + interrupt_before 3개 PM 노드 | ✅ 완료 | |
| 5 | SqliteSaver 세션 체크포인터 | ✅ 완료 | sqlite3.connect(check_same_thread=False) 직접 사용 |
| 6 | 프롬프트 YAML 6종 + expert_persona | ✅ 완료 | |
| 7 | verify_phase3.py 검증 (Phase 3+4 포함 97개 항목) | ✅ 완료 | 97/97 통과 |
| 8 | **코드 리뷰 + 버그 수정** (2026-06-19) | ✅ 완료 | 아래 §코드 리뷰 섹션 참고 |

---

### Phase 4 — Streamlit MVP UI (Week 3) ✅ 구현 + 코드 리뷰 완료 (2026-06-19)

**목표:** RFP 업로드 → 제안전략 실시간 생성 검증 + 슬라이드 샘플 검색 (기능 우선, 디자인 무관)

```
src/app/streamlit_app.py
├── 사이드바: LLM 선택
│   ├── 기본 LLM (sLLM / API)
│   └── 전략 생성 LLM (STEP 5·7 — LLM API 권장, node_llm override)
│
├── 탭 1 — 제안전략 수립
│   ├── RFP 파일 업로드 (PDF만, 50MB 이하 — 공공 RFP 표준 형식)
│   ├── 7단계 진행 표시 (현재·완료·대기 — FR-13 MVP; 풀 스테퍼는 Phase 5)
│   ├── PM 입력 폼 (비공식 요구사항·경쟁력 분석·의사결정)
│   ├── 각 단계 결과 실시간 스트리밍 출력
│   └── 최종 산출물 Markdown 다운로드
│
└── 탭 2 — 슬라이드 샘플 검색
    ├── 주제 텍스트 입력 + 표시 개수 슬라이더 (3~10)
    ├── 검색 결과: 슬라이드 이미지 그리드 (**3열**, 기본 10장 / 슬라이더 3~10)
    │   └── 각 카드: 이미지 + 프로젝트명·연도·수주여부 + LLM 선정 사유
    └── 필터 옵션: 도메인·사업유형·수주/실주 여부
```

#### 📋 완료 체크리스트

| # | 작업 | 상태 | 비고 |
|---|------|------|------|
| 1 | Streamlit 8단계 상태 기계 (idle→done) | ✅ 완료 | st.session_state.stage |
| 2 | LangGraph 연동 — stream() → update_state() → Command(resume=None) | ✅ 완료 | |
| 3 | PM 입력 폼 3종 (step2_informal / step4 / step6) | ✅ 완료 | |
| 4 | SlideSearcher — Dense+BM25+RRF+Reranker + _embedder_cache | ✅ 완료 | |
| 5 | SlideExplainer — LLM 선정 사유 (temp=0.3, max_tokens=256) | ✅ 완료 | |
| 6 | 실행: `streamlit run src/app/streamlit_app.py --server.port 8501` | ✅ 완료 | |
| 7 | **코드 리뷰 + 버그 수정 1차** (2026-06-19) | ✅ 완료 | 아래 §코드 리뷰 섹션 참고 |
| 8 | **코드 리뷰 + 버그 수정 2차** (2026-06-19) — project_type 필터·JSON 오류 UI·docstring·dead config·unused import | ✅ 완료 | 아래 §코드 리뷰 2차 섹션 참고 |

#### 📋 남은 작업 (사용자)

| # | 작업 | 비고 |
|---|------|------|
| 1 | **실제 RFP 1건으로 end-to-end 테스트** | 수주 경험이 있는 RFP 우선 사용 |
| 2 | **PM 입력 폼 실제 데이터 입력** — Hidden Needs·Pain Point, 경쟁력 분석 | 실제 영업 정보 기반으로 입력 |
| 3 | **각 단계 출력 품질 검토** — 추출 정확도(STEP 1~3)·전략 설득력(STEP 5·7) | G2·G3 사전 파악용 |
| 4 | **UI 사용성 피드백** — 폼 구조, 진행 표시 등 불편사항 메모 | Phase 5 Next.js 요구사항 반영 |
| 5 | **STEP 6 건너뛰기 vs 진행 결정** | 팀 합의 후 기본값 결정 |

---

### Phase 4 코드 리뷰 기술 결정사항

| 항목 | 내용 |
|------|------|
| LLM 선택 변경 감지 | `node_llm` 설정 문자열을 `_cfg_key`로 해시 → 변경 시 app 재생성 |
| SQLite 연결 수명 | "새 세션 시작" 시 `old_conn.close()` 명시 호출 |
| `_resume_after_pm` | `node_name` dead param 제거, 알 수 없는 interrupt → `stage="idle"` + 에러 메시지 |
| `project_type` 필터 추가 (2차) | 슬라이드 탭 필터에 사업유형 4종(구축·운영·유지보수·컨설팅·기타) Selectbox 추가 |
| JSON 파싱 실패 UI 알림 (2차) | `_warn_if_parse_failed()` — `raw_output` 키 감지 시 `st.warning()` 표시 |
| `get_app()` docstring 수정 (2차) | MemorySaver 반환임을 명시, 운영 패턴은 SqliteSaver 사용 안내 |
| dead `node_llm` PM 설정 제거 (2차) | interrupt 노드(pm_step2_informal·pm_step4·pm_step6)는 LLM 불필요 |
| `Pt` 미사용 import 제거 (2차) | `pptx_parser.py` — `from pptx.util import Pt` 삭제 |

---

### Phase 5 — Next.js + FastAPI 최종 UI (Week 4~5)

**목표:** Streamlit MVP 검증 후 상용 수준 UI로 전환

```
백엔드 (FastAPI)
├── POST /api/rfp/analyze            RFP(PDF) 업로드 → 분석 결과
├── POST /api/strategy/generate      제안전략 생성 (SSE 스트리밍)
├── POST /api/strategy/resume        PM 입력 후 그래프 재개 (thread_id)
├── GET  /api/sessions/{thread_id}   세션 상태·체크포인트 조회
├── GET  /api/projects               프로젝트 목록 조회
├── GET  /api/slides/search          슬라이드 샘플 검색 (topic, top_k, filters)
└── GET  /api/slides/{project}/{n}   슬라이드 PNG 정적 파일 서빙

프론트엔드 (Next.js)
├── App Router 기반
├── 제안전략 수립 페이지
│   ├── 7단계 스텝퍼 UI (진행 상태 시각화)
│   ├── PM 입력 폼 (각 단계별)
│   └── 전략 생성 실시간 스트리밍 (SSE)
└── 슬라이드 샘플 검색 페이지
    ├── 검색 인풋 + 필터 패널
    ├── 슬라이드 이미지 그리드 (Masonry 레이아웃)
    └── 슬라이드 클릭 시 전체화면 모달 + 선정 사유
```

> Streamlit MVP에서 검증된 파이프라인 로직을 FastAPI 엔드포인트로 그대로 이전.

#### 📋 내가 해야 할 일

| # | 작업 | 비고 |
|---|------|------|
| 1 | **Phase 4 불편사항·개선사항 목록 정리** — Streamlit MVP 사용 중 메모한 내용 취합 | Next.js UI 요구사항 문서로 정리 |
| 2 | **FastAPI 엔드포인트 테스트** — `curl` 또는 HTTP 클라이언트로 각 API 동작 확인 | PDF 업로드·SSE 스트리밍·세션 재개 위주 |
| 3 | **Next.js UI 검토** — 7단계 스텝퍼 UI, 슬라이드 그리드, 모달 동작 확인 | 기능 완성도 및 응답성 체크 |
| 4 | **최종 산출물 Markdown 포맷 확인** — 4대 섹션 구조가 Word/HWP 변환 시 호환되는지 테스트 | 실제 제안서 작업 전 확인 |
| 5 | **FR-27: LLM 토큰 단위 스트리밍** — FastAPI SSE 엔드포인트에서 `llm.stream()` 연결 | Streamlit MVP는 노드 완료 단위 스트리밍만 지원; 토큰 단위는 Phase 5로 이관 |

---

### 코드 리뷰 결과 (Phase 1~4) {#코드-리뷰}

**1차 리뷰 (2026-06-19):** Phase 1~4 전체 Python 소스에 대해 Angle A(정확성)·B(제거된 가드)·C(크로스파일 호출자)·효율 각도로 high-effort 코드 리뷰를 실시하고, **버그 22건**을 수정했습니다. 검증 스크립트(`scripts/verify_phase3.py`) **97/97 통과**.

**2차 리뷰 (2026-06-19):** 1차 수정 반영 확인 후 잔여 갭 5건 추가 수정 (아래 §2차 수정 참고).

#### Phase 1 수정 (7건)

| 심각도 | 파일 | 수정 내용 |
|--------|------|-----------|
| HIGH | `parsers/pptx_parser.py` | `ph.idx in (0, 1)` → `ph.idx == 0` — idx=1 본문 플레이스홀더가 제목을 덮어쓰는 버그 |
| HIGH | `slide_sampler/renderer.py` | `fitz.open()` → `with fitz.open() as doc:` — 예외 시 파일 핸들 누수 방지 |
| HIGH | `ingestion/chunker.py` | PNG 경로 `"data/projects/..."` 상대경로 → `project_dir.parent` 기반 절대경로 |
| MEDIUM | `ingestion/chunker.py` | methodology 병합 시 `tokenize_for_bm25(전체)` 반복 호출 → `+= tokenize_for_bm25(text)` 증분 추가 (O(n²)→O(n)) |
| MEDIUM | `ingestion/indexer.py` | `_upsert` 내 `payload={k:v if k!="text"} + payload["text"]=...` dead code → `dict(chunk)` 단순화 |
| LOW | `ingestion/chunker.py` | `_kiwi = Kiwi()` 모듈 레벨 즉시 초기화 → `_get_kiwi()` 지연 초기화 |
| LOW | `rag/retriever.py` | 동일 Kiwi 지연 초기화 적용 |

#### Phase 2 수정 (4건)

| 심각도 | 파일 | 수정 내용 |
|--------|------|-----------|
| HIGH | `slide_sampler/searcher.py` | `get_embedder(cfg)` 매 검색마다 호출 (bge-m3 재로드) → `_get_cached_embedder()` 모듈 캐시 |
| MEDIUM | `pipeline/nodes/retriever_node.py` | `metadata` dict 직접 변형 → `dict()` 얕은 복사 (Phase 3 수정에서 누락) |
| MEDIUM | `rag/retriever.py` | `BM25Okapi([[]])` avgdl=0 divide-by-zero → `any(token_corpus)` 체크 후 빈 경우 Dense 결과로 대체 |
| LOW | `rag/retriever.py` | Kiwi 지연 초기화 (Phase 1과 동일 패턴) |

#### Phase 3 수정 (11건)

| 심각도 | 파일 | 수정 내용 |
|--------|------|-----------|
| HIGH | `llm/factory.py` | `OmegaConf.load("configs/llm/solar.yaml")` CWD 의존 상대경로 → `Path(__file__)` 기반 절대경로 |
| HIGH | `pipeline/nodes/strategy_generator.py` | `_split_step7` off-by-one — `-1` sentinel 사용 시 `text[p0:-1]`로 마지막 문자 유실 → `len(text)` sentinel로 수정 |
| HIGH | `pipeline/nodes/rfp_analyzer.py` | `metadata` dict 직접 변형 3곳 → `dict()` 얕은 복사 |
| HIGH | `pipeline/nodes/strategy_generator.py` | 동일 `metadata` 얕은 복사 2곳 |
| MEDIUM | `pipeline/nodes/rfp_analyzer.py` | `" extract_step1"` leading space 타이포 → `"extract_step1"` |
| MEDIUM | `pipeline/graph.py` | `checkpointer=None` 시 interrupt 비활성화 → `warnings.warn()` 추가 |
| MEDIUM | `slide_sampler/searcher.py` | `project_name=r.payload.get("doc_id", "")` → `r.doc_id` (payload에 해당 키 없어 항상 빈 문자열) |
| MEDIUM | `slide_sampler/searcher.py` | `id(c)` 기반 score_map → `c.rerank_score` 직접 할당 방식 |
| MEDIUM | `slide_sampler/searcher.py` | `get_reranker()` 전역 싱글턴 — double-checked locking (`threading.Lock`) 추가 |
| LOW | `pipeline/nodes/` | `_load_prompt()` rfp_analyzer·strategy_generator 중복 → `_prompt_utils.py` 공통 유틸로 추출 |
| LOW | `app/streamlit_app.py` | LLM 선택 변경 시 app 재생성, SQLite 연결 명시 종료, `_resume_after_pm` dead param 제거, 알 수 없는 interrupt 처리 |

#### 2차 추가 수정 (5건, 2026-06-19)

| 심각도 | 파일 | 수정 내용 |
|--------|------|-----------|
| MEDIUM | `app/streamlit_app.py` | 슬라이드 탭에 `project_type`(사업유형) 필터 추가 — PLAN 명세 갭 해소 |
| MEDIUM | `app/streamlit_app.py` | JSON 파싱 실패 시 `_warn_if_parse_failed()` → `st.warning()` 표시 |
| LOW | `pipeline/graph.py` | `get_app()` docstring 수정 — MemorySaver 반환임을 명시, 운영 패턴 안내 |
| LOW | `app/streamlit_app.py` | dead `node_llm` PM 설정 제거 — interrupt 노드는 LLM 불필요 |
| LOW | `parsers/pptx_parser.py` | `from pptx.util import Pt` 미사용 import 제거 |

---

#### 슬라이드 분류·검색 품질 개선 (2026-06-22) {#검색-품질-개선}

슬라이드 샘플 검색에서 개요·목차 슬라이드가 상위에 노출되는 문제를 해결하고,
Dense 점수가 낮지만 BM25로 구제 가능한 슬라이드도 결과에 포함되도록 파이프라인을 개선했습니다.

| 파일 | 변경 내용 | 효과 |
|------|-----------|------|
| `ingestion/slide_classifier.py` | **신규** — `detect_slide_type()` · `SectionEnricher` · `extract_hierarchy_labels()` | 슬라이드 유형(toc/overview/detail/general) 정규 분류 |
| `ingestion/chunker.py` | `slide_type` · `hierarchy_labels` · `section_context` 메타 추가 · SectionEnricher로 개요→상세 섹션 제목 전파(max 12장) | 상세 슬라이드에 섹션 컨텍스트 보강 색인 |
| `rag/retriever.py` | Dense 사전 필터 0.50→**0.35** · RRF 반환 `top_k*4`(union 전체) · `hybrid_alpha` 0.7→**0.8** | BM25 고순위·Dense 저순위 슬라이드도 reranker 후보 풀에 포함 |
| `slide_sampler/searcher.py` | 실시간 slide_type 재분류 · overview/toc 패널티(0.3×) · **dedup을 reranker 이후로 이동** · `_MIN_RERANK_SCORE=0.05` | 개요 슬라이드 후순위, 상세 슬라이드 우선 선별 |

**slide_classifier.py 분류 패턴 정확도 개선:**

| 패턴 | 이전 | 이후 | 수정 이유 |
|------|------|------|---------|
| `_SEQUENTIAL_NUMS` (연속 숫자 나열 → toc) | 5개 이상 | **9개 이상** | "1 2 3 4 5" 형태 특징·단계 번호 오감지 방지 |
| `_NUMBERED_ITEMS` (순번 항목 → overview) | `\d{2,}\.` | **`0[1-9]\.`** | "12. 데이터 이관" 같은 슬라이드 자체 번호 제외, 공공 제안서 표준 "01~09." 형식만 감지 |
| `_HIER_LABEL` 임계값 (overview 판정) | 2개 이상 | **3개 이상** | 섹션 헤더 "전략 2" + 내용 "전략 1" 조합으로 오감지된 개별 전략 상세 슬라이드 제거 |

**분류 결과 개선 (1,160 청크 기준):**

| 유형 | 이전 | 이후 |
|------|------|------|
| toc | 55건 (4.7%) | 43건 (3.7%) |
| overview | 37건 (3.2%) | 14건 (1.2%) |
| detail | 29건 (2.5%) | 30건 (2.6%) |
| general | 1039건 (89.6%) | 1073건 (92.5%) |

**확인된 검색 품질 개선 사례 ("조직 구성 전략" 쿼리):**

| 슬라이드 | 이전 문제 | 이후 결과 |
|---------|----------|----------|
| NHIS slide35 (개요 — 조직구성 섹션 헤더) | rerank=0.9533 → **1위** | overview 패널티(0.3×) → adj=0.2860 → 14위로 하락 |
| NHIS slide36 (상세 — 조직구성 구체 내용) | Dense=0.44 → min_score=0.50 필터에 걸려 **결과 제외** | 0.35 가드 통과 + BM25 13위 구제 → reranker 후보 포함 → **7위** |
| KERIS slide41 (목차 인덱스 "1~9") | **9위** 노출 | toc 분류 → 패널티 → 결과 제외 |
| NHIS slide13 (전략 목록 개요) | **10위** 노출 | overview 분류 → 패널티 → 결과 제외 |

**dedup 순서 변경의 핵심 효과:**  
이전: dedup → reranker → 패널티 (개요 슬라이드가 프로젝트 슬롯을 먼저 차지 후 상세 슬라이드 탈락)  
이후: reranker → 패널티 → dedup (관련도 높은 상세 슬라이드가 개요보다 먼저 슬롯 확보)

---

### 알려진 기술 부채 및 설계 한계 {#기술-부채}

아래 항목은 현재 동작에는 영향 없으나, Phase 5 또는 그 이후에 정리 권장:

| ID | 항목 | 영향 | 권장 시점 |
|----|------|------|----------|
| M3 | RFP `[:12000]` truncation — STEP 1~3 프롬프트 전부 | 대형 RFP(100페이지+) 후반 요구사항 누락 가능 | Phase 6 품질 측정 후 청킹 또는 요약 전처리 검토 |
| M4 | STEP 7 CSF·스토리보드 list에 원문 통째 저장 | 구조화 재활용 어려움 (현재는 Markdown 그대로 출력) | Phase 5 데이터 모델 정비 시 |
| L1 | `_tcp_reachable()` — indexer·vectorstore 중복 | 수정 번거로움 | 공통 `utils/network.py`로 추출 |
| L1 | Kiwi 토크나이저 — chunker·retriever 중복 선언 | 동작 정상, 초기화 비용 1회 | 공통 `utils/kiwi.py`로 추출 |
| L2 | `streamlit_app.py` 850줄 단일 파일 | 유지보수 어려움 | Phase 5 FastAPI 전환 시 분리 |
| L6 | `clear_cache()` 매 PM resume마다 호출 | LLM 싱글턴 재생성 비용 | factory 캐시 키를 cfg 기반으로 교체 후 제거 |

---

### Phase 6 — 평가 및 최적화 (Week 3 중반 ~ Week 4)

**PM 시범 사용 품질 평가 (PRD G2·G3):**
- **G2 — RFP 추출 정확도:** STEP 1~3 결과에서 PM이 수정한 필드 수 / 전체 필드 수 → **목표 < 30%**
- **G3 — 전략 초안 채택률:** STEP 5·7 산출물 중 PM이 편집 후 실제 사용한 비율 → **목표 ≥ 70%**
- PM 시범 사용(R3) 후 스프레드시트 또는 간단 설문으로 1~2건 측정 → Phase 6 튜닝 입력

**RAG 품질 평가:**
- Hit Rate: 관련 문서가 top_k 내 포함 비율
- MRR: 첫 번째 관련 문서 순위

**슬라이드 샘플러 품질 평가:**
- 주제 관련성: 검색된 슬라이드가 주제와 실제로 관련 있는지 PM 피드백 수집
- 중복성: 동일 프로젝트 슬라이드 과집중 여부 확인 → `max_per_project` 파라미터 튜닝
- 사유 품질: LLM 선정 사유의 구체성·유용성 프롬프트 개선

**최적화 대상:**
- `hybrid_alpha` 튜닝 (키워드 vs 의미 검색 비율)
- 청킹 크기 조정
- 프롬프트 개선
- BM25 `tokenized_text` payload: Phase 1에서 이미 구현 완료 (인덱싱 시 사전 분석·저장)

#### 📋 내가 해야 할 일

| # | 작업 | 비고 |
|---|------|------|
| 1 | **G2 측정** — RFP 2~3건으로 STEP 1~3 추출 결과에서 수정한 필드 수 스프레드시트에 기록 | 목표: 수정률 < 30% |
| 2 | **G3 측정** — STEP 5·7 전략 산출물 중 실제 제안서에 활용한 비율 기록 | 목표: 채택률 ≥ 70% |
| 3 | **슬라이드 검색 관련성 평가** — 쿼리 10개로 테스트, 각 결과 5점 척도로 평가 | `max_per_project` 튜닝 기준 데이터 |
| 4 | **파라미터 조정 승인** — `hybrid_alpha`, 청킹 크기, 프롬프트 개선 방향 최종 결정 | Phase 6 산출물: 확정된 `configs/` |
| 5 | **추가 RFP 수집 완료 여부 확인** — 목표 43건 중 현재 26건, 17건 추가 수집 진행 상황 점검 | 품질 높은 RFP일수록 RAG 정확도 향상 |

---

## 14. 개발 일정 (요약)

### Week 0 — 선행 작업 (사용자)

| 구분 | 작업 | 상태 |
|------|------|------|
| 데이터 | review.csv 검토/수정 → `organize_data.py Phase 2 --apply` | ✅ 완료 |
| 데이터 | 나라장터에서 우선순위 RFP 추가 수집 (17건 미수집) | ⚠️ 진행 중 |
| 환경 | Solar Pro API 키 / Claude API 키 발급 | — |
| 환경 | Mac Mini M5 Pro: mlx-lm + Qwen3.5-9B (4-bit) + Qdrant Docker | — |
| 환경 | RTX 3090: CUDA 임베딩·PNG 렌더링 (**초기 빌드 시에만**) | — |
| 환경 | **LibreOffice** — Mac·RTX 양쪽 설치 (PNG 렌더링) | — |

```bash
# macOS (Mac Mini)
brew install libreoffice

# Linux (RTX 3090)
apt-get install -y libreoffice
```

---

### Week 1 — Phase 1 + 2: 데이터 처리 및 검색 파이프라인 (RTX 3090 초기 빌드)

```
Phase 1  ✅ 코드 완료 (2026-06-18) — 인덱싱·렌더링 실행 중
         [RTX 3090] PPTX/PDF 파싱 → 슬라이드 청킹 → bge-m3 CPU 임베딩 (CUDA 드라이버 버전 이슈)
         → data/vectorstore/ 로컬 저장 (Docker 미설치 → 로컬 파일 모드 자동 폴백)
         → LibreOffice PNG 렌더링 → data/projects/{id}/slides/
         산출물: src/ingestion/ + src/slide_sampler/renderer.py + configs/ + main.py 전체 구현
         ★ Mac Qdrant 전환: QDRANT_HOST=<Mac IP> 환경변수 설정 후 동일 명령어 실행

Phase 2  [Mac Mini] Qdrant Dense + BM25 + RRF 검색 모듈
         tags.json 메타 연동, 메타데이터 필터 (domain / project_type / result)
         산출물: src/rag/ 모듈 완성, 검색 품질 기초 검증
         ⚠️ Qdrant 1.18.0+ API: query_points() 사용 (search() 제거됨 — §13 Phase 2 구현 시 주의)
```

---

### Week 2 — Phase 3: LangGraph 7단계 파이프라인

```
Phase 3  GraphState TypedDict (step1~step7 전체 필드)
         자동 노드: parse_rfp → extract_step1~3
         PM 입력 노드: pm_step2_informal, pm_step4, pm_step6  (interrupt_before)
         AI 도출 노드: retrieve_rag (병렬), generate_step5, generate_step7
         LLM 추상화: Solar Pro / Claude / Qwen3.5 Hydra config 전환
         산출물: src/pipeline/ 완성, 단일 RFP로 end-to-end 동작 검증

         [추가 태스크] 최종 산출물 Markdown 표준 구조 확정
           - format_output 노드 프롬프트 템플릿에 7단계 통합 문서 양식 고정
           - **문서 4대 섹션** (STEP 7-3 MECE 4영역과 별개 — PRD §7.3):
             ① 고객 분석(STEP 1~3) / ② 경쟁 포지션(STEP 4) /
             ③ 차별화 전략(STEP 5~6) / ④ 사업수행전략(STEP 7)
           - 각 영역: 제목·핵심 메시지·테이블·이행방안 순 고정 → Word/HWP 변환 호환
           - 템플릿 위치: src/pipeline/nodes/output_formatter.py 내 상수로 관리
```

---

### Week 3 — Phase 4 + 6: Streamlit MVP + 검증 (Mac Mini 운영)

```
Phase 4  [탭 1] 제안전략 수립
           RFP 업로드 → 7단계 진행 상태 표시
           PM 입력 폼 (비공식 요구사항·경쟁력 분석·의사결정)
           각 단계 결과 스트리밍 + 최종 산출물 Markdown 다운로드
         [탭 2] 슬라이드 샘플 검색                          ← 슬라이드 샘플러
           주제 입력 → 슬라이드 이미지 그리드 (**3열**, 기본 10장)
           LLM 선정 사유 카드 + 도메인/사업유형/수주여부 필터
         산출물: Streamlit MVP 전기능 동작, PM 시범 사용 가능

Phase 6  RAG 품질: Hit Rate / MRR 측정 → hybrid_alpha 튜닝
         PM 시범: G2(추출 수정률) · G3(전략 채택률) 측정
         슬라이드 샘플러: 주제 관련성 PM 피드백 → max_per_project 튜닝
         프롬프트: 7단계 각 노드 프롬프트 개선
         산출물: 최적화 파라미터 확정, configs/ 업데이트
```

---

### Week 4~5 — Phase 5: Next.js + FastAPI 최종 UI

```
Phase 5  [FastAPI — Mac Mini]
           POST /api/rfp/analyze · POST /api/strategy/generate
           POST /api/strategy/resume · GET /api/sessions/{id}
           GET /api/slides/search · GET /api/slides/{project}/{n}
         [Next.js]
           제안전략 수립 페이지 (7단계 스텝퍼 UI + PM 입력 폼)
           슬라이드 샘플 검색 페이지 (Masonry 그리드 + 전체화면 모달)
         산출물: 상용 수준 UI 완성, Streamlit MVP 대체
```

---

### 전체 일정 한눈에

| 주차 | Phase | 주요 산출물 | 슬라이드 샘플러 |
|------|-------|------------|----------------|
| Week 0 | 선행 | Mac 운영 환경 + RTX 빌드 환경 | LibreOffice · Qdrant(Mac) |
| Week 1 | 1·2 | Qdrant DB (RTX 빌드→Mac) + RAG | **PNG 캐시 (RTX에서 1회 생성)** |
| Week 2 | 3 | LangGraph 7단계 파이프라인 | — |
| Week 3 | 4·6 | Streamlit MVP 전기능 | **슬라이드 검색 탭 (이미지+사유)** |
| Week 4~5 | 5 | Next.js + FastAPI 최종 UI | **검색 API + 이미지 그리드 UI** |

---

## 15. 환경 변수

```bash
# .env (Mac Mini M5 Pro — 운영) — .env.template에서 복사 후 값 입력
SOLAR_API_KEY=up_xxxxxxxxxxxxxxxxxxxx
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxx   # Claude API (선택)

# 로컬 LLM (MLX 1순위, 동일 포트)
LOCAL_LLM_BASE_URL=http://localhost:11434

# Qdrant (Mac Mini 로컬 — 운영·유일한 DB)
QDRANT_HOST=localhost
QDRANT_PORT=6333

# 세션 체크포인트 (SqliteSaver — LangGraph thread_id 기반)
SESSIONS_DB_PATH=data/sessions.db

# RTX 3090 초기 빌드 시에만 (셸 export 또는 RTX용 .env)
# QDRANT_HOST=192.168.x.x                          # Mac Mini IP
```

---

## 16. 의존성 (requirements.txt)

> 아래 내용은 `requirements.txt`와 동기화 상태를 유지한다. 실제 설치는 `pip install -r requirements.txt` 사용.

**공통 (Mac Mini·RTX 3090 모두):**
```
# LLM 클라이언트
anthropic>=0.109.1          # Claude API (claude.py)
openai>=1.30.0              # Solar Pro (OpenAI 호환) + qwen_local OpenAI 호환 API

# LangGraph / LangChain
langgraph>=0.2.0
langgraph-checkpoint-sqlite>=0.1.0  # SqliteSaver — 세션 영속 체크포인트 (data/sessions.db)
langchain>=0.3.0
langchain-community>=0.3.0
langchain-openai>=0.2.0     # Solar Pro / Ollama OpenAI 호환 래퍼

# 설정 관리
hydra-core>=1.3.0
omegaconf>=2.3.0

# RAG
sentence-transformers>=3.0.0  # bge-m3 임베딩 + bge-reranker-v2-m3 CrossEncoder
qdrant-client>=1.9.0
rank-bm25>=0.2.2
kiwipiepy>=0.18.0           # 한국어 형태소 분석 (BM25 쿼리 토크나이저)

# 파일 파싱
python-pptx>=1.0.0
pdfplumber>=0.11.0
pymupdf>=1.24.0

# UI (MVP — Phase 4)
streamlit>=1.35.0

# 백엔드 API (Phase 5 — Next.js + FastAPI)
fastapi>=0.111.0
uvicorn[standard]>=0.30.0
python-multipart>=0.0.9     # RFP 파일 업로드

# 유틸리티
httpx>=0.27.0
python-dotenv>=1.0.0
tqdm>=4.66.0
```

**Mac Mini M5 Pro 전용 (requirements.txt에 포함, 기본 활성):**
```
mlx-lm>=0.19.0           # Apple Silicon 네이티브 LLM 서버 (mlx_lm.server)
torch                     # pip 기본 (MPS 자동 지원)
```

**RTX 3090 Linux 추가 (초기 빌드 — CUDA 임베딩·렌더링):**
```
# CUDA 12.1 기준
# pip install torch --index-url https://download.pytorch.org/whl/cu121
# apt-get install libreoffice     # PNG 렌더링
# Ollama: 선택 (LLM 실험·파인튜닝 검증용)
```

---

## 17. PRD 요구사항 추적 (FR ↔ 구현)

> [PRD.md](./PRD.md) 기능 요구사항과 본 문서 구현 위치 매핑. 검증 시 PRD 수용 기준을 기준으로 한다.

| PRD ID | 요약 | PLAN 구현 위치 |
|--------|------|---------------|
| G1 | 7단계 end-to-end 완주 | Phase 3 CLI + Phase 4 Streamlit |
| G2 | RFP 추출 수정률 < 30% | Phase 6 PM 시범 측정 |
| G3 | 전략 초안 채택률 ≥ 70% | Phase 6 PM 시범 측정 |
| G4 | 슬라이드 참고 가치 | Phase 6 슬라이드 PM 피드백 |
| G5 | Mac Mini 단독 운영 | §4 운영 vs 빌드 |
| FR-01~05 | RFP PDF 업로드·STEP 1~3 추출 | §10 `parse_rfp`(50MB), `extract_step1~3` / Phase 4 탭1 |
| FR-10~12,14 | PM 입력·세션 | §10 `pm_step2/4/6`, SqliteSaver / Phase 4 폼 |
| FR-13 | 진행 표시(MVP) / 스테퍼(R5) | Phase 4 진행 표시 / Phase 5 스텝퍼 UI |
| FR-20~28 | STEP 5·7 AI 전략·Markdown | §10 `retrieve_rag`, `generate_step5/7`, `format_output`(문서 4대 섹션) |
| FR-30~35 | 슬라이드 샘플 검색 | §11 `slide_sampler/` / Phase 4 탭2 (3열) |
| FR-40~41 | LLM·RAG 설정 | §3.1 `node_llm`, §9 Hydra / Phase 4 사이드바 |
| FR-42 | Mac Mini 단독 운영 | §4 운영 vs 빌드 |
| NFR-01~07 | 성능·보안·LLM | §4 메모리, §3.1 temp, PRD §10 |

**LLM 역할:** PRD §6.3·§4.1 ↔ PLAN §3.1 (STEP 5·7 → LLM API 권장, 추출·구조화 → sLLM).
