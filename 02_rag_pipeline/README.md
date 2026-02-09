# 02_rag_pipeline - RAG 파이프라인 핵심

> Day 3-4 학습: RAG의 4단계 파이프라인을 이해하고, End-to-End로 연결하여 PDF 논문에 질문하는 시스템 구축

---

## 전체 구조

```
[문서]  ─→  Loader  ─→  Splitter  ─→  Embedding  ─→  VectorStore
                                                          │
[질문]  ─→  Embedding  ─→  Retriever  ─→  Context + Prompt  ─→  LLM  ─→  [답변]
```

```
02_rag_pipeline/
├── 01_document_loaders.py   # 1단계: 다양한 소스에서 문서 로딩
├── 02_text_splitters.py     # 2단계: 문서를 청크로 분할
├── 03_embeddings.py         # 3단계: 텍스트를 벡터로 변환
├── 04_vectorstore.py        # 4단계: 벡터 저장 & 유사도 검색
├── 05_rag_end_to_end.py     # 종합: 전체 파이프라인 통합
└── README.md
```

---

## 실습 데이터

| 소스 | 내용 |
|------|------|
| **PDF** | `predicting_music.pdf` - CNN 기반 Spotify 음악 인기도 예측 논문 (12페이지, arXiv 2025) |
| **Web** | `https://research.atspotify.com/` - Spotify Research 블로그 |

---

## 파일별 상세

### 01_document_loaders.py - 문서 로딩

**학습 목표:** 다양한 소스(PDF, 웹, 텍스트, 폴더)에서 문서를 로딩하고 Document 객체 구조를 이해한다.

**핵심 개념:**
- `Document` = `page_content`(텍스트) + `metadata`(출처, 페이지 번호 등)
- `load()` vs `lazy_load()` - 메모리 전략에 따른 선택

**다루는 Loader:**

| Loader | 대상 | 특징 |
|--------|------|------|
| PyPDFLoader | PDF 파일 | 페이지별 Document 생성 |
| WebBaseLoader | 웹 페이지 | HTML을 텍스트로 변환 |
| TextLoader | 텍스트 파일 | 파일 전체가 1개 Document |
| DirectoryLoader | 폴더 내 파일 | glob 패턴으로 필터링 |

**실습 결과:**
- PDF 12페이지 로딩 (메타데이터에 저자, DOI, arXiv ID 자동 추출)
- Spotify Research 웹 페이지 크롤링 성공
- LLM 연결하여 논문 1페이지 요약 생성

---

### 02_text_splitters.py - 텍스트 분할

**학습 목표:** 긴 문서를 적절한 크기의 청크로 분할하는 전략을 이해하고, chunk_size/overlap 파라미터의 영향을 실험한다.

**핵심 개념:**
- `chunk_size`: 각 청크의 최대 크기
- `chunk_overlap`: 청크 간 겹치는 부분 (문맥 단절 방지)
- `RecursiveCharacterTextSplitter`: 다중 구분자(`\n\n` → `\n` → `. ` → ` `)를 순서대로 시도하여 의미 단위 보존
- `split_text()` vs `split_documents()`: 메타데이터 보존 여부

**실습 결과:**

| 설정 | 청크 수 | 평균 크기 |
|------|---------|----------|
| size=200, overlap=0 | 278개 | 134자 |
| size=200, overlap=50 | 287개 | 136자 |
| **size=500, overlap=50** | **90개** | **423자** |
| size=1000, overlap=100 | 46개 | 834자 |

- overlap 시각화: `A(100)B(20)` → `A(10)B(100)C(10)` 경계 문맥 보존 확인
- 토큰 기반 분할(tiktoken)과 글자 기반 분할 비교

**권장 설정:** `chunk_size=500, overlap=50` (논문/기술문서 범용)

---

### 03_embeddings.py - 임베딩

**학습 목표:** 텍스트를 벡터로 변환하는 임베딩의 원리를 이해하고, 코사인 유사도로 의미 검색을 직접 구현한다.

**핵심 개념:**
- 임베딩: 텍스트 → 고정 길이 숫자 벡터 (의미의 수치화)
- `embed_query()`: 검색 질문 1개 임베딩
- `embed_documents()`: 문서 여러 개 일괄 임베딩
- 코사인 유사도: 1에 가까울수록 의미적으로 유사

**임베딩 모델 비교:**

| 모델 | 차원 | 특징 |
|------|------|------|
| HuggingFace all-MiniLM-L6-v2 | 384 | 빠름, 가벼움, 무료 |
| Ollama llama3.2:3b | 3072 | 높은 차원, 범용 LLM 기반 |

**실습 결과:**
- 코사인 유사도 검증: 관련 문장 0.83, 무관 문장 -0.02로 명확히 구분
- 직접 구현한 `simple_search()` 함수로 의미 검색 작동 확인
- PCA 시각화: 음악/ML/기타 주제가 벡터 공간에서 클러스터링됨

---

### 04_vectorstore.py - 벡터 저장 & 검색

**학습 목표:** ChromaDB와 FAISS를 활용한 벡터 저장/검색, MMR 검색, 메타데이터 필터링, Retriever 인터페이스를 학습한다.

