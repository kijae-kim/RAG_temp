# Launcher UX 개선 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 앱 실행 시 자동으로 런처 창을 띄워 새 PDF 열기·이전 세션 재개·논문 폴더 설정을 한 화면에서 즉시 처리한다.

**Architecture:** 기존 pywebview 창에 `#pane-launcher`를 기본 화면으로 추가하고, FastAPI 서버 ready 감지 후 menubar_app.py가 webview를 자동 오픈한다. 채팅 메시지를 session JSON에 영속 저장해 "이어서 읽기" 시 복원한다.

**Tech Stack:** Python dataclasses, FastAPI, pywebview js_api, rumps, vanilla JS

---

## 파일 구조

| 파일 | 역할 |
|------|------|
| `session/models.py` | `pdf_path`, `chat_messages` 필드 추가 |
| `session/session_manager.py` | `upsert_session`에 pdf_path 저장, `append_chat_message()` 추가 |
| `api/routes/chat.py` | 스트리밍 완료 후 메시지 세션 저장 |
| `api/routes/settings.py` | GET 응답에 `watched_folder` 추가 |
| `api/routes/session.py` | `GET /api/sessions`, `POST /api/sessions/{hash}/resume` 추가 |
| `menubar_app.py` | 서버 ready 후 webview 자동 오픈, 메뉴 텍스트 수정 |
| `webview_process.py` | `open_file_dialog()`, `set_paper_folder()` bridge 추가 |
| `ui/chat.js` | `switchTab()` — launcher 분기 추가 |
| `ui/onboarding.js` | `_hideOnboarding()` → launcher로 전환 |
| `ui/index.html` | `#pane-launcher` 추가, 기본 pane을 launcher로 변경 |
| `ui/launcher.js` | 신규: 런처 로직 |
| `ui/style.css` | 런처 스타일 추가 |
| `setup.py` | `launcher.js` DATA_FILES 추가 |

---

### Task 1: session/models.py — pdf_path + chat_messages 필드 추가

**Files:**
- Modify: `05_pdf_agent/session/models.py`

**Context:** `StudySession` 데이터클래스에 두 필드를 추가한다. 기본값이 있으므로 기존 JSON 파일과 하위 호환된다.

- [ ] **Step 1: models.py 전체를 아래 코드로 교체한다**

```python
"""
session/models.py

학습 세션 데이터 모델.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class ConceptNote:
    concept: str           # 영어 원문 태그 (e.g. "BM25")
    understood: bool = False  # 퀴즈 통과 여부
    quiz_score: int = 0    # 누적 퀴즈 정답 수


@dataclass
class StudySession:
    pdf_hash: str          # SHA256[:12] — 파일명 충돌 방지
    pdf_name: str          # 표시용 파일명
    started_at: str        # ISO datetime (첫 세션 시작)
    last_accessed: str     # ISO datetime (최종 접근)
    total_sessions: int = 1
    questions_asked: int = 0
    concepts_learned: list[ConceptNote] = field(default_factory=list)
    summary: str = ""
    pdf_path: str = ""                           # 재개 시 PDF 재로드용
    chat_messages: list[dict] = field(default_factory=list)
    # chat_messages 항목: {"role": "user"|"assistant", "content": str}

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "StudySession":
        d = dict(d)  # 원본 변형 방지
        concepts_data = d.pop("concepts_learned", [])
        d.pop("chat_messages", None)   # 아래서 별도 처리
        chat_data = d.get("chat_messages", [])
        # from_dict 재진입 방지: 나머지 필드만 넘김
        d2 = {k: v for k, v in d.items() if k != "chat_messages"}
        s = cls(**d2)
        s.concepts_learned = [ConceptNote(**c) for c in concepts_data]
        s.chat_messages = list(chat_data)
        return s
```

- [ ] **Step 2: from_dict 버그 수정 확인 — Python REPL로 검증**

```bash
cd /Users/gimgijae/Desktop/Paper/RAG/RAG_Study
poetry run python - <<'EOF'
import sys; sys.path.insert(0, "05_pdf_agent")
from session.models import StudySession, ConceptNote

# 기존 JSON (pdf_path/chat_messages 없음) 로드 테스트
old_data = {
    "pdf_hash": "abc123",
    "pdf_name": "paper.pdf",
    "started_at": "2026-04-01T10:00:00",
    "last_accessed": "2026-04-01T10:00:00",
    "concepts_learned": [{"concept": "BM25", "understood": False, "quiz_score": 0}],
}
s = StudySession.from_dict(old_data)
assert s.pdf_path == "", f"pdf_path default 실패: {s.pdf_path}"
assert s.chat_messages == [], f"chat_messages default 실패"
assert s.concepts_learned[0].concept == "BM25"

# 새 JSON (pdf_path/chat_messages 있음) 로드 테스트
new_data = {**old_data, "pdf_path": "/tmp/paper.pdf",
            "chat_messages": [{"role": "user", "content": "hello"}]}
s2 = StudySession.from_dict(new_data)
assert s2.pdf_path == "/tmp/paper.pdf"
assert s2.chat_messages[0]["role"] == "user"
print("OK: models.py 검증 통과")
EOF
```

Expected: `OK: models.py 검증 통과`

- [ ] **Step 3: 커밋**

```bash
cd /Users/gimgijae/Desktop/Paper/RAG/RAG_Study
git add 05_pdf_agent/session/models.py
git commit -m "Feat: StudySession에 pdf_path, chat_messages 필드 추가"
```

