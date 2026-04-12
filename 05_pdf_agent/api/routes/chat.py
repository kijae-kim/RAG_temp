"""
api/routes/chat.py

GET  /api/status  — 엔진 상태 조회
POST /api/chat    — 질문 → SSE 스트리밍 답변

Phase 1: PDFChatbot.stream_chat() 직접 호출
Phase 2: LangGraph router_node로 의도 분류 후 스트리밍 함수 선택
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent.tools import STREAM_FN_MAP, classify_intent
from api.engine_state import get_chatbot, get_paper_path, get_status

logger = logging.getLogger(__name__)
router = APIRouter()


class ChatRequest(BaseModel):
    question: str
    session_id: str = "default"
    style: str = "default"  # "brief" | "default" | "detailed"


def _serialize_sources(sources: list, pdf_path: str | None = None) -> str:
    result = []
    for doc in sources:
        result.append({
            "page": doc.metadata.get("page", "?"),
            "text": doc.page_content[:200],
            "pdf_path": pdf_path or "",
        })
    return json.dumps(result, ensure_ascii=False)


@router.get("/api/status")
async def get_engine_status() -> dict:
    """서버·엔진 상태 조회."""
    import socket
    ollama_ok = socket.socket().connect_ex(("localhost", 11434)) == 0

    status = get_status()
    return {
        "status": status["status"],
        "ollama_ok": ollama_ok,
        "paper_name": status["paper_name"],
        "loading_pct": status["loading_pct"],
        "error_msg": status["error_msg"],
    }


@router.post("/api/chat")
async def chat_stream(req: ChatRequest) -> StreamingResponse:
    """질문을 받아 SSE 스트리밍으로 답변한다."""
    chatbot = get_chatbot()
    if chatbot is None:
        raise HTTPException(status_code=400, detail="논문이 로드되지 않았습니다.")

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

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
