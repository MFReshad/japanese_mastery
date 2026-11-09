from __future__ import annotations
from app.services.lookup_cache import lookup_cache

import random
from datetime import datetime, timezone

from app.errors import NotFound, Conflict, InvalidOperation
from sqlalchemy import case, func, select, update
from sqlalchemy.orm import Session

from app.models.practice import (
    ItemProgress,
    PracticeAnswer,
    PracticeQuestion,
    PracticeSession,
)
from app.schemas.practice import PracticeStartRequest
from app.services.mastery import record_answer
from .cache import practice_session_cache


from .types import QuestionDraft
from .selection import _eligible_sources
from .vocabulary_questions import question_from_vocab
from .kanji_questions import questions_from_kanji, example_word_questions


def start_practice(
    db: Session, payload: PracticeStartRequest
) -> tuple[PracticeSession, list[PracticeQuestion]]:
    drafts: list[QuestionDraft] = []
    if payload.practice_type in ("vocabulary", "mixed"):
        vocab = _eligible_sources(db, payload, "vocabulary")
        drafts.extend(
            draft
            for source in vocab
            if (draft := question_from_vocab(source)) is not None
        )
    if payload.practice_type in ("kanji", "mixed", "important_kanji_words", "kanji_example_words"):
        kanji = _eligible_sources(db, payload, "kanji")
        if payload.practice_type in ("important_kanji_words", "kanji_example_words"):
            selected_conditions = set(payload.conditions)
            manual_knowledge = selected_conditions & {"known", "unknown"}
            # With mixed conditions (for example ✕ OR Weak), the automatic
            # source-level match must still include all of that source's words.
            knowledge = manual_knowledge if not (selected_conditions - {"known", "unknown"}) else set()
            drafts.extend(
                draft
                for source in kanji
                for draft in example_word_questions(
                    source,
                    important_only=payload.practice_type == "important_kanji_words",
                    knowledge=knowledge or None,
                )
            )
        else:
            drafts.extend(draft for source in kanji for draft in questions_from_kanji(source))
    if payload.mode == "starred_priority":
        random.shuffle(
            drafts
        )  # Fair ties across domains before ranking the combined pool.
        ranks = {"weak": 0, "learning": 1, "new": 2, "mastered": 3}
        priorities = {
            (p.item_type, p.item_id): ranks[p.status]
            for p in db.scalars(
                select(ItemProgress).where(ItemProgress.is_starred.is_(True))
            )
        }
        drafts.sort(
            key=lambda draft: priorities.get((draft.item_type, draft.item_id), 4)
        )
    else:
        random.shuffle(drafts)
    if payload.question_count is not None:
        drafts = drafts[: payload.question_count]
    if not drafts:
        raise InvalidOperation("No eligible questions for these filters")
    drafts = drafts[:2000]
    session = PracticeSession(
        practice_type=payload.practice_type,
        mode=payload.mode,
        total_questions=len(drafts),
    )
    db.add(session)
    db.flush()
    questions = [
        PracticeQuestion(session_id=session.id, position=index, **draft.__dict__)
        for index, draft in enumerate(drafts)
    ]
    db.add_all(questions)
    db.commit()
    lookup_cache.invalidate_progress()
    practice_session_cache.store(questions)
    return session, questions


