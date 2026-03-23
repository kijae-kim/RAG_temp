"""
api/routes/agent.py

POST /api/analyze — 논문 자동 분석 SSE 스트리밍.

JS가 /api/events의 paper_ready 이벤트 수신 시 자동 호출한다.
LangGraph analyze_graph를 .stream(stream_mode="updates")로 실행해
노드 완료마다 SSE 이벤트를 push한다.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from api.engine_state import get_chatbot

logger = logging.getLogger(__name__)
router = APIRouter()

# 노드별 진행률 및 단계명
_NODE_PROGRESS = {
    "summary_node": ("summary",  40),
    "concept_node": ("concepts", 80),
    "session_save": ("saving",  100),
}


@router.post("/api/analyze")
async def analyze_stream() -> StreamingResponse:
    """
    논문 자동 분석 SSE 스트리밍.
    summary_node → concept_node 완료 시 각각 SSE 이벤트 전송.
    """
    if get_chatbot() is None:
        raise HTTPException(status_code=400, detail="논문이 로드되지 않았습니다.")

    def generate():
        from agent.paper_agent import get_analyze_graph
        from agent.state import AgentState

        graph = get_analyze_graph()
        initial_state: AgentState = {
            "question":   "",
            "intent":     "",
            "summary":    "",
            "concepts":   [],
            "answer":     "",
            "session_id": "analyze",
        }

        yield 'data: {"type":"progress","step":"start","pct":10}\n\n'

        try:
            for chunk in graph.stream(initial_state, stream_mode="updates"):
                node_name = list(chunk.keys())[0]
                state_update = chunk[node_name]
                step, pct = _NODE_PROGRESS.get(node_name, ("unknown", 0))

                yield f'data: {{"type":"progress","step":"{step}","pct":{pct}}}\n\n'

                if node_name == "summary_node" and state_update.get("summary"):
                    yield (
                        f"data: {json.dumps({'type': 'summary', 'content': state_update['summary']}, ensure_ascii=False)}\n\n"
                    )

                elif node_name == "concept_node" and state_update.get("concepts"):
                    yield (
                        f"data: {json.dumps({'type': 'concepts', 'content': state_update['concepts']}, ensure_ascii=False)}\n\n"
                    )

        except Exception as exc:
            logger.exception("분석 오류: %s", exc)
            yield f"data: {json.dumps({'type': 'error', 'content': str(exc)}, ensure_ascii=False)}\n\n"

        yield 'data: {"type":"done","content":null}\n\n'

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
