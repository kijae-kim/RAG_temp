"""
04_mini_project/evaluate.py

Phase 3 — Ragas 기반 RAG 품질 정량 평가 스크립트.

통과 기준 (README §개발 우선순위):
    Faithfulness       ≥ 0.80
    Answer Relevancy   ≥ 0.85

평가 LLM:        Ollama llama3.2:3b  (로컬, 무료, 오프라인)
평가 임베딩:     HuggingFace all-MiniLM-L6-v2

실행:
    poetry run python 04_mini_project/evaluate.py

주의:
    - Ollama 서버가 실행 중이어야 한다  (`ollama serve`)
    - 로컬 LLM 평가로 5~15분 소요될 수 있다
    - 리포트는 04_mini_project/eval_report_<timestamp>.json 에 저장된다
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Final

# poetry run python 04_mini_project/evaluate.py 실행 시
# 스크립트 디렉터리가 sys.path에 없으므로 명시적으로 추가한다
sys.path.insert(0, str(Path(__file__).parent))

from rag_engine import IndexBuildError, LLMConnectionError, PDFChatbot, PDFLoadError

# =============================================================================
# 상수
# =============================================================================

PDF_PATH: Final = (
    Path(__file__).parent.parent.parent / "predicting_music.pdf"
).resolve()

# Phase 3 통과 기준
THRESHOLDS: Final[dict[str, float]] = {
    "faithfulness": 0.80,
    "answer_relevancy": 0.85,
}

# predicting_music.pdf 기반 테스트 질문셋
#
# ⚠️ 질문은 반드시 영어로 작성해야 한다.
#
# 이유: predicting_music.pdf는 영어 문서다.
#   - BM25는 토큰 정확 매칭 → 한국어 토큰은 영어 문서에 존재하지 않아 히트 0
#   - all-MiniLM-L6-v2는 영어 특화 임베딩 → 한국어 벡터와 영어 벡터의
#     코사인 유사도가 낮아 FAISS 검색도 실패
#   → 결과: LLM이 빈 컨텍스트를 받아 "해당 정보를 찾을 수 없습니다" 반환
#
# QA 프롬프트에 "Answer in Korean"이 명시되어 있으므로
# 영어 질문을 넣어도 답변은 한국어로 나온다.
TEST_QUESTIONS: Final[list[dict[str, str]]] = [
    {
        "question": "What is the main contribution of this paper?",
        "purpose": "Answer Relevancy — 논문 전반의 핵심 주장 파악",
    },
    {
        "question": "What Spotify audio features were used in this study?",
        "purpose": "Faithfulness — 정확한 목록 열거, 환각(Hallucination) 탐지",
    },
    {
        "question": "What is the accuracy of the classification model?",
        "purpose": "Context Precision — 특정 수치 검색",
    },
    {
        "question": "What are the limitations of the deep learning model used in this paper?",
        "purpose": "Faithfulness + Answer Relevancy — 비판적 분석",
    },
    {
        "question": "What future research directions do the authors suggest?",
        "purpose": "의미 검색 (FAISS) — 명시적 키워드 없는 개념 탐색",
    },
]

# =============================================================================
# 데이터 구조
# =============================================================================


@dataclass
class EvalSample:
    """단일 질문에 대한 RAG 출력을 담는 컨테이너."""

    question: str
    purpose: str
    answer: str = ""
    contexts: list[str] = field(default_factory=list)
    elapsed_sec: float = 0.0
    error: str = ""  # 비어 있으면 성공


# =============================================================================
# 1단계: RAG 출력 수집
# =============================================================================


def collect_rag_outputs(chatbot: PDFChatbot) -> list[EvalSample]:
    """각 질문을 독립 세션으로 실행하여 답변과 컨텍스트를 수집한다.

    세션을 분리하는 이유:
        이전 질문의 대화 히스토리가 다음 질문의 검색 쿼리 재작성에
        영향을 주면 평가가 오염된다. 각 질문은 독립적으로 평가돼야 한다.
    """
    samples: list[EvalSample] = []
    total = len(TEST_QUESTIONS)

    for i, item in enumerate(TEST_QUESTIONS, 1):
        question = item["question"]
        sample = EvalSample(question=question, purpose=item["purpose"])

        print(f"\n  [{i}/{total}] {question}")

        try:
            t0 = time.perf_counter()
            result = chatbot.chat(question, session_id=f"eval_{i}")
            sample.elapsed_sec = round(time.perf_counter() - t0, 2)

            sample.answer = result["answer"]
            sample.contexts = [doc.page_content for doc in result["sources"]]

            answer_preview = sample.answer[:80].replace("\n", " ")
            if len(sample.answer) > 80:
                answer_preview += "..."
            print(f"         답변: {answer_preview}")
            print(
                f"         컨텍스트: {len(sample.contexts)}개  "
                f"응답시간: {sample.elapsed_sec}s"
            )

        except LLMConnectionError as exc:
            sample.error = str(exc)
            print(f"         [ERROR] {exc}")
        except Exception as exc:
            sample.error = f"예상치 못한 오류: {exc}"
            print(f"         [ERROR] {exc}")

        samples.append(sample)

    return samples


# =============================================================================
# 2단계: Ragas 평가
# =============================================================================


def run_ragas_evaluation(samples: list[EvalSample]) -> dict[str, float]:
    """Ragas로 RAG 품질을 정량 평가한다.

    평가 가능 조건:
        - 답변과 컨텍스트가 모두 있는 샘플만 평가한다
        - 오류 샘플은 건너뛴다

    Returns:
        metric_name → 평균 점수 (0.0 ~ 1.0) 딕셔너리

    Raises:
        RuntimeError: 평가 가능한 샘플이 하나도 없을 때
        LLMConnectionError: 평가 중 Ollama 서버 연결 실패 시
    """
    valid = [s for s in samples if not s.error and s.contexts]
    if not valid:
        raise RuntimeError(
            "평가 가능한 샘플이 없습니다. RAG 출력 수집 결과를 확인하세요."
        )

    print(f"\n  유효 샘플: {len(valid)}/{len(samples)}개")

    import openai
    from langchain_huggingface import HuggingFaceEmbeddings
    from ragas import EvaluationDataset, SingleTurnSample, evaluate
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import llm_factory
    from ragas.metrics.collections import AnswerRelevancy, Faithfulness

    # ragas 0.4.x의 collections 메트릭은 instructor 기반 InstructorLLM만 허용한다.
    # LangchainLLMWrapper(legacy)는 ValueError를 발생시킨다.
    # → Ollama의 OpenAI 호환 엔드포인트(http://localhost:11434/v1)를 통해
    #   llm_factory로 InstructorLLM을 생성한다.
    ollama_client = openai.OpenAI(
        base_url="http://localhost:11434/v1",
        api_key="ollama",  # Ollama는 인증 불필요, dummy 값
    )
    ragas_llm = llm_factory("llama3.2:3b", client=ollama_client)

    # 임베딩은 여전히 LangchainEmbeddingsWrapper 사용 가능
    embeddings = LangchainEmbeddingsWrapper(
        HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={"device": "cpu"},
        )
    )

    metrics = [
        Faithfulness(llm=ragas_llm),
        AnswerRelevancy(llm=ragas_llm, embeddings=embeddings),
    ]

    try:
        from ragas.metrics.collections import ContextPrecisionWithoutReference

        metrics.append(ContextPrecisionWithoutReference(llm=ragas_llm))
        print("  ContextPrecisionWithoutReference: 활성화")
    except Exception:
        print("  ContextPrecisionWithoutReference: 현재 설정 미지원, 스킵")

    ragas_samples = [
        SingleTurnSample(
            user_input=s.question,
            response=s.answer,
            retrieved_contexts=s.contexts,
        )
        for s in valid
    ]

    print(
        f"  Ragas 평가 시작 (로컬 LLM 사용으로 5~15분 소요될 수 있습니다)..."
    )

    try:
        result = evaluate(
            EvaluationDataset(samples=ragas_samples),
            metrics=metrics,
            raise_exceptions=False,  # 개별 샘플 실패 시 NaN 처리, 전체 중단 방지
        )
    except Exception as exc:
        err = str(exc).lower()
        if "connection" in err or "refused" in err:
            raise LLMConnectionError(
                "평가 중 Ollama 서버 연결이 끊겼습니다. `ollama serve` 상태를 확인하세요."
            ) from exc
        raise

    df = result.to_pandas()

    # to_pandas()는 metric 컬럼 외에 입력 데이터 컬럼도 포함하므로
    # 숫자형 컬럼만 추출해 평균을 계산한다
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    scores = {col: round(float(df[col].mean()), 4) for col in numeric_cols}

    return scores


# =============================================================================
# 결과 출력
# =============================================================================


def print_results(samples: list[EvalSample], scores: dict[str, float]) -> None:
    print("\n" + "=" * 60)
    print("평가 결과")
    print("=" * 60)

    all_pass = True
    for metric, score in scores.items():
        threshold = THRESHOLDS.get(metric, 0.0)
        passed = score >= threshold
        if threshold > 0 and not passed:
            all_pass = False
        status = "PASS" if (threshold == 0 or passed) else "FAIL"
        threshold_str = f"기준: {threshold:.2f}" if threshold > 0 else "기준 없음"
        print(f"  {metric:<40} {score:.3f}  ({threshold_str})  [{status}]")

    print("─" * 60)
    verdict = "PASS ─ Phase 3 완료 조건 충족" if all_pass else "FAIL ─ 파라미터 조정 필요"
    print(f"  최종 판정: {verdict}")

    print("\n질문별 요약:")
    print(f"  {'#':<3} {'상태':<8} {'응답시간':>6}  질문")
    print("  " + "─" * 54)
    for i, s in enumerate(samples, 1):
        if s.error:
            status_str = "ERROR"
            time_str = "─"
        else:
            status_str = "OK"
            time_str = f"{s.elapsed_sec:.1f}s"
        q_preview = s.question[:44] + ("..." if len(s.question) > 44 else "")
        print(f"  {i:<3} {status_str:<8} {time_str:>6}  {q_preview}")
        if s.error:
            print(f"           → {s.error}")


# =============================================================================
# 리포트 저장
# =============================================================================


def save_report(
    samples: list[EvalSample],
    scores: dict[str, float],
) -> Path:
    """평가 결과를 JSON 리포트로 저장한다."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = Path(__file__).parent / f"eval_report_{timestamp}.json"

    passed = all(
        scores.get(m, 0) >= t
        for m, t in THRESHOLDS.items()
        if m in scores
    )

    report = {
        "timestamp": timestamp,
        "pdf": PDF_PATH.name,
        "thresholds": THRESHOLDS,
        "scores": scores,
        "passed": passed,
        "samples": [
            {
                "question": s.question,
                "purpose": s.purpose,
                "answer": s.answer,
                "contexts_count": len(s.contexts),
                "elapsed_sec": s.elapsed_sec,
                "error": s.error,
            }
            for s in samples
        ],
    }

    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return report_path


