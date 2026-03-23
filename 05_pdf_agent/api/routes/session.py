"""
api/routes/session.py

GET  /api/session              — 현재 학습 세션 조회
POST /api/session/clear        — 대화 히스토리 초기화 (세션 파일 유지)
POST /api/session/concept      — 개념 이해 완료 마킹
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.engine_state import get_chatbot, get_paper_path

logger = logging.getLogger(__name__)
router = APIRouter()


class ConceptMarkRequest(BaseModel):
    concept: str


@router.get("/api/session")
async def get_session() -> dict:
    """현재 로드된 PDF의 학습 세션 정보를 반환한다."""
    pdf_path = get_paper_path()
    if not pdf_path:
        raise HTTPException(status_code=404, detail="로드된 논문이 없습니다.")

    from session.session_manager import load_session
    session = load_session(pdf_path)
    if not session:
        raise HTTPException(status_code=404, detail="세션 기록이 없습니다. 분석 탭에서 분석을 먼저 실행하세요.")

    return session.to_dict()


class ClearRequest(BaseModel):
    session_id: str = "default"


@router.post("/api/session/clear")
async def clear_session(req: ClearRequest = ClearRequest()) -> dict:
    """
    LangChain 대화 히스토리를 초기화한다.
    세션 JSON 파일(questions_asked 등 통계)은 유지한다.
    """
    chatbot = get_chatbot()
    if chatbot and hasattr(chatbot, "clear_session"):
        try:
            chatbot.clear_session(req.session_id)
        except Exception as exc:
            logger.warning("세션 초기화 오류: %s", exc)
    return {"cleared": True}


@router.post("/api/session/concept")
async def mark_concept(req: ConceptMarkRequest) -> dict:
    """개념을 '이해 완료'로 마킹한다."""
    pdf_path = get_paper_path()
    if not pdf_path:
        raise HTTPException(status_code=400, detail="로드된 논문이 없습니다.")

    from session.session_manager import mark_concept_understood
    ok = mark_concept_understood(pdf_path, req.concept)
    return {"concept": req.concept, "marked": ok}
