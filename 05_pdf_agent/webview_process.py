"""
webview_process.py

pywebview 채팅 창 프로세스 — menubar_app.py가 subprocess.Popen()으로 실행한다.

창 구성:
  - 메인 채팅 창: 420×700 frameless, 항상 위, PDF 뷰어 오른쪽에 배치
  - FAB 버튼 창: 72×72 원형, 투명 배경, 채팅 창 토글

WebviewBridge 메서드:
  - close_window()         : 채팅 창 닫기
  - toggle_chat()          : 채팅 창 표시/숨기기
  - open_pdf_at_page()     : PDF 뷰어에서 특정 페이지로 이동
  - open_file_in_finder()  : Finder에서 파일 위치 열기
  - is_ollama_running()    : Ollama 상태 확인
"""

from __future__ import annotations

import json
import subprocess
import threading
import time
from pathlib import Path

import webview

# ── 설정 ─────────────────────────────────────────────────────────────────────
API_BASE = "http://localhost:8765"
CHAT_W, CHAT_H, MARGIN = 420, 700, 10
FAB_SIZE = 72
PREFS_PATH = Path("~/Library/Application Support/PDFChatbot/preferences.json").expanduser()
PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)

PDF_APPS = {"Preview", "Adobe Acrobat", "PDF Expert", "Skim", "PDF Viewer"}


# ── preferences.json ─────────────────────────────────────────────────────────
def _load_prefs() -> dict:
    if PREFS_PATH.exists():
        try:
            return json.loads(PREFS_PATH.read_text())
        except Exception:
            pass
    return {}


def _save_prefs(prefs: dict) -> None:
    PREFS_PATH.write_text(json.dumps(prefs, ensure_ascii=False, indent=2))


# ── 화면 크기 (webview.start() 전에도 안전하게 동작) ─────────────────────────
def _get_screen_size() -> tuple[int, int]:
    """AppKit으로 주 화면 크기를 반환한다 — webview.screens 대신 사용."""
    try:
        import AppKit
        frame = AppKit.NSScreen.mainScreen().frame()
        return int(frame.size.width), int(frame.size.height)
    except Exception:
        return 1440, 900


# ── 창 위치 계산 ─────────────────────────────────────────────────────────────
def _get_pdf_viewer_frame() -> dict | None:
    """현재 화면에 표시된 PDF 뷰어 앱의 위치·크기를 반환한다."""
    try:
        import Quartz
        window_list = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly
            | Quartz.kCGWindowListExcludeDesktopElements,
            Quartz.kCGNullWindowID,
        )
        for win in window_list:
            owner = win.get(Quartz.kCGWindowOwnerName, "")
            layer = win.get(Quartz.kCGWindowLayer, -1)
            if owner in PDF_APPS and layer == 0:
                return win.get(Quartz.kCGWindowBounds)
    except Exception:
        pass
    return None


def _calculate_window_position(prefs: dict) -> tuple[int, int]:
    sw, _sh = _get_screen_size()

    pdf_frame = _get_pdf_viewer_frame()
    if pdf_frame:
        x = int(pdf_frame["X"] + pdf_frame["Width"] + MARGIN)
        y = int(pdf_frame["Y"])
        if x + CHAT_W > sw:
            x = int(pdf_frame["X"]) - CHAT_W - MARGIN
        return max(0, x), max(0, y)

    wx, wy = prefs.get("window_x"), prefs.get("window_y")
    if isinstance(wx, (int, float)) and isinstance(wy, (int, float)):
        return int(wx), int(wy)

    return sw - CHAT_W - MARGIN, 24


def _fab_position(chat_x: int, chat_y: int) -> tuple[int, int]:
    """FAB 버튼 위치: 채팅 창 왼쪽, 세로 중앙. 공간 없으면 오른쪽."""
    sw, _sh = _get_screen_size()
    fab_x = chat_x - FAB_SIZE - MARGIN
    fab_y = chat_y + CHAT_H // 2 - FAB_SIZE // 2
    if fab_x < 0:
        fab_x = chat_x + CHAT_W + MARGIN
    return max(0, fab_x), max(0, fab_y)


# ── 창 위치 자동 저장 ─────────────────────────────────────────────────────────
def _watch_position(window: webview.Window) -> None:
    last: tuple | None = None
    while True:
        try:
            pos = (window.x, window.y)
            if pos != last and pos != (0, 0):
                prefs = _load_prefs()
                prefs["window_x"], prefs["window_y"] = pos
                _save_prefs(prefs)
                last = pos
        except Exception:
            pass
        time.sleep(1)


