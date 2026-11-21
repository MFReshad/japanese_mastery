from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import NotFound
from app.models.book import Book, Chapter
from app.models.item import Kanji, KanjiSource, VocabularySource
from app.models.practice import PracticeAnswer, PracticeQuestion, PracticeSession


def _session_row(session: PracticeSession) -> dict:
    answered = session.correct_count + session.wrong_count
    return {
        "session_id": session.id,
        "started_at": session.started_at,
        "completed_at": session.completed_at,
        "practice_type": session.practice_type,
        "mode": session.mode,
        "total_questions": session.total_questions,
        "answered_count": answered,
        "correct_count": session.correct_count,
        "wrong_count": session.wrong_count,
        "filter_snapshot": session.filter_snapshot,
    }


def list_history(db: Session, limit: int, offset: int) -> dict:
    total = db.scalar(select(func.count()).select_from(PracticeSession)) or 0
    sessions = db.scalars(
        select(PracticeSession)
        .order_by(PracticeSession.started_at.desc(), PracticeSession.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return {"sessions": [_session_row(row) for row in sessions], "total": total, "limit": limit, "offset": offset}


def _source_map(db: Session, model, source_ids: set[int]) -> dict[int, dict]:
    if not source_ids:
        return {}
    columns = [model, Book, Chapter]
    statement = (
        select(*columns)
        .join(Book, Book.id == model.book_id)
        .outerjoin(Chapter, Chapter.id == model.chapter_id)
        .where(model.id.in_(source_ids))
    )
    if model is KanjiSource:
        statement = statement.add_columns(Kanji.character).join(Kanji, Kanji.id == KanjiSource.kanji_id)
    rows = db.execute(statement).all()
    result = {}
    for row in rows:
        source, book, chapter = row[:3]
        result[source.id] = {
            "book_id": book.id,
            "book_title": book.title,
            "chapter_id": chapter.id if chapter else None,
            "chapter_number": chapter.chapter_number if chapter else None,
            "chapter_title": chapter.title if chapter else None,
            "study_source_id": source.source_id,
            "main_kanji": row[3] if model is KanjiSource else None,
        }
    return result


def history_detail(db: Session, session_id: int) -> dict:
    session = db.get(PracticeSession, session_id)
    if session is None:
        raise NotFound("Practice session not found")
    rows = db.execute(
        select(PracticeQuestion, PracticeAnswer)
        .outerjoin(PracticeAnswer, PracticeAnswer.question_id == PracticeQuestion.id)
        .where(PracticeQuestion.session_id == session_id)
        .order_by(PracticeQuestion.position)
    ).all()
    vocabulary_ids = {question.source_entry_id for question, _ in rows if question.item_type == "vocabulary"}
    kanji_ids = {question.source_entry_id for question, _ in rows if question.item_type in ("kanji", "kanji_example")}
    vocabulary = _source_map(db, VocabularySource, vocabulary_ids)
    kanji = _source_map(db, KanjiSource, kanji_ids)
    answers = []
    for question, answer in rows:
        source = vocabulary.get(question.source_entry_id) if question.item_type == "vocabulary" else kanji.get(question.source_entry_id)
        answers.append({
            "question_id": question.id,
            "position": question.position,
            "item_type": question.item_type,
            "question_type": question.question_type,
            "prompt": question.prompt,
            "answer_primary": question.answer_primary,
            "answer_secondary": question.answer_secondary,
            "result": answer.result if answer else None,
            "wrong_note": answer.wrong_note if answer else None,
            "answered_at": answer.answered_at if answer else None,
            "book_id": source["book_id"] if source else None,
            "book_title": source["book_title"] if source else None,
            "chapter_id": source["chapter_id"] if source else None,
            "chapter_number": source["chapter_number"] if source else None,
            "chapter_title": source["chapter_title"] if source else None,
            "study_kind": "vocabulary" if question.item_type == "vocabulary" else "kanji" if source else None,
            "study_source_id": source["study_source_id"] if source else None,
            "main_kanji": source["main_kanji"] if source else None,
        })
    return {"session": _session_row(session), "answers": answers}
