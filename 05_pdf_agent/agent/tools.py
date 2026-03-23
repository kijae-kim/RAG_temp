"""
agent/tools.py

PDFChatbot 위에서 동작하는 스트리밍 도구 함수.

모든 AI 출력은 한국어로 고정.
개념 태그(BM25, FAISS 등)는 영어 원문 유지.

/api/chat Phase 2에서 STREAM_FN_MAP이 이 함수들을 사용한다.
"""

from __future__ import annotations

from typing import Generator


def stream_qa(chatbot, question: str, session_id: str) -> Generator[str, None, None]:
    """논문 내용 일반 Q&A — 기본 stream_chat() 위임."""
    yield from chatbot.stream_chat(question, session_id)


def stream_explain(chatbot, question: str, session_id: str) -> Generator[str, None, None]:
    """개념·용어 단계적 설명."""
    prompt = (
        f"다음 개념이나 용어를 논문 내용을 바탕으로 한국어로 단계적으로 설명하세요.\n"
        f"1) 핵심 정의 2) 작동 원리 3) 논문에서의 활용 순서로 설명해주세요.\n\n"
        f"개념: {question}"
    )
    yield from chatbot.stream_chat(prompt, session_id)


def stream_quiz(chatbot, question: str, session_id: str) -> Generator[str, None, None]:
    """퀴즈 생성 — 문제·선택지 4개·정답 포함."""
    prompt = (
        f"논문 내용을 바탕으로 다음 주제에 관한 퀴즈를 한국어로 만들어주세요.\n"
        f"형식: 문제 → 선택지 ①②③④ → 정답 → 해설\n\n"
        f"주제: {question}"
    )
    yield from chatbot.stream_chat(prompt, session_id)


def stream_summarize(chatbot, question: str, session_id: str) -> Generator[str, None, None]:
    """논문 요약 — 전체 또는 특정 섹션."""
    prompt = (
        "이 논문의 핵심 내용을 한국어로 요약해주세요.\n"
        "1) 연구 목적 2) 방법론 3) 주요 결과 4) 결론 순서로 작성하세요."
    )
    yield from chatbot.stream_chat(prompt, session_id)


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
_INTENT_PROMPT = """다음 질문의 의도를 분류하세요.

질문: {question}

분류 기준:
- explain: 개념, 용어, 원리 설명 요청 (예: "~가 뭐야", "~을 설명해줘", "~란?")
- quiz: 퀴즈, 문제, 테스트 요청 (예: "퀴즈 내줘", "문제 출제해줘")
- summarize: 요약 요청 (예: "요약해줘", "정리해줘", "핵심이 뭐야")
- qa: 그 외 논문 내용 질문

반드시 explain, quiz, summarize, qa 중 하나만 소문자로 답하세요."""


def classify_intent(question: str) -> str:
    """
    질문 의도를 LLM으로 분류한다 (동기, ~1~2초).
    반환값: "qa" | "explain" | "quiz" | "summarize"
    """
    from langchain_ollama import ChatOllama
    llm = ChatOllama(model="llama3.2:3b", temperature=0)
    result = llm.invoke(_INTENT_PROMPT.format(question=question))
    content = result.content.strip().lower()
    for intent in ("explain", "quiz", "summarize", "qa"):
        if intent in content:
            return intent
    return "qa"


# ── STREAM_FN_MAP (chat.py Phase 2에서 사용) ──────────────────────────────────
STREAM_FN_MAP: dict[str, callable] = {
    "qa":        stream_qa,
    "explain":   stream_explain,
    "quiz":      stream_quiz,
    "summarize": stream_summarize,
}
