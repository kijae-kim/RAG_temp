"""
api/routes/events.py

GET /api/events — 서버 → 채팅 창 SSE push 전용 채널.

engine_state.push_event()가 상태 변경 시 큐에 이벤트를 넣으면
이 핸들러가 연결된 채팅 창 JS에 즉시 전달한다.

이벤트 타입:
  model_loading   임베딩 모델 초기화 중
  model_ready     임베딩 모델 준비 완료
  paper_changed   새 PDF 선택됨 (로딩 시작)
  loading_progress 인덱싱 진행률 (pct: 0~100)
  paper_ready     인덱싱 완료 → JS가 /api/analyze 자동 호출
  error           오류 발생
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)
router = APIRouter()

_queue: asyncio.Queue | None = None


def set_queue(queue: asyncio.Queue) -> None:
    """server.py startup에서 호출해 큐를 등록한다."""
    global _queue
    _queue = queue


@router.get("/api/events")
async def event_stream() -> StreamingResponse:
    """
    채팅 창 JS가 앱 시작 시 1회 연결.
    서버가 상태 변경 시 push → JS가 즉시 반응.
    """
    async def generate():
        # 연결 즉시 현재 상태 전송
        from api.engine_state import get_status
        status = get_status()
        yield f"data: {json.dumps({'type': 'connected', 'status': status['status']}, ensure_ascii=False)}\n\n"

        while True:
            try:
                event = await asyncio.wait_for(_queue.get(), timeout=30.0)
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            except asyncio.TimeoutError:
                # 연결 유지용 heartbeat
                yield "data: {\"type\":\"heartbeat\"}\n\n"
            except Exception as exc:
                logger.exception("이벤트 스트림 오류: %s", exc)
                break

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
