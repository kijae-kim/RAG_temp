# 05_pdf_agent — 프로젝트 전체 흐름 & 다음 단계 계획

> 최종 업데이트: 2026-03-27
> 목표: 논문 PDF를 열면 AI 챗봇이 자동 활성화되는 macOS 네이티브 앱

---

## 1. 프로젝트 최종 목표

**"논문을 읽는 화면 옆에 AI 챗봇이 항상 떠 있고, 출처를 누르면 해당 페이지가 열린다."**

| 관점 | 구체적 목표 |
|------|------------|
| UX | 감시 폴더에서 PDF 열기 → 챗봇 자동 활성화 |
| UI | 원형 FAB 토글, 답변 스타일 선택, 이어서 학습 카드 |
| 품질 | Hallucination 차단, Intent 분류 안정화 |
| 배포 | py2app `.app` 번들 → `.dmg` 배포 |

---

## 2. 전체 아키텍처

```
[ macOS 환경 ]
  Preview / PDF Expert / Acrobat
      ↓ 감시 폴더 (lsof 폴링, 3초)
  menubar_app.py  ←→  rumps (NSRunLoop, 메뉴바)
      ↕ subprocess.Popen
  webview_process.py  ←→  pywebview
      ├── 채팅 창 (420×700, frameless)
      └── FAB 버튼 창 (72×72, 원형)
            ↕ JS Bridge (window.pywebview.api)
  [ FastAPI  port 8765 ]
      ├── GET  /api/status      → 헬스체크
      ├── POST /api/load        → PDF 로드 + 인덱싱
      ├── GET  /api/doc-info    → 논문 메타 정보
      ├── POST /api/chat        → SSE 스트리밍 응답
      ├── POST /api/analyze     → LangGraph 분석
      ├── GET  /api/events      → 실시간 상태 push
      └── GET  /api/session     → 학습 기록 조회
            ↕
  PDFChatbot (BM25 + FAISS Ensemble RAG)
      ↕
  Ollama llama3.2:3b  /  paraphrase-multilingual-MiniLM-L12-v2
```

### 데이터 흐름 (채팅 기준)

```
사용자 질문
  → classify_intent()          # 3단계: 키워드 → scope yes/no → 4-way
  → STREAM_FN_MAP[intent]()    # qa / explain / quiz / summarize / out_of_scope
      → RAG 검색 (BM25 + FAISS Ensemble)
      → LLM 스트리밍 (SSE token-by-token)
      → sources 반환 (page + text + pdf_path)
  → JS renderSources()         # 출처 칩 클릭 → open_pdf_at_page() 브릿지
```

---

## 3. Phase별 진행 현황

### Phase 1 — FastAPI 백엔드 ✅
- `api/server.py`: FastAPI 앱 팩토리, CORS, `/ui` 정적 파일 서빙
- `api/routes/chat.py`: SSE 스트리밍 채팅 (`/api/chat`)
- `api/routes/document.py`: PDF 로드 + 비동기 인덱싱 (`/api/load`)
- `api/routes/events.py`: 실시간 상태 push (`/api/events`)
- `api/routes/session.py`: 학습 기록 CRUD (`/api/session`)
- `api/engine_state.py`: 공유 상태 관리 (chatbot 싱글턴, paper_path)

### Phase 2 — LangGraph 논문 분석 에이전트 ✅
- `agent/paper_agent.py`: `StateGraph` (summary_node → concept_node → session_save)
- `agent/tools.py`: RAG 스트리밍 함수 4종 + intent 분류기
- `api/routes/agent.py`: `/api/analyze` 엔드포인트 (SSE)

### Phase 3 — 품질 개선 (3종) ✅

#### 개선 1: Hallucination 방지
```python
# 3단계 intent 분류
def classify_intent(question: str) -> str:
    # 1) 키워드 사전 필터 (_OOS_KEYWORDS, _KEYWORD_MAP)
    # 2) LLM scope yes/no 체크 (_SCOPE_PROMPT)
    # 3) LLM 4-way intent 분류 (_INTENT_PROMPT)
```
- "GPT가 뭐야?" → `out_of_scope` (17,000자 hallucination 제거)
- `stream_out_of_scope()` → 정중한 거절 메시지

#### 개선 2: 답변 스타일 제어
```python
_STYLE_PREFIX = {
    "brief":    "답변을 2~3문장으로 간결하게...",
    "default":  "",
    "detailed": "단계별로 자세하게, 수식·수치 포함...",
}
# ChatRequest에 style 필드 추가
```

#### 개선 3: sources에 pdf_path 포함
- `_serialize_sources()` → `{"page": n, "text": "...", "pdf_path": "/path/to/file.pdf"}`
- 출처 칩 클릭 → `open_pdf_at_page()` 브릿지 → Preview 해당 페이지 이동