---

### Task 2: session/session_manager.py — upsert_session + append_chat_message

**Files:**
- Modify: `05_pdf_agent/session/session_manager.py`

**Context:** `upsert_session`이 `pdf_path`를 받아 저장하도록 수정하고, 채팅 메시지를 세션에 append하는 함수를 추가한다.

- [ ] **Step 1: session_manager.py 전체를 아래 코드로 교체한다**

```python
"""
session/session_manager.py

학습 세션 JSON 영속성 관리.

저장 위치: ~/Library/Application Support/PDFChatbot/sessions/{pdf_hash}.json
해시: SHA256(pdf_path)[:12] — 경로 기반 고유 식별
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path

from session.models import ConceptNote, StudySession

logger = logging.getLogger(__name__)

_SESSIONS_DIR = Path(
    "~/Library/Application Support/PDFChatbot/sessions"
).expanduser()


def _pdf_hash(pdf_path: str) -> str:
    return hashlib.sha256(pdf_path.encode()).hexdigest()[:12]


def _session_path(pdf_hash: str) -> Path:
    _SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    return _SESSIONS_DIR / f"{pdf_hash}.json"


def load_session(pdf_path: str) -> StudySession | None:
    """PDF 경로로 저장된 세션을 불러온다. 없으면 None."""
    h = _pdf_hash(pdf_path)
    p = _session_path(h)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return StudySession.from_dict(data)
    except Exception as exc:
        logger.warning("세션 로드 실패 (%s): %s", p, exc)
        return None


def save_session(session: StudySession) -> None:
    """세션을 JSON 파일로 저장한다."""
    p = _session_path(session.pdf_hash)
    try:
        p.write_text(
            json.dumps(session.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("세션 저장: %s", p.name)
    except Exception as exc:
        logger.error("세션 저장 실패: %s", exc)


def upsert_session(
    pdf_path: str,
    pdf_name: str,
    summary: str,
    concepts: list[str],
) -> StudySession:
    """
    세션을 새로 만들거나 기존 세션을 갱신한다.

    - 기존 세션: total_sessions+1, concepts_learned의 understood 상태 보존
    - 신규 세션: 모든 필드 초기화
    """
    now = datetime.now().isoformat(timespec="seconds")
    existing = load_session(pdf_path)

    if existing:
        existing.last_accessed = now
        existing.total_sessions += 1
        existing.summary = summary
        existing.pdf_path = pdf_path  # 항상 최신 경로로 갱신
        prev_map = {c.concept: c for c in existing.concepts_learned}
        existing.concepts_learned = [
            prev_map.get(c, ConceptNote(concept=c)) for c in concepts
        ]
        save_session(existing)
        return existing

    h = _pdf_hash(pdf_path)
    session = StudySession(
        pdf_hash=h,
        pdf_name=pdf_name,
        started_at=now,
        last_accessed=now,
        pdf_path=pdf_path,
        summary=summary,
        concepts_learned=[ConceptNote(concept=c) for c in concepts],
    )
    save_session(session)
    return session


def increment_questions(pdf_path: str) -> None:
    """채팅 질문 1회 → questions_asked 증가 + last_accessed 갱신."""
    session = load_session(pdf_path)
    if session:
        session.questions_asked += 1
        session.last_accessed = datetime.now().isoformat(timespec="seconds")
        save_session(session)


def mark_concept_understood(pdf_path: str, concept: str) -> bool:
    """개념을 '이해 완료'로 마킹하고 quiz_score+1한다."""
    session = load_session(pdf_path)
    if not session:
        return False
    for c in session.concepts_learned:
        if c.concept == concept:
            c.understood = True
            c.quiz_score += 1
            save_session(session)
            return True
    return False


def append_chat_message(pdf_path: str, role: str, content: str) -> None:
    """채팅 메시지를 세션에 추가한다. 세션이 없으면 무시."""
    session = load_session(pdf_path)
    if not session:
        return
    session.chat_messages.append({"role": role, "content": content})
    session.last_accessed = datetime.now().isoformat(timespec="seconds")
    save_session(session)
```

- [ ] **Step 2: append_chat_message 동작 검증**

```bash
cd /Users/gimgijae/Desktop/Paper/RAG/RAG_Study
poetry run python - <<'EOF'
import sys; sys.path.insert(0, "05_pdf_agent")
from session.session_manager import upsert_session, append_chat_message, load_session
import tempfile, os

# 임시 PDF 경로 (실제 파일 없어도 됨)
pdf_path = "/tmp/test_paper_plan.pdf"

upsert_session(pdf_path, "test.pdf", "요약", ["BM25"])
append_chat_message(pdf_path, "user", "BM25가 뭐야?")
append_chat_message(pdf_path, "assistant", "BM25는 정보 검색 알고리즘입니다.")

s = load_session(pdf_path)
assert s.pdf_path == pdf_path, f"pdf_path 저장 실패: {s.pdf_path}"
assert len(s.chat_messages) == 2, f"메시지 수 실패: {len(s.chat_messages)}"
assert s.chat_messages[0]["role"] == "user"
assert s.chat_messages[1]["role"] == "assistant"
print("OK: session_manager 검증 통과")
EOF
```

Expected: `OK: session_manager 검증 통과`

- [ ] **Step 3: 커밋**

```bash
cd /Users/gimgijae/Desktop/Paper/RAG/RAG_Study
git add 05_pdf_agent/session/session_manager.py
git commit -m "Feat: upsert_session pdf_path 저장, append_chat_message 추가"
```

