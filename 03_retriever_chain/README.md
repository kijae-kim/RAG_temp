# 03_retriever_chain - Retriever 전략 & 대화형 RAG

> Day 5-6 학습: Retriever 전략(Similarity/MMR/MultiQuery/Ensemble)을 비교하고, 대화 히스토리를 유지하는 완전한 대화형 RAG 시스템 구축

---

## 전체 구조

```
[문서] → Loader → Splitter → Embedding → VectorStore
                                              │
         ┌────────────────────────────────────┘
         │
[질문] → ★Retriever 전략 선택★ → 관련 문서
              │                        │
         (히스토리 인식              (Context)
          질문 재작성)                  │
              │                        ↓
[히스토리] ──→ QA 프롬프트 + LLM ──→ [답변] → 히스토리 저장
```

```
03_retriever_chain/
├── 01_retriever_types.py           # Retriever 종류 비교 (Similarity/MMR/MultiQuery)
├── 02_ensemble_retriever.py        # BM25 + 의미검색 하이브리드
├── 03_conversational_chain.py      # 대화 히스토리 유지 RAG (기본)
├── 04_history_aware_retrieval.py   # 히스토리 인식 검색 + 완전한 대화형 RAG
├── 05_day5_practice.py             # 종합 실습 - 인터랙티브 챗봇
└── README.md
```

---

## 실습 데이터

| 소스 | 내용 |
|------|------|
| **PDF** | `predicting_music.pdf` - CNN 기반 Spotify 음악 인기도 예측 논문 (12페이지, arXiv 2025) |

---

## 파일별 상세

### 01_retriever_types.py - Retriever 종류 비교

**학습 목표:** VectorStore Retriever의 k 파라미터, Similarity vs MMR 검색, MultiQueryRetriever의 질문 확장 효과를 실험하고 비교한다.

**핵심 개념:**
- `search_kwargs={"k": N}`: 검색 결과 수 조절
- `search_type="mmr"`: 관련성 + 다양성 균형
- `lambda_mult`: MMR의 다양성 조절 (0.0=최대 다양성, 1.0=최대 유사도)
- `MultiQueryRetriever.from_llm()`: LLM이 질문을 3가지로 변형하여 검색

**다루는 Retriever:**

| Retriever | 검색 방식 | 특징 |
|-----------|----------|------|
| Similarity | 코사인 유사도 | 가장 유사한 문서 반환 (기본) |
| MMR | 유사도 + 다양성 | 중복 없는 다양한 관점 반환 |
| MultiQuery | LLM 질문 확장 | 검색 범위 확대, 놓칠 수 있는 문서 발견 |

**실습 결과:**
- k 파라미터 실험: k=1,3,5,10에 따른 결과 수/페이지 분포 비교
- MMR lambda_mult 실험: 0.0/0.5/1.0에 따른 다양성 변화
- 동일 질문으로 세 Retriever 결과 비교 테이블 출력

---

### 02_ensemble_retriever.py - 하이브리드 검색

**학습 목표:** BM25(키워드 기반) 검색의 원리를 이해하고, EnsembleRetriever로 BM25 + 벡터 검색을 결합하여 하이브리드 RAG를 구현한다.

**핵심 개념:**
- `BM25Retriever`: TF-IDF 기반 키워드 검색 (임베딩 불필요)
- `EnsembleRetriever`: 여러 Retriever를 결합하는 메타 Retriever
- `Reciprocal Rank Fusion (RRF)`: 여러 검색 결과의 순위를 통합하는 알고리즘
- `weights`: 각 Retriever의 기여도 조절

**BM25 vs 벡터 검색:**

| | BM25 (키워드) | Vector (의미) |
|---|--------------|--------------|
| 원리 | TF-IDF, 단어 빈도 | 코사인 유사도, 의미 벡터 |
| 강점 | 정확한 용어/고유명사 | 유사한 의미, 동의어 |
| 약점 | 의미적 유사성 무시 | 정확한 키워드 매칭 약함 |

