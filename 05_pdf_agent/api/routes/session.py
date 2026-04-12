"""
api/routes/session.py

GET  /api/session              — 현재 학습 세션 조회
POST /api/session/clear        — 대화 히스토리 초기화 (세션 파일 유지)
POST /api/session/concept      — 개념 이해 완료 마킹
GET  /api/sessions             — 모든 세션 목록 (런처용)
POST /api/sessions/{hash}/resume — 세션 재개 (PDF 재로드 + 채팅 기록 반환)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.engine_state import get_chatbot, get_paper_path

logger = logging.getLogger(__name__)
router = APIRouter()

_SESSIONS_DIR = Path(
    "~/Library/Application Support/PDFChatbot/sessions"
).expanduser()


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


# ── 런처용 엔드포인트 ────────────────────────────────────────────────────────


@router.get("/api/sessions")
async def list_sessions() -> dict:
    """
    모든 학습 세션을 최신순으로 반환한다 (최대 10개).
    pdf_path가 존재하지 않는 파일은 missing=true 포함.
    """
    if not _SESSIONS_DIR.exists():
        return {"sessions": []}

    result = []
    for f in _SESSIONS_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            pdf_path = data.get("pdf_path", "")
            result.append({
                "pdf_hash": data.get("pdf_hash", ""),
                "pdf_name": data.get("pdf_name", ""),
                "pdf_path": pdf_path,
                "last_accessed": data.get("last_accessed", ""),
                "total_sessions": data.get("total_sessions", 1),
                "missing": bool(pdf_path) and not Path(pdf_path).exists(),
            })
        except Exception as exc:
            logger.warning("세션 파일 읽기 실패 (%s): %s", f.name, exc)

    result.sort(key=lambda x: x["last_accessed"], reverse=True)
    return {"sessions": result[:10]}


@router.post("/api/sessions/{pdf_hash}/resume")
async def resume_session(pdf_hash: str) -> dict:
    """
    저장된 pdf_path로 PDF를 재로드하고 채팅 기록을 반환한다.
    """
    session_file = _SESSIONS_DIR / f"{pdf_hash}.json"
    if not session_file.exists():
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    try:
        data = json.loads(session_file.read_text(encoding="utf-8"))
    except Exception:
        raise HTTPException(status_code=500, detail="세션 파일 읽기 실패.")

    pdf_path = data.get("pdf_path", "")
    if not pdf_path:
        raise HTTPException(status_code=400, detail="세션에 PDF 경로가 없습니다. 분석을 다시 실행하세요.")
    if not Path(pdf_path).exists():
        raise HTTPException(status_code=404, detail=f"PDF 파일을 찾을 수 없습니다: {pdf_path}")

    from api.engine_state import load_pdf_async
    load_pdf_async(pdf_path)

    return {
        "ok": True,
        "pdf_path": pdf_path,
        "pdf_name": data.get("pdf_name", ""),
        "chat_messages": data.get("chat_messages", []),
    }