# =============================================================================
# 진입점
# =============================================================================


def main() -> None:
    print("=" * 60)
    print("Phase 3 — RAG 품질 평가 (Ragas)")
    print("=" * 60)
    print(f"PDF:      {PDF_PATH}")
    print(f"질문 수:  {len(TEST_QUESTIONS)}개")
    print(f"통과 기준: {THRESHOLDS}")

    # ── RAG 엔진 초기화 ──────────────────────────────────────────────────────
    print("\nRAG 엔진 초기화 중...")
    try:
        chatbot = PDFChatbot(str(PDF_PATH))
    except (PDFLoadError, IndexBuildError) as exc:
        print(f"\n[ERROR] {exc}")
        sys.exit(1)

    # ── 1단계: RAG 출력 수집 ─────────────────────────────────────────────────
    print("\n" + "─" * 60)
    print("1단계: RAG 출력 수집")
    print("─" * 60)
    samples = collect_rag_outputs(chatbot)

    success_count = sum(1 for s in samples if not s.error)
    print(f"\n  완료: {success_count}/{len(samples)}개 성공")

    # ── 2단계: Ragas 평가 ────────────────────────────────────────────────────
    print("\n" + "─" * 60)
    print("2단계: Ragas 평가")
    print("─" * 60)

    try:
        scores = run_ragas_evaluation(samples)
    except LLMConnectionError as exc:
        print(f"\n[ERROR] {exc}")
        sys.exit(1)
    except RuntimeError as exc:
        print(f"\n[ERROR] {exc}")
        sys.exit(1)

    # ── 결과 출력 및 저장 ────────────────────────────────────────────────────
    print_results(samples, scores)

    report_path = save_report(samples, scores)
    print(f"\n리포트 저장: {report_path.name}")


if __name__ == "__main__":
    main()
