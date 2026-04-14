"""
agent/tools.py

PDFChatbot 위에서 동작하는 스트리밍 도구 함수.

모든 AI 출력은 한국어로 고정.
개념 태그(BM25, FAISS 등)는 영어 원문 유지.

/api/chat Phase 2에서 STREAM_FN_MAP이 이 함수들을 사용한다.
"""

from __future__ import annotations

from typing import Generator

# ── 답변 스타일 prefix ────────────────────────────────────────────────────────
_STYLE_PREFIX: dict[str, str] = {
    "brief":    "답변을 2~3문장으로 간결하게 핵심만 작성하세요.\n\n",
    "default":  "",
    "detailed": "답변을 단계별로 자세하게 작성하세요. 예시와 구체적인 수식·수치를 포함하세요.\n\n",
}


def _apply_style(prompt: str, style: str) -> str:
    prefix = _STYLE_PREFIX.get(style, "")
    return prefix + prompt if prefix else prompt


def stream_qa(chatbot, question: str, session_id: str, style: str = "default") -> Generator[str, None, None]:
    """논문 내용 일반 Q&A."""
    prompt = _apply_style(question, style)
    yield from chatbot.stream_chat(prompt, session_id)


def stream_explain(chatbot, question: str, session_id: str, style: str = "default") -> Generator[str, None, None]:
    """개념·용어 단계적 설명."""
    base = (
        f"다음 개념이나 용어를 논문 내용을 바탕으로 한국어로 단계적으로 설명하세요.\n"
        f"1) 핵심 정의 2) 작동 원리 3) 논문에서의 활용 순서로 설명해주세요.\n\n"
        f"개념: {question}"
    )
    yield from chatbot.stream_chat(_apply_style(base, style), session_id)


def stream_quiz(chatbot, question: str, session_id: str, style: str = "default") -> Generator[str, None, None]:
    """퀴즈 생성 — 문제·선택지 4개·정답 포함."""
    prompt = (
        f"논문 내용을 바탕으로 다음 주제에 관한 퀴즈를 한국어로 만들어주세요.\n"
        f"형식: 문제 → 선택지 ①②③④ → 정답 → 해설\n\n"
        f"주제: {question}"
    )
    # quiz는 형식이 고정이므로 style prefix를 앞에 붙이지 않음
    yield from chatbot.stream_chat(prompt, session_id)


def stream_summarize(chatbot, question: str, session_id: str, style: str = "default") -> Generator[str, None, None]:
    """논문 요약 — 전체 또는 특정 섹션."""
    base = (
        "이 논문의 핵심 내용을 한국어로 요약해주세요.\n"
        "1) 연구 목적 2) 방법론 3) 주요 결과 4) 결론 순서로 작성하세요."
    )
    yield from chatbot.stream_chat(_apply_style(base, style), session_id)


def stream_out_of_scope(chatbot, question: str, session_id: str, style: str = "default") -> Generator[str, None, None]:
    """논문 범위 밖 질문 — 즉시 거절 메시지 반환."""
    yield "죄송합니다. 현재 로드된 논문의 범위를 벗어난 질문입니다.\n\n"
    yield "논문에서 다루는 내용에 대해 질문해주세요. 예를 들어:\n"
    yield "- 논문의 핵심 개념 설명\n"
    yield "- 논문에서 사용된 방법론\n"
    yield "- 논문의 실험 결과\n"
    yield "- 관련 퀴즈 생성"


# ── /api/analyze 전용 동기 함수 ───────────────────────────────────────────────
def _answer(result) -> str:
    """chatbot.chat() 반환값에서 answer 문자열만 추출."""
    if isinstance(result, dict):
        return str(result.get("answer", ""))
    if isinstance(result, str):
        return result
    if hasattr(result, "content"):
        return str(result.content)
    return str(result)


def summarize_paper(chatbot) -> str:
    """논문 전체 요약 (한국어). analyze_node에서 사용."""
    prompt = (
        "이 논문의 핵심 내용을 한국어로 3~5문장으로 요약하세요.\n"
        "연구 목적, 방법, 결론을 포함해주세요."
    )
    return _answer(chatbot.chat(prompt, session_id="analyze"))