---

### Task 3: api/routes/chat.py — 스트리밍 완료 후 메시지 저장

**Files:**
- Modify: `05_pdf_agent/api/routes/chat.py`

**Context:** `generate()` 제너레이터에서 토큰을 누적해 스트리밍 완료 후 user/assistant 메시지를 세션에 저장한다.

- [ ] **Step 1: chat.py의 generate() 함수를 아래 코드로 교체한다**

`05_pdf_agent/api/routes/chat.py`의 `generate()` 함수 전체 (67~95번째 줄):

```python
    def generate():
        full_response: list[str] = []
        try:
            # Phase 2: LangGraph로 의도 분류 (동기, ~1~2초)
            yield 'data: {"type":"intent_classifying"}\n\n'
            intent = classify_intent(req.question)
            yield f"data: {json.dumps({'type': 'intent', 'content': intent}, ensure_ascii=False)}\n\n"

            # 의도에 맞는 스트리밍 함수 선택 후 API 레이어에서 직접 스트리밍
            stream_fn = STREAM_FN_MAP.get(intent, STREAM_FN_MAP["qa"])
            for token in stream_fn(chatbot, req.question, req.session_id, req.style):
                full_response.append(token)
                yield f"data: {json.dumps({'type': 'token', 'content': token}, ensure_ascii=False)}\n\n"

            sources = chatbot.last_sources or []
            yield f"data: {{\"type\":\"sources\",\"content\":{_serialize_sources(sources, get_paper_path())}}}\n\n"
            yield "data: {\"type\":\"done\",\"content\":null}\n\n"

            # 질문 카운터 증가 + 채팅 메시지 저장
            try:
                from session.session_manager import append_chat_message, increment_questions
                paper_path = get_paper_path()
                if paper_path:
                    increment_questions(paper_path)
                    append_chat_message(paper_path, "user", req.question)
                    append_chat_message(paper_path, "assistant", "".join(full_response))
            except Exception:
                pass

        except Exception as exc:
            logger.exception("스트리밍 오류: %s", exc)
            yield f"data: {json.dumps({'type': 'error', 'content': str(exc)}, ensure_ascii=False)}\n\n"
            yield "data: {\"type\":\"done\",\"content\":null}\n\n"
```

- [ ] **Step 2: 개발 서버로 동작 확인**

```bash
cd /Users/gimgijae/Desktop/Paper/RAG/RAG_Study
poetry run python 05_pdf_agent/menubar_app.py &
sleep 3
# 별도 터미널에서 PDF 로드 후 채팅 요청 → 세션 파일에 chat_messages 확인
# cat ~/Library/Application\ Support/PDFChatbot/sessions/*.json | grep chat_messages
```

- [ ] **Step 3: 커밋**

```bash
cd /Users/gimgijae/Desktop/Paper/RAG/RAG_Study
git add 05_pdf_agent/api/routes/chat.py
git commit -m "Feat: 채팅 스트리밍 완료 후 메시지 세션 저장"
```

---

### Task 4: api/routes/settings.py — watched_folder 응답에 추가

**Files:**
- Modify: `05_pdf_agent/api/routes/settings.py`

**Context:** `GET /api/settings`가 `watched_folder`를 반환해야 launcher.js가 논문 폴더 현재 설정을 표시할 수 있다.

- [ ] **Step 1: get_settings() 함수를 아래 코드로 교체한다**

`05_pdf_agent/api/routes/settings.py`의 `get_settings()` (40~48번째 줄):

```python
@router.get("")
async def get_settings():
    import json as _json
    from pathlib import Path as _Path
    _prefs_path = _Path("~/Library/Application Support/PDFChatbot/preferences.json").expanduser()
    _prefs: dict = {}
    if _prefs_path.exists():
        try:
            _prefs = _json.loads(_prefs_path.read_text())
        except Exception:
            pass

    provider = get_provider()
    return {
        "provider": provider,
        "model": get_llm_model(),
        "api_key_saved": bool(get_api_key(provider)),
        "model_options": _MODEL_OPTIONS,
        "watched_folder": _prefs.get("watched_folder", ""),
    }
```

- [ ] **Step 2: curl로 응답 확인**

```bash
cd /Users/gimgijae/Desktop/Paper/RAG/RAG_Study
# 서버가 이미 실행 중이면:
curl -s http://localhost:8765/api/settings | python3 -m json.tool | grep watched_folder
```

Expected: `"watched_folder": "..."` (설정된 경우 경로, 없으면 빈 문자열)

- [ ] **Step 3: 커밋**

```bash
cd /Users/gimgijae/Desktop/Paper/RAG/RAG_Study
git add 05_pdf_agent/api/routes/settings.py
git commit -m "Feat: GET /api/settings에 watched_folder 포함"
```

---

### Task 5: api/routes/session.py — 세션 목록 + 재개 API

**Files:**
- Modify: `05_pdf_agent/api/routes/session.py`

**Context:** 런처가 모든 세션을 목록으로 표시하고 특정 세션을 재개할 수 있도록 두 엔드포인트를 추가한다.

- [ ] **Step 1: session.py 파일 전체를 아래 코드로 교체한다**

