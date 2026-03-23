"""
api/routes/document.py

POST /api/load           — PDF 로드 및 인덱싱 트리거 (202, 백그라운드)
GET  /api/doc-info       — 현재 문서 메타데이터
GET  /api/recent-papers  — 최근 논문 목록 (최대 5개)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.engine_state import CACHE_DIR, get_chatbot, load_pdf_async

logger = logging.getLogger(__name__)
router = APIRouter()

_PREFS_PATH = Path("~/Library/Application Support/PDFChatbot/preferences.json").expanduser()
_PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)


def _load_prefs() -> dict:
    if _PREFS_PATH.exists():
        try:
            return json.loads(_PREFS_PATH.read_text())
        except Exception:
            pass
    return {"recent_papers": []}


def _save_prefs(prefs: dict) -> None:
    _PREFS_PATH.write_text(json.dumps(prefs, ensure_ascii=False, indent=2))


def _add_to_recent(pdf_path: str) -> None:
    prefs = _load_prefs()
    recent = prefs.get("recent_papers", [])
    # 중복 제거 후 최신 순 정렬
    recent = [p for p in recent if p != pdf_path]
    recent.insert(0, pdf_path)
    prefs["recent_papers"] = recent[:5]
    _save_prefs(prefs)


class LoadRequest(BaseModel):
    path: str


@router.post("/api/load", status_code=202)
async def load_pdf(req: LoadRequest) -> dict:
    """
    PDF 로드 및 인덱싱을 백그라운드에서 시작한다.
    진행 상황은 GET /api/events SSE로 push된다.
    """
    path = Path(req.path)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"파일을 찾을 수 없습니다: {req.path}")
    if path.suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="PDF 파일만 지원합니다.")

    # FAISS 캐시 존재 여부로 즉시 로드 여부 판단
    pdf_hash = path.stem
    cached = (CACHE_DIR / pdf_hash).exists()

    _add_to_recent(req.path)
    load_pdf_async(req.path)

    return {
        "accepted": True,
        "cached": cached,
        "msg": "캐시에서 즉시 로드" if cached else "인덱싱 시작 (~30초)",
    }


@router.get("/api/doc-info")
async def get_doc_info() -> dict:
    """현재 로드된 문서의 메타데이터를 반환한다."""
    chatbot = get_chatbot()
    if chatbot is None:
        raise HTTPException(status_code=404, detail="로드된 논문이 없습니다.")
    return chatbot.get_doc_info()


@router.get("/api/recent-papers")
async def get_recent_papers() -> dict:
    """최근 선택한 논문 목록을 반환한다 (최대 5개, 존재하는 파일만)."""
    prefs = _load_prefs()
    recent = [p for p in prefs.get("recent_papers", []) if Path(p).exists()]
    return {"papers": [{"path": p, "name": Path(p).name} for p in recent]}
