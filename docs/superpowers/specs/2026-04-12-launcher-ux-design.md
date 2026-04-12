# Launcher UX 개선 설계

## Goal

앱 실행 시 메뉴바 클릭 없이 런처 창이 자동으로 표시되어, 사용자가 즉시 새 PDF를 열거나 이전 세션을 이어서 읽을 수 있도록 한다.

## Architecture

기존 420×700 pywebview 창 내에 `#pane-launcher`를 기본 화면으로 추가한다. FastAPI 서버 ready 감지 후 `menubar_app.py`가 webview를 자동으로 오픈한다. 논문이 로드되면 상태 폴링을 통해 채팅 pane으로 자동 전환된다.

## Tech Stack

- pywebview (`window.create_file_dialog`) — 네이티브 파일/폴더 다이얼로그
- FastAPI — 세션 목록·재개 API
- rumps — 메뉴바 텍스트 자동 갱신
- JSON — 채팅 기록 영속성 (session/*.json)

---

## 1. 앱 시작 흐름

1. 앱 실행 → FastAPI 서버 백그라운드 시작
2. 별도 스레드에서 `GET /api/status` 폴링으로 서버 ready 감지
3. ready 확인 즉시 `webview_process.py` subprocess 오픈 (기존 `_open_chat()` 재사용)
4. webview 기본 화면: `#pane-launcher`
5. 런처에서 논문 로드 시 → 채팅 pane 자동 전환
6. 메뉴바 "챗봇 열기": 창이 이미 열려 있으면 포커스만 이동 (현재 동작 유지)

**자동 전환 트리거:** `launcher.js`가 1초마다 `GET /api/status` 폴링.
- `no_paper` → 런처 유지
- `loading` 또는 `ready` → `switchTab('chat')` 호출

## 2. 런처 UI (`#pane-launcher`)

기존 온보딩 pane과 동일한 구조로 `index.html`에 추가.

```
┌──────────────────────────┐
│  🤖 PDFChatbot      [✕]  │  ← 기존 헤더 (탭 버튼 숨김)
├──────────────────────────┤
│  [📄 새 PDF 열기]         │
│  [📁 논문 폴더: Downloads] │  ← 설정된 폴더명 표시
├──────────────────────────┤
│  최근 세션                 │
│  ┌────────────────────┐  │
│  │ 📄 paper.pdf       │  │
│  │ 2026-04-10 · 3회   │  │
│  │       [이어서 읽기]  │  │
│  └────────────────────┘  │
│  (세션 없음: 안내 문구)    │
└──────────────────────────┘
```

- 탭 헤더(채팅/분석/설정)는 런처 pane 표시 중 숨김, 논문 로드 후 표시
- "논문 폴더" 버튼: 현재 설정된 폴더명을 버튼 텍스트에 표시
- 세션 카드: `last_accessed` 기준 최신순 정렬, 최대 10개

## 3. 파일/폴더 다이얼로그

`WebviewBridge`에 두 메서드 추가. JS에서 `window.pywebview.api.method()` 직접 호출.

```python
def open_file_dialog(self) -> str | None:
    """PDF 파일 선택 → 경로 반환"""
    result = self._window_ref[0].create_file_dialog(
        webview.OPEN_DIALOG,
        allow_multiple=False,
        file_types=('PDF files (*.pdf)',)
    )
    return result[0] if result else None

def set_paper_folder(self) -> str | None:
    """논문 폴더 선택 → preferences.json 저장 → 경로 반환"""
    result = self._window_ref[0].create_file_dialog(webview.FOLDER_DIALOG)
    if result:
        path = result[0]
        prefs = _load_prefs()
        prefs["watched_folder"] = path
        _save_prefs(prefs)
        return path
    return None
```

`menubar_app.py`의 `_poll_status()`에서 `preferences.json` 변경을 감지해 메뉴 텍스트를 갱신한다.

## 4. 채팅 기록 영속성

### `session/models.py`

`StudySession`에 필드 추가:

```python
pdf_path: str = ""                          # 재개 시 PDF 재로드용
chat_messages: list[dict] = field(default_factory=list)
# 각 항목: {"role": "user"|"assistant", "content": str}
```

### `session/session_manager.py`

- `upsert_session()`: `pdf_path` 파라미터 추가
- `append_chat_message(pdf_path, role, content)` 신규 함수

### `api/routes/chat.py`

스트리밍 응답 완료 후 user/assistant 메시지를 세션에 저장:

```python
append_chat_message(pdf_path, "user", question)
append_chat_message(pdf_path, "assistant", full_response)
```

## 5. 새 API 엔드포인트 (`api/routes/session.py`)

### `GET /api/sessions`

세션 디렉터리의 모든 JSON 파일을 읽어 최신순으로 반환.

```json
[
  {
    "pdf_hash": "abc123",
    "pdf_name": "paper.pdf",
    "pdf_path": "/path/to/paper.pdf",
    "last_accessed": "2026-04-10T12:00:00",
    "total_sessions": 3
  }
]
```

`pdf_path`가 존재하지 않는 파일은 `"missing": true` 플래그 포함.

### `POST /api/sessions/{hash}/resume`

저장된 `pdf_path`로 PDF를 재로드하고 채팅 기록을 반환.

```json
{
  "ok": true,
  "chat_messages": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}
```

실패 시(파일 없음, 로드 오류): `{"ok": false, "detail": "..."}`

## 6. `launcher.js` 동작

```
loadLauncher()
  ├── GET /api/sessions → 세션 카드 렌더링
  ├── GET /api/settings → 논문 폴더 버튼 텍스트 설정
  └── 1초 폴링 시작 (status 감시)

openNewPdf()
  └── window.pywebview.api.open_file_dialog()
      └── POST /api/load → 성공 시 switchTab('chat')

setPaperFolder()
  └── window.pywebview.api.set_paper_folder()
      └── 버튼 텍스트 갱신

resumeSession(hash)
  └── POST /api/sessions/{hash}/resume
      └── 채팅 기록 렌더링 → switchTab('chat')
```

## 7. 변경 파일 목록

| 파일 | 변경 |
|------|------|
| `menubar_app.py` | 서버 ready 후 webview 자동 오픈; 메뉴 텍스트 "논문 폴더"로 변경; poll에서 폴더 라벨 갱신 |
| `webview_process.py` | `open_file_dialog()`, `set_paper_folder()` bridge 추가 |
| `session/models.py` | `pdf_path`, `chat_messages` 필드 추가 |
| `session/session_manager.py` | `upsert_session` pdf_path 파라미터 추가; `append_chat_message()` 추가 |
| `api/routes/chat.py` | 응답 완료 후 메시지 세션 저장 |
| `api/routes/session.py` | `GET /api/sessions`, `POST /api/sessions/{hash}/resume` 추가 |
| `ui/index.html` | `#pane-launcher` 추가; 탭 헤더 조건부 표시 로직 |
| `ui/launcher.js` | 신규 파일 |
| `ui/style.css` | 런처 스타일 추가 |
| `setup.py` | `launcher.js` DATA_FILES 추가 |