**실습 결과:**
- BM25 vs FAISS 개별 검색 결과 비교
- 가중치 조정 실험: [0.7,0.3] / [0.5,0.5] / [0.3,0.7]
- Ensemble Retriever로 Hybrid RAG 체인 구성, 3개 질문 테스트

---

### 03_conversational_chain.py - 대화형 RAG (기본)

**학습 목표:** 기존 stateless RAG의 한계를 확인하고, ChatMessageHistory와 RunnableWithMessageHistory를 사용하여 대화 맥락을 유지하는 RAG를 구현한다.

**핵심 개념:**
- Stateless RAG의 한계: "그것의 정확도?" 같은 후속 질문 실패
- `ChatMessageHistory`: 대화 기록(HumanMessage, AIMessage) 저장소
- `MessagesPlaceholder("chat_history")`: 프롬프트에 히스토리 삽입 위치
- `RunnableWithMessageHistory`: 체인에 자동 히스토리 관리 추가
- `session_id`: 사용자별 독립 세션 관리

**실습 결과:**
- Stateless RAG 실패 시연: "What was its accuracy?" → 맥락 없이 부정확한 답변
- 4턴 연속 대화 성공, 히스토리 자동 저장 확인
- 남은 한계점 확인: 검색 단계는 여전히 stateless (04에서 해결)

---

### 04_history_aware_retrieval.py - 히스토리 인식 검색

**학습 목표:** 질문 재작성(contextualize) 원리를 이해하고, create_history_aware_retriever로 검색 단계에서도 대화 맥락을 활용하는 완전한 대화형 RAG를 구현한다.

**핵심 개념:**
- Contextualize: "그것의 정확도?" → "CNN 모델의 정확도?" 재작성
- `create_history_aware_retriever`: 히스토리 참조 → 질문 재작성 → 검색
- `create_stuff_documents_chain`: 검색된 문서들을 프롬프트에 주입
- `create_retrieval_chain`: Retriever + QA 체인 통합
- `output_messages_key="answer"`: 딕셔너리 반환 시 필수 설정

**03 vs 04 비교:**

| | 03 (기본 대화형) | 04 (히스토리 인식) |
|---|----------------|------------------|
| LLM 히스토리 | ✅ 있음 | ✅ 있음 |
| 검색 히스토리 | ❌ 없음 | ✅ 질문 재작성 후 검색 |
| 핵심 API | RunnableWithMessageHistory | + create_history_aware_retriever |
| 반환 형태 | 문자열 | {"answer", "context"} 딕셔너리 |

**실습 결과:**
- 질문 재작성 데모: 3가지 후속 질문을 독립 질문으로 변환 확인
- 4턴 대화 성공, 각 턴마다 참조 페이지 표시
- 03 대비 검색 정확도 향상 확인

---

### 05_day5_practice.py - 종합 실습 (인터랙티브 챗봇)

**학습 목표:** Day 5-6에서 배운 모든 개념을 통합하여 Retriever 전략 선택, History-Aware 대화형 RAG, JSON 구조화 출력을 지원하는 인터랙티브 챗봇을 구현한다.

**구현한 기능:**

| PART | 내용 |
|------|------|
| PART 1 | 환경 설정 & FAISS 벡터스토어 구축 |
| PART 2 | Retriever 전략 선택 (Similarity/MMR/Ensemble 비교) |
| PART 3 | History-Aware 대화형 RAG 파이프라인 조립 |
| PART 4 | JsonOutputParser 구조화 출력 데모 |
| 챗봇 | 인터랙티브 루프 (quit/clear/history/json 명령어) |

**챗봇 명령어:**

| 명령어 | 기능 |
|--------|------|
| `quit` | 종료 |
| `clear` | 대화 히스토리 초기화 |
| `history` | 대화 히스토리 보기 |
| `json` | 다음 질문을 JSON 구조화 출력으로 답변 |

---

## 핵심 코드 패턴

### 1. EnsembleRetriever (하이브리드 검색)
```python
from langchain_community.retrievers import BM25Retriever
from langchain_classic.retrievers import EnsembleRetriever

bm25 = BM25Retriever.from_documents(docs, k=4)
faiss_ret = faiss_db.as_retriever(search_kwargs={"k": 4})

ensemble = EnsembleRetriever(
    retrievers=[bm25, faiss_ret],
    weights=[0.5, 0.5]  # BM25 50% + FAISS 50%
)
```

