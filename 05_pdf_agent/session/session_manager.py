"""
session/session_manager.py

학습 세션 JSON 영속성 관리.

저장 위치: ~/Library/Application Support/PDFChatbot/sessions/{pdf_hash}.json
해시: SHA256(pdf_path)[:12] — 경로 기반 고유 식별
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path

from session.models import ConceptNote, StudySession

logger = logging.getLogger(__name__)

_SESSIONS_DIR = Path(
    "~/Library/Application Support/PDFChatbot/sessions"
).expanduser()


def _pdf_hash(pdf_path: str) -> str:
    return hashlib.sha256(pdf_path.encode()).hexdigest()[:12]


def _session_path(pdf_hash: str) -> Path:
    _SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    return _SESSIONS_DIR / f"{pdf_hash}.json"


def load_session(pdf_path: str) -> StudySession | None:
    """PDF 경로로 저장된 세션을 불러온다. 없으면 None."""
    h = _pdf_hash(pdf_path)
    p = _session_path(h)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return StudySession.from_dict(data)
    except Exception as exc:
        logger.warning("세션 로드 실패 (%s): %s", p, exc)
        return None


def save_session(session: StudySession) -> None:
    """세션을 JSON 파일로 저장한다."""
    p = _session_path(session.pdf_hash)
    try:
        p.write_text(
            json.dumps(session.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("세션 저장: %s", p.name)
    except Exception as exc:
        logger.error("세션 저장 실패: %s", exc)


def upsert_session(
    pdf_path: str,
    pdf_name: str,
    summary: str,
    concepts: list[str],
) -> StudySession:
    """
    세션을 새로 만들거나 기존 세션을 갱신한다.

    - 기존 세션: total_sessions+1, concepts_learned의 understood 상태 보존
    - 신규 세션: 모든 필드 초기화
    """
    now = datetime.now().isoformat(timespec="seconds")
    existing = load_session(pdf_path)

    if existing:
        existing.last_accessed = now
        existing.total_sessions += 1
        existing.summary = summary
        # 기존 understood 상태 보존하며 개념 목록 갱신
        prev_map = {c.concept: c for c in existing.concepts_learned}
        existing.concepts_learned = [
            prev_map.get(c, ConceptNote(concept=c)) for c in concepts
        ]
        save_session(existing)
        return existing

    h = _pdf_hash(pdf_path)
    session = StudySession(
        pdf_hash=h,
        pdf_name=pdf_name,
        started_at=now,
        last_accessed=now,
        summary=summary,
        concepts_learned=[ConceptNote(concept=c) for c in concepts],
    )
    save_session(session)
    return session


def increment_questions(pdf_path: str) -> None:
    """채팅 질문 1회 → questions_asked 증가 + last_accessed 갱신."""
    session = load_session(pdf_path)
    if session:
        session.questions_asked += 1
        session.last_accessed = datetime.now().isoformat(timespec="seconds")
        save_session(session)


def mark_concept_understood(pdf_path: str, concept: str) -> bool:
    """개념을 '이해 완료'로 마킹하고 quiz_score+1한다."""
    session = load_session(pdf_path)
    if not session:
        return False
    for c in session.concepts_learned:
        if c.concept == concept:
            c.understood = True
            c.quiz_score += 1
            save_session(session)
            return True
    return False
