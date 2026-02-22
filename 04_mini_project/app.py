"""
04_mini_project/app.py

Streamlit UI — PDF Q&A 챗봇 (Stage 1).

Stage 2 (macOS 연동):
    PDF_PATH 환경변수가 설정된 경우 파일 업로더 없이 자동으로 PDF를 로딩한다.
    $ PDF_PATH="/path/to/paper.pdf" poetry run streamlit run 04_mini_project/app.py

실행:
    poetry run streamlit run 04_mini_project/app.py
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Final

import streamlit as st
from langchain_core.documents import Document

# streamlit run 실행 시 스크립트 디렉터리가 sys.path에 추가되므로 상대 임포트 사용
from rag_engine import (
    IndexBuildError,
    LLMConnectionError,
    PDFChatbot,
    PDFLoadError,
)

# =============================================================================
# 상수
# =============================================================================

APP_TITLE: Final = "PDF Q&A 챗봇"
CHAT_PLACEHOLDER: Final = "논문에 대해 무엇이든 질문하세요..."
INDEXING_SPINNER: Final = "PDF 인덱싱 중... 처음 실행 시 약 15~30초가 소요됩니다."

# =============================================================================
# 페이지 설정 — 반드시 다른 st 호출보다 먼저 실행되어야 한다
# =============================================================================

st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =============================================================================
# 세션 상태 초기화
# =============================================================================


def _init_session_state() -> None:
    """Streamlit 세션 최초 로딩 시 상태 키를 초기화한다."""
    defaults: dict = {
        # 브라우저 탭 단위로 고유한 LangChain 대화 세션 ID
        "session_id": str(uuid.uuid4()),
        "chatbot": None,
        # 재인덱싱 트리거: 이전에 로딩된 PDF 파일명
        "pdf_name": None,
        # 화면 재렌더링용 대화 내역. 각 항목: {"role", "content", "sources"}
        "messages": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# =============================================================================
# PDF 로딩
# =============================================================================


def _load_pdf_from_path(pdf_path: str) -> None:
    """로컬 파일 경로로 PDFChatbot을 초기화한다 (Stage 2 전용)."""
    path = Path(pdf_path)
    if st.session_state.pdf_name == path.name:
        return  # 동일한 파일이 이미 로딩되어 있으면 재인덱싱 생략

    with st.spinner(INDEXING_SPINNER):
        try:
            st.session_state.chatbot = PDFChatbot(pdf_path)
            st.session_state.pdf_name = path.name
            st.session_state.messages = []
        except (PDFLoadError, IndexBuildError) as exc:
            st.error(f"PDF 로딩 실패: {exc}")
            st.session_state.chatbot = None


def _load_pdf_from_upload(uploaded_file: object) -> None:
    """Streamlit UploadedFile로 PDFChatbot을 초기화한다 (Stage 1 전용)."""
    if st.session_state.pdf_name == uploaded_file.name:
        return  # 동일한 파일을 재업로드한 경우 재인덱싱 생략

    # 이전 인스턴스의 임시 파일을 즉시 정리한다
    prev: PDFChatbot | None = st.session_state.chatbot
    if prev is not None:
        prev.cleanup()

    with st.spinner(INDEXING_SPINNER):
        try:
            st.session_state.chatbot = PDFChatbot(uploaded_file)
            st.session_state.pdf_name = uploaded_file.name
            st.session_state.messages = []
            # 새 PDF에는 새로운 대화 세션을 부여해 이전 히스토리가 섞이지 않도록 한다
            st.session_state.session_id = str(uuid.uuid4())
        except (PDFLoadError, IndexBuildError) as exc:
            st.error(f"PDF 로딩 실패: {exc}")
            st.session_state.chatbot = None


# =============================================================================
# 사이드바
# =============================================================================


def _render_sidebar(stage2_path: str | None) -> None:
    with st.sidebar:
        st.title(APP_TITLE)
        st.divider()

        if stage2_path:
            # Stage 2: 환경변수로 파일이 전달된 경우 — 업로더 대신 파일 정보 표시
            st.info(f"macOS 자동 실행\n\n📄 **{Path(stage2_path).name}**")
        else:
            # Stage 1: 사용자가 파일을 직접 선택
            uploaded = st.file_uploader(
                "PDF 파일 선택",
                type=["pdf"],
                help="논문, 보고서 등 PDF 파일을 업로드하세요.",
            )
            if uploaded:
                _load_pdf_from_upload(uploaded)

        chatbot: PDFChatbot | None = st.session_state.chatbot
        if chatbot is None:
            return

        # 문서 정보 패널
        st.divider()
        st.subheader("문서 정보")
        info = chatbot.get_doc_info()
        col1, col2 = st.columns(2)
        col1.metric("페이지", info.get("pages", "-"))
        col2.metric("청크", info.get("chunks", "-"))

        with st.expander("모델 설정"):
            st.caption(f"**LLM**: `{info.get('llm_model', '-')}`")
            st.caption(f"**임베딩**: `{info.get('embedding_model', '-')}`")

        st.divider()
        if st.button("대화 초기화", use_container_width=True, type="secondary"):
            chatbot.clear_session(st.session_state.session_id)
            st.session_state.messages = []
            st.rerun()


# =============================================================================
# 출처 렌더링
# =============================================================================


def _render_sources(sources: list[Document]) -> None:
    """검색된 출처 문서를 접기/펼치기 형식으로 표시한다."""
    if not sources:
        return

    pages = sorted({int(d.metadata.get("page", 0)) + 1 for d in sources})
    label = "📄 출처: " + ", ".join(f"p.{p}" for p in pages)

    with st.expander(label):
        for doc in sources:
            page = int(doc.metadata.get("page", 0)) + 1
            snippet = doc.page_content.strip()
            # 너무 긴 청크는 앞부분만 표시한다
            if len(snippet) > 250:
                snippet = snippet[:250] + "..."
            st.caption(f"**p.{page}**")
            st.text(snippet)
            st.divider()


# =============================================================================
# 채팅 인터페이스
# =============================================================================


def _render_chat_history() -> None:
    """세션에 저장된 대화 내역을 화면에 다시 그린다."""
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant":
                _render_sources(msg.get("sources", []))


def _handle_user_input(question: str) -> None:
    """사용자 질문을 처리하고 스트리밍 응답을 출력한다."""
    chatbot: PDFChatbot = st.session_state.chatbot
    session_id: str = st.session_state.session_id

    # 사용자 메시지를 즉시 화면에 표시하고 저장
    with st.chat_message("user"):
        st.markdown(question)
    st.session_state.messages.append(
        {"role": "user", "content": question, "sources": []}
    )

    # 어시스턴트 스트리밍 응답
    with st.chat_message("assistant"):
        try:
            # st.write_stream은 generator를 소비하며 토큰을 실시간 출력하고
            # 완성된 전체 텍스트를 반환한다
            response_text: str = st.write_stream(
                chatbot.stream_chat(question, session_id)
            )
        except LLMConnectionError:
            st.error(
                "Ollama 서버에 연결할 수 없습니다.  \n"
                "터미널에서 `ollama serve`를 실행한 뒤 다시 시도하세요."
            )
            # 실패한 사용자 메시지를 히스토리에서 제거해 재시도 시 혼란을 방지한다
            st.session_state.messages.pop()
            return
        except Exception as exc:
            st.error(f"예상치 못한 오류가 발생했습니다: {exc}")
            st.session_state.messages.pop()
            return

        sources = chatbot.last_sources
        _render_sources(sources)

    st.session_state.messages.append(
        {"role": "assistant", "content": response_text, "sources": sources}
    )


# =============================================================================
# 초기 화면 (PDF 미로딩 상태)
# =============================================================================


def _render_welcome() -> None:
    st.markdown(
        """
        ## 왼쪽 사이드바에서 PDF 파일을 업로드하세요.

        업로드가 완료되면 아래와 같이 바로 질문할 수 있습니다.

        ---

        **질문 예시:**

        | 유형 | 예시 질문 |
        |---|---|
        | 핵심 내용 파악 | "이 논문의 핵심 contribution은?" |
        | 수치/데이터 | "사용된 모델의 정확도 수치는?" |
        | 방법론 | "어떤 머신러닝 알고리즘을 사용했나요?" |
        | 후속 질문 | "그 방법의 한계점은?" |
        | 섹션 요약 | "실험 설정을 요약해줘" |

        > 후속 질문("그것의 정확도는?")도 대화 맥락을 기억하여 정확하게 답변합니다.
        """
    )


# =============================================================================
# 진입점
# =============================================================================


def main() -> None:
    _init_session_state()

    # Stage 2: PDF_PATH 환경변수가 설정된 경우 파일 업로더 없이 자동 로딩
    stage2_path: str | None = os.environ.get("PDF_PATH")
    if stage2_path:
        _load_pdf_from_path(stage2_path)

    _render_sidebar(stage2_path)

    st.header(APP_TITLE)

    chatbot: PDFChatbot | None = st.session_state.chatbot
    if chatbot is None:
        _render_welcome()
        return

    _render_chat_history()

    question = st.chat_input(CHAT_PLACEHOLDER)
    if question:
        _handle_user_input(question)


if __name__ == "__main__":
    main()