def extract_concepts(chatbot) -> list[str]:
    """핵심 개념 태그 추출 (영어 원문). analyze_node에서 사용."""
    import re
    prompt = (
        "List 5-8 core technical concepts from this paper.\n"
        "Rules: English terms only, comma-separated, no numbering, no intro text.\n"
        "Example output: BM25, FAISS, Ensemble Retrieval, TF-IDF"
    )
    raw = _answer(chatbot.chat(prompt, session_id="analyze_concepts"))

    # 번호 목록 형태(1. Foo\n2. Bar) 파싱
    numbered = re.findall(r"\d+\.\s*([^\n,]+)", raw)
    if numbered:
        return [c.strip() for c in numbered if c.strip()][:8]

    # 쉼표 구분 형태
    concepts = [c.strip() for c in raw.split(",") if c.strip()]
    # 한국어 혼입 항목 필터: 대부분 영문자인 것만 유지
    concepts = [c for c in concepts if sum(1 for ch in c if ch.isascii()) / max(len(c), 1) > 0.6]
    return concepts[:8]


# ── intent 분류 ──────────────────────────────────────────────────────────────
# scope + intent를 단일 LLM 호출로 통합 (2회 → 1회)
_CLASSIFY_PROMPT = """You are a classifier for an academic paper Q&A assistant.
Classify the user question into exactly one intent. Output one word only.

Intents:
- quiz      : explicitly requesting a quiz/test/problem ("퀴즈 내줘", "문제 출제", "테스트해줘")
- summarize : explicitly requesting a summary of the whole paper ("요약해줘", "정리해줘", "핵심이 뭐야", "결론 요약")
- explain   : asking to explain a concept, term, or mechanism ("~가 뭐야?", "~란?", "설명해줘", "차이가 뭐야?", "역할이 뭐야?")
- qa        : specific factual question about the paper (author, result, method, number, comparison)
- out_of_scope : code implementation requests OR topics completely unrelated to any academic paper
                 (날씨, 주식, 점심, 코드 짜줘, PyTorch 구현, SNS 연락처)

Rules:
- Default to "qa" when unsure — academic and conceptual questions are almost never out_of_scope
- "~가 뭐야?" about a concept → explain (not qa)
- Comparison/reason questions → qa (not summarize)

Question: {question}
Answer (one word only):"""


_KEYWORD_MAP: list[tuple[list[str], str]] = [
    # 키워드가 포함되면 즉시 해당 intent 반환 (LLM 호출 없음)
    (["퀴즈", "문제 출제", "문제를 출제", "테스트해줘", "문제 내줘"], "quiz"),
    (["요약해줘", "요약 해줘", "정리해줘", "핵심이 뭐야", "결론 요약", "전체 요약"], "summarize"),
]

_OOS_KEYWORDS: list[str] = [
    "pytorch", "tensorflow", "코드 짜줘", "코드 작성", "구현해줘", "구현하는 법",
    "gpt", "bert", "chatgpt", "openai", "몇 살", "나이가", "살이야",
]


def classify_intent(question: str) -> str:
    """
    질문 의도를 분류한다 (동기).
    1단계: 키워드 사전 필터 (LLM 없이 즉시 처리)
    2단계: LLM — scope + intent 단일 호출 (기존 2회 → 1회)
    반환값: "qa" | "explain" | "quiz" | "summarize" | "out_of_scope"
    """
    q_lower = question.lower()

    # 1단계-A: out_of_scope 키워드 사전 필터
    if any(kw in q_lower for kw in _OOS_KEYWORDS):
        return "out_of_scope"

    # 1단계-B: intent 키워드 사전 필터
    for keywords, intent in _KEYWORD_MAP:
        if any(kw in question for kw in keywords):
            return intent

    # 2단계: LLM 단일 호출로 scope + intent 분류
    from agent.llm_config import get_intent_llm
    llm = get_intent_llm()
    result = llm.invoke(_CLASSIFY_PROMPT.format(question=question))
    content = result.content.strip().lower()
    for intent in ("out_of_scope", "explain", "quiz", "summarize", "qa"):
        if intent in content:
            return intent
    return "qa"


# ── STREAM_FN_MAP (chat.py Phase 2에서 사용) ──────────────────────────────────
STREAM_FN_MAP: dict[str, callable] = {
    "qa":            stream_qa,
    "explain":       stream_explain,
    "quiz":          stream_quiz,
    "summarize":     stream_summarize,
    "out_of_scope":  stream_out_of_scope,
}
