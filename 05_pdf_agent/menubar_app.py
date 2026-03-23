"""
menubar_app.py

macOS 메뉴바 앱 진입점.

Process 1 (이 파일):
  - 단일 인스턴스 보장 (포트 8765 점유 확인)
  - Main Thread: rumps.App (NSRunLoop)
  - Background Thread: uvicorn FastAPI 서버 (port 8765)
  - subprocess.Popen(): webview_process.py (채팅 창, 온디맨드)

실행:
  poetry run python 05_pdf_agent/menubar_app.py
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import threading
from pathlib import Path

import requests
import rumps
import uvicorn

# ── 단일 인스턴스 보장 ────────────────────────────────────────────────────────
def _ensure_single_instance(port: int = 8765) -> None:
    """포트가 이미 점유된 경우 종료한다."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    already_running = sock.connect_ex(("localhost", port)) == 0
    sock.close()
    if already_running:
        # 패키지 앱(.app 번들)이면 포커스 시도, 아니면 그냥 종료
        result = subprocess.run(
            ["open", "-a", "PDFChatbot"], capture_output=True
        )
        if result.returncode != 0:
            print("PDFChatbot이 이미 실행 중입니다.")
        sys.exit(0)


_ensure_single_instance()

# ── FastAPI 서버 ─────────────────────────────────────────────────────────────
_THIS_DIR = Path(__file__).parent
sys.path.insert(0, str(_THIS_DIR))

from api.server import app as fastapi_app  # noqa: E402


def _start_server() -> None:
    uvicorn.run(fastapi_app, host="127.0.0.1", port=8765, log_level="warning")


_server_thread = threading.Thread(target=_start_server, daemon=True)
_server_thread.start()

# ── preferences ──────────────────────────────────────────────────────────────
_PREFS_PATH = Path("~/Library/Application Support/PDFChatbot/preferences.json").expanduser()
_PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)


def _load_prefs() -> dict:
    if _PREFS_PATH.exists():
        try:
            return json.loads(_PREFS_PATH.read_text())
        except Exception:
            pass
    return {"recent_papers": []}


def _save_prefs(prefs: dict) -> None:
    _PREFS_PATH.write_text(json.dumps(prefs, ensure_ascii=False, indent=2))


# ── 메뉴바 앱 ────────────────────────────────────────────────────────────────
class PDFChatbotApp(rumps.App):
    def __init__(self):
        super().__init__("🤖", quit_button=None)
        self._webview_proc: subprocess.Popen | None = None

        # 나중에 title을 바꿔야 하는 항목은 인스턴스 변수로 보관
        self._current_paper_item = rumps.MenuItem("현재 논문: 없음")
        self._recent_submenu = rumps.MenuItem("최근 논문")

        self._populate_recent_submenu()  # 첫 초기화: add()만, clear() 없음

        self.menu = [
            self._current_paper_item,
            None,
            rumps.MenuItem("챗봇 열기",    callback=self._open_chat),
            rumps.MenuItem("논문 선택...", callback=self._select_paper),
            self._recent_submenu,
            None,
            rumps.MenuItem("학습 기록 보기", callback=self._open_sessions),
            None,
            rumps.MenuItem("종료",        callback=self._quit_app),
        ]

    # ── 최근 논문 서브메뉴 ────────────────────────────────────────────────────
    def _populate_recent_submenu(self) -> None:
        """서브메뉴 아이템을 채운다 — clear() 없이 add()만 사용 (최초 초기화용)."""
        prefs = _load_prefs()
        recent = [p for p in prefs.get("recent_papers", []) if Path(p).exists()]
        if recent:
            for path in recent:
                self._recent_submenu.add(
                    rumps.MenuItem(Path(path).name, callback=self._make_load_callback(path))
                )
        else:
            self._recent_submenu.add(rumps.MenuItem("(없음)"))

    def _build_recent_submenu(self) -> None:
        """서브메뉴를 갱신한다 — PDF 로드 후 재호출 (NSMenu 이미 초기화됨)."""
        self._recent_submenu.clear()  # 두 번째 이후 호출: _menu(NSMenu) 존재 보장
        self._populate_recent_submenu()

    def _make_load_callback(self, path: str):
        def callback(_):
            self._load_paper(path)
        return callback

    # ── 메뉴 핸들러 ──────────────────────────────────────────────────────────
    def _open_chat(self, _=None) -> None:
        """채팅 창이 없으면 실행, 이미 실행 중이면 무시."""
        if self._webview_proc is None or self._webview_proc.poll() is not None:
            self._webview_proc = subprocess.Popen(
                [sys.executable, str(_THIS_DIR / "webview_process.py")]
            )

    def _select_paper(self, _=None) -> None:
        """NSOpenPanel로 PDF 파일을 선택한다."""
        try:
            import AppKit
            panel = AppKit.NSOpenPanel.openPanel()
            panel.setCanChooseFiles_(True)
            panel.setCanChooseDirectories_(False)
            panel.setAllowsMultipleSelection_(False)
            panel.setAllowedFileTypes_(["pdf"])
            panel.setTitle_("논문 PDF 선택")

            if panel.runModal() == AppKit.NSOKButton:
                pdf_path = panel.URLs()[0].path()
                self._load_paper(pdf_path)
        except Exception as exc:
            rumps.notification("PDF 챗봇", "파일 선택 오류", str(exc))

    def _open_sessions(self, _=None) -> None:
        sessions_dir = Path("~/Library/Application Support/PDFChatbot/sessions").expanduser()
        sessions_dir.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["open", str(sessions_dir)])

    def _quit_app(self, _=None) -> None:
        if self._webview_proc and self._webview_proc.poll() is None:
            self._webview_proc.terminate()
        rumps.quit_application()

    # ── PDF 로드 ─────────────────────────────────────────────────────────────
    def _load_paper(self, pdf_path: str) -> None:
        paper_name = Path(pdf_path).name
        try:
            resp = requests.post(
                "http://localhost:8765/api/load",
                json={"path": pdf_path},
                timeout=5,
            )
            if resp.status_code == 202:
                self.title = "📄"
                self._current_paper_item.title = f"현재 논문: {paper_name}"
                self._open_chat()
                self._build_recent_submenu()
            else:
                detail = resp.json().get("detail", "알 수 없는 오류")
                rumps.notification("PDF 챗봇", "로드 실패", detail)
        except requests.RequestException as exc:
            rumps.notification("PDF 챗봇", "서버 연결 실패", str(exc))

    # ── 상태 아이콘 폴링 ──────────────────────────────────────────────────────
    @rumps.timer(5)
    def _poll_status(self, _) -> None:
        """5초마다 서버 상태를 확인해 메뉴바 아이콘을 업데이트한다."""
        try:
            resp = requests.get("http://localhost:8765/api/status", timeout=2)
            data = resp.json()
            ollama_ok = data.get("ollama_ok", True)
            status    = data.get("status", "no_paper")

            if not ollama_ok:
                self.title = "⚠️"
            elif status == "loading":
                self.title = "📄"
            elif status == "ready":
                self.title = "✅"
            elif status == "no_paper":
                self.title = "🤖"
            else:
                self.title = "⚠️"
        except Exception:
            pass  # 서버 아직 시작 중이면 무시


if __name__ == "__main__":
    PDFChatbotApp().run()
