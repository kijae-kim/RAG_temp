"""
agent/llm_config.py

LLM 프로바이더 중앙 설정.
preferences.json에서 provider / model / api_key를 읽어 LangChain 모델 인스턴스를 반환한다.

지원 프로바이더:
  - ollama   : 로컬 Ollama (기본값, 인터넷 불필요)
  - openai   : OpenAI API (GPT-4o, GPT-4o-mini 등)
  - anthropic: Anthropic API (claude-3-5-sonnet 등)
  - google   : Google Gemini API (gemini-2.0-flash 등)
"""

from __future__ import annotations

import json
from pathlib import Path

_PREFS_PATH = Path(
    "~/Library/Application Support/PDFChatbot/preferences.json"
).expanduser()

# ── 기본값 ────────────────────────────────────────────────────────────────────
_DEFAULT_PROVIDER = "ollama"
_DEFAULT_MODEL: dict[str, str] = {
    "ollama":    "qwen2.5:7b",
    "openai":    "gpt-4o-mini",
    "anthropic": "claude-3-5-haiku-20241022",
    "google":    "gemini-2.0-flash",
}
_DEFAULT_TEMPERATURE = 0.0


# ── preferences.json 읽기/쓰기 ────────────────────────────────────────────────
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


# ── 게터 ─────────────────────────────────────────────────────────────────────
def get_provider() -> str:
    return _load_prefs().get("provider", _DEFAULT_PROVIDER)


def get_llm_model() -> str:
    prefs = _load_prefs()
    provider = prefs.get("provider", _DEFAULT_PROVIDER)
    model = prefs.get("llm_model", "")
    return model or _DEFAULT_MODEL.get(provider, "qwen2.5:7b")


def get_llm_temperature() -> float:
    return _load_prefs().get("llm_temperature", _DEFAULT_TEMPERATURE)


def get_api_key(provider: str) -> str:
    """저장된 API 키를 반환한다. 없으면 빈 문자열."""
    return _load_prefs().get("api_keys", {}).get(provider, "")


# ── 세터 ─────────────────────────────────────────────────────────────────────
def save_settings(provider: str, model: str, api_key: str = "") -> None:
    """설정을 preferences.json에 저장한다."""
    prefs = _load_prefs()
    prefs["provider"] = provider
    prefs["llm_model"] = model
    api_keys = prefs.get("api_keys", {})
    if api_key:
        api_keys[provider] = api_key
    prefs["api_keys"] = api_keys
    _save_prefs(prefs)


# ── LLM 인스턴스 팩토리 ───────────────────────────────────────────────────────
def get_chat_llm(temperature: float | None = None):
    """
    현재 설정에 맞는 LangChain ChatModel 인스턴스를 반환한다.
    temperature=None 이면 preferences의 값을 사용한다.
    """
    provider = get_provider()
    model = get_llm_model()
    temp = temperature if temperature is not None else get_llm_temperature()

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        api_key = get_api_key("openai")
        if not api_key:
            raise ValueError("OpenAI API 키가 설정되지 않았습니다.")
        return ChatOpenAI(model=model, temperature=temp, api_key=api_key)

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        api_key = get_api_key("anthropic")
        if not api_key:
            raise ValueError("Anthropic API 키가 설정되지 않았습니다.")
        return ChatAnthropic(model=model, temperature=temp, api_key=api_key)

    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        api_key = get_api_key("google")
        if not api_key:
            raise ValueError("Google API 키가 설정되지 않았습니다.")
        return ChatGoogleGenerativeAI(model=model, temperature=temp, google_api_key=api_key)

    # 기본: ollama
    from langchain_ollama import ChatOllama
    return ChatOllama(model=model, temperature=temp)


def get_intent_llm():
    """intent 분류용 LLM (temperature=0 고정)."""
    return get_chat_llm(temperature=0)
