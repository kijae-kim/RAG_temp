"""
api/routes/onboarding.py

온보딩 상태 확인 API.

GET  /api/onboarding   preferences.json 존재 여부 + onboarding_done 플래그 반환
POST /api/onboarding/complete   onboarding_done: true 저장
"""
from __future__ import annotations

from fastapi import APIRouter
from agent.llm_config import _PREFS_PATH, _load_prefs, _save_prefs

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


@router.get("")
async def get_onboarding_status():
    """온보딩 완료 여부를 반환한다."""
    prefs = _load_prefs()
    done = prefs.get("onboarding_done", False)
    return {"onboarding_done": done}


@router.post("/complete")
async def complete_onboarding():
    """온보딩 완료를 저장한다."""
    prefs = _load_prefs()
    prefs["onboarding_done"] = True
    _save_prefs(prefs)
    return {"ok": True}