```python
"""
api/routes/session.py

GET  /api/session              — 현재 학습 세션 조회
POST /api/session/clear        — 대화 히스토리 초기화 (세션 파일 유지)
POST /api/session/concept      — 개념 이해 완료 마킹
GET  /api/sessions             — 모든 세션 목록 (런처용)
POST /api/sessions/{hash}/resume — 세션 재개 (PDF 재로드 + 채팅 기록 반환)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.engine_state import get_chatbot, get_paper_path

logger = logging.getLogger(__name__)
router = APIRouter()

_SESSIONS_DIR = Path(
    "~/Library/Application Support/PDFChatbot/sessions"
).expanduser()


class ConceptMarkRequest(BaseModel):
    concept: str


@router.get("/api/session")
async def get_session() -> dict:
    """현재 로드된 PDF의 학습 세션 정보를 반환한다."""
    pdf_path = get_paper_path()
    if not pdf_path:
        raise HTTPException(status_code=404, detail="로드된 논문이 없습니다.")

    from session.session_manager import load_session
    session = load_session(pdf_path)
    if not session:
        raise HTTPException(status_code=404, detail="세션 기록이 없습니다. 분석 탭에서 분석을 먼저 실행하세요.")

    return session.to_dict()


class ClearRequest(BaseModel):
    session_id: str = "default"


@router.post("/api/session/clear")
async def clear_session(req: ClearRequest = ClearRequest()) -> dict:
    """
    LangChain 대화 히스토리를 초기화한다.
    세션 JSON 파일(questions_asked 등 통계)은 유지한다.
    """
    chatbot = get_chatbot()
    if chatbot and hasattr(chatbot, "clear_session"):
        try:
            chatbot.clear_session(req.session_id)
        except Exception as exc:
            logger.warning("세션 초기화 오류: %s", exc)
    return {"cleared": True}


@router.post("/api/session/concept")
async def mark_concept(req: ConceptMarkRequest) -> dict:
    """개념을 '이해 완료'로 마킹한다."""
    pdf_path = get_paper_path()
    if not pdf_path:
        raise HTTPException(status_code=400, detail="로드된 논문이 없습니다.")

    from session.session_manager import mark_concept_understood
    ok = mark_concept_understood(pdf_path, req.concept)
    return {"concept": req.concept, "marked": ok}


# ── 런처용 엔드포인트 ────────────────────────────────────────────────────────


@router.get("/api/sessions")
async def list_sessions() -> dict:
    """
    모든 학습 세션을 최신순으로 반환한다 (최대 10개).
    pdf_path가 존재하지 않는 파일은 missing=true 포함.
    """
    if not _SESSIONS_DIR.exists():
        return {"sessions": []}

    result = []
    for f in _SESSIONS_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            pdf_path = data.get("pdf_path", "")
            result.append({
                "pdf_hash": data.get("pdf_hash", ""),
                "pdf_name": data.get("pdf_name", ""),
                "pdf_path": pdf_path,
                "last_accessed": data.get("last_accessed", ""),
                "total_sessions": data.get("total_sessions", 1),
                "missing": bool(pdf_path) and not Path(pdf_path).exists(),
            })
        except Exception as exc:
            logger.warning("세션 파일 읽기 실패 (%s): %s", f.name, exc)

    result.sort(key=lambda x: x["last_accessed"], reverse=True)
    return {"sessions": result[:10]}


@router.post("/api/sessions/{pdf_hash}/resume")
async def resume_session(pdf_hash: str) -> dict:
    """
    저장된 pdf_path로 PDF를 재로드하고 채팅 기록을 반환한다.
    """
    session_file = _SESSIONS_DIR / f"{pdf_hash}.json"
    if not session_file.exists():
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    try:
        data = json.loads(session_file.read_text(encoding="utf-8"))
    except Exception:
        raise HTTPException(status_code=500, detail="세션 파일 읽기 실패.")

    pdf_path = data.get("pdf_path", "")
    if not pdf_path:
        raise HTTPException(status_code=400, detail="세션에 PDF 경로가 없습니다. 분석을 다시 실행하세요.")
    if not Path(pdf_path).exists():
        raise HTTPException(status_code=404, detail=f"PDF 파일을 찾을 수 없습니다: {pdf_path}")

    from api.engine_state import load_pdf_async
    load_pdf_async(pdf_path)

    return {
        "ok": True,
        "pdf_path": pdf_path,
        "pdf_name": data.get("pdf_name", ""),
        "chat_messages": data.get("chat_messages", []),
    }
```

- [ ] **Step 2: 두 엔드포인트 curl 검증**

```bash
# GET /api/sessions
curl -s http://localhost:8765/api/sessions | python3 -m json.tool

# POST /api/sessions/{hash}/resume (실제 hash는 위 GET 결과에서 가져옴)
# curl -s -X POST http://localhost:8765/api/sessions/abc123def456/resume | python3 -m json.tool
```

Expected: `{"sessions": [...]}` 형태 (세션이 있을 경우 목록 반환)

- [ ] **Step 3: 커밋**

```bash
cd /Users/gimgijae/Desktop/Paper/RAG/RAG_Study
git add 05_pdf_agent/api/routes/session.py
git commit -m "Feat: GET /api/sessions, POST /api/sessions/{hash}/resume 추가"
```

---

### Task 6: menubar_app.py — 자동 오픈 + 메뉴 텍스트 수정

**Files:**
- Modify: `05_pdf_agent/menubar_app.py`

**Context:** 서버 ready 감지 후 webview를 자동으로 오픈하고, "감시 폴더" 레이블을 "논문 폴더"로 변경한다. `_poll_status`에서 preferences.json 변경을 감지해 메뉴 라벨도 갱신한다.

- [ ] **Step 1: `__init__` 메서드의 watched 레이블 초기화 부분 수정**