### 2. create_history_aware_retriever (히스토리 인식 검색)
```python
from langchain_classic.chains import create_history_aware_retriever

contextualize_prompt = ChatPromptTemplate.from_messages([
    ("system", "Reformulate the question to be standalone..."),
    MessagesPlaceholder("chat_history"),
    ("human", "{input}"),  # ⚠️ "input" 키 사용!
])

history_aware_retriever = create_history_aware_retriever(
    llm, retriever, contextualize_prompt
)
```

### 3. RunnableWithMessageHistory (완전한 대화형 RAG)
```python
from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.runnables.history import RunnableWithMessageHistory

qa_chain = create_stuff_documents_chain(llm, qa_prompt)
rag_chain = create_retrieval_chain(history_aware_retriever, qa_chain)

conversational_rag = RunnableWithMessageHistory(
    rag_chain,
    get_session_history,
    input_messages_key="input",
    history_messages_key="chat_history",
    output_messages_key="answer",  # 딕셔너리 반환 시 필수
)

# 실행
result = conversational_rag.invoke(
    {"input": "질문"},
    config={"configurable": {"session_id": "user_1"}},
)
print(result["answer"])
```

---

## 기획 의도

1. **점진적 학습 설계**: 01(Retriever 종류) → 02(하이브리드) → 03(대화형 기본) → 04(히스토리 인식) 순서로 개념을 쌓아가며, 각 단계에서 이전 단계의 한계를 명시적으로 제시하고 해결
2. **문제-해결 중심**: "stateless RAG의 후속 질문 실패" 문제를 먼저 시연하고, 단계적으로 해결하는 과정을 체험
3. **비교 실험**: k 파라미터, lambda_mult, 가중치 등을 변경하며 결과 차이를 직접 확인하여 직관적 이해
4. **Day 3-4 연결**: 02_rag_pipeline에서 배운 VectorStore, Retriever, LCEL 체인을 기반으로 Retriever 전략과 대화형 체인을 확장

---

## 생각해볼 점

- **Retriever 전략의 정답은 없다**: 데이터 특성과 질문 유형에 따라 최적 전략이 다르다. 전문 용어가 많으면 BM25 비중↑, 자연어 질문이면 벡터 검색 비중↑.
- **히스토리 길이 관리**: 대화가 길어지면 히스토리가 프롬프트 토큰 제한을 초과할 수 있다. 실제 시스템에서는 최근 N턴만 유지하거나 요약하는 전략이 필요하다.
- **질문 재작성의 비용**: create_history_aware_retriever는 매 질문마다 LLM을 추가 호출한다. 지연시간과 비용이 증가하므로, 첫 질문(히스토리 없음)에는 불필요한 호출을 건너뛰는 최적화가 가능하다.
- **검색 품질 > LLM 능력**: RAG의 답변 품질은 검색된 컨텍스트에 크게 의존한다. Retriever 전략을 잘 선택하는 것이 LLM을 바꾸는 것보다 효과적일 수 있다.

---

## 향후 학습 방향 (04_mini_project)

다음 `04_mini_project/`에서 다룰 내용:

- 지금까지 배운 RAG 기법들을 종합한 실제 프로젝트 구현
- 사용자 인터페이스 (Streamlit 등)와 RAG 백엔드 연결
- 평가 메트릭을 활용한 RAG 파이프라인 성능 측정
- 프로덕션 수준의 에러 처리와 최적화

---

## 사용 기술 스택

| 구분 | 기술 |
|------|------|
| LLM | Ollama (llama3.2:3b) |
| 임베딩 | HuggingFace all-MiniLM-L6-v2 (384차원) |
| 벡터 저장소 | FAISS, ChromaDB |
| 키워드 검색 | BM25 (rank_bm25) |
| Retriever | Similarity, MMR, MultiQuery, Ensemble |
| 대화형 RAG | create_history_aware_retriever, RunnableWithMessageHistory |
| 프레임워크 | LangChain, LCEL |
