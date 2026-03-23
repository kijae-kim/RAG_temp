"""
webview_process.py

pywebview 채팅 창 프로세스 — menubar_app.py가 subprocess.Popen()으로 실행한다.

- 420×700 frameless 창, 항상 위, PDF 뷰어 오른쪽에 배치
- Python 백그라운드 스레드로 창 위치를 1초마다 감지해 preferences.json에 저장
- WebviewBridge: JS에서 window.pywebview.api.method()로 macOS 네이티브 동작 호출
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
    screens = webview.screens
    sw = screens[0].width if screens else 1440
    sh = screens[0].height if screens else 900

    pdf_frame = _get_pdf_viewer_frame()
    if pdf_frame:
        x = int(pdf_frame["X"] + pdf_frame["Width"] + MARGIN)
        y = int(pdf_frame["Y"])
        if x + CHAT_W > sw:
            x = int(pdf_frame["X"]) - CHAT_W - MARGIN
        return max(0, x), max(0, y)

    if "window_x" in prefs and "window_y" in prefs:
        return prefs["window_x"], prefs["window_y"]

    # 폴백: 화면 우상단 (macOS 메뉴바 높이 24px 고려)
    return sw - CHAT_W - MARGIN, 24


# ── 창 위치 자동 저장 ─────────────────────────────────────────────────────────
def _watch_position(window: webview.Window) -> None:
    """
    1초마다 창 위치를 확인해 변경 시 preferences.json에 저장.
    window.screenX/Y가 아닌 Python window.x, window.y 사용.
    """
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

    def __init__(self, window_ref: list) -> None:
        # window 객체는 webview.start() 이후에 생성되므로 list로 참조 전달
        self._window_ref = window_ref

    def close_window(self) -> None:
        """채팅 창을 닫는다."""
        win = self._window_ref[0]
        if win:
            win.destroy()

    def open_file_in_finder(self, path: str) -> None:
        """Finder에서 파일 위치 열기."""
        subprocess.Popen(["open", "-R", path])

    def is_ollama_running(self) -> bool:
        """Ollama 상태 즉시 확인 (UI 배너용)."""
        import socket
        with socket.socket() as s:
            return s.connect_ex(("localhost", 11434)) == 0


# ── 진입점 ───────────────────────────────────────────────────────────────────
def main() -> None:
    prefs = _load_prefs()
    x, y = _calculate_window_position(prefs)

    # window 객체는 create_window() 반환값이지만 브릿지에 미리 참조 전달
    window_ref: list = [None]
    bridge = WebviewBridge(window_ref)

    window = webview.create_window(
        title="논문 AI 챗봇",
        url=f"{API_BASE}/ui/index.html",
        width=CHAT_W,
        height=CHAT_H,
        x=x,
        y=y,
        frameless=True,
        on_top=True,
        resizable=False,
        js_api=bridge,
    )
    window_ref[0] = window

    def on_shown():
        threading.Thread(
            target=_watch_position,
            args=(window,),
            daemon=True,
        ).start()

    webview.start(on_shown)


if __name__ == "__main__":
    main()