`05_pdf_agent/menubar_app.py` 94~96번째 줄:

```python
        watched_label = f"논문 폴더: {Path(watched).name}" if watched else "논문 폴더 설정..."
        self._watched_folder_item = rumps.MenuItem(watched_label, callback=self._set_watched_folder)
```

- [ ] **Step 2: `__init__` 메서드 끝에 자동 오픈 스레드 추가**

`self._populate_recent_submenu()` 호출 직후, `self.menu = [...]` 이전에 삽입:

```python
        # 서버 준비 후 자동으로 챗봇 창 오픈
        threading.Thread(target=self._open_when_ready, daemon=True).start()
```

- [ ] **Step 3: `_open_when_ready` 메서드 추가**

`_open_chat` 메서드 바로 위에 삽입:

```python
    def _open_when_ready(self) -> None:
        """서버 ready 감지 후 webview를 자동 오픈한다."""
        import time
        for _ in range(60):          # 최대 30초 대기
            try:
                resp = requests.get("http://localhost:8765/api/status", timeout=1)
                if resp.ok:
                    self._open_chat()
                    return
            except Exception:
                pass
            time.sleep(0.5)
```

- [ ] **Step 4: `_set_watched_folder` 메서드의 알림 메시지 수정**

179번째 줄 rumps.notification 텍스트:

```python
                self._watched_folder_item.title = f"논문 폴더: {Path(folder_path).name}"
                rumps.notification("PDF 챗봇", "논문 폴더 설정", f"{Path(folder_path).name} 폴더를 감시합니다.")
```

- [ ] **Step 5: `_poll_status`에 폴더 라벨 갱신 로직 추가**

`_poll_status` 메서드 마지막 `except` 블록 바로 앞에 삽입:

```python
            # 논문 폴더 라벨 동기화 (webview_process에서 변경 시 반영)
            watched = _load_prefs().get("watched_folder", "")
            new_label = f"논문 폴더: {Path(watched).name}" if watched else "논문 폴더 설정..."
            if self._watched_folder_item.title != new_label:
                self._watched_folder_item.title = new_label
```

- [ ] **Step 6: 실행해서 앱 시작 시 자동으로 창이 뜨는지 확인**

```bash
cd /Users/gimgijae/Desktop/Paper/RAG/RAG_Study
poetry run python 05_pdf_agent/menubar_app.py
# 약 3초 후 pywebview 창이 자동으로 열리는지 확인
```

- [ ] **Step 7: 커밋**

```bash
cd /Users/gimgijae/Desktop/Paper/RAG/RAG_Study
git add 05_pdf_agent/menubar_app.py
git commit -m "Feat: 서버 ready 후 webview 자동 오픈, 메뉴 텍스트 논문 폴더로 변경"
```

---

### Task 7: webview_process.py — 파일/폴더 다이얼로그 bridge 추가

**Files:**
- Modify: `05_pdf_agent/webview_process.py`

**Context:** JS에서 `window.pywebview.api.open_file_dialog()`, `window.pywebview.api.set_paper_folder()`를 호출하면 네이티브 파일/폴더 선택 창이 뜬다. `set_paper_folder`는 선택 후 preferences.json에도 저장한다.

- [ ] **Step 1: `WebviewBridge` 클래스에 두 메서드 추가**

`is_ollama_running` 메서드 바로 뒤에 삽입:

```python
    def open_file_dialog(self) -> str | None:
        """PDF 파일 선택 다이얼로그. 선택된 경로를 반환하거나 None."""
        win = self._window_ref[0]
        if not win:
            return None
        result = win.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=False,
            file_types=('PDF files (*.pdf)',),
        )
        return result[0] if result else None

    def set_paper_folder(self) -> str | None:
        """논문 폴더 선택 → preferences.json에 저장 → 경로 반환."""
        win = self._window_ref[0]
        if not win:
            return None
        result = win.create_file_dialog(webview.FOLDER_DIALOG)
        if result:
            path = result[0]
            prefs = _load_prefs()
            prefs["watched_folder"] = path
            _save_prefs(prefs)
            return path
        return None
```

- [ ] **Step 2: 커밋**

```bash
cd /Users/gimgijae/Desktop/Paper/RAG/RAG_Study
git add 05_pdf_agent/webview_process.py
git commit -m "Feat: WebviewBridge에 open_file_dialog, set_paper_folder 추가"
```

---

### Task 8: ui/chat.js — switchTab에 launcher 분기 추가

**Files:**
- Modify: `05_pdf_agent/ui/chat.js`

**Context:** `switchTab('launcher')` 호출 시 탭 버튼을 숨기고 런처 pane을 표시한다. 다른 탭으로 전환 시 탭 버튼을 다시 표시한다.

- [ ] **Step 1: `switchTab` 함수 전체를 아래 코드로 교체한다**

`05_pdf_agent/ui/chat.js` 172~178번째 줄:

```javascript
function switchTab(name) {
  document.querySelectorAll(".tab-content").forEach((p) => p.classList.add("hidden"));

  if (name === "launcher") {
    // 런처: 탭 버튼 숨김, 런처 pane 표시
    document.querySelector(".tabs").classList.add("hidden");
    document.getElementById("pane-launcher").classList.remove("hidden");
    if (typeof loadLauncher === "function") loadLauncher();
    return;
  }

  // 일반 탭: 탭 버튼 표시
  document.querySelector(".tabs").classList.remove("hidden");
  document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
  document.getElementById(`tab-${name}`).classList.add("active");
  document.getElementById(`pane-${name}`).classList.remove("hidden");
  if (name === "settings" && typeof loadSettings === "function") loadSettings();
}
```