# ── pywebview JS Bridge ───────────────────────────────────────────────────────
class WebviewBridge:
    """JS에서 window.pywebview.api.method() 형태로 호출한다."""

    def __init__(self, window_ref: list, chat_visible: list) -> None:
        self._window_ref = window_ref   # [main_window]
        self._chat_visible = chat_visible  # [True/False]

    def close_window(self) -> None:
        """채팅 창을 숨긴다 (destroy 대신 hide — FAB으로 재표시 가능)."""
        win = self._window_ref[0]
        if win:
            win.hide()
            self._chat_visible[0] = False

    def toggle_chat(self) -> None:
        """채팅 창을 표시하거나 숨긴다."""
        win = self._window_ref[0]
        if not win:
            return
        if self._chat_visible[0]:
            win.hide()
            self._chat_visible[0] = False
        else:
            win.show()
            win.on_top = True   # 다시 표시할 때 최상단 보장
            self._chat_visible[0] = True

    def open_pdf_at_page(self, path: str, page: int, text: str = "") -> None:
        """
        PDF를 Preview에서 지정 페이지로 이동한다.
        이미 열려 있으면 포커스만 이동하고 새 창을 열지 않는다.
        page: RAG metadata의 page 값 (0-indexed 정수)

        Preview 11(macOS Ventura/Sonoma)에서 AppleScript 'current page' 속성이
        제거되었으므로 System Events의 '이동 > 페이지로 이동…' 메뉴를 사용한다.
        """
        def _do() -> None:
            target_page_1 = max(1, int(page) + 1)   # 1-indexed

            # PDF 열기 (이미 Preview에 열려 있으면 포커스만 이동)
            subprocess.Popen(["open", "-a", "Preview", path])
            time.sleep(0.8)

            # System Events: 이동 > 페이지로 이동… 메뉴 클릭 후 페이지 번호 입력
            script = (
                'tell application "Preview" to activate\n'
                'delay 0.3\n'
                'tell application "System Events"\n'
                '    tell process "Preview"\n'
                '        click menu item "페이지로 이동\u2026"'
                ' of menu "이동" of menu bar 1\n'
                '    end tell\n'
                'end tell\n'
                'delay 0.4\n'
                'tell application "System Events"\n'
                f'    keystroke "{target_page_1}"\n'
                '    key code 36\n'
                'end tell'
            )
            try:
                subprocess.run(["osascript", "-e", script], timeout=8)
            except Exception:
                pass

        threading.Thread(target=_do, daemon=True).start()

    def open_file_in_finder(self, path: str) -> None:
        """Finder에서 파일 위치 열기."""
        subprocess.Popen(["open", "-R", path])

    def is_ollama_running(self) -> bool:
        """Ollama 상태 즉시 확인 (UI 배너용)."""
        import socket
        with socket.socket() as s:
            return s.connect_ex(("localhost", 11434)) == 0

    def open_pdf(self, path: str) -> None:
        """PDF를 Preview에서 연다 (인덱싱과 병렬로 즉시 실행)."""
        subprocess.Popen(["open", "-a", "Preview", path])

    def open_file_dialog(self) -> str | None:
        """PDF 파일 선택 다이얼로그. 선택된 경로를 반환하거나 None."""
        win = self._window_ref[0]
        if not win:
            return None
        # 다이얼로그가 챗봇 창 뒤로 숨지 않도록 on_top을 일시 해제
        win.on_top = False
        try:
            result = win.create_file_dialog(
                webview.OPEN_DIALOG,
                allow_multiple=False,
                file_types=('PDF files (*.pdf)',),
            )
        finally:
            win.on_top = True
        return result[0] if result else None

    def set_paper_folder(self) -> str | None:
        """논문 폴더 선택 → preferences.json에 저장 → 경로 반환."""
        win = self._window_ref[0]
        if not win:
            return None
        win.on_top = False
        try:
            result = win.create_file_dialog(webview.FOLDER_DIALOG)
        finally:
            win.on_top = True
        if result:
            path = result[0]
            prefs = _load_prefs()
            prefs["watched_folder"] = path
            _save_prefs(prefs)
            return path
        return None


# ── 진입점 ───────────────────────────────────────────────────────────────────
def main() -> None:
    prefs = _load_prefs()
    chat_x, chat_y = _calculate_window_position(prefs)
    fab_x, fab_y = _fab_position(chat_x, chat_y)

    window_ref: list = [None]
    chat_visible: list = [True]
    bridge = WebviewBridge(window_ref, chat_visible)

    # 메인 채팅 창
    window = webview.create_window(
        title="논문 AI 챗봇",
        url=f"{API_BASE}/ui/index.html",
        width=CHAT_W,
        height=CHAT_H,
        x=chat_x,
        y=chat_y,
        frameless=True,
        on_top=True,
        resizable=False,
        js_api=bridge,
    )
    window_ref[0] = window

    # FAB 토글 버튼 창 (원형, 투명 배경)
    webview.create_window(
        title="",
        url=f"{API_BASE}/ui/floating_button.html",
        width=FAB_SIZE,
        height=FAB_SIZE,
        x=fab_x,
        y=fab_y,
        frameless=True,
        on_top=True,
        resizable=False,
        background_color="#1e1e2e",
        js_api=bridge,
    )

    def on_shown():
        threading.Thread(
            target=_watch_position,
            args=(window,),
            daemon=True,
        ).start()

    webview.start(on_shown)


if __name__ == "__main__":
    main()
