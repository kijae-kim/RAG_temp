# PDF 논문 학습 AI 챗봇 — 05_pdf_agent

> **RAG Study Day 8~10 | AI Engineer 설계 문서**
>
> macOS 메뉴바에 상주하는 AI 챗봇. 논문 PDF를 선택하면 네이티브 채팅 창으로
> 즉시 학습 세션을 시작하는 로컬 AI 애플리케이션.
>
> 배포 목표: 개발 환경 → macOS .dmg 독립 배포 → (선택) App Store

---

## 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [기술 선택 근거](#2-기술-선택-근거)
3. [전체 아키텍처](#3-전체-아키텍처)
4. [UI 설계](#4-ui-설계)
5. [FastAPI 엔드포인트 설계](#5-fastapi-엔드포인트-설계)
6. [pywebview-FastAPI 통신 설계](#6-pywebview-fastapi-통신-설계)
7. [Phase별 개발 계획](#7-phase별-개발-계획)
8. [App Store 배포 로드맵](#8-app-store-배포-로드맵)
9. [폴더 구조](#9-폴더-구조)
10. [학습 연계 맵](#10-학습-연계-맵)
11. [엔지니어링 표준](#11-엔지니어링-표준)

---

## 1. 프로젝트 개요

### 04_mini_project vs 05_pdf_agent

```text
04_mini_project (Streamlit)           05_pdf_agent (macOS Native)
──────────────────────────────        ──────────────────────────────
브라우저 탭에서 동작                  macOS 메뉴바 상주
수동 PDF 업로드 필요                  파일 선택 다이얼로그 (NSOpenPanel)
Streamlit 단일 프로세스               rumps + pywebview + FastAPI 분리
App Store 배포 불가                   py2app 번들 → .dmg → App Store
LangChain LCEL 체인                   LangGraph Agent (능동적 분석)
세션 소멸 (앱 종료 시)               학습 세션 JSON 영구 저장
```

### 목표 UX

```text
[사용자]  macOS 메뉴바의 🤖 아이콘 클릭
[메뉴]    "챗봇 열기" 선택
[시스템]  420×700 채팅 창이 화면 우하단에 팝업 (항상 위)

[사용자]  메뉴바 → "논문 선택..." → PDF 파일 선택
[시스템]  채팅 창: "████████ 87개 청크 인덱싱 완료"

[Agent]   "분석 완료. 이 논문은 Spotify 오디오 피처로 음악 인기도를 예측하는
           연구입니다. 핵심 개념: BM25, FAISS, Ensemble Retrieval
           어떤 내용부터 시작할까요?"

[사용자]  "BM25가 뭐야?"
[시스템]  스트리밍 타이핑 애니메이션으로 답변 → 출처: p.3, p.7

[시스템]  학습 세션 자동 저장: sessions/{pdf_hash}.json
```

---

## 2. 기술 선택 근거

### 2-1. 메뉴바: rumps vs macOS Quick Action

| 항목 | rumps (메뉴바 앱) | Quick Action (Automator) |
|------|-----------------|--------------------------|
| 상시 접근 | 메뉴바 아이콘 클릭 1회 | PDF 파일 우클릭 필요 |
| 상태 표시 | 현재 논문 실시간 표시 | 상태 표시 불가 |
| 최근 논문 | submenu로 이력 관리 | 불가 |
| App Store 배포 | py2app 번들링 가능 | 불가 |
| 구현 복잡도 | 중간 | 낮음 |
| **선택** | **채택** | **Quick Action은 fallback 유지** |

### 2-2. 채팅 창: pywebview vs PyQt6

| 항목 | pywebview | PyQt6 |
|------|-----------|-------|
| 렌더링 엔진 | WKWebView (macOS 네이티브) | Chromium 번들 |
| 번들 크기 | ~5MB | ~200MB+ |
| HTML/CSS/JS 재사용 | 그대로 사용 | QSS로 재작성 필요 |
| App Store 허가 | WKWebView = macOS 기본 허가 | 별도 심사 필요 |
| SSE 스트리밍 | fetch/EventSource 표준 사용 | 별도 구현 필요 |
| **선택** | **채택** | **미채택** |

### 2-3. 백엔드: FastAPI vs Flask

| 항목 | FastAPI | Flask |
|------|---------|-------|
| SSE 스트리밍 | `StreamingResponse` 내장 | 수동 구현 필요 |
| 타입 안전성 | Pydantic 모델 | 없음 |
| 비동기 | async/await 기본 | 별도 확장 필요 |
| **선택** | **채택** | **미채택** |

FastAPI의 `StreamingResponse`가 `PDFChatbot.stream_chat()` Generator와 자연스럽게 결합된다.

### 2-4. 프로세스 분리: rumps + pywebview NSRunLoop 충돌 해결

macOS에서 `rumps`와 `pywebview` 모두 메인 스레드(NSRunLoop)를 요구한다.

```text
[단일 프로세스 시도 → 실패]
  Main thread → rumps.App.run() (NSRunLoop 점유)
  Thread → webview.create_window() → 크래시
  이유: macOS WKWebView는 반드시 main thread에서만 생성 가능

[해결: 두 프로세스 분리]
  Process 1 (메인): rumps + FastAPI 서버 (백그라운드 스레드)
  Process 2 (온디맨드): pywebview 채팅 창 → subprocess.Popen()으로 실행
  통신: FastAPI HTTP + SSE (두 프로세스 공통 인터페이스)
  결과: 각 프로세스 독립 NSRunLoop → 충돌 없음
```

---

## 3. 전체 아키텍처

### 프로세스 구조

```text
┌──────────────────────────────────────────────────────────────────────┐
│  PROCESS 1 — 메뉴바 앱 (메인, 항상 실행 중)                          │
│                                                                      │
│  Main Thread                      Background Thread                  │
│  ┌─────────────────────────┐      ┌──────────────────────────────┐   │
│  │  rumps.App (NSRunLoop)  │      │  uvicorn FastAPI Server      │   │
│  │                         │      │  localhost:8765              │   │
│  │  🤖 메뉴바 아이콘       │      │                              │   │
│  │  ├─ 현재 논문: xxx.pdf  │      │  GET  /api/status            │   │
│  │  ├─ 챗봇 열기           │      │  POST /api/load              │   │
│  │  ├─ 논문 선택...        │      │  POST /api/chat     (SSE)    │   │
│  │  ├─ 최근 논문 ▶         │      │  GET  /api/doc-info          │   │
│  │  ├─ 학습 기록 보기      │      │  POST /api/analyze  (SSE)    │   │
│  │  └─ 종료               │      │  GET  /api/session           │   │
│  └──────────┬──────────────┘      └──────────────────────────────┘   │
│             │ subprocess.Popen()          │ PDFChatbot 싱글톤         │
└─────────────┼───────────────────────────-┼──────────────────────────┘
              │                             │ HTTP + SSE
              ▼                             │
┌─────────────────────────────┐            │
│  PROCESS 2 — 채팅 창         │            │
│  (온디맨드, 클릭 시 실행)    │            │
│                             │            │
│  ┌───────────────────────┐  │            │
│  │  pywebview (WKWebView)│  │  fetch()   │
│  │  420×700, 우하단, 위에 │──┼────────────┘
│  │                       │  │
│  │  [채팅 탭] [분석 탭]  │  │
│  │  타이핑 애니메이션    │  │
│  │  출처: p.N 카드       │  │
│  └───────────────────────┘  │
└─────────────────────────────┘
              │
              ▼
┌──────────────────────────────────────────────────────────────────────┐
│  RAG ENGINE LAYER (04_mini_project 재사용)                           │
│                                                                      │
│  PDFChatbot ← sys.path import (코드 복사 없음)                        │
│  ├── BM25 + FAISS Ensemble Retriever                                 │
│  ├── History-Aware RAG Chain                                         │
│  └── FAISS 디스크 캐시 (.cache/ 공유, 재인덱싱 없음)                 │
└──────────────────────────────────────────────────────────────────────┘
```

### 데이터 흐름

```text
[메뉴] "논문 선택..."
  → NSOpenPanel (PDF 선택)
  → POST /api/load {"path": "..."}
  → PDFChatbot 초기화
      ├─ FAISS 캐시 히트: ~1초 로드
      └─ 캐시 없음:  ~30초 인덱싱
  → GET /api/status 폴링 → {"status": "ready"}

[사용자] "BM25가 뭐야?" 입력
  → POST /api/chat SSE 스트리밍
  → LangGraph Router → explain_node
  → stream_chat() Generator → SSE
      data: {"type":"token", "content":"B"}
      data: {"type":"token", "content":"M25는 "}
      ...
      data: {"type":"sources", "content":[{"page":3,...}]}
      data: {"type":"done"}
  → 타이핑 애니메이션 + 출처 카드 렌더링
  → sessions/{hash}.json 자동 저장
```

---

## 4. UI 설계

### 4-1. 메뉴바 구조 (rumps)

```text
🤖  (클릭 시 드롭다운)
├── 현재 논문: predicting_music.pdf   ← 비활성 상태 텍스트
├── ─────────────────────────────────
├── 챗봇 열기                          ← 창 없으면 subprocess.Popen()
│                                        창 있으면 최상단으로 올리기
├── 논문 선택...                        ← NSOpenPanel 파일 다이얼로그
├── 최근 논문 ▶
│   ├── predicting_music.pdf           ← 클릭 시 즉시 로드
│   ├── attention_is_all_you_need.pdf
│   └── ...
├── ─────────────────────────────────
├── 학습 기록 보기                      ← Finder에서 sessions/ 폴더 열기
├── ─────────────────────────────────
└── 종료                               ← FastAPI 서버 종료 후 앱 종료

메뉴바 아이콘 상태 변화:
  🤖  논문 없음 (기본)
  📄  인덱싱 중
  ✅  준비 완료
  ⚠️  Ollama 연결 오류
```

### 4-2. 채팅 창 레이아웃 (pywebview HTML/CSS)

```text
┌──────────────────────────────────────────────┐  ← 420px
│ ╔════════════════════════════════════════╗   │
│ ║  🤖 논문 AI 챗봇        [채팅] [분석]  ║   │  ← 헤더 (드래그 핸들, -webkit-app-region: drag)
│ ╚════════════════════════════════════════╝   │     헤더 잡고 드래그 → 창 이동
│                                              │
│ ┌──────────────────────────────────────────┐ │
│ │ 📄 predicting_music.pdf  87청크 12페이지│ │  ← 논문 배너
│ └──────────────────────────────────────────┘ │
│                                              │
│ ─────────────── 대화 영역 ─────────────── ↑ │
│                                           │  │
│ 🤖 이 논문은 Spotify 오디오 피처로...    │  │  스크롤
│    📄 출처: p.1, p.2                      │  │  가능
│                                           │  │
│ 👤 BM25가 뭐야?                          │  │
│                                           │  │
│ 🤖 BM25는 키워드 기반 검색 알고리즘으로  │  │
│    ▌ ← 타이핑 커서 애니메이션            │  │
│                                           ↓  │
│ ──────────────────────────────────────────   │
│ ┌──────────────────────────────────────────┐ │
│ │ 질문을 입력하세요...                     │ │  ← textarea
│ └──────────────────────────────────────────┘ │
│ [        전송        ]  [초기화]              │
└──────────────────────────────────────────────┘
                    700px
         기본 위치: PDF 뷰어 오른쪽 · 항상 위 (on_top=True)
         이동 후 위치 자동 기억 (preferences.json)
```

**창 드래그 구현 (CSS)**

```css
/* ui/style.css */
.header {
    -webkit-app-region: drag;   /* 헤더 전체: 드래그 핸들 */
    cursor: grab;
}

/* 헤더 안 버튼/탭은 클릭 가능하게 예외 처리 */
.header button,
.header .tab {
    -webkit-app-region: no-drag;
}

/* 나머지 영역: 드래그 불가 (텍스트 선택, 스크롤 보장) */
.chat-area, .input-area {
    -webkit-app-region: no-drag;
}
```

**pywebview 창 생성 옵션**

```python
# webview_process.py
window = webview.create_window(
    title="논문 AI 챗봇",
    url=f"http://localhost:8765/ui/index.html",
    width=420,
    height=700,
    x=calculated_x,          # Quartz로 계산한 PDF 오른쪽 좌표
    y=calculated_y,
    frameless=True,           # 타이틀바 제거 → CSS 헤더가 드래그 핸들
    on_top=True,              # 항상 위 (Always on Top)
    resizable=False,          # 고정 크기 (채팅 UI 레이아웃 유지)
)
```

### 4-2a. 스마트 창 위치 계산

PDF 뷰어(Preview, Adobe Acrobat 등)의 실제 화면 좌표를 읽어 오른쪽에 배치한다.
PDF 뷰어를 찾지 못하면 마지막 사용 위치(preferences.json) → 없으면 화면 우상단.

```text
창 위치 결정 우선순위:
  1순위: Quartz로 PDF 뷰어 위치 감지 → PDF 오른쪽에 배치
  2순위: preferences.json에 저장된 마지막 위치
  3순위: 폴백 — 화면 우상단 (screen_width - 440, 60)
```

```python
# webview_process.py
import Quartz

PDF_APPS = {"Preview", "Adobe Acrobat", "PDF Expert", "Skim", "PDF Viewer"}
CHAT_W, CHAT_H, MARGIN = 420, 700, 10

def get_pdf_viewer_frame() -> dict | None:
    """현재 화면에 표시된 PDF 뷰어 앱의 위치·크기를 반환한다."""
    window_list = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly |
        Quartz.kCGWindowListExcludeDesktopElements,
        Quartz.kCGNullWindowID,
    )
    for win in window_list:
        owner = win.get(Quartz.kCGWindowOwnerName, "")
        layer = win.get(Quartz.kCGWindowLayer, -1)
        if owner in PDF_APPS and layer == 0:
            return win.get(Quartz.kCGWindowBounds)  # {'X','Y','Width','Height'}
    return None

def calculate_window_position(prefs: dict) -> tuple[int, int]:
    screen = webview.screens[0]
    sw, sh = screen.width, screen.height

    pdf_frame = get_pdf_viewer_frame()
    if pdf_frame:
        x = int(pdf_frame["X"] + pdf_frame["Width"] + MARGIN)
        y = int(pdf_frame["Y"])
        # 화면 오른쪽을 벗어나면 PDF 왼쪽에 배치
        if x + CHAT_W > sw:
            x = int(pdf_frame["X"]) - CHAT_W - MARGIN
        return max(0, x), max(0, y)

    # 마지막 위치 복원
    if "window_x" in prefs and "window_y" in prefs:
        return prefs["window_x"], prefs["window_y"]

    # 폴백: 화면 우상단 (macOS 메뉴바 높이 24px 고려)
    return sw - CHAT_W - MARGIN, 60
```

**창 이동 시 위치 자동 저장**

pywebview에서 창 이동을 감지하는 직접 이벤트는 없으므로, JS가 주기적으로 위치를 읽어 Python에 전달한다.

```javascript
// ui/chat.js — 1초마다 위치 변경 감지 → Python에 저장
let lastX = null, lastY = null;
setInterval(async () => {
    // pywebview JS API: window.screenX, window.screenY는 pywebview가 주입
    const x = window.screenX, y = window.screenY;
    if (x !== lastX || y !== lastY) {
        lastX = x; lastY = y;
        await window.pywebview.api.save_window_position(x, y);
    }
}, 1000);
```

### 4-3. 분석 탭 (Phase 2)

```text
┌──────────────────────────────────────────────┐
│  [채팅] [분석 ✓]                             │
│                                              │
│  📋 논문 요약                                │
│  ┌──────────────────────────────────────┐   │
│  │ 이 논문은 Spotify API에서 추출한     │   │
│  │ 오디오 피처를 활용하여 음악 인기도를  │   │
│  │ 예측하는 머신러닝 연구입니다.         │   │
│  └──────────────────────────────────────┘   │
│                                              │
│  🏷️ 핵심 개념                               │
│  [BM25] [FAISS] [Ensemble Retrieval]        │
│  [TF-IDF] [Cosine Similarity]               │
│                                              │
│  📊 학습 진도                                │
│  ✅ BM25  ⬜ FAISS  ⬜ Ensemble            │
└──────────────────────────────────────────────┘
```

### 4-4. 이어서 학습 화면 (Phase 3)

```text
┌──────────────────────────────────────────────┐
│  이전에 이 논문을 학습한 기록이 있습니다.     │
│                                              │
│  📅 마지막 접속:   2026-03-20 11:30          │
│  💬 질문한 내용:   7개                       │
│  ✅ 이해한 개념:   BM25 (1개)               │
│  ⬜ 미학습 개념:   FAISS, Ensemble... (4개)  │
│                                              │
│  [이어서 학습하기]   [처음부터 시작하기]      │
└──────────────────────────────────────────────┘
```

---

## 5. FastAPI 엔드포인트 설계

**포트: `8765`** (Streamlit 8501/8502와 충돌 없음)

### 5-1. 전체 엔드포인트 목록

```text
Method  Endpoint             스트리밍   설명
──────  ───────────────────  ─────────  ─────────────────────────────
GET     /api/status          No         서버·엔진 상태 조회
POST    /api/load            No         PDF 로드 및 인덱싱 트리거
GET     /api/doc-info        No         현재 문서 메타데이터
POST    /api/chat            Yes (SSE)  질문 → 스트리밍 답변
POST    /api/analyze         Yes (SSE)  논문 자동 분석 (초기 1회)
GET     /api/session         No         현재 학습 세션 조회
POST    /api/session/clear   No         대화 히스토리 초기화
GET     /api/recent-papers   No         최근 논문 목록 (최대 5개)
```

### 5-2. 주요 엔드포인트 상세

**GET /api/status**
```json
// Response 200
{
  "status":      "ready | loading | no_paper | error",
  "ollama_ok":   true,
  "paper_name":  "predicting_music.pdf",
  "loading_pct": 0
}
```

**POST /api/load**
```json
// Request
{"path": "/Users/.../predicting_music.pdf"}

// Response 202
{"accepted": true, "cached": true, "msg": "캐시에서 즉시 로드"}
// 실제 인덱싱은 백그라운드에서 진행, GET /api/status로 진행 상태 확인
```

**POST /api/chat** — SSE 스트리밍
```text
// Request
{"question": "BM25가 뭐야?", "session_id": "webview_session_1"}

// Response: text/event-stream
data: {"type": "token",   "content": "BM25는 "}
data: {"type": "token",   "content": "키워드 기반 "}
...
data: {"type": "sources", "content": [{"page": 3, "text": "BM25 (Best Match 25)..."}]}
data: {"type": "done",    "content": null}

// 오류 시
data: {"type": "error",   "content": "Ollama 서버에 연결할 수 없습니다."}
data: {"type": "done",    "content": null}
```

**POST /api/analyze** — SSE 스트리밍 (분석 탭)
```text
// Response: text/event-stream
data: {"type": "progress", "step": "summary",  "pct": 30}
data: {"type": "token",    "content": "이 논문은 "}
...
data: {"type": "progress", "step": "concepts", "pct": 70}
data: {"type": "concepts", "content": ["BM25", "FAISS", "Ensemble Retrieval"]}
data: {"type": "progress", "step": "done",     "pct": 100}
data: {"type": "done",     "content": null}
```

**GET /api/session**
```json
// Response 200
{
  "pdf_hash":     "a1b2c3d4e5f6",
  "started_at":   "2026-03-20T10:00:00",
  "last_accessed":"2026-03-20T11:30:00",
  "total_sessions": 3,
  "questions_asked": 7,
  "concepts_learned": [
    {"concept": "BM25",  "understood": true,  "quiz_score": 1},
    {"concept": "FAISS", "understood": null,  "quiz_score": null}
  ]
}
```

---

## 6. pywebview-FastAPI 통신 설계

### 6-1. 통신 방식 결정

```text
방향                     방식                    용도
─────────────────────    ──────────────────────  ─────────────────────────────
JS → FastAPI             fetch() API             질문 전송, PDF 로드, 상태 조회
FastAPI → JS (스트리밍)  SSE (ReadableStream)    토큰 스트리밍, 분석 진행률
JS → Python (동기)       window.pywebview.api    창 위치 저장, Finder 열기
```

### 6-2. SSE 스트리밍 JS 구현 패턴

```javascript
// chat.js — 스트리밍 채팅
async function sendMessage(question) {
  const response = await fetch('http://localhost:8765/api/chat', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({question, session_id: getSessionId()})
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const {done, value} = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, {stream: true});
    const lines = buffer.split('\n\n');
    buffer = lines.pop();   // 미완성 청크 보관

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      const event = JSON.parse(line.slice(6));

      if (event.type === 'token')   appendToken(event.content);   // 타이핑
      if (event.type === 'sources') renderSourceCards(event.content);
      if (event.type === 'done')    finalizeMessage();
      if (event.type === 'error')   showErrorBanner(event.content);
    }
  }
}
```

### 6-3. FastAPI SSE 구현 패턴

```python
# api/routes/chat.py
from fastapi.responses import StreamingResponse

@router.post("/api/chat")
async def chat_stream(req: ChatRequest):
    def generate():
        chatbot = get_chatbot()   # 싱글톤에서 가져오기
        for token in chatbot.stream_chat(req.question, req.session_id):
            yield f'data: {{"type":"token","content":{json.dumps(token)}}}\n\n'

        sources = chatbot.last_sources
        yield f'data: {{"type":"sources","content":{serialize_sources(sources)}}}\n\n'
        yield 'data: {"type":"done","content":null}\n\n'

    return StreamingResponse(generate(), media_type="text/event-stream")
```

### 6-4. pywebview JS Bridge (macOS 네이티브 동작)

```python
# webview_process.py — Python 측 Bridge
class WebviewBridge:
    """JS에서 window.pywebview.api.method() 형태로 호출."""

    def open_file_in_finder(self, path: str) -> None:
        """Finder에서 파일 위치 열기."""
        subprocess.Popen(["open", "-R", path])

    def save_window_position(self, x: int, y: int) -> None:
        """창 위치를 preferences.json에 저장 (다음 열기 시 PDF 뷰어가 없으면 복원)."""
        prefs = load_preferences()
        prefs["window_x"], prefs["window_y"] = x, y
        save_preferences(prefs)

    def is_ollama_running(self) -> bool:
        """Ollama 상태 즉시 확인 (UI 배너용)."""
        import socket
        with socket.socket() as s:
            return s.connect_ex(("localhost", 11434)) == 0
```

```javascript
// JS에서 사용
const ollamaOk = await window.pywebview.api.is_ollama_running();
if (!ollamaOk) {
  showBanner("⚠️ ollama serve를 실행해주세요.");
}
```

### 6-5. CORS 설정

```python
# api/server.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],    # 로컬 전용 서버, 보안 위협 없음
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 7. Phase별 개발 계획

### Phase 1 — 메뉴바 앱 + 기본 채팅

```text
목표: rumps 메뉴바 + pywebview 채팅 창 + FastAPI 연동

신규 의존성:
  rumps>=0.4.0, pywebview>=5.0, fastapi>=0.115.0, uvicorn>=0.32.0

구현 순서 (의존성 기준):
  1. api/engine_state.py     ← PDFChatbot 싱글톤 + threading.Lock
  2. api/server.py           ← FastAPI 앱 + CORS
  3. api/routes/chat.py      ← /api/status + /api/chat SSE
  4. api/routes/document.py  ← /api/load + /api/doc-info + /api/recent-papers
  5. ui/index.html + chat.js + style.css
  6. webview_process.py      ← pywebview 창 + WebviewBridge
  7. menubar_app.py          ← rumps 앱 + uvicorn 스레드 + subprocess 관리

완료 기준:
  ✅ 메뉴바 아이콘 클릭 → 채팅 창 팝업 (420×700, 우하단, 항상 위)
  ✅ "논문 선택..." → NSOpenPanel → PDF 로드 → 채팅 창 상태 업데이트
  ✅ 질문 → SSE 스트리밍 타이핑 애니메이션 → 출처 카드
  ✅ Ollama 미실행 시 에러 배너 자동 표시
  ✅ 04_mini_project FAISS 캐시 공유 (재인덱싱 없음)
  ✅ 동일 PDF 재선택 시 즉시 로드 (~1초)
```

### Phase 2 — LangGraph Agent 통합

```text
목표: 논문 자동 분석 + 의도 기반 도구 선택

구현 파일:
  agent/state.py         ← AgentState TypedDict
  agent/tools.py         ← @tool 5개 (search_paper, summarize, explain, quiz, extract)
  agent/paper_agent.py   ← LangGraph StateGraph
  api/routes/agent.py    ← /api/analyze SSE
  ui/analysis.js         ← 분석 탭 (진행률 바, 개념 태그)

LangGraph 노드:
  analyze_node   → PDF 로드 후 자동 1회 실행 (요약 + 개념 추출)
  router_node    → 의도 분류 (qa / explain / quiz / summarize)
  rag_node       → PDFChatbot.chat() 위임
  explain_node   → explain_concept() 호출
  quiz_node      → generate_quiz() 반환
  summarize_node → summarize_paper() 호출
  session_save   → sessions/{hash}.json 자동 업데이트

완료 기준:
  ✅ PDF 로드 후 30초 내 분석 탭에 요약 + 개념 5개 이상 표시
  ✅ "BM25 설명해줘" → router가 explain_node 선택 → 단계적 설명
  ✅ "퀴즈 내줘" → quiz_node → 문제 + 선택지 + 정답 표시
  ✅ 채팅 창 하단 "🔧 도구: explain_concept" 표시 (투명성)
```

### Phase 3 — 학습 세션 저장

```text
목표: 학습 기록 JSON 영속성 + 이어서 학습

구현 파일:
  session/models.py          ← StudySession, ConceptNote dataclass
  session/session_manager.py ← JSON 저장·로드·이어하기 감지
  api/routes/session.py      ← /api/session GET/POST/clear

완료 기준:
  ✅ 세션 종료 후 sessions/{hash}.json 자동 생성
  ✅ 동일 PDF 재오픈 시 이전 세션 감지 → "이어서 학습하기" 제안
  ✅ 퀴즈 통과 개념 ✅ 마킹, 미학습 개념 우선 안내
  ✅ 메뉴바 → "학습 기록 보기" → Finder에서 sessions/ 폴더 열기
```

### Phase 4 — 배포 준비

```text
목표: py2app 번들링 → .dmg → 코드 서명

구현 파일:
  build/setup.py           ← py2app 빌드 설정
  build/build.sh           ← 빌드 자동화
  build/resources/Icon.icns
  build/resources/entitlements.plist

완료 기준:
  ✅ poetry run python setup.py py2app → dist/PDFChatbot.app 생성
  ✅ 앱 더블클릭 → 메뉴바 아이콘 (Python 설치 불필요)
  ✅ macOS Gatekeeper 경고 없이 실행
```

### Phase 5 — App Store 준비 (선택)

```text
샌드박스 entitlements 설정, 코드 서명, App Store Connect 제출
[상세 내용: Section 8]
```

---

## 8. App Store 배포 로드맵

### 8-1. py2app 번들 설정 (Phase 4)

```python
# build/setup.py
OPTIONS = {
    'plist': {
        'CFBundleIdentifier':    'com.yourname.pdfchatbot',
        'CFBundleVersion':       '1.0.0',
        'LSUIElement':           True,   # Dock 아이콘 숨김 (메뉴바 앱)
        'NSHighResolutionCapable': True,
    },
    'packages': [
        'langchain_classic', 'langchain_community', 'langchain_core',
        'langchain_ollama', 'langchain_huggingface', 'langgraph',
        'fastapi', 'uvicorn', 'pywebview', 'rumps',
        'sentence_transformers', 'faiss',
    ],
    'excludes': ['streamlit', 'ragas', 'playwright'],  # 불필요 패키지 제외
}
```

**빌드 명령:**
```bash
# 개발 모드 (빠름, 시스템 경로 공유)
poetry run python build/setup.py py2app -A

# 배포 모드 (독립 번들, 모든 의존성 복사)
poetry run python build/setup.py py2app
```

### 8-2. 코드 서명 + 공증 (독립 배포)

```bash
# 서명 (Apple Developer Program 필요)
codesign --deep --force --options runtime \
  --entitlements build/resources/entitlements.plist \
  --sign "Developer ID Application: Your Name (TEAMID)" \
  dist/PDFChatbot.app

# 공증 제출
xcrun notarytool submit PDFChatbot.zip \
  --apple-id "your@email.com" --team-id "TEAMID" \
  --password "app-specific-password" --wait

# 공증 스테이플
xcrun stapler staple dist/PDFChatbot.app

# DMG 생성
create-dmg dist/PDFChatbot.app dist/
```

### 8-3. App Store Sandbox Entitlements

```xml
<!-- build/resources/entitlements.plist -->
<dict>
  <key>com.apple.security.app-sandbox</key>
  <true/>
  <key>com.apple.security.files.user-selected.read-only</key>
  <true/>   <!-- NSOpenPanel로 선택한 PDF 읽기 -->
  <key>com.apple.security.files.bookmarks.app-scope</key>
  <true/>   <!-- 최근 논문 목록 복원 (Security-Scoped Bookmark) -->
  <key>com.apple.security.network.client</key>
  <true/>   <!-- Ollama localhost:11434 연결 -->
</dict>
```

### 8-4. Ollama 의존성 처리 전략

App Store 심사 규정상 외부 실행 파일 직접 실행은 거절 사유가 된다.

```text
방법 A — 독립 배포 (.dmg, App Store 미제출)   ← Phase 4 채택
  Ollama를 별도 앱으로 사전 설치 안내
  앱 시작 시 Ollama 상태 확인 → 미설치 시 다운로드 링크 제공

방법 C — 클라우드 LLM 대안                   ← Phase 5 인터페이스 준비
  App Store 버전: OpenAI / Claude API 사용
  독립 배포 버전: Ollama 사용
  환경변수 분기: LLM_BACKEND=ollama|openai
```

**Ollama 미설치 시 UI:**
```text
┌────────────────────────────────────────────────────┐
│  ⚠️  Ollama가 실행되지 않았습니다                  │
│                                                    │
│  1. ollama.ai에서 Ollama 설치                      │
│  2. 터미널: ollama pull llama3.2:3b                │
│  3. ollama serve 실행                              │
│                                                    │
│  [Ollama 다운로드 열기]        [나중에 설정]        │
└────────────────────────────────────────────────────┘
```

---

## 9. 폴더 구조

### 9-1. 개발 구조

```text
05_pdf_agent/
├── README.md
│
├── menubar_app.py         ← 진입점: rumps + uvicorn 스레드 + subprocess 관리
├── webview_process.py     ← pywebview 채팅 창 프로세스 (subprocess로 분리 실행)
│
├── api/                   ← FastAPI 백엔드
│   ├── __init__.py
│   ├── server.py          ← FastAPI 앱 + CORS + 라우터 등록
│   ├── engine_state.py    ← PDFChatbot 싱글톤 + threading.Lock 보호
│   └── routes/
│       ├── __init__.py
│       ├── chat.py        ← /api/chat (SSE), /api/status
│       ├── document.py    ← /api/load, /api/doc-info, /api/recent-papers
│       ├── agent.py       ← /api/analyze (SSE) — Phase 2
│       └── session.py     ← /api/session — Phase 3
│
├── agent/                 ← LangGraph Agent — Phase 2
│   ├── __init__.py
│   ├── state.py           ← AgentState TypedDict
│   ├── tools.py           ← @tool 5개
│   └── paper_agent.py     ← LangGraph StateGraph 정의·컴파일
│
├── session/               ← 학습 세션 저장 — Phase 3
│   ├── __init__.py
│   ├── models.py          ← StudySession, ConceptNote dataclass
│   └── session_manager.py ← JSON 저장·로드·이어하기 감지
│
├── ui/                    ← 채팅 창 HTML/CSS/JS
│   ├── index.html         ← 창 뼈대 (탭, 헤더, 입력창)
│   ├── chat.js            ← SSE 스트리밍, 타이핑 애니메이션
│   ├── analysis.js        ← 분석 탭 렌더링 — Phase 2
│   └── style.css          ← 기업 챗봇 스타일 (다크/라이트 모드)
│
├── macos/                 ← Quick Action fallback
│   ├── open_paper_chatbot.sh
│   ├── install_quick_action.sh
│   └── README_macos.md
│
└── build/                 ← 배포 빌드 — Phase 4 (gitignore)
    ├── setup.py           ← py2app 빌드 설정
    ├── build.sh           ← 빌드 자동화 스크립트
    └── resources/
        ├── Icon.icns
        ├── entitlements.plist
        └── Info.plist
```

### 9-2. 배포 번들 구조 (py2app 결과)

```text
dist/PDFChatbot.app/
└── Contents/
    ├── Info.plist               ← LSUIElement=true (Dock 숨김)
    ├── MacOS/PDFChatbot         ← 실행 바이너리
    ├── Resources/
    │   ├── ui/                  ← HTML/CSS/JS (그대로 복사)
    │   ├── Icon.icns
    │   └── lib/python311/       ← 모든 Python 의존성
    └── Frameworks/Python.framework/  ← Python 런타임 독립 번들

사용자 데이터 (앱 업데이트 시 보존):
~/Library/Application Support/PDFChatbot/
├── .cache/           ← FAISS 인덱스 캐시
├── sessions/         ← 학습 세션 JSON
└── preferences.json  ← 최근 논문 목록, 창 위치
```

---

## 10. 학습 연계 맵

```text
04_mini_project/rag_engine.py
  ├── PDFChatbot.stream_chat()    → api/routes/chat.py SSE StreamingResponse에서 소비
  ├── BM25 + FAISS Ensemble       → agent/tools.py search_paper 도구의 백엔드
  └── FAISS .cache/               → 05에서 경로 공유, 재인덱싱 없음

STUDY_PLAN Day 8-9: 에이전트 & Tools
  ├─ @tool 데코레이터             → agent/tools.py 5개 도구
  └─ ReAct 패턴                  → router_node 의도 분류 + 도구 실행

STUDY_PLAN Day 10-11: LangGraph 기초
  ├─ StateGraph, TypedDict        → agent/state.py + paper_agent.py
  ├─ Conditional Edge             → router → 4개 노드 분기
  └─ 사이클 & 루프                → wait_for_input 반복 루프

신규 학습 영역
  ├─ FastAPI + SSE                → api/server.py + StreamingResponse 패턴
  ├─ pywebview WKWebView          → webview_process.py
  ├─ rumps NSStatusBar            → menubar_app.py
  ├─ subprocess 멀티프로세스      → NSRunLoop 충돌 해결
  └─ py2app 번들링                → build/setup.py

                ↓ 통합

        05_pdf_agent/
        (04 RAG + LangGraph + FastAPI + macOS Native UI)

                ↓ 다음

        06_langgraph/ — 05에서 경험한 StateGraph 패턴 체계적 정리
```

---

## 11. 엔지니어링 표준

### 주요 설계 결정

| 결정 | 내용 | 근거 |
|------|------|------|
| 포트 고정 | FastAPI `8765` | 8501(04 Streamlit)과 충돌 없음 |
| 프로세스 분리 | rumps + subprocess(pywebview) | NSRunLoop 충돌 원천 차단 |
| PDFChatbot 싱글톤 | `engine_state.py`에서 `threading.Lock` 보호 | 동시 요청 시 인덱싱 중복 방지 |
| SSE 이벤트 포맷 | `{"type": "...", "content": "..."}` | JS 파서 단순화, 이벤트 타입 명시 |
| 세션 저장 위치 | `~/Library/Application Support/PDFChatbot/` | 앱 업데이트 시 데이터 보존 |
| FAISS 캐시 공유 | `04_mini_project/.cache/` 경로 공유 | 04에서 인덱싱한 논문 즉시 재사용 |
| Ollama 전략 | 독립 배포(.dmg) + API 분기 인터페이스 준비 | App Store 확장 가능성 확보 |

### pyproject.toml 추가 항목

```toml
# poetry add로 설치
rumps = ">=0.4.0"         # macOS 메뉴바 앱
pywebview = ">=5.0"       # 네이티브 WKWebView 창
fastapi = ">=0.115.0"     # REST API + SSE
uvicorn = ">=0.32.0"      # ASGI 서버

# Phase 4 (dev dependency)
py2app = ">=0.28.0"       # macOS 앱 번들링
```

### 핵심 구현 순서

```text
[Phase 1 구현 순서]
  1. api/engine_state.py     ← 모든 라우터의 의존점, 최우선
  2. api/server.py
  3. api/routes/chat.py
  4. api/routes/document.py
  5. ui/ (HTML/CSS/JS)
  6. webview_process.py
  7. menubar_app.py          ← 최후 통합

[Phase 2~3 추가]
  8. agent/ 전체
  9. api/routes/agent.py
  10. session/ 전체
  11. api/routes/session.py
```

---

## 개발 우선순위

```text
Phase 1  메뉴바 앱 + 기본 채팅       — 핵심 UX 완성
Phase 2  LangGraph Agent 통합        — 능동적 학습 안내
Phase 3  학습 세션 저장              — 장기 학습 지원
Phase 4  py2app 번들 + .dmg 배포     — 독립 배포
Phase 5  App Store 준비 (선택)       — 상업적 배포
```

---

RAG Study — Day 8~10 | 작성일: 2026-03-20