- [ ] **Step 2: `paper_ready` 이벤트 핸들러에 런처 → 채팅 자동 전환 추가**

`handleServerEvent`의 `paper_ready` case (54~61번째 줄):

```javascript
    case "paper_ready":
      document.getElementById("banner-text").textContent =
        `📄 ${event.paper_name}  ${event.chunks}청크`;
      hideStatusBanner();
      setBtnEnabled(true);
      // 런처에서 보고 있을 경우 채팅 탭으로 자동 전환
      if (!document.getElementById("pane-launcher").classList.contains("hidden")) {
        switchTab("chat");
      }
      appendBotMessage(`**${event.paper_name}** 로드 완료 (${event.chunks}청크)\n분석 탭에서 요약과 핵심 개념을 확인하세요.`);
      if (typeof triggerAnalyze === "function") triggerAnalyze();
      break;
```

- [ ] **Step 3: 커밋**

```bash
cd /Users/gimgijae/Desktop/Paper/RAG/RAG_Study
git add 05_pdf_agent/ui/chat.js
git commit -m "Feat: switchTab launcher 분기 추가, paper_ready 시 자동 전환"
```

---

### Task 9: ui/onboarding.js — 온보딩 완료 후 런처로 전환

**Files:**
- Modify: `05_pdf_agent/ui/onboarding.js`

**Context:** 온보딩 완료(`obDone`) 시 `_hideOnboarding`이 `switchTab("chat")`을 호출하는데, 이를 `switchTab("launcher")`로 변경한다.

- [ ] **Step 1: `_hideOnboarding` 함수 내 switchTab 호출 변경**

`05_pdf_agent/ui/onboarding.js` 43~48번째 줄:

```javascript
function _hideOnboarding() {
  document.getElementById("pane-onboarding").classList.add("hidden");
  document.querySelectorAll(".tab").forEach(el => el.disabled = false);
  // 런처 탭으로 전환
  switchTab("launcher");
}
```

- [ ] **Step 2: 커밋**

```bash
cd /Users/gimgijae/Desktop/Paper/RAG/RAG_Study
git add 05_pdf_agent/ui/onboarding.js
git commit -m "Feat: 온보딩 완료 후 런처로 전환"
```

---

### Task 10: ui/index.html — #pane-launcher 추가 + 기본 화면 변경

**Files:**
- Modify: `05_pdf_agent/ui/index.html`

**Context:** 기본 표시 pane을 chat → launcher로 변경하고 `#pane-launcher` HTML을 추가한다. launcher.js 스크립트 태그도 삽입한다.

- [ ] **Step 1: 헤더의 채팅 탭 버튼에서 `active` 클래스 제거**

`05_pdf_agent/ui/index.html` 15번째 줄:

```html
        <button class="tab" id="tab-chat" onclick="switchTab('chat')">채팅</button>
```

(`active` 제거 — 런처가 기본이므로 채팅 탭이 active 상태로 시작하지 않음)

- [ ] **Step 2: 채팅 pane div에 `hidden` 클래스 추가**

34번째 줄:

```html
  <div class="tab-content hidden" id="pane-chat">
```

- [ ] **Step 3: `#pane-onboarding` div 바로 앞에 런처 pane 추가**

`<!-- 온보딩 마법사 탭 -->` 주석 바로 앞에 삽입:

```html
  <!-- 런처 pane (기본 화면) -->
  <div class="tab-content" id="pane-launcher">
    <div class="launcher-area">
      <div class="launcher-actions">
        <button class="launcher-btn-primary" onclick="openNewPdf()">📄 새 PDF 열기</button>
        <button class="launcher-btn-secondary" id="btn-paper-folder" onclick="setPaperFolder()">
          📁 논문 폴더 설정...
        </button>
      </div>
      <div class="launcher-section-title">최근 세션</div>
      <div id="launcher-sessions" class="launcher-sessions"></div>
    </div>
  </div>
```

- [ ] **Step 4: `launcher.js` 스크립트 태그 추가**

`<script src="onboarding.js">` 바로 앞에 삽입:

```html
  <script src="launcher.js"></script>
```

- [ ] **Step 5: DOMContentLoaded 인라인 스크립트 수정**

기존 인라인 스크립트 블록을 아래로 교체:

```html
  <script>
    document.addEventListener("DOMContentLoaded", () => {
      setTimeout(async () => {
        // 온보딩 확인: 완료됐으면 런처 표시, 아니면 온보딩
        const res = await fetch("http://localhost:8765/api/onboarding").catch(() => null);
        if (res && res.ok) {
          const data = await res.json();
          if (!data.onboarding_done) {
            // onboarding.js의 _showOnboarding 직접 호출 (checkOnboarding 중복 방지)
            if (typeof _showOnboarding === "function") _showOnboarding();
            return;
          }
        }
        // 온보딩 완료 → 런처 표시
        switchTab("launcher");
      }, 300);
    });
  </script>
```

> **주의:** 기존 `checkOnboarding()` 호출 제거 — 인라인 스크립트에서 직접 처리하므로 중복 방지.

- [ ] **Step 6: 커밋**

```bash
cd /Users/gimgijae/Desktop/Paper/RAG/RAG_Study
git add 05_pdf_agent/ui/index.html
git commit -m "Feat: #pane-launcher 추가, 기본 화면 런처로 변경"
```