**핵심 개념:**
- `similarity_search()`: 유사도 기반 검색
- `max_marginal_relevance_search()`: 관련성 + 다양성 균형 (MMR)
- `filter={"page": 0}`: 메타데이터 기반 필터링
- `persist_directory`: 영구 저장 (프로그램 종료 후에도 유지)
- `as_retriever()`: VectorStore → LCEL 체인 연결 가능한 Retriever 변환

**ChromaDB vs FAISS:**

| | ChromaDB | FAISS |
|---|----------|-------|
| 저장 방식 | 파일 기반 (영구) | 인메모리 (파일 저장 가능) |
| 필터링 | 메타데이터 필터 지원 | 기본 필터만 |
| 적합한 경우 | 중소규모, 프로토타입 | 대규모, 프로덕션 |

**실습 결과:**
- 89개 청크 저장, 유사도 점수 포함 검색 성공
- MMR 검색이 일반 검색보다 더 다양한 페이지에서 결과 반환
- 문서 추가(91개)/삭제(89개) CRUD 작업 확인

---

### 05_rag_end_to_end.py - 종합 실습

**학습 목표:** 4단계를 하나로 연결한 완전한 RAG 파이프라인을 구축하고, PDF 논문과 웹 데이터에 질문하여 근거 기반 답변을 받는다.

**구현한 RAG 변형:**

| PART | 내용 |
|------|------|
| PART 1-2 | PDF 논문 RAG (기본) |
| PART 3 | 출처(Source) 표시 RAG |
| PART 4 | 스트리밍 RAG (실시간 답변) |
| PART 5 | 웹 데이터 RAG (Spotify Research) |
| PART 6 | 멀티 소스 RAG (PDF + 웹 통합) |

**핵심 코드 패턴:**
```python
rag_chain = (
    {"context": retriever | format_docs,
     "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)
answer = rag_chain.invoke("질문")
```

**실습 결과:**
- "CNN 모델 정확도?" → **95.68%** (PDF 근거 기반 답변)
- "딥러닝 아키텍처?" → **CNN** + 출처 4개 청크 표시
- PDF 89개 + 웹 13개 = 102개 청크 통합 검색 성공

---

## 기획 의도

1. **점진적 학습 설계**: 각 파일이 RAG 파이프라인의 한 단계를 담당하며, 01→05 순서대로 실행하면 자연스럽게 전체 흐름을 이해할 수 있도록 구성
2. **실제 데이터 활용**: 더미 데이터가 아닌 실제 arXiv 논문(predicting_music.pdf)과 Spotify Research 웹사이트를 사용하여 현실적인 RAG 경험 제공
3. **비교 실험 중심**: 단순히 "이렇게 하세요"가 아니라, 파라미터를 바꿔가며 결과 차이를 직접 확인 (chunk_size 비교, similarity vs MMR, ChromaDB vs FAISS 등)
4. **Day 1 연결**: LCEL 체인(`|` 파이프), PromptTemplate, OutputParser 등 Day 1에서 배운 개념이 RAG에서 어떻게 활용되는지 자연스럽게 연결

---

## 생각해볼 점

- **chunk_size의 정답은 없다**: 500자가 범용적이지만, 데이터 특성(논문 vs 대화 vs 코드)에 따라 최적값이 다르다. 실제 프로젝트에서는 검색 품질을 평가하며 튜닝해야 한다.
- **작은 LLM의 한계**: llama3.2:3b는 무료/로컬이라는 장점이 있지만, 복잡한 질문이나 한국어 응답에서 품질이 떨어질 수 있다. 프로덕션에서는 더 큰 모델이나 OpenAI API를 고려할 필요가 있다.
- **임베딩 모델 선택의 중요성**: all-MiniLM-L6-v2는 영어에 최적화되어 있어 한국어 문서에는 다국어 모델(multilingual-e5, bge-m3 등)이 더 적합할 수 있다.
- **검색 품질 = RAG 품질**: LLM이 아무리 좋아도 검색된 컨텍스트가 부정확하면 답변도 부정확하다. Retriever 성능 개선이 RAG 시스템의 핵심이다.

---

## 향후 학습 방향 (Day 5-6)

다음 `03_retriever_chain/`에서 다룰 내용:

- **MultiQuery Retriever**: 하나의 질문을 여러 관점으로 변환하여 검색 범위 확대
- **Ensemble Retriever**: 키워드 검색(BM25) + 의미 검색을 결합한 하이브리드 검색
- **ConversationalRetrievalChain**: 대화 히스토리를 유지하면서 RAG 수행
- **History-aware Retrieval**: 이전 대화 맥락을 고려한 질문 재작성

---

## 사용 기술 스택

| 구분 | 기술 |
|------|------|
| LLM | Ollama (llama3.2:3b) |
| 임베딩 | HuggingFace all-MiniLM-L6-v2 (384차원) |
| 벡터 저장소 | ChromaDB, FAISS |
| 프레임워크 | LangChain, LCEL |
| 데이터 소스 | PDF (PyPDFLoader), Web (WebBaseLoader) |
