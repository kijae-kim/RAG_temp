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

__version__ = "1.0.0"

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
        self._last_watched_pdf: str = ""   # 감시 폴더 자동 로드 중복 방지
        self._start_time = __import__("time").time()  # 서버 준비 대기용

        # 나중에 title을 바꿔야 하는 항목은 인스턴스 변수로 보관
        self._current_paper_item = rumps.MenuItem("현재 논문: 없음")
        self._recent_submenu = rumps.MenuItem("최근 논문")

        prefs = _load_prefs()
        watched = prefs.get("watched_folder", "")
        watched_label = f"논문 폴더: {Path(watched).name}" if watched else "논문 폴더 설정..."
        self._watched_folder_item = rumps.MenuItem(watched_label, callback=self._set_watched_folder)

        self._populate_recent_submenu()  # 첫 초기화: add()만, clear() 없음

        # 서버 준비 후 자동으로 챗봇 창 오픈
        threading.Thread(target=self._open_when_ready, daemon=True).start()

        self.menu = [
            self._current_paper_item,
            None,
            rumps.MenuItem("챗봇 열기",    callback=self._open_chat),
            rumps.MenuItem("논문 선택...", callback=self._select_paper),
            self._recent_submenu,
            None,
            self._watched_folder_item,
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

    def _set_watched_folder(self, _=None) -> None:
        """NSOpenPanel으로 감시 폴더를 선택한다."""
        try:
            import AppKit
            panel = AppKit.NSOpenPanel.openPanel()
            panel.setCanChooseFiles_(False)
            panel.setCanChooseDirectories_(True)
            panel.setAllowsMultipleSelection_(False)
            panel.setTitle_("논문 PDF 감시 폴더 선택")

            if panel.runModal() == AppKit.NSOKButton:
                folder_path = panel.URLs()[0].path()
                prefs = _load_prefs()
                prefs["watched_folder"] = folder_path
                _save_prefs(prefs)
                self._last_watched_pdf = ""  # 새 폴더 설정 시 감지 초기화
                self._watched_folder_item.title = f"논문 폴더: {Path(folder_path).name}"
                rumps.notification("PDF 챗봇", "논문 폴더 설정", f"{Path(folder_path).name} 폴더를 감시합니다.")
        except Exception as exc:
            rumps.notification("PDF 챗봇", "폴더 선택 오류", str(exc))

    def _open_sessions(self, _=None) -> None:
        sessions_dir = Path("~/Library/Application Support/PDFChatbot/sessions").expanduser()
        sessions_dir.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["open", str(sessions_dir)])

    def _quit_app(self, _=None) -> None:
        if self._webview_proc and self._webview_proc.poll() is None:
            self._webview_proc.terminate()
        rumps.quit_application()

    # ── PDF 로드 ─────────────────────────────────────────────────────────────
    def _load_paper(self, pdf_path: str) -> bool:
        """PDF 로드 요청. 성공(202) 시 True, 실패 시 False 반환."""
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
                return True
            else:
                detail = resp.json().get("detail", "알 수 없는 오류")
                rumps.notification("PDF 챗봇", "로드 실패", detail)
        except requests.RequestException:
            pass  # 서버 미준비 상태 — 다음 타이머 틱에서 재시도
        return False

    # ── 감시 폴더: 열린 PDF 파일 감지 ───────────────────────────────────────
    @rumps.timer(3)
    def _check_watched_folder(self, _) -> None:
        """
        3초마다 lsof로 감시 폴더 내 열린 PDF를 감지해 자동 로드한다.
        AppleScript 대신 lsof를 사용해 앱 종류에 무관하게 동작.
        서버 준비 전 15초 이내에는 스킵한다.
        """
        if __import__("time").time() - self._start_time < 15:
            return  # 서버 아직 준비 중

        prefs = _load_prefs()
        watched = prefs.get("watched_folder", "")
        if not watched:
            return

        try:
            # lsof +d: 해당 디렉토리에 열린 파일 목록 (비재귀, -F n: 파일명만)
            result = subprocess.run(
                ["lsof", "+d", watched, "-F", "n"],
                capture_output=True, text=True, timeout=3,
            )
            # 열린 PDF 후보를 모두 수집 — 이미 로드한 파일은 제외
            candidates = []
            for line in result.stdout.splitlines():
                if line.startswith("n") and line.lower().endswith(".pdf"):
                    candidate = line[1:]
                    p = Path(candidate)
                    if p.exists() and candidate != self._last_watched_pdf:
                        candidates.append(candidate)

            if not candidates:
                return

            # 여러 PDF가 열려 있을 때 가장 최근에 액세스된 파일 선택
            pdf_path = max(candidates, key=lambda p: Path(p).stat().st_atime)

            if self._load_paper(pdf_path):   # 성공 시에만 중복 방지 플래그 설정
                self._last_watched_pdf = pdf_path
        except Exception:
            pass

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

            # 논문 폴더 라벨 동기화 (webview_process에서 변경 시 반영)
            watched = _load_prefs().get("watched_folder", "")
            new_label = f"논문 폴더: {Path(watched).name}" if watched else "논문 폴더 설정..."
            if self._watched_folder_item.title != new_label:
                self._watched_folder_item.title = new_label
        except Exception:
            pass  # 서버 아직 시작 중이면 무시


if __name__ == "__main__":
    PDFChatbotApp().run()