---

### Task 11: ui/launcher.js — 런처 로직 신규 파일

**Files:**
- Create: `05_pdf_agent/ui/launcher.js`

**Context:** 런처 pane의 모든 동작을 담당한다. 세션 목록 로드, 파일/폴더 다이얼로그 호출, 세션 재개, 채팅 기록 복원을 처리한다.

- [ ] **Step 1: `05_pdf_agent/ui/launcher.js` 파일 생성**

```javascript
/**
 * launcher.js
 *
 * 런처 pane (#pane-launcher) 로직.
 * - 앱 시작 시 세션 목록 표시
 * - 새 PDF 열기 / 논문 폴더 설정 / 이어서 읽기
 */

const LAUNCHER_API = "http://localhost:8765";
let _launcherPollId = null;

// ── 진입점: switchTab('launcher') 시 호출 ──────────────────────────────────
async function loadLauncher() {
  // 이미 폴링 중이면 재시작 방지
  if (_launcherPollId) clearInterval(_launcherPollId);

  await _refreshSessionList();
  await _refreshFolderButton();

  // 논문이 로드되면 채팅으로 자동 전환
  _launcherPollId = setInterval(async () => {
    try {
      const res = await fetch(`${LAUNCHER_API}/api/status`);
      const data = await res.json();
      if (data.status === "loading" || data.status === "ready") {
        clearInterval(_launcherPollId);
        _launcherPollId = null;
        switchTab("chat");
      }
    } catch (e) { /* 서버 준비 중 */ }
  }, 1000);
}

// ── 세션 목록 새로 고침 ────────────────────────────────────────────────────
async function _refreshSessionList() {
  const container = document.getElementById("launcher-sessions");
  try {
    const res = await fetch(`${LAUNCHER_API}/api/sessions`);
    const data = await res.json();
    _renderSessions(data.sessions || []);
  } catch (e) {
    container.innerHTML = '<p class="launcher-empty">세션 목록을 불러오지 못했습니다.</p>';
  }
}

function _renderSessions(sessions) {
  const container = document.getElementById("launcher-sessions");
  if (!sessions.length) {
    container.innerHTML = '<p class="launcher-empty">저장된 세션이 없습니다.<br>새 PDF를 열어 시작하세요.</p>';
    return;
  }
  container.innerHTML = sessions.map(s => `
    <div class="launcher-card${s.missing ? " launcher-card-missing" : ""}">
      <div class="launcher-card-name">📄 ${_escLauncher(s.pdf_name)}</div>
      <div class="launcher-card-meta">${_fmtDate(s.last_accessed)} · ${s.total_sessions}회</div>
      ${s.missing
        ? '<div class="launcher-missing-label">파일 없음</div>'
        : `<button class="launcher-btn-resume" onclick="resumeSession('${s.pdf_hash}')">이어서 읽기</button>`
      }
    </div>
  `).join("");
}

// ── 논문 폴더 버튼 텍스트 갱신 ───────────────────────────────────────────
async function _refreshFolderButton() {
  try {
    const res = await fetch(`${LAUNCHER_API}/api/settings`);
    const data = await res.json();
    const btn = document.getElementById("btn-paper-folder");
    if (!btn) return;
    if (data.watched_folder) {
      const name = data.watched_folder.split("/").pop();
      btn.textContent = `📁 논문 폴더: ${name}`;
    } else {
      btn.textContent = "📁 논문 폴더 설정...";
    }
  } catch (e) { /* 무시 */ }
}

// ── 새 PDF 열기 ───────────────────────────────────────────────────────────
async function openNewPdf() {
  let path;
  try {
    path = await window.pywebview.api.open_file_dialog();
  } catch (e) {
    // 개발 모드(pywebview 없음): 경로 수동 입력
    path = prompt("PDF 경로 입력 (개발 모드):");
  }
  if (!path) return;

  const res = await fetch(`${LAUNCHER_API}/api/load`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    alert(err.detail || "PDF 로드 실패");
  }
  // 성공 시 상태 폴링이 paper_ready 감지해 자동으로 switchTab('chat') 호출
}

// ── 논문 폴더 설정 ────────────────────────────────────────────────────────
async function setPaperFolder() {
  let path;
  try {
    path = await window.pywebview.api.set_paper_folder();
  } catch (e) {
    path = prompt("논문 폴더 경로 입력 (개발 모드):");
  }
  if (!path) return;
  const name = path.split("/").pop();
  document.getElementById("btn-paper-folder").textContent = `📁 논문 폴더: ${name}`;
}

// ── 세션 재개 ─────────────────────────────────────────────────────────────
async function resumeSession(hash) {
  const res = await fetch(`${LAUNCHER_API}/api/sessions/${hash}/resume`, {
    method: "POST",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    alert(err.detail || "세션 재개 실패: PDF 파일을 찾을 수 없습니다.");
    await _refreshSessionList();
    return;
  }
  const data = await res.json();

  // 채팅 기록 복원
  if (data.chat_messages && data.chat_messages.length) {
    _restoreChatHistory(data.chat_messages);
  }

  clearInterval(_launcherPollId);
  _launcherPollId = null;
  switchTab("chat");
}

function _restoreChatHistory(messages) {
  const area = document.getElementById("chat-area");
  area.innerHTML = "";
  messages.forEach(m => {
    const div = document.createElement("div");
    div.className = `message ${m.role === "user" ? "user" : "bot"}`;
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = m.content;
    div.appendChild(bubble);
    area.appendChild(div);
  });
  area.scrollTop = area.scrollHeight;
}

// ── 유틸 ─────────────────────────────────────────────────────────────────
function _fmtDate(iso) {
  return iso ? iso.slice(0, 10) : "";
}

function _escLauncher(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
```