def reveal_question(db: Session, session_id: int, question_id: int):
    cached = practice_session_cache.get(session_id, question_id)
    if cached is not None:
        persisted = db.execute(
            update(PracticeQuestion)
            .where(
                PracticeQuestion.id == question_id,
                PracticeQuestion.session_id == session_id,
                PracticeQuestion.answered_at.is_(None),
            )
            .values(
                revealed_at=func.coalesce(
                    PracticeQuestion.revealed_at, datetime.now(timezone.utc)
                )
            )
            .returning(PracticeQuestion.id)
        ).scalar_one_or_none()
        if persisted is None:
            raise Conflict("Question unavailable or already answered")
        db.commit()
        return cached
    question = db.scalar(
        select(PracticeQuestion)
        .where(
            PracticeQuestion.id == question_id,
            PracticeQuestion.session_id == session_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if question is None:
        raise NotFound("Question not found in session")
    if question.answered_at is not None:
        raise Conflict("Question already answered")
    if question.revealed_at is None:
        question.revealed_at = datetime.now(timezone.utc)
    db.commit()
    practice_session_cache.store([question])
    return question


def answer_practice(
    db: Session, session_id: int, question_id: int, result: str, note: str | None = None
):
    question = db.scalar(
        select(PracticeQuestion)
        .where(
            PracticeQuestion.id == question_id,
            PracticeQuestion.session_id == session_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if question is None:
        raise NotFound("Question not found in session")
    normalized_note = note.strip() if note and note.strip() else None
    if question.revealed_at is None and question.answered_at is None:
        raise Conflict("Reveal the answer before marking it")
    now = datetime.now(timezone.utc)
    claimed = db.execute(
        update(PracticeQuestion)
        .where(
            PracticeQuestion.id == question_id,
            PracticeQuestion.session_id == session_id,
            PracticeQuestion.answered_at.is_(None),
        )
        .values(answered_at=now, revealed_at=question.revealed_at)
        .returning(PracticeQuestion.id)
    ).scalar_one_or_none()
    if claimed is None:
        existing = db.scalar(
            select(PracticeAnswer).where(
                PracticeAnswer.question_id == question_id,
                PracticeAnswer.session_id == session_id,
            )
        )
        if (
            existing
            and existing.result == result
            and existing.wrong_note == normalized_note
        ):
            progress = db.scalar(
                select(ItemProgress).where(
                    ItemProgress.item_type == existing.item_type,
                    ItemProgress.item_id == existing.item_id,
                )
            )
            return progress, existing.answered_at
        raise Conflict("Question already answered")
    answer = PracticeAnswer(
        question_id=question_id,
        session_id=session_id,
        item_type=question.item_type,
        item_id=question.item_id,
        source_entry_id=question.source_entry_id,
        question_type=question.question_type,
        result=result,
        wrong_note=normalized_note,
    )
    db.add(answer)
    db.execute(
        update(PracticeSession)
        .where(PracticeSession.id == session_id)
        .values(
            correct_count=PracticeSession.correct_count
            + (1 if result == "correct" else 0),
            wrong_count=PracticeSession.wrong_count + (1 if result == "wrong" else 0),
            completed_at=case(
                (
                    PracticeSession.correct_count + PracticeSession.wrong_count + 1
                    >= PracticeSession.total_questions,
                    now,
                ),
                else_=PracticeSession.completed_at,
            ),
        )
    )
    progress = record_answer(db, question.item_type, question.item_id, result)
    db.commit()
    lookup_cache.invalidate_progress()
    return progress, now


def resume_session(db: Session, session_id: int):
    from app.models.practice import PracticeSession, PracticeQuestion as StoredQuestion

    if db.get(PracticeSession, session_id) is None:
        raise NotFound("Session not found")
    rows = db.scalars(
        select(StoredQuestion)
        .where(StoredQuestion.session_id == session_id)
        .order_by(StoredQuestion.position)
    ).all()
    return {
        "version": 1,
        "session_id": session_id,
        "questions": [
            {
                "question_id": q.id,
                "item_type": q.item_type,
                "question_type": q.question_type,
                "prompt": q.prompt,
                "revealed": q.revealed_at is not None,
                "answered": q.answered_at is not None,
            }
            for q in rows
        ],
    }


class PracticeService:
    """Owns durable session/reveal/answer operations and their commits."""

    resume = staticmethod(resume_session)
    start = staticmethod(start_practice)
    reveal = staticmethod(reveal_question)
    answer = staticmethod(answer_practice)
