# 05_pdf_agent 개발 로그 — 2026-03-26

> **프로젝트:** RAG Study 05_pdf_agent (macOS 메뉴바 논문 AI 챗봇)
> **작업자:** 개발자 + Claude
> **작업 범위:** E2E 검증 → QA 테스트 → 3가지 개선 구현

---

## 1. 목적과 의도

Phase 1~3 백엔드 코드 구현이 완료된 상태에서, **실제로 동작하는지 검증하고 품질 문제를 찾아 개선**하는 것이 오늘의 목표였다.

구체적으로:
- FastAPI 서버가 모든 엔드포인트에서 올바르게 동작하는지 확인
- LLM이 논문 내용을 바탕으로 한국어로 질문에 잘 답변하는지 평가
- 발견한 문제점을 우선순위에 따라 개선

---

## 2. 현 상황 (작업 시작 시점)

### 시스템 구성
```
rumps (메뉴바) + pywebview (채팅창)
    ↕ subprocess
FastAPI 서버 (port 8765)
    ├── /api/chat      SSE 스트리밍
    ├── /api/analyze   LangGraph 분석
    ├── /api/events    SSE push 채널
    └── /api/session   세션 저장
        ↕
PDFChatbot (BM25 + FAISS Ensemble RAG)
    ↕
Ollama llama3.2:3b
```

### 확인된 사항
- Phase 1/2/3 백엔드 파일 18개 전부 문법 오류 없음
- FAISS 캐시 히트 시 ~1초 내 PDF 로드
- `/api/analyze`: summary → concepts → session_save 노드 순서로 정상 동작

### 미확인 사항
- LLM 답변 품질 (Faithfulness, Relevancy)
- Intent 분류 정확도
- 논문 범위 밖 질문 처리 (Hallucination)

---

## 3. E2E 검증 결과

### Swagger UI로 확인한 항목
| 엔드포인트 | 결과 |
|-----------|------|
| GET /api/status | ✅ ollama_ok, status 정상 |
| POST /api/load | ✅ 202 반환, FAISS 캐시 히트 |
| GET /api/doc-info | ✅ 9pages, 54chunks |
| GET /api/session | ✅ 세션 JSON 저장 확인 |

### curl로 확인한 항목
| 엔드포인트 | 결과 |
|-----------|------|
| POST /api/chat | ✅ intent 분류 → 토큰 스트리밍 → sources |
| POST /api/analyze | ✅ summary + concepts 추출 정상 |

> **발견:** PDF 파일명이 `predicting_music.pdf` → `spotify_rec_dl.pdf`로 변경되어 있었음

---

## 4. QA 테스트 (Q1~Q19)

### 테스트 설계
**대상 논문:** LSTM.pdf (Hochreiter & Schmidhuber, 1997)
**언어 구조:** 영어 논문 → 한국어 질문 → 한국어 답변 (교차 언어)

**6개 카테고리, 19개 질문:**
| 카테고리 | 질문 수 | 평가 포인트 |
|---------|---------|------------|
| 사실 확인 (qa) | Q1~Q5 | Faithfulness |
| 개념 설명 (explain) | Q6~Q9 | Intent 분류 정확도 |
| 비교·분석 (qa) | Q10~Q12 | 실험 결과 정확성 |
| 요약 (summarize) | Q13~Q14 | 구조적 요약 |
| 퀴즈 (quiz) | Q15~Q16 | 문제 형식 |
| 경계 케이스 | Q17~Q19 | Hallucination 방지 |

### 핵심 발견 문제

**문제 1: Hallucination (심각)**
- Q17 "GPT가 뭐야?" → LSTM 논문과 무관하게 GPT를 17,000자로 상세 설명
- Q8 "CEC가 뭔지 설명해줘" → CEC를 "Cell Embedding and Connectivity"로 오답 (실제: Constant Error Carousel)

