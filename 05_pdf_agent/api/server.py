"""
api/server.py

FastAPI 앱 팩토리 및 CORS, 라우터 등록.
포트 8765 고정 (Streamlit 8501/8502와 충돌 없음).
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from api.engine_state import set_event_loop, start_warmup
from api.routes import agent, chat, document, events, session, settings

logger = logging.getLogger(__name__)

UI_DIR = Path(__file__).parent.parent / "ui"


def create_app() -> FastAPI:
    app = FastAPI(title="PDF Agent API", version="1.0.0")

    # CORS — 로컬 전용 서버
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # UI 정적 파일 서빙 (pywebview가 http://localhost:8765/ui/ 로 접근)
    if UI_DIR.exists():
        app.mount("/ui", StaticFiles(directory=str(UI_DIR), html=True), name="ui")

    # 라우터 등록
    app.include_router(events.router)
    app.include_router(chat.router)
    app.include_router(document.router)
    app.include_router(agent.router)
    app.include_router(session.router)
    app.include_router(settings.router)

    @app.on_event("startup")
    async def _startup() -> None:
        # SSE 이벤트 큐를 engine_state에 등록
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()
        set_event_loop(loop, queue)
        events.set_queue(queue)

        # 임베딩 모델 백그라운드 워밍업 시작
        start_warmup()
        logger.info("FastAPI 서버 시작 완료 — port 8765")

    return app


app = create_app()
