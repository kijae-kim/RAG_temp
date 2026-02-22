"""
04_mini_project/rag_engine.py

PDF Q&A 핵심 RAG 파이프라인 모듈.

설계 원칙:
- 이 모듈은 Streamlit에 독립적이다. app.py(Stage 1)와 macOS 연동(Stage 2) 모두 재사용 가능.
- 파일 경로(str/Path) 또는 파일-유사 객체(Streamlit UploadedFile) 모두 허용한다.
- 임시 파일은 항상 정리(cleanup)된다.
- 모든 오류는 타입이 명확한 커스텀 예외로 raise된다.

외부 의존성 (pyproject.toml 기준):
- langchain-classic, langchain-community, langchain-ollama
- langchain-huggingface, langchain-core
- faiss-cpu, rank-bm25, pypdf
"""

from __future__ import annotations

import logging
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, Generator, Never, Union

from dotenv import load_dotenv
from langchain_classic.chains import create_history_aware_retriever, create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_classic.retrievers import EnsembleRetriever
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import ChatOllama
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()


# =============================================================================
# 설정
# =============================================================================

@dataclass
class RAGConfig:
    """RAG 파이프라인 전체에서 사용하는 파라미터 중앙 관리.

    코드 변경 없이 청크 크기, 가중치 등을 조정할 수 있다.
    """

    chunk_size: int = 500
    chunk_overlap: int = 50
    retriever_k: int = 4
    faiss_fetch_k: int = 20
    # MMR 다양성 계수: 0.0 = 다양성 최대, 1.0 = 관련성만 추구
    faiss_lambda_mult: float = 0.6
    ensemble_weights: list[float] = field(default_factory=lambda: [0.5, 0.5])
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    llm_model: str = "llama3.2:3b"
    # 사실 기반 답변이 목적이므로 temperature는 낮게 설정
    llm_temperature: float = 0.0


# =============================================================================
# 커스텀 예외
# =============================================================================

class PDFLoadError(RuntimeError):
    """PDF 파일 로딩 실패 — 파일 없음, 권한 오류, 손상된 파일, 텍스트 추출 불가."""


class IndexBuildError(RuntimeError):
    """벡터 인덱스 생성 실패 — 빈 문서 또는 임베딩 오류."""


class LLMConnectionError(RuntimeError):
    """LLM 서버(Ollama) 연결 실패. `ollama serve` 실행 여부를 확인하세요."""


# =============================================================================
# 로거
# =============================================================================

def _create_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "[%(asctime)s] %(levelname)-9s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(handler)
    return logger


_logger = _create_logger("rag_engine")


# =============================================================================
# PDFChatbot
# =============================================================================

# Streamlit의 UploadedFile은 BinaryIO 호환 객체이므로 Union으로 허용한다.
# Streamlit을 직접 import하지 않아야 이 모듈이 독립적으로 유지된다.
PDFSource = Union[str, "os.PathLike[str]", BinaryIO]