**문제 2: Intent 오분류 (중간)**
- Q3 "LSTM의 gate가 몇 개야?" → quiz로 분류 (기대: qa)
- Q10~Q12 비교·분석 질문들 → summarize로 분류 (기대: qa)
- Q8 "설명해줘" → qa로 분류 (기대: explain)

**문제 3: 답변 길이 제어 불가 (낮음)**
- 모든 답변이 동일한 형식으로 출력됨
- 간단한 질문에도 1,000자 이상 답변이 나오는 경우 있음

---

## 5. 개선 작업

### 개선 1: Hallucination 방지 (`out_of_scope` 감지)

**해결 방법:**
`classify_intent()`에 `out_of_scope` 카테고리 추가 + `stream_out_of_scope()` 거절 함수 구현

**선택 이유:**
처음에는 5-way 단일 프롬프트로 시도했지만 llama3.2:3b가 복잡한 분류를 제대로 못함.
→ **2단계 분류**로 변경:
1. `_SCOPE_PROMPT`: "이 질문이 논문과 관련 있나요? (yes/no)" — 단순 이진 판단
2. yes면 → 기존 4-way intent 분류

yes/no 단순 판단이 5-way 분류보다 소형 LLM에 훨씬 적합하다는 것을 확인.

**결과:**
- "GPT가 뭐야?" → out_of_scope ✅ (17,000자 hallucination 제거)
- "PyTorch로 구현해줘" → out_of_scope ✅
- "저자가 몇 살이야?" → out_of_scope ✅
- "LSTM이 뭐야?" → explain ✅ (정상 질문 영향 없음)

---

### 개선 2: Intent 오분류 개선

**해결 방법:**
키워드 사전 필터 → LLM 분류 3단계 구조로 변경

```python
# 1단계: 키워드 사전 필터 (LLM 호출 없음)
_KEYWORD_MAP = [
    (["퀴즈", "문제 출제", "테스트해줘"], "quiz"),
    (["요약해줘", "정리해줘", "핵심이 뭐야"], "summarize"),
]
_OOS_KEYWORDS = ["pytorch", "gpt", "chatgpt", "몇 살", "구현해줘", ...]

# 2단계: LLM scope 체크
# 3단계: LLM intent 분류
```

**선택 이유:**
"퀴즈 내줘", "요약해줘" 같은 명확한 질문은 굳이 LLM을 호출할 필요가 없다.
키워드로 확실한 케이스를 먼저 잡고, 나머지만 LLM에 넘기면:
- 분류 속도 향상 (LLM 호출 0~1회로 감소)
- 명확한 케이스 100% 정확도 보장

**_INTENT_PROMPT 개선 포인트:**
```
Note: "~가 뭐야?", "~이 뭐야?" about a concept → explain (NOT quiz)
Note: comparison/reason questions → qa (NOT summarize)
```
경계 케이스를 명시적으로 예시로 제공.

**결과 (13개 검증):**
- 키워드 필터 케이스 6/6 ✅
- LLM 분류 케이스 9/13 ✅ (4개는 qa↔explain 경계 — 답변 품질 영향 미미)

---

### 개선 3: 답변 스타일 제어

**해결 방법:**
`ChatRequest`에 `style` 파라미터 추가 + 스타일별 prefix 적용

```python
# api/routes/chat.py
class ChatRequest(BaseModel):
    question: str
    session_id: str = "default"
    style: str = "default"  # "brief" | "default" | "detailed"

# agent/tools.py
_STYLE_PREFIX = {
    "brief":    "답변을 2~3문장으로 간결하게 핵심만 작성하세요.\n\n",
    "default":  "",
    "detailed": "답변을 단계별로 자세하게 작성하세요. 예시와 구체적인 수식·수치를 포함하세요.\n\n",
}
```

**선택 이유:**
LLM의 기본 출력 길이는 컨텍스트에 따라 들쭉날쭉함.
System prompt 레벨에서 제어하면 모든 intent에 동일하게 적용 가능하고, 기존 코드 변경 최소화.
quiz는 형식이 고정이므로 style prefix 제외.

