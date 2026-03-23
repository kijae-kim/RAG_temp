"""
agent/state.py

LangGraph Agent 공유 상태 정의.
"""

from __future__ import annotations

from typing import TypedDict


class AgentState(TypedDict):
    question:   str          # 사용자 질문
    intent:     str          # qa | explain | quiz | summarize
    summary:    str          # 논문 요약 (summary_node 결과)
    concepts:   list[str]    # 핵심 개념 태그 (concept_node 결과)
    answer:     str          # 최종 답변
    session_id: str