### Phase 3 UI ✅
- `showResumeCard()`: 텍스트 → 버튼 카드 UI (이어서 학습 / 처음부터)
- 스타일 셀렉터: 입력창 위 간결 / 기본 / 상세 버튼
- `out_of_scope` badge: `labels` 딕셔너리에 `"🚫 범위 밖"` 추가
- CSS: `.resume-card`, `.style-selector`, `.source-chip.clickable`

### UX 기능 추가 (2026-03-27) ⚠️ 부분 완료
| 기능 | 상태 | 비고 |
|------|------|------|
| 감시 폴더 설정 (NSOpenPanel) | ✅ | preferences.json 저장 |
| lsof 기반 PDF 감지 + 자동 로드 | ⚠️ | 동작 확인 중 |
| FAB 원형 토글 버튼 | ✅ | 72×72, `#1e1e2e` 배경 |
| FAB → 채팅창 show/hide | ✅ | `close_window()` = hide로 변경 |
| 출처 클릭 → PDF 페이지 이동 | ✅ | AppleScript + Preview |
| AppKit 화면 크기 조회 | ✅ | `webview.screens` 의존성 제거 |

---

## 4. 알려진 이슈 & 기술 부채

| 구분 | 내용 | 우선순위 |
|------|------|---------|
| 버그 | 감시 폴더 감지: lsof가 동작 확인 필요 | 🔴 높음 |
| 버그 | FAB 첫 표시 위치가 화면 밖일 수 있음 (PDF 뷰어 없을 때) | 🟡 중간 |
| 품질 | qa↔explain 경계 분류 (4/13 오분류) | 🟡 중간 |
| 품질 | CEC 등 특정 개념의 retrieval 실패 (청크 미검색) | 🟡 중간 |
| UX | 한국어 답변의 기술 용어 어색함 (영어 원문 → 한국어) | 🟢 낮음 |
| 미구현 | Phase 4: py2app 번들링 | 🟢 낮음 |

---

## 5. 다음 단계 계획

### Step 1. 감시 폴더 감지 안정화 (즉시)

**목표:** PDF를 열었을 때 100% 감지해 자동 로드

**검증 방법:**
```bash
# 터미널에서 직접 lsof 출력 확인
lsof +d "/감시폴더경로" -F n | grep -i '.pdf'
```

**fallback 전략 (lsof 실패 시):**
- `watchdog` 라이브러리의 `FileSystemEventHandler.on_opened()` 사용
- 또는 macOS `NSWorkspace.sharedWorkspace().noteFileSystemChanged_()` 활용

---

### Step 2. FAB 위치 로직 개선 (1~2일)

**현재 문제:** PDF 뷰어가 없는 상태에서 창을 열면 FAB이 화면 밖에 배치될 수 있음

**개선안:**
```python
def _fab_position(chat_x: int, chat_y: int) -> tuple[int, int]:
    sw, sh = _get_screen_size()
    fab_x = chat_x - FAB_SIZE - MARGIN
    fab_y = chat_y + CHAT_H // 2 - FAB_SIZE // 2
    # 화면 경계 클리핑 (모든 방향)
    fab_x = max(0, min(fab_x, sw - FAB_SIZE))
    fab_y = max(24, min(fab_y, sh - FAB_SIZE))  # 24: 메뉴바 높이
    return fab_x, fab_y
```

---

### Step 3. 출처 클릭 → PDF 이동 검증 (1일)

**검증 항목:**
1. 출처 칩에 `pdf_path`가 실제로 채워지는지 확인 (브라우저 devtools)
2. `open_pdf_at_page()` 브릿지 호출 확인
3. Preview 페이지 이동 AppleScript 동작 확인
4. 0-indexed vs 1-indexed 오프셋 최종 검증

---

### Step 4. 검색 품질 개선 (2~3일)

**문제:** CEC, Vanishing Gradient 같은 용어의 청크가 검색에서 누락됨

**개선 방법:**

**4-1. 청크 크기 조정 (빠름)**
```python
# 현재: chunk_size=500, overlap=50
# 개선: chunk_size=400, overlap=100 (개념 단위로 더 작게)
```

**4-2. Reranker 추가 (중간)**
```python
from langchain.retrievers import ContextualCompressionRetriever
from langchain_community.document_compressors import CrossEncoderReranker
```
검색 → top-10 후보 → reranker로 top-3 재정렬

**4-3. 한국어 쿼리 번역 (복잡)**
```python
# 질문이 한국어인 경우 영어로 번역 후 검색
# llama3.2:3b로 "Translate to English: {question}" 선행 실행
```

---

### Step 5. Phase 4 — py2app 번들링 (3~5일)

