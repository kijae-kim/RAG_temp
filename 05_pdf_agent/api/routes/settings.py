"""
api/routes/settings.py

LLM 프로바이더 설정 API.

GET  /api/settings         현재 설정 + 기본 모델 목록 반환
POST /api/settings         provider / model / api_key 저장
POST /api/settings/test    현재 설정으로 LLM 연결 테스트
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from agent.llm_config import (
    get_api_key,
    get_llm_model,
    get_provider,
    save_settings,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])

# provider별 선택 가능한 모델 목록
_MODEL_OPTIONS: dict[str, list[str]] = {
    "ollama":    ["qwen2.5:7b", "llama3.2:3b", "gemma3:4b", "phi4-mini"],
    "openai":    ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo"],
    "anthropic": ["claude-3-5-haiku-20241022", "claude-3-5-sonnet-20241022", "claude-3-opus-20240229"],
    "google":    ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-pro", "gemini-1.5-flash"],
}


class SettingsPayload(BaseModel):
    provider: str
    model: str
    api_key: str = ""


@router.get("")
async def get_settings():
    import json as _json
    from pathlib import Path as _Path
    _prefs_path = _Path("~/Library/Application Support/PDFChatbot/preferences.json").expanduser()
    _prefs: dict = {}
    if _prefs_path.exists():
        try:
            _prefs = _json.loads(_prefs_path.read_text())
        except Exception:
            pass

    provider = get_provider()
    return {
        "provider": provider,
        "model": get_llm_model(),
        "api_key_saved": bool(get_api_key(provider)),
        "model_options": _MODEL_OPTIONS,
        "watched_folder": _prefs.get("watched_folder", ""),
    }


@router.post("")
async def post_settings(payload: SettingsPayload):
    if payload.provider not in _MODEL_OPTIONS:
        return {"ok": False, "error": f"지원하지 않는 provider: {payload.provider}"}
    save_settings(payload.provider, payload.model, payload.api_key)
    return {"ok": True}


@router.post("/test")
async def test_connection():
    """현재 설정으로 LLM 연결을 테스트한다."""
    from agent.llm_config import get_chat_llm
    try:
        llm = get_chat_llm(temperature=0)
        llm.invoke("Reply with one word: ok")
        return {"ok": True}
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": f"연결 실패: {e}"}
