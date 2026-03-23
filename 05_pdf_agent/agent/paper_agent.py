"""
agent/paper_agent.py

LangGraph StateGraph 정의.

역할 분리 (설계 결정):
  /api/chat  — classify_intent()만 사용 (동기, 그래프 불필요)
  /api/analyze — analyze_graph로 전체 분석 흐름 실행
                 .stream(stream_mode="updates")로 노드별 진행 이벤트 SSE 전송

analyze_graph 노드 순서:
  summary_node → concept_node → session_save → END
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from agent.state import AgentState
from agent.tools import extract_concepts, summarize_paper


# ── 노드 함수 ─────────────────────────────────────────────────────────────────
def summary_node(state: AgentState) -> dict:
    """논문 전체 요약 (한국어)."""
    from api.engine_state import get_chatbot
    chatbot = get_chatbot()
    if chatbot is None:
        return {"summary": "논문이 로드되지 않았습니다."}
    summary = summarize_paper(chatbot)
    return {"summary": summary}


def concept_node(state: AgentState) -> dict:
    """핵심 개념 태그 추출 (영어 원문)."""
    from api.engine_state import get_chatbot
    chatbot = get_chatbot()
    if chatbot is None:
        return {"concepts": []}
    concepts = extract_concepts(chatbot)
    return {"concepts": concepts}


def session_save_node(state: AgentState) -> dict:
    """분석 결과(summary, concepts)를 세션 JSON으로 저장한다."""
    from api.engine_state import get_paper_path, get_status
    from session.session_manager import upsert_session

    pdf_path = get_paper_path()
    if not pdf_path:
        return {}

    pdf_name = get_status().get("paper_name", "unknown.pdf")
    try:
        upsert_session(
            pdf_path=pdf_path,
            pdf_name=pdf_name,
            summary=state.get("summary", ""),
            concepts=state.get("concepts", []),
        )
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("세션 저장 실패: %s", exc)

    return {}


# ── 그래프 빌드 ───────────────────────────────────────────────────────────────
def build_analyze_graph():
    graph = StateGraph(AgentState)

    graph.add_node("summary_node",   summary_node)
    graph.add_node("concept_node",   concept_node)
    graph.add_node("session_save",   session_save_node)

    graph.add_edge(START,          "summary_node")
    graph.add_edge("summary_node", "concept_node")
    graph.add_edge("concept_node", "session_save")
    graph.add_edge("session_save", END)

    return graph.compile()


# 모듈 로드 시 1회 컴파일 (재사용)
_analyze_graph = None


def get_analyze_graph():
    global _analyze_graph
    if _analyze_graph is None:
        _analyze_graph = build_analyze_graph()
    return _analyze_graph
