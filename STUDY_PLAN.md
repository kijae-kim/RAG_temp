# 🚀 2주 RAG & LangChain 마스터 플랜

> 목표: RAG/LangChain 실무 역량 확보 + 포트폴리오 프로젝트 완성

---

## 📅 Week 1: LangChain 기초 & RAG 핵심

### Day 1-2: 환경설정 & LangChain 기초
**학습 목표:** LangChain의 핵심 개념 이해

| 시간 | 내용 | 실습 |
|------|------|------|
| 2h | 환경설정, API 키 발급 | `.env` 설정, 연결 테스트 |
| 3h | PromptTemplate | 다양한 프롬프트 패턴 실습 |
| 3h | ChatModel & LLM | OpenAI, Anthropic 모델 호출 |
| 2h | LCEL (LangChain Expression Language) | 파이프 연산자 체인 구성 |

**핵심 개념:**
- `|` 파이프 연산자로 체인 연결
- `RunnablePassthrough`, `RunnableLambda`
- `invoke()`, `stream()`, `batch()` 실행 방식

**실습 코드:** `01_langchain_basics/`

---

### Day 3-4: RAG 파이프라인 핵심
**학습 목표:** RAG의 4단계 파이프라인 완벽 이해

```
[문서] → [Loader] → [Splitter] → [Embedding] → [VectorStore]
                                                    ↓
[질문] → [Embedding] → [Retriever] → [Context + Prompt] → [LLM] → [답변]
```

| 시간 | 내용 | 실습 |
|------|------|------|
| 2h | Document Loaders | PDF, TXT, Web 문서 로딩 |
| 2h | Text Splitters | RecursiveCharacterTextSplitter |
| 3h | Embeddings | OpenAI, HuggingFace 임베딩 |
| 3h | VectorStore | ChromaDB, FAISS 저장/검색 |

**핵심 개념:**
- Chunk size & Overlap 전략
- 임베딩 차원과 유사도 검색
- 메타데이터 필터링

**실습 코드:** `02_rag_pipeline/`

---

### Day 5-6: Retriever & Chain
**학습 목표:** 검색 전략과 체인 패턴 마스터

| 시간 | 내용 | 실습 |
|------|------|------|
| 3h | Retriever 종류 | VectorStore, MultiQuery, Ensemble |
| 3h | RetrievalQA Chain | 기본 RAG 체인 구현 |
| 2h | ConversationalRetrievalChain | 대화 맥락 유지 |
| 2h | 출력 파서 | StrOutputParser, JsonOutputParser |

**핵심 개념:**
- `k` 파라미터와 검색 정확도
- MMR (Maximum Marginal Relevance)
- History-aware retrieval

**실습 코드:** `03_retriever_chain/`

---

### Day 7: 복습 & 미니 프로젝트
**미니 프로젝트:** PDF Q&A 챗봇

```python
# 구현할 기능
1. PDF 업로드 → 청크 분할 → 벡터 저장
2. 질문 입력 → 관련 문서 검색 → 답변 생성
3. 대화 히스토리 유지
```

**실습 코드:** `04_mini_project/`

---

## 📅 Week 2: 심화 & 포트폴리오 프로젝트

### Day 8-9: 에이전트 & Tools
**학습 목표:** 자율적으로 도구를 사용하는 에이전트 구현

| 시간 | 내용 | 실습 |
|------|------|------|
| 3h | Tools 정의 | `@tool` 데코레이터, 커스텀 도구 |
| 3h | Agent 종류 | ReAct, OpenAI Functions |
| 2h | Agent Executor | 실행 및 디버깅 |
| 2h | 멀티 도구 에이전트 | 검색 + 계산 + 코드실행 |

**핵심 개념:**
- ReAct 패턴 (Reasoning + Acting)
- Tool description의 중요성
- Agent 디버깅 방법

**실습 코드:** `05_agents/`

---

### Day 10-11: LangGraph 기초
**학습 목표:** 상태 기반 복잡한 워크플로우 구현

| 시간 | 내용 | 실습 |
|------|------|------|
| 3h | LangGraph 개념 | State, Node, Edge |
| 3h | 조건부 분기 | Conditional Edge |
| 2h | 사이클 & 루프 | 반복 처리 패턴 |
| 2h | Human-in-the-loop | 인간 개입 워크플로우 |

**핵심 개념:**
- `StateGraph` 정의
- `add_node()`, `add_edge()`, `add_conditional_edges()`
- `compile()` 및 실행

**실습 코드:** `06_langgraph/`

---

### Day 12-14: 포트폴리오 프로젝트
**추천 프로젝트:** 기술 문서 Q&A 시스템 (Advanced RAG)

```
📦 프로젝트 구조
├── app/
│   ├── main.py          # Streamlit 메인
│   ├── rag_pipeline.py  # RAG 파이프라인
│   ├── agent.py         # 에이전트 (선택)
│   └── utils.py         # 유틸리티
├── data/                # 샘플 문서
├── vectorstore/         # 벡터 DB 저장소
└── README.md            # 프로젝트 설명
```

**구현 기능:**
1. ✅ 다중 문서 업로드 (PDF, TXT, MD)
2. ✅ 하이브리드 검색 (키워드 + 의미)
3. ✅ 스트리밍 응답
4. ✅ 출처 표시 (Source Citation)
5. ✅ 대화 히스토리

**실습 코드:** `07_portfolio_project/`

---

## 🔑 API 키 설정

```bash
# .env 파일 생성
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
LANGCHAIN_API_KEY=ls__...  # (선택) LangSmith 추적용
LANGCHAIN_TRACING_V2=true
```

---

## 📊 일일 체크리스트

매일 학습 후 체크:
- [ ] 핵심 개념 정리 (노션/마크다운)
- [ ] 실습 코드 작성 및 커밋
- [ ] 에러/트러블슈팅 기록
- [ ] 다음 날 학습 범위 확인

---

## 🎯 이력서 어필 포인트

프로젝트 완성 후 작성할 내용:

```
• LangChain/LangGraph 기반 RAG 시스템 설계 및 구현
• ChromaDB 벡터스토어를 활용한 의미 기반 문서 검색 파이프라인 구축
• 하이브리드 검색(BM25 + Dense Retrieval) 적용으로 검색 정확도 향상
• Streamlit 기반 대화형 Q&A 인터페이스 개발
• LangSmith를 활용한 LLM 애플리케이션 모니터링 및 디버깅 경험
```

---

## 📚 참고 자료

- [위키독스 - 테디노트 LangChain](https://wikidocs.net/book/14473)
- [LangChain 공식 문서](https://python.langchain.com/)
- [LangGraph 공식 문서](https://langchain-ai.github.io/langgraph/)
- [LangSmith](https://smith.langchain.com/)

---

**시작일:** 2025-02-06
**목표 완료일:** 2025-02-20