- [ ] **Step 2: 커밋**

```bash
cd /Users/gimgijae/Desktop/Paper/RAG/RAG_Study
git add 05_pdf_agent/ui/launcher.js
git commit -m "Feat: launcher.js 신규 파일 추가"
```

---

### Task 12: ui/style.css — 런처 스타일 추가

**Files:**
- Modify: `05_pdf_agent/ui/style.css`

**Context:** Catppuccin Mocha 테마를 유지하면서 런처 pane의 레이아웃 스타일을 추가한다.

- [ ] **Step 1: style.css 파일 끝에 아래 CSS를 추가한다**

```css

/* ── 런처 pane ────────────────────────────────────────────────────────── */
.launcher-area {
  display: flex;
  flex-direction: column;
  padding: 16px;
  gap: 12px;
  height: 100%;
  overflow-y: auto;
}

.launcher-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.launcher-btn-primary {
  background: #89b4fa;
  color: #1e1e2e;
  border: none;
  border-radius: 8px;
  padding: 12px 16px;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  text-align: left;
}

.launcher-btn-primary:hover {
  background: #74c7ec;
}

.launcher-btn-secondary {
  background: #313244;
  color: #cdd6f4;
  border: 1px solid #45475a;
  border-radius: 8px;
  padding: 10px 16px;
  font-size: 13px;
  cursor: pointer;
  text-align: left;
}

.launcher-btn-secondary:hover {
  background: #45475a;
}

.launcher-section-title {
  font-size: 12px;
  font-weight: 600;
  color: #6c7086;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-top: 4px;
}

.launcher-sessions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.launcher-card {
  background: #313244;
  border-radius: 8px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.launcher-card-missing {
  opacity: 0.5;
}

.launcher-card-name {
  font-size: 13px;
  font-weight: 600;
  color: #cdd6f4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.launcher-card-meta {
  font-size: 11px;
  color: #6c7086;
}

.launcher-btn-resume {
  align-self: flex-end;
  background: #a6e3a1;
  color: #1e1e2e;
  border: none;
  border-radius: 6px;
  padding: 6px 12px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  margin-top: 4px;
}

.launcher-btn-resume:hover {
  background: #94e2d5;
}

.launcher-missing-label {
  font-size: 11px;
  color: #f38ba8;
  align-self: flex-end;
  margin-top: 4px;
}

.launcher-empty {
  font-size: 13px;
  color: #6c7086;
  text-align: center;
  padding: 24px 0;
  line-height: 1.6;
}
```

- [ ] **Step 2: 커밋**

```bash
cd /Users/gimgijae/Desktop/Paper/RAG/RAG_Study
git add 05_pdf_agent/ui/style.css
git commit -m "Feat: 런처 pane CSS 추가"
```

---

### Task 13: setup.py + 재빌드

**Files:**
- Modify: `05_pdf_agent/setup.py`

**Context:** `launcher.js`를 DATA_FILES에 추가하고 py2app 번들을 재빌드한다.

- [ ] **Step 1: setup.py의 ui DATA_FILES에 launcher.js 추가**

`05_pdf_agent/setup.py` 29~37번째 줄 (`'ui'` 섹션):

```python
    ('ui', [
        _p('ui', 'index.html'),
        _p('ui', 'chat.js'),
        _p('ui', 'style.css'),
        _p('ui', 'settings.js'),
        _p('ui', 'analysis.js'),
        _p('ui', 'onboarding.js'),
        _p('ui', 'launcher.js'),
        _p('ui', 'floating_button.html'),
    ]),
```

- [ ] **Step 2: 커밋**

```bash
cd /Users/gimgijae/Desktop/Paper/RAG/RAG_Study
git add 05_pdf_agent/setup.py
git commit -m "Chore: setup.py에 launcher.js 추가"
```

- [ ] **Step 3: 개발 서버에서 전체 흐름 E2E 검증**

```bash
cd /Users/gimgijae/Desktop/Paper/RAG/RAG_Study
poetry run python 05_pdf_agent/menubar_app.py
```

확인 항목:
1. 앱 시작 약 3초 후 webview 창이 자동으로 열린다
2. 런처 pane이 기본으로 표시된다 (탭 버튼 숨김)
3. "새 PDF 열기" 클릭 → 네이티브 파일 선택창 → 선택 후 채팅 탭으로 전환
4. "논문 폴더 설정" 클릭 → 네이티브 폴더 선택창 → 버튼 텍스트에 폴더명 반영
5. 세션이 있으면 카드 목록 표시, "이어서 읽기" 클릭 → 채팅 기록 복원 + 채팅 탭 전환
6. 논문 로드 완료 후 탭 버튼(채팅/분석/설정) 표시됨

- [ ] **Step 4: py2app 재빌드**

```bash
cd /Users/gimgijae/Desktop/Paper/RAG/RAG_Study/05_pdf_agent
./build.sh
```

- [ ] **Step 5: 번들 앱 실행해서 E2E 재확인**

```bash
open /Users/gimgijae/Desktop/Paper/RAG/RAG_Study/05_pdf_agent/dist/PDFChatbot.app
```

위 6개 확인 항목 동일하게 검증.