**목표:** `.app` + `.dmg` 생성 → 일반 사용자 배포 가능

**작업 항목:**

**5-1. `setup.py` 작성**
```python
from setuptools import setup
import py2app

APP = ['05_pdf_agent/menubar_app.py']
OPTIONS = {
    'argv_emulation': True,
    'plist': {
        'LSUIElement': True,           # Dock 아이콘 숨김 (메뉴바 전용)
        'NSHighResolutionCapable': True,
    },
    'packages': ['rumps', 'webview', 'fastapi', 'uvicorn',
                 'langchain_community', 'langchain_classic',
                 'langchain_huggingface', 'langchain_core'],
    'includes': ['AppKit', 'Quartz'],
}
setup(app=APP, options={'py2app': OPTIONS})
```

**5-2. 의존성 체크리스트**
- [ ] Ollama: 번들에 포함 불가 → 사용자가 별도 설치 필요 (설치 가이드 포함)
- [ ] `sentence-transformers` 모델 캐시 경로 설정 (`~/Library/Caches/PDFChatbot/`)
- [ ] FAISS 인덱스 저장 경로 앱 번들 외부로 지정

**5-3. 빌드 & 테스트**
```bash
poetry run python setup.py py2app --semi-standalone
# → dist/PDFChatbot.app 생성
# create-dmg로 배포 패키지 생성
```

---

### Step 6. 장기 개선 (선택적)

| 개선 | 설명 | 효과 |
|------|------|------|
| 멀티 논문 지원 | 세션별로 다른 논문 인덱스 유지 | 논문 비교 질문 가능 |
| 더 큰 모델 | llama3.1:8b 또는 llama3.2:11b | 분류 정확도 향상 |
| 하이라이트 기능 | 출처 클릭 시 PDF 텍스트 하이라이트 | 검증 경험 개선 |
| 음성 입력 | macOS Speech API 연동 | 손 없이 질문 가능 |
| 내보내기 | 대화 내용 → Markdown 저장 | 학습 노트 활용 |

---

## 6. 진행 체크리스트

### 현재 완료 ✅
- [x] FastAPI 백엔드 (Phase 1)
- [x] LangGraph 분석 에이전트 (Phase 2)
- [x] Hallucination 방지 / Intent 분류 / 스타일 제어 (Phase 3 백엔드)
- [x] Resume 카드 / 스타일 셀렉터 / out_of_scope badge (Phase 3 UI)
- [x] 감시 폴더 메뉴 + lsof 감지 로직
- [x] FAB 원형 토글 버튼
- [x] 출처 클릭 → PDF 페이지 이동 (bridge 구현)

### 진행 중 ⚠️
- [ ] 감시 폴더 감지 실제 동작 검증
- [ ] FAB 위치 화면 경계 클리핑

### 미완료 📋
- [ ] 청크 크기 / Reranker 품질 개선
- [ ] py2app 번들링 (Phase 4)
- [ ] `.dmg` 배포 패키지 생성

---

## 7. 실행 방법

```bash
# 개발 모드 실행
cd /Users/gimgijae/Desktop/Paper/RAG/RAG_Study
poetry run python 05_pdf_agent/menubar_app.py

# 서버만 실행 (디버깅용)
poetry run uvicorn 05_pdf_agent.api.server:app --port 8765 --reload

# 환경 변수 문제 시
unset VIRTUAL_ENV
poetry run python 05_pdf_agent/menubar_app.py
```

---

## 8. 파일 구조

```
05_pdf_agent/
├── menubar_app.py          # 메뉴바 앱 진입점 (rumps + 감시 폴더)
├── webview_process.py      # pywebview 채팅창 + FAB 버튼
├── api/
│   ├── server.py           # FastAPI 앱 팩토리
│   ├── engine_state.py     # 공유 상태 (chatbot, paper_path)
│   └── routes/
│       ├── chat.py         # SSE 채팅 (/api/chat)
│       ├── document.py     # PDF 로드 (/api/load)
│       ├── agent.py        # LangGraph 분석 (/api/analyze)
│       ├── events.py       # SSE 상태 push (/api/events)
│       └── session.py      # 학습 기록 (/api/session)
├── agent/
│   ├── paper_agent.py      # LangGraph StateGraph
│   ├── tools.py            # RAG 스트리밍 + intent 분류
│   └── state.py            # AgentState TypedDict
├── session/
│   ├── session_manager.py  # JSON 세션 저장
│   └── models.py           # Pydantic 모델
└── ui/
    ├── index.html          # 채팅 UI
    ├── chat.js             # 채팅 로직 + 출처 클릭
    ├── analysis.js         # 분석 탭 로직
    ├── style.css           # 다크 테마 스타일
    └── floating_button.html # FAB 원형 버튼
```
