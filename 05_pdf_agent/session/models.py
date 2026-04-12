"""
session/models.py

학습 세션 데이터 모델.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class ConceptNote:
    concept: str           # 영어 원문 태그 (e.g. "BM25")
    understood: bool = False  # 퀴즈 통과 여부
    quiz_score: int = 0    # 누적 퀴즈 정답 수


@dataclass
class StudySession:
    pdf_hash: str          # SHA256[:12] — 파일명 충돌 방지
    pdf_name: str          # 표시용 파일명
    started_at: str        # ISO datetime (첫 세션 시작)
    last_accessed: str     # ISO datetime (최종 접근)
    total_sessions: int = 1
    questions_asked: int = 0
    concepts_learned: list[ConceptNote] = field(default_factory=list)
    summary: str = ""
    pdf_path: str = ""                           # 재개 시 PDF 재로드용
    chat_messages: list[dict] = field(default_factory=list)
    # chat_messages 항목: {"role": "user"|"assistant", "content": str}

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "StudySession":
        d = dict(d)  # 원본 변형 방지
        concepts_data = d.pop("concepts_learned", [])
        chat_data = d.pop("chat_messages", [])
        s = cls(**d)
        s.concepts_learned = [ConceptNote(**c) for c in concepts_data]
        s.chat_messages = list(chat_data)
        return s
