# PDF Q&A Chatbot — Mini Project

> **RAG Study Day 7 | AI Engineer 설계 문서**
>
> LangChain으로 학습한 RAG 파이프라인을 실제 사용 가능한 시스템으로 통합한다.
> 최종 목표: macOS에서 PDF 논문을 열면 AI 챗봇이 자동으로 팝업되어 즉시 질문 가능한 환경 구축.

---

## 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [시스템 아키텍처](#2-시스템-아키텍처)
3. [Stage 1 — Streamlit RAG 챗봇](#3-stage-1--streamlit-rag-챗봇)
4. [Stage 2 — macOS 논문 뷰어 연동](#4-stage-2--macos-논문-뷰어-연동)
5. [기술 스택](#5-기술-스택)
6. [RAG 파이프라인 설계](#6-rag-파이프라인-설계)
7. [모듈 구조](#7-모듈-구조)
8. [실행 방법](#8-실행-방법)
9. [학습 연계 맵](#9-학습-연계-맵)
10. [엔지니어링 표준](#10-엔지니어링-표준)

---

## 1. 프로젝트 개요

### 배경

기존 RAG 학습(01~03)은 각 개념을 독립적으로 실습했다. 이 프로젝트는 **모든 구성요소를 하나의 작동하는 시스템으로 통합**하고, 실제 사용 시나리오(논문 읽기)에 적용하는 것을 목표로 한다.

### 해결하는 문제

```text
기존 방식                          개선 방식
─────────────────────────────      ─────────────────────────────
논문 읽기 → 모르는 내용 → 구글링   논문 열기 → 챗봇에 바로 질문
논문 전체를 다시 뒤짐               "3섹션 요약해줘" → 즉시 답변
컨텍스트 없이 LLM에게 질문          PDF 내용 기반의 정확한 답변
```

### 목표 사용자 경험 (Target UX)

```text
[사용자]  논문 PDF 더블클릭
[시스템]  RAG 엔진 자동 실행 (인덱싱)
[사용자]  팝업 챗봇에 질문: "이 논문의 핵심 contribution은?"
[시스템]  관련 섹션 검색 → 한국어로 답변 + 출처 페이지 표시
[사용자]  "그 방법론의 한계는?" (후속 질문)
[시스템]  대화 맥락 유지하며 정확한 검색 후 답변
```

---

## 2. 시스템 아키텍처

### 전체 아키텍처 (2-Stage)

```text
┌─────────────────────────────────────────────────────────────────┐
│                        STAGE 2 (macOS Layer)                    │
│                                                                 │
│   PDF 파일                macOS Automator                       │
│   더블클릭/우클릭  ──→   Quick Action / 메뉴바 앱  ──→  트리거  │
│                                                      │          │
└──────────────────────────────────────────────────────┼──────────┘
                                                       │ PDF 경로 전달
┌──────────────────────────────────────────────────────▼──────────┐
│                        STAGE 1 (Application Layer)              │
│                                                                 │
│  ┌──────────────────┐          ┌──────────────────────────────┐ │
│  │   Streamlit UI   │          │       RAG Engine             │ │
│  │                  │          │                              │ │
│  │  📂 PDF 업로드   │  invoke  │  PDF → Chunks → Index       │ │
│  │  💬 채팅 인터페이스│ ──────→ │  Query → Retrieve → Answer │ │
│  │  📄 출처 표시    │  ←────── │  History-Aware Retrieval    │ │
│  │  🔄 세션 상태    │  answer  │  BM25 + FAISS Ensemble     │ │
│  └──────────────────┘          └──────────────────────────────┘ │
│                                          │                      │
│                                          ▼ logging              │
│                                 ┌─────────────────┐            │
│                                 │  Terminal (백엔드) │           │
│                                 │  [INFO] 청크 생성  │           │
│                                 │  [RETRIEVER] 검색  │           │
│                                 │  [LLM] 생성 중...  │           │
│                                 └─────────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

### RAG 내부 데이터 흐름

```text
                         [ INDEXING PHASE ]
                         (PDF 업로드 시 1회 실행)

  PDF 파일
     │
     ▼
  PyPDFLoader ──→ [Page 1] [Page 2] ... [Page N]
                              │
                              ▼
  RecursiveCharacterTextSplitter
  chunk_size=500, overlap=50
                              │
                              ▼
              [chunk_1] [chunk_2] ... [chunk_M]
                    │               │
                    ▼               ▼
             BM25 Index        HuggingFace
          (rank_bm25)          Embeddings
               │            (all-MiniLM-L6-v2)
               │                   │
               │                   ▼
               │              FAISS Index
               │                   │
               └─────────┬─────────┘
                          ▼
                   EnsembleRetriever
                   weights=[0.5, 0.5]


                         [ QUERY PHASE ]
                         (질문마다 실행)

  사용자 질문 ("그 모델의 정확도는?")
     │
     ▼
  History-Aware Retriever
  ├─ 대화 히스토리 참조
  └─ LLM이 질문 재작성: "CNN 모델의 정확도는?"
                    │
                    ▼
           EnsembleRetriever (BM25 + FAISS)
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
     BM25 검색            FAISS 검색
  (키워드 매칭)          (의미 유사도)
          │                   │
          └─────────┬─────────┘
                    ▼
              RRF 알고리즘
          score = Σ 1/(k + rank)
                    │
                    ▼
           상위 k개 청크 선택
                    │
                    ▼
  ┌─────────────────────────────────┐
  │  Prompt                         │
  │  system: 연구 어시스턴트         │
  │  context: [검색된 청크들]        │
  │  history: [이전 대화 내역]       │
  │  human: 재작성된 질문            │
  └─────────────────────────────────┘
                    │
                    ▼
            ChatOllama (llama3.2:3b)
                    │
                    ▼
           답변 + 출처 페이지 번호
```

---

## 3. Stage 1 — Streamlit RAG 챗봇

### Stage 1 목표

브라우저에서 동작하는 PDF Q&A 챗봇. 어떤 PDF도 업로드해서 대화 가능.

### 구현 기능

| 기능 | 설명 | 구현 방법 |
| --- | --- | --- |
| PDF 업로드 | 임의의 PDF 파일 업로드 | `st.file_uploader` |
| 자동 인덱싱 | 업로드 시 BM25 + FAISS 자동 생성 | `st.session_state` 캐싱 |
| 하이브리드 검색 | 키워드 + 의미 검색 결합 | EnsembleRetriever |
| 대화 맥락 유지 | 후속 질문 처리 | History-Aware Retriever |
| 스트리밍 응답 | LLM 답변 실시간 출력 | `ChatOllama(streaming=True)` + `st.write_stream` |
| 출처 표시 | 답변 근거 페이지 표시 | Document metadata |
| 백엔드 로그 | 처리 과정 터미널 출력 | Python logging |

### UI 레이아웃

```text
┌──────────────────────────────────────────────────────┐
│  🤖 PDF Q&A 챗봇                                     │
├────────────────┬─────────────────────────────────────┤
│  [사이드바]    │  [메인 채팅 영역]                   │
│                │                                     │
│  📂 PDF 업로드 │  🧑 이 논문에서 사용한 모델은?      │
│  ──────────── │  🤖 CNN을 사용했습니다.              │
│  📊 문서 정보  │     📄 출처: p.3, p.7               │
│  - N 페이지   │                                     │
│  - M 청크     │  🧑 그 모델의 정확도는?              │
│  - 모델 정보  │  🤖 78.3%였으며...                  │
│                │     📄 출처: p.8                    │
│  🔄 대화 초기화│  ──────────────────────────────    │
│                │  💬 질문을 입력하세요...            │
└────────────────┴─────────────────────────────────────┘
```

### 핵심 설계 결정

#### `st.session_state` 활용 전략

```python
# PDF가 바뀔 때만 재인덱싱 (비용 절감)
if st.session_state.get("pdf_name") != uploaded_file.name:
    st.session_state.rag_engine = PDFChatbot(uploaded_file)
    st.session_state.pdf_name = uploaded_file.name
    st.session_state.messages = []
```

#### 로그 레벨 분리

```text
터미널 (개발자 뷰)        브라우저 (사용자 뷰)
──────────────────        ──────────────────
[INFO] PDF 로딩 중        ⏳ 로딩 중...
[INFO] BM25 인덱싱        ✅ 준비 완료!
[RETRIEVER] 4청크 검색    💬 답변 생성 중...
[LLM] 토큰 생성           🤖 [답변 출력]
```

---

## 4. Stage 2 — macOS 논문 뷰어 연동

### Stage 2 목표

PDF를 열면 Streamlit 챗봇이 자동으로 팝업. 논문을 읽으면서 즉시 질문 가능한 환경.

### 구현 방법 A: macOS Quick Action (우선 구현)

```text
PDF 파일 우클릭
       │
       ▼
"Q&A 챗봇으로 열기" (Quick Action)
       │
       ▼
Shell Script 실행
  1. Streamlit 서버 실행 (포트 8501)
  2. PDF 경로를 환경변수로 전달
  3. 브라우저에서 소형 창으로 열기
       │
       ▼
챗봇 창 팝업 (800×600, 항상 위에)
```

#### Automator 설정 흐름

```bash
# Automator → 새 Quick Action
# → 입력: PDF 파일
# → 동작: Shell Script 실행
export PDF_PATH="$1"
poetry run streamlit run app.py --server.port 8501
open -a "Google Chrome" --args --app=http://localhost:8501
```

### 구현 방법 B: 메뉴바 앱 (고도화)

```text
macOS 메뉴바
  🤖 아이콘 상주 (rumps 라이브러리)
       │
  클릭 → "PDF 선택" / "챗봇 열기" / "종료"
       │
  PDF 선택 → 자동 인덱싱 → 팝업 창
```

```python
# 메뉴바 앱 핵심 구조 (rumps)
import rumps

class PaperChatApp(rumps.App):
    def __init__(self):
        super().__init__("🤖")

    @rumps.clicked("PDF 선택 후 챗봇 열기")
    def open_chatbot(self, _):
        pdf_path = select_pdf_dialog()
        launch_streamlit(pdf_path)
        open_popup_window()
```

### Stage 2 추가 기술 요소

| 요소 | 기술 | 이유 |
| --- | --- | --- |
| 메뉴바 앱 | `rumps` | Python macOS 메뉴바 라이브러리 |
| 팝업 창 | `pywebview` or AppleScript | 항상 위에 뜨는 소형 창 |
| PDF 경로 감지 | 환경변수 / CLI 인자 | Stage 1 엔진 재사용 |
| 프로세스 관리 | `subprocess` | 백그라운드 서버 관리 |

---

## 5. 기술 스택

```text
Application Layer
├── Streamlit 1.x          — UI 프레임워크
├── Python 3.11            — 런타임
└── Poetry 2.3.2           — 패키지 관리

RAG Engine
├── LangChain Classic      — RAG 체인 구성
│   ├── EnsembleRetriever  — 하이브리드 검색
│   ├── create_history_aware_retriever
│   └── create_retrieval_chain
├── LangChain Community
│   ├── PyPDFLoader        — PDF 로딩
│   ├── BM25Retriever      — 키워드 검색
│   ├── FAISS              — 벡터 검색
│   └── ChatMessageHistory — 대화 저장
└── LangChain HuggingFace
    └── HuggingFaceEmbeddings (all-MiniLM-L6-v2)

LLM
└── Ollama (llama3.2:3b)   — 로컬 LLM (무료, 오프라인)

Evaluation
└── Ragas                  — RAG 품질 정량 평가 (Phase 3)
    ├── faithfulness        — 답변이 컨텍스트에 충실한가
    ├── answer_relevancy    — 답변이 질문에 관련된가
    └── context_precision   — 검색된 청크가 적절히 선택됐는가

Observability (선택)
└── LangSmith              — 체인 전체 추적·디버깅 (LANGCHAIN_TRACING=true)

macOS Integration (Stage 2)
├── macOS Automator        — Quick Action 등록
├── rumps                  — 메뉴바 앱
└── pywebview              — 네이티브 팝업 창
```

---

## 6. RAG 파이프라인 설계

### 하이브리드 검색 선택 이유

```text
논문 Q&A에서 발생하는 두 종류의 질문:

유형 A (키워드 중심)          유형 B (의미 중심)
──────────────────────        ──────────────────────
"CNN의 F1 score는?"           "이 모델이 잘 작동하나?"
"Spotify 피처 목록은?"        "연구의 한계점은?"
"표 3의 결과는?"              "저자들의 결론은?"
      │                              │
      ▼                              ▼
  BM25가 유리                  FAISS가 유리
      │                              │
      └──────────┬───────────────────┘
                 ▼
          Ensemble (RRF)
          두 방식의 강점 모두 활용
```

### History-Aware Retriever 필요 이유

```text
대화 흐름 예시:

Q1: "이 논문에서 사용한 딥러닝 모델은?"
A1: "CNN을 사용했습니다."

Q2: "그것의 정확도는?" ← "그것"이 뭔지 Retriever가 모름!

── 해결: History-Aware Retriever ──
Q2 + History → LLM이 재작성 → "CNN 모델의 정확도는?"
                                        │
                                        ▼
                               정확한 검색 가능!
```

### Retriever 설정값 (논문 Q&A 최적화)

```python
# BM25: 논문의 전문 용어 검색에 강함
bm25_retriever = BM25Retriever.from_documents(docs, k=4)

# FAISS: 의미적 질문 처리
faiss_retriever = faiss_db.as_retriever(
    search_type="mmr",           # 다양성 확보 (논문의 여러 섹션 커버)
    search_kwargs={"k": 4, "fetch_k": 20, "lambda_mult": 0.6}
)

# Ensemble: 균형 가중치 (논문 Q&A 기본값)
ensemble = EnsembleRetriever(
    retrievers=[bm25_retriever, faiss_retriever],
    weights=[0.5, 0.5]
)
```

### RAG 품질 평가 (Ragas)

"답변이 그럴듯하다"는 주관적 판단 대신, Phase 3에서 Ragas로 정량적 검증한다.

```text
3대 평가 지표:

  Faithfulness      : 0.0 ~ 1.0  ← 답변이 검색된 청크에 충실한가
                                    (환각(Hallucination) 탐지)
  Answer Relevancy  : 0.0 ~ 1.0  ← 답변이 질문에 관련된가
  Context Precision : 0.0 ~ 1.0  ← 검색된 청크가 실제로 필요한 내용인가

  Phase 3 통과 기준:
  Faithfulness ≥ 0.80, Answer Relevancy ≥ 0.85
```

`predicting_music.pdf` 기반 테스트 질문셋:

| 질문 | 평가 포인트 |
| --- | --- |
| "이 논문의 핵심 contribution은?" | Answer Relevancy |
| "사용된 오디오 피처 목록은 무엇인가?" | Faithfulness (정확한 열거) |
| "분류 모델의 정확도 수치는?" | Context Precision (수치 검색) |
| "그 모델의 한계는?" (후속 질문) | History-Aware 동작 확인 |
| "저자들이 제안한 향후 연구 방향은?" | 의미 검색 (FAISS 담당) |

---

## 7. 모듈 구조

```text
04_mini_project/
├── app.py              # Streamlit UI
│   ├── 사이드바: PDF 업로드, 문서 정보
│   ├── 채팅 인터페이스: 메시지 출력, 입력창
│   └── 세션 상태 관리: PDF 캐싱, 대화 히스토리
│
├── rag_engine.py       # RAG 파이프라인 (재사용 가능 모듈)
│   ├── class PDFChatbot
│   │   ├── __init__(pdf_source)    # 파일 경로 or 업로드 객체
│   │   ├── _build_index()          # BM25 + FAISS 인덱싱
│   │   ├── _build_chain()          # History-Aware RAG 체인
│   │   ├── chat(question, session) # 질문 → 답변 + 출처 반환 (스트리밍)
│   │   └── get_doc_info()          # 페이지 수, 청크 수 반환
│   └── 로깅 설정 (터미널 출력)
│
├── evaluate.py         # Ragas 평가 스크립트 (Phase 3)
│   ├── TEST_QUESTIONS  # predicting_music.pdf 기반 검증 질문셋
│   └── run_ragas()     # Faithfulness / Answer Relevancy / Context Precision 측정
│
└── README.md           # 이 문서
```

### `rag_engine.py` 인터페이스 설계

```python
from langchain_core.documents import Document

class PDFChatbot:
    def __init__(self, pdf_source: str | UploadedFile) -> None: ...
    def chat(self, question: str, session_id: str) -> dict[str, str | list[Document]]: ...
    def get_doc_info(self) -> dict[str, int | str]: ...

# chat() 반환 구조
result = chatbot.chat("질문", session_id="user_1")
# → {"answer": str, "sources": list[Document], "query": str}

# Stage 1 (Streamlit)에서 사용
chatbot = PDFChatbot(uploaded_file)      # 업로드된 파일 객체

# Stage 2 (macOS 연동)에서 재사용
chatbot = PDFChatbot("/path/to/paper.pdf")  # 로컬 파일 경로
```

`PDFChatbot`은 입력 소스(업로드 객체 vs 파일 경로)만 추상화하고, 내부 RAG 로직은 동일하게 재사용.

---

## 8. 실행 방법

### Stage 1 실행

```bash
# 프로젝트 루트에서
poetry run streamlit run 04_mini_project/app.py

# 브라우저에서 자동으로 열림
# http://localhost:8501
```

### Stage 2 실행 (macOS Quick Action 등록 후)

```bash
# PDF 파일 우클릭 → "Q&A 챗봇으로 열기"
# 또는 CLI로 직접 실행
PDF_PATH="/path/to/paper.pdf" poetry run streamlit run 04_mini_project/app.py
```

### 백엔드 로그 확인

Streamlit 실행 터미널에서 실시간 확인:

```text
[2026-02-20 10:00:01] INFO      PDF 로딩: paper.pdf
[2026-02-20 10:00:02] INFO      청크 분할 완료: 87개
[2026-02-20 10:00:04] INFO      BM25 인덱싱 완료
[2026-02-20 10:00:08] INFO      FAISS 인덱싱 완료
[2026-02-20 10:00:10] RETRIEVER 질문 재작성: "CNN 모델의 정확도는?"
[2026-02-20 10:00:10] RETRIEVER 검색된 청크: 4개 (p.3, p.7, p.8, p.9)
[2026-02-20 10:00:12] LLM       답변 생성 완료 (2.1s)
```

---

## 9. 학습 연계 맵

이 프로젝트에서 사용하는 기술과 학습 모듈의 연결:

```text
01_langchain_basics
  └─ LCEL 파이프(|), RunnablePassthrough          → rag_engine.py 체인 구성

02_rag_pipeline
  ├─ PyPDFLoader, RecursiveCharacterTextSplitter  → PDF 전처리
  ├─ HuggingFaceEmbeddings (all-MiniLM-L6-v2)    → 벡터 생성
  └─ FAISS.from_documents()                       → 벡터 인덱싱

03_retriever_chain/01 — Retriever 전략
  └─ MMR (lambda_mult=0.6)                        → FAISS 검색 다양성

03_retriever_chain/02 — Ensemble Retriever
  └─ BM25 + FAISS, RRF weights=[0.5, 0.5]        → 하이브리드 검색

03_retriever_chain/03 — 대화형 RAG
  └─ RunnableWithMessageHistory, session_id       → 멀티턴 대화

03_retriever_chain/04 — History-Aware Retrieval
  └─ create_history_aware_retriever               → 후속 질문 처리

                      ↓ 모두 통합

              04_mini_project/rag_engine.py
                 (재사용 가능한 핵심 모듈)

                      ↓ Stage 2에서 재사용

              macOS 메뉴바 앱 / Quick Action
```

---

## 개발 우선순위

```text
Phase 1  rag_engine.py 구현 (RAG 엔진 모듈화)
         완료 기준: PDFChatbot이 파일 경로·업로드 객체 모두 처리, chat() 정상 반환

Phase 2  app.py 구현 (Streamlit UI)
         완료 기준: PDF 업로드 → 스트리밍 답변 → 출처 표시 전 과정 동작

Phase 3  Ragas 평가 (predicting_music.pdf 정량 검증)
         완료 기준: Faithfulness ≥ 0.80 AND Answer Relevancy ≥ 0.85

Phase 4  macOS Quick Action 등록 (Stage 2 진입)
         완료 기준: PDF 우클릭 → 챗봇 팝업 자동 실행 (포트 충돌 없이)

Phase 5  메뉴바 앱 고도화 (선택)
         완료 기준: 메뉴바 아이콘에서 PDF 선택 → 팝업 실행
```

---

## 10. 엔지니어링 표준

학습 단계지만 프로덕션 수준의 코드 습관을 실천한다.

| 표준 | 적용 방식 | 이유 |
| --- | --- | --- |
| **Type Safety** | 모든 함수·클래스에 Python Type Hints 적용 | 런타임 오류 방지, IDE 자동완성 향상 |
| **Streaming Response** | `ChatOllama(streaming=True)` + `st.write_stream` | 답변을 기다리지 않고 실시간으로 확인 |
| **Config 중앙화** | 청크 크기·가중치 등 파라미터를 상수로 분리 | 코드 변경 없이 파라미터 조정 가능 |
| **Observability** | 터미널 로깅 기본 + LangSmith 선택 연동 | 체인 전체 흐름 추적, 디버깅 가시성 확보 |

### Config 예시

```python
# rag_engine.py 상단에 모아서 관리
CHUNK_SIZE: int = 500
CHUNK_OVERLAP: int = 50
RETRIEVER_K: int = 4
ENSEMBLE_WEIGHTS: list[float] = [0.5, 0.5]
EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
LLM_MODEL: str = "llama3.2:3b"
```

### LangSmith 선택 연동

```bash
# .env 파일에 추가 (없으면 비활성화, 터미널 로깅만 동작)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_key_here
LANGCHAIN_PROJECT=rag-mini-project
```

---

RAG Study — Day 7 | 작성일: 2026-02-20
