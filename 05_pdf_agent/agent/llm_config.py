"""
agent/llm_config.py

LLM 모델 중앙 설정.
모델을 바꾸려면 이 파일의 LLM_MODEL 한 줄만 수정하면 된다.

Ollama 로컬 모델 옵션:
  - "llama3.2:3b"   (2.0GB, 기존 모델)
  - "qwen2.5:7b"    (4.7GB, 한국어 강화, 권장)
  - "gemma3:4b"     (3.3GB, Google, M1 최적화)
  - "phi4-mini"     (2.5GB, 추론 특화)

향후 외부 API 모드가 추가되면 provider / api_key 필드도 여기서 관리한다.
"""

from __future__ import annotations

from pathlib import Path
import json

_PREFS_PATH = Path(
    "~/Library/Application Support/PDFChatbot/preferences.json"
).expanduser()


def _load_prefs() -> dict:
    if _PREFS_PATH.exists():
        try:
            return json.loads(_PREFS_PATH.read_text())
        except Exception:
            pass
    return {}


def _save_prefs(prefs: dict) -> None:
    _PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _PREFS_PATH.write_text(json.dumps(prefs, ensure_ascii=False, indent=2))


# ── 기본값 ────────────────────────────────────────────────────────────────────
_DEFAULT_MODEL = "qwen2.5:7b"
_DEFAULT_TEMPERATURE = 0.0


def get_llm_model() -> str:
    """preferences.json의 llm_model 값을 반환한다. 없으면 기본값 사용."""
    return _load_prefs().get("llm_model", _DEFAULT_MODEL)


def set_llm_model(model: str) -> None:
    """사용할 Ollama 모델명을 preferences.json에 저장한다."""
    prefs = _load_prefs()
    prefs["llm_model"] = model
    _save_prefs(prefs)


def get_llm_temperature() -> float:
    return _load_prefs().get("llm_temperature", _DEFAULT_TEMPERATURE)


def get_intent_llm():
    """intent 분류에 사용할 ChatOllama 인스턴스를 반환한다."""
    from langchain_ollama import ChatOllama
    return ChatOllama(model=get_llm_model(), temperature=0)
