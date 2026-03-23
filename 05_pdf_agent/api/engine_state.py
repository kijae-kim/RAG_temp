"""
api/engine_state.py

PDFChatbot 싱글톤 상태 관리 모듈.

- PDFChatbot 인스턴스를 프로세스 전체에서 단 하나만 유지한다.
- threading.Lock으로 동시 인덱싱 요청을 직렬화한다.
- FAISS 캐시 경로를 환경에 따라 자동 감지한다.
  개발: 04_mini_project/.cache/ 존재 시 공유
  배포: ~/Library/Application Support/PDFChatbot/.cache/
- push_event()로 상태 변경을 /api/events SSE 채널에 브로드캐스트한다.
- 앱 시작 시 임베딩 모델을 백그라운드에서 워밍업한다.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import threading
from pathlib import Path
from typing import Any

# 04_mini_project를 sys.path에 추가해 PDFChatbot 재사용
_MINI_PROJECT_DIR = Path(__file__).parent.parent.parent / "04_mini_project"
if str(_MINI_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(_MINI_PROJECT_DIR))

from rag_engine import PDFChatbot, RAGConfig  # noqa: E402

logger = logging.getLogger(__name__)

# ── FAISS 캐시 경로 자동 감지 ─────────────────────────────────────────────────
_DEV_CACHE = _MINI_PROJECT_DIR / ".cache"
_APP_CACHE = Path("~/Library/Application Support/PDFChatbot/.cache").expanduser()

CACHE_DIR: Path = _DEV_CACHE if _DEV_CACHE.exists() else _APP_CACHE
CACHE_DIR.mkdir(parents=True, exist_ok=True)

logger.info("FAISS 캐시 경로: %s", CACHE_DIR)

# ── SSE 이벤트 브로드캐스트 ──────────────────────────────────────────────────
_event_loop: asyncio.AbstractEventLoop | None = None
_event_queue: asyncio.Queue | None = None


def set_event_loop(loop: asyncio.AbstractEventLoop, queue: asyncio.Queue) -> None:
    """FastAPI 서버 시작 시 이벤트 루프와 큐를 등록한다."""
    global _event_loop, _event_queue
    _event_loop = loop
    _event_queue = queue


def push_event(event: dict) -> None:
    """
    상태 변경을 /api/events SSE 채널에 push한다.
    백그라운드 스레드에서 안전하게 호출 가능.
    """
    if _event_loop is None or _event_queue is None:
        return
    _event_loop.call_soon_threadsafe(_event_queue.put_nowait, event)


# ── PDFChatbot 싱글톤 상태 ────────────────────────────────────────────────────
_lock = threading.Lock()

_state: dict[str, Any] = {
    "chatbot": None,        # PDFChatbot 인스턴스
    "status": "no_paper",  # no_paper | loading | ready | error
    "loading_pct": 0,
    "paper_name": None,
    "paper_path": None,
    "error_msg": None,
    "embedding_model": None,
}


def get_status() -> dict:
    """현재 엔진 상태를 반환한다."""
    return {
        "status": _state["status"],
        "paper_name": _state["paper_name"],
        "loading_pct": _state["loading_pct"],
        "error_msg": _state["error_msg"],
    }


def get_chatbot() -> PDFChatbot | None:
    """현재 PDFChatbot 싱글톤을 반환한다. 없으면 None."""
    return _state["chatbot"]


def get_paper_path() -> str | None:
    """현재 로드된 PDF 경로를 반환한다. 없으면 None."""
    return _state.get("paper_path")


def load_pdf_async(pdf_path: str) -> None:
    """
    PDF 인덱싱을 백그라운드 스레드에서 실행한다.
    완료 시 /api/events로 paper_ready 이벤트를 push한다.
    """
    def _load() -> None:
        path = Path(pdf_path)
        paper_name = path.name

        with _lock:
            if _state["status"] == "loading":
                logger.warning("이미 인덱싱 중 — 요청 무시: %s", paper_name)
                return

            _state["status"] = "loading"
            _state["loading_pct"] = 0
            _state["paper_name"] = paper_name
            _state["paper_path"] = pdf_path
            _state["error_msg"] = None

        push_event({"type": "paper_changed", "paper_name": paper_name, "status": "loading"})
        logger.info("PDF 인덱싱 시작: %s", paper_name)

        try:
            push_event({"type": "loading_progress", "pct": 20})
            config = RAGConfig(cache_dir=CACHE_DIR)
            chatbot = PDFChatbot(
                pdf_source=pdf_path,
                config=config,
                embeddings=_state["embedding_model"],
            )
            push_event({"type": "loading_progress", "pct": 100})

            with _lock:
                _state["chatbot"] = chatbot
                _state["status"] = "ready"
                _state["loading_pct"] = 100

            push_event({
                "type": "paper_ready",
                "paper_name": paper_name,
                "chunks": chatbot.get_doc_info().get("chunks", 0),
            })
            logger.info("PDF 인덱싱 완료: %s", paper_name)

            # 이전 세션이 있으면 클라이언트에 알림
            try:
                from session.session_manager import load_session
                prev = load_session(pdf_path)
                if prev:
                    push_event({"type": "session_resume", "session": prev.to_dict()})
            except Exception:
                pass

        except Exception as exc:
            logger.exception("PDF 인덱싱 실패: %s", exc)
            with _lock:
                _state["status"] = "error"
                _state["error_msg"] = str(exc)
            push_event({"type": "error", "msg": str(exc)})

    threading.Thread(target=_load, daemon=True).start()


# ── 임베딩 모델 워밍업 ────────────────────────────────────────────────────────
_EMBED_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"


def _warmup_embedding_model() -> None:
    """
    앱 시작 시 임베딩 모델을 미리 로드한다.
    HuggingFace 캐시가 없으면 다운로드 (~400MB, 최초 1회).
    완료 후 PDFChatbot에 주입해 재로딩을 방지한다.
    """
    from langchain_huggingface import HuggingFaceEmbeddings

    push_event({"type": "model_loading", "msg": "임베딩 모델 초기화 중... (최초 실행 시 다운로드)"})
    logger.info("임베딩 모델 로딩: %s", _EMBED_MODEL)

    try:
        model = HuggingFaceEmbeddings(model_name=_EMBED_MODEL)
        _state["embedding_model"] = model
        push_event({"type": "model_ready"})
        logger.info("임베딩 모델 준비 완료")
    except Exception as exc:
        logger.exception("임베딩 모델 로딩 실패: %s", exc)
        push_event({"type": "error", "msg": f"임베딩 모델 로딩 실패: {exc}"})


def start_warmup() -> None:
    """FastAPI 서버 startup 이벤트에서 호출한다."""
    threading.Thread(target=_warmup_embedding_model, daemon=True).start()