class PDFChatbot:
    """PDF 기반 Q&A 챗봇.

    사용 예:
        # Streamlit UploadedFile
        chatbot = PDFChatbot(uploaded_file)

        # 로컬 파일 경로 (Stage 2 macOS 연동)
        chatbot = PDFChatbot("/path/to/paper.pdf")

        # 동기 호출
        result = chatbot.chat("이 논문의 핵심 기여는?", session_id="user_1")
        # → {"answer": str, "sources": list[Document], "query": str}

        # 스트리밍 (Streamlit st.write_stream 호환)
        text = st.write_stream(chatbot.stream_chat(question, session_id))
        sources = chatbot.last_sources  # 스트림 소진 후 접근

    컨텍스트 매니저로도 사용 가능 (임시 파일 즉시 정리):
        with PDFChatbot(uploaded_file) as chatbot:
            result = chatbot.chat("질문")
    """

    def __init__(
        self,
        pdf_source: PDFSource,
        config: RAGConfig | None = None,
    ) -> None:
        self._config = config or RAGConfig()
        self._session_store: dict[str, ChatMessageHistory] = {}
        self._temp_path: Path | None = None
        self._last_sources: list[Document] = []
        self._doc_info: dict[str, int | str] = {}

        pdf_path = self._resolve_pdf_path(pdf_source)
        try:
            docs = self._load_and_split(pdf_path)
            retriever = self._build_index(docs)
            self._chain = self._build_chain(retriever)
        except Exception:
            self._cleanup_temp()
            raise

    # -------------------------------------------------------------------------
    # 공개 API
    # -------------------------------------------------------------------------

    def chat(
        self,
        question: str,
        session_id: str = "default",
    ) -> dict[str, str | list[Document]]:
        """질문에 대한 답변을 동기적으로 반환한다.

        Returns:
            {"answer": str, "sources": list[Document], "query": str}

        Raises:
            LLMConnectionError: Ollama 서버 연결 실패 시
        """
        if not question.strip():
            return {"answer": "", "sources": [], "query": question}

        result = self._invoke_chain(question, session_id)

        sources: list[Document] = result.get("context", [])
        self._last_sources = sources
        self._log_retrieval(sources)

        return {
            "answer": result["answer"],
            "sources": sources,
            "query": question,
        }

    def stream_chat(
        self,
        question: str,
        session_id: str = "default",
    ) -> Generator[str, None, None]:
        """답변 토큰을 스트리밍 방식으로 yield한다.

        스트림 소진 후 last_sources 프로퍼티로 검색된 출처 문서에 접근 가능.
        Streamlit의 st.write_stream()과 직접 호환된다.

        Yields:
            str: 답변 텍스트 토큰

        Raises:
            LLMConnectionError: Ollama 서버 연결 실패 시
        """
        if not question.strip():
            return

        try:
            for chunk in self._chain.stream(
                {"input": question},
                config={"configurable": {"session_id": session_id}},
            ):
                if "context" in chunk:
                    self._last_sources = chunk["context"]
                    self._log_retrieval(chunk["context"])
                if chunk.get("answer"):
                    yield chunk["answer"]
        except Exception as exc:
            self._reraise_as_llm_error(exc)

    def get_doc_info(self) -> dict[str, int | str]:
        """인덱싱된 문서의 메타데이터를 반환한다.

        Returns:
            {"filename": str, "pages": int, "chunks": int,
             "embedding_model": str, "llm_model": str}
        """
        return dict(self._doc_info)

    def clear_session(self, session_id: str) -> None:
        """특정 세션의 대화 히스토리를 초기화한다."""
        if session_id in self._session_store:
            self._session_store[session_id].clear()
            _logger.info("세션 '%s' 히스토리 초기화", session_id)

    @property
    def last_sources(self) -> list[Document]:
        """가장 최근 chat / stream_chat 호출에서 검색된 출처 문서 목록."""
        return list(self._last_sources)

    def cleanup(self) -> None:
        """임시 PDF 파일을 명시적으로 삭제한다.

        Streamlit에서 PDF가 교체될 때 이전 PDFChatbot 인스턴스에 호출하면 된다.
        """
        self._cleanup_temp()

    def __enter__(self) -> "PDFChatbot":
        return self

    def __exit__(self, *_: object) -> None:
        self._cleanup_temp()

    def __del__(self) -> None:
        # __exit__이나 cleanup()이 이미 호출된 경우에도 안전하게 재호출된다.
        self._cleanup_temp()

    # -------------------------------------------------------------------------
    # 내부 구현
    # -------------------------------------------------------------------------

    def _resolve_pdf_path(self, pdf_source: PDFSource) -> Path:
        """파일 경로 또는 파일-유사 객체를 실제 Path로 변환한다.

        UploadedFile(BytesIO 계열)은 PyPDFLoader가 Path를 요구하므로
        임시 파일로 기록한 뒤 경로를 반환한다.
        임시 파일의 존재는 self._temp_path에 저장해 cleanup 대상으로 관리한다.
        """
        if isinstance(pdf_source, (str, os.PathLike)):
            path = Path(pdf_source).resolve()
            self._validate_pdf_path(path)
            return path

        # 파일-유사 객체 처리 (Streamlit UploadedFile 등)
        filename: str = getattr(pdf_source, "name", "upload.pdf")
        if not filename.lower().endswith(".pdf"):
            raise PDFLoadError(f"PDF 파일만 지원합니다: {filename!r}")

        # 읽기 위치가 중간에 있을 경우 처음부터 읽도록 보장
        if hasattr(pdf_source, "seek"):
            pdf_source.seek(0)

        # delete=False: PyPDFLoader가 경로를 열 수 있어야 하므로 즉시 삭제하지 않는다.
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        try:
            tmp.write(pdf_source.read())
            tmp.flush()
        except Exception as exc:
            tmp.close()
            Path(tmp.name).unlink(missing_ok=True)
            raise PDFLoadError(f"업로드 파일 기록 실패: {exc}") from exc
        finally:
            tmp.close()

        self._temp_path = Path(tmp.name)
        return self._temp_path

    @staticmethod
    def _validate_pdf_path(path: Path) -> None:
        if not path.exists():
            raise PDFLoadError(f"파일을 찾을 수 없습니다: {path}")
        if not path.is_file():
            raise PDFLoadError(f"경로가 파일이 아닙니다: {path}")
        if path.suffix.lower() != ".pdf":
            raise PDFLoadError(f"PDF 파일만 지원합니다: {path.name!r}")

    def _load_and_split(self, pdf_path: Path) -> list[Document]:
        _logger.info("PDF 로딩: %s", pdf_path.name)

        try:
            pages = PyPDFLoader(str(pdf_path)).load()
        except Exception as exc:
            raise PDFLoadError(f"PDF 파싱 실패: {exc}") from exc

        if not pages:
            raise PDFLoadError(
                "PDF에서 텍스트를 추출할 수 없습니다 (스캔본이거나 손상된 파일일 수 있습니다)."
            )

        docs = RecursiveCharacterTextSplitter(
            chunk_size=self._config.chunk_size,
            chunk_overlap=self._config.chunk_overlap,
        ).split_documents(pages)

        _logger.info("청크 분할 완료: %d페이지 → %d개 청크", len(pages), len(docs))

        self._doc_info = {
            "filename": pdf_path.name,
            "pages": len(pages),
            "chunks": len(docs),
            "embedding_model": self._config.embedding_model,
            "llm_model": self._config.llm_model,
        }
        return docs

    def _build_index(self, docs: list[Document]) -> EnsembleRetriever:
        if not docs:
            raise IndexBuildError("인덱싱할 문서가 없습니다.")

        _logger.info("BM25 인덱싱 중...")
        bm25 = BM25Retriever.from_documents(docs, k=self._config.retriever_k)
        _logger.info("BM25 인덱싱 완료")

        _logger.info("FAISS 인덱싱 중...")
        embeddings = HuggingFaceEmbeddings(
            model_name=self._config.embedding_model,
            model_kwargs={"device": "cpu"},
        )
        faiss_retriever = FAISS.from_documents(docs, embeddings).as_retriever(
            search_type="mmr",
            search_kwargs={
                "k": self._config.retriever_k,
                "fetch_k": self._config.faiss_fetch_k,
                "lambda_mult": self._config.faiss_lambda_mult,
            },
        )
        _logger.info("FAISS 인덱싱 완료")

        return EnsembleRetriever(
            retrievers=[bm25, faiss_retriever],
            weights=self._config.ensemble_weights,
        )

    def _build_chain(self, retriever: EnsembleRetriever) -> RunnableWithMessageHistory:
        llm = ChatOllama(
            model=self._config.llm_model,
            temperature=self._config.llm_temperature,
        )

        # 후속 질문("그것의 정확도는?")을 독립적인 질문("CNN 모델의 정확도는?")으로 재작성
        contextualize_prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "Given a chat history and the latest user question which might reference "
                "context in the chat history, formulate a standalone question which can be "
                "understood without the chat history. "
                "Do NOT answer the question, just reformulate it if needed and otherwise "
                "return it as is.",
            ),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ])

        qa_prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "You are a helpful research assistant. "
                "Answer the question based ONLY on the following context. "
                "If the answer is not found in the context, respond with: "
                "'해당 정보를 문서에서 찾을 수 없습니다.' "
                "Always answer in Korean.\n\nContext:\n{context}",
            ),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ])

        rag_chain = create_retrieval_chain(
            create_history_aware_retriever(llm, retriever, contextualize_prompt),
            create_stuff_documents_chain(llm, qa_prompt),
        )

        return RunnableWithMessageHistory(
            rag_chain,
            self._get_session_history,
            input_messages_key="input",
            history_messages_key="chat_history",
            output_messages_key="answer",
        )

    def _get_session_history(self, session_id: str) -> ChatMessageHistory:
        if session_id not in self._session_store:
            self._session_store[session_id] = ChatMessageHistory()
        return self._session_store[session_id]

    def _invoke_chain(self, question: str, session_id: str) -> dict:
        try:
            return self._chain.invoke(
                {"input": question},
                config={"configurable": {"session_id": session_id}},
            )
        except Exception as exc:
            self._reraise_as_llm_error(exc)

    @staticmethod
    def _reraise_as_llm_error(exc: Exception) -> Never:
        error_msg = str(exc).lower()
        if "connection" in error_msg or "refused" in error_msg:
            raise LLMConnectionError(
                "Ollama 서버에 연결할 수 없습니다. "
                "`ollama serve` 실행 후 다시 시도하세요."
            ) from exc
        raise exc

    @staticmethod
    def _log_retrieval(sources: list[Document]) -> None:
        pages = [int(d.metadata.get("page", 0)) + 1 for d in sources]
        _logger.info("RETRIEVER 검색된 청크: %d개 (페이지: %s)", len(sources), pages)

    def _cleanup_temp(self) -> None:
        if self._temp_path and self._temp_path.exists():
            try:
                self._temp_path.unlink()
                _logger.debug("임시 파일 삭제: %s", self._temp_path)
            except OSError as exc:
                _logger.warning("임시 파일 삭제 실패: %s (%s)", self._temp_path, exc)
            finally:
                self._temp_path = None