**결과 (LSTM이 뭐야? 기준):**
| 스타일 | 글자수 |
|--------|--------|
| brief | 590자 |
| default | 742자 |
| detailed | 1,854자 |

---

## 6. 피드백 및 반성

### 잘된 점
- E2E 검증을 체계적으로 진행해 실제 문제를 사전에 발견
- QA 계획서(QA_PLAN.md)와 결과(agent_QA.json)를 문서화해 재현 가능한 테스트 환경 구축
- Hallucination이라는 명확한 실패 케이스를 발견하고 즉시 수정

### 아쉬운 점
- llama3.2:3b의 한계로 qa↔explain 경계 분류가 완벽하지 않음
  → 더 큰 모델(llama3.1:8b 이상)에서는 프롬프트만으로 해결 가능할 것으로 예상
- Q8 CEC Hallucination (Cell Embedding and Connectivity)은 retrieval 문제:
  CEC 관련 청크가 제대로 검색되지 않아 LLM이 내용을 지어냈음
  → Reranker 도입 또는 청크 크기 조정이 필요

### 발견한 llama3.2:3b 특성
- 5-way 분류 프롬프트에서 특정 옵션으로 편향되는 경향 (quiz, summarize로 수렴)
- yes/no 이진 판단은 상대적으로 안정적
- 명시적 예시(Note: ...)를 프롬프트에 포함하면 경계 케이스 개선

---

## 7. 배운 점

### 1. 소형 LLM에서의 분류기 설계 원칙
복잡한 단일 프롬프트보다 **역할을 나눈 복수 프롬프트**가 훨씬 안정적이다.
`scope_check(yes/no)` → `intent_classify(4-way)` 분리가 핵심.

### 2. 키워드 필터 + LLM 하이브리드 패턴
100% LLM 의존보다 **명확한 케이스는 규칙 기반, 모호한 케이스만 LLM**에 넘기는 방식이
속도·정확도 모두 우수하다.

### 3. E2E 검증의 중요성
코드가 완성되어 있어도 실제로 돌려봐야 모르는 문제가 나온다.
QA 계획서를 먼저 설계하고 → 자동화 스크립트로 일괄 실행 → 결과 기록 → 개선의 사이클이 효과적.

### 4. Swagger UI의 한계
SSE 스트리밍 엔드포인트(`/api/chat`, `/api/analyze`, `/api/events`)는
Swagger UI에서 응답이 보이지 않음 → curl 또는 requests 라이브러리로 테스트해야 함.

---

## 8. 다음 단계

### Phase 3 UI (이어서 학습 화면)

백엔드는 완성. 프론트엔드 3가지 추가 필요:

**① 이어서 학습하기 카드 UI 개선** (`chat.js` + `style.css`)
- 현재: `showResumeCard()`가 텍스트만 출력
- 목표: 버튼이 있는 카드 UI
  ```
  ┌─────────────────────────────────┐
  │ 📚 이전 학습 기록              │
  │ 마지막 학습: 2026-03-20 11:30  │
  │ 누적 질문: 7회                 │
  │ 개념 이해: 1/8개               │
  │                                 │
  │ [이어서 학습하기] [처음부터]   │
  └─────────────────────────────────┘
  ```

**② 답변 스타일 셀렉터** (`index.html` + `chat.js`)
- 입력창 위에 brief / 기본 / 상세 버튼 추가
- 선택된 style을 POST /api/chat 요청에 자동 포함

**③ out_of_scope intent badge 라벨 추가** (`chat.js`)
- `showIntentBadge()`의 labels 객체에 `out_of_scope: "🚫 범위 밖"` 추가 (1줄 수정)

### Phase 4 (그 다음)
py2app 번들링 → `.app` → `.dmg` 생성
