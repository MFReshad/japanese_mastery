from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.errors import InvalidOperation
from app.models.book import Book, Chapter
from app.models.item import Kanji, KanjiExample, KanjiSource, VocabularySource
from app.models.practice import ItemProgress
from app.repositories.practice import get_or_create_progress
from app.services.lookup_cache import lookup_cache

router = APIRouter(prefix="/review")


class BulkReviewUpdate(BaseModel):
    kind: Literal["vocabulary", "kanji_examples"]
    ids: list[int] = Field(min_length=1, max_length=2000)
    action: Literal["known", "unknown", "clear_knowledge", "important", "not_important"]


@router.get("/items")
def review_items(
    kind: Literal["vocabulary", "kanji_examples"] = "vocabulary",
    book_id: int | None = None,
    chapter_id: int | None = None,
    knowledge: Literal["all", "known", "unknown", "unmarked"] = "all",
    practice_status: Literal["all", "new", "learning", "weak", "mastered"] = "all",
    importance: Literal["all", "important", "not_important"] = "all",
    search: str = "",
    db: Session = Depends(get_db),
):
    if kind == "vocabulary":
        model, progress_id = VocabularySource, VocabularySource.vocabulary_id
        stmt = select(
            model.id, model.book_id, model.chapter_id, model.expression_as_printed,
            model.reading_as_printed, model.meaning_as_printed, model.knowledge_status,
            Chapter.chapter_number, Chapter.title, Book.title,
            case((func.coalesce(ItemProgress.attempts, 0) == 0, "new"), else_=ItemProgress.status),
            func.coalesce(ItemProgress.is_starred, False),
        ).join(Book, Book.id == model.book_id).outerjoin(Chapter, Chapter.id == model.chapter_id)
        term = search.strip()
        if term:
            pattern = f"%{term}%"
            stmt = stmt.where(or_(model.expression_as_printed.ilike(pattern), model.reading_as_printed.ilike(pattern), model.meaning_as_printed.ilike(pattern)))
        knowledge_col, important_col = model.knowledge_status, ItemProgress.is_starred
    else:
        model, progress_id = KanjiExample, KanjiSource.kanji_id
        stmt = select(
            model.id, KanjiSource.book_id, KanjiSource.chapter_id, model.word,
            model.reading, model.meaning, model.knowledge_status,
            Chapter.chapter_number, Chapter.title, Book.title,
            case((func.coalesce(ItemProgress.attempts, 0) == 0, "new"), else_=ItemProgress.status),
            model.is_important,
        ).join(KanjiSource, KanjiSource.id == model.kanji_source_id).join(Kanji, Kanji.id == KanjiSource.kanji_id).join(Book, Book.id == KanjiSource.book_id).outerjoin(Chapter, Chapter.id == KanjiSource.chapter_id)
        term = search.strip()
        if term:
            pattern = f"%{term}%"
            stmt = stmt.where(or_(model.word.ilike(pattern), model.reading.ilike(pattern), model.meaning.ilike(pattern), Kanji.character.ilike(pattern)))
        knowledge_col, important_col = model.knowledge_status, model.is_important
    stmt = stmt.outerjoin(ItemProgress, and_(ItemProgress.item_type == ("vocabulary" if kind == "vocabulary" else "kanji"), ItemProgress.item_id == progress_id)).where(Book.is_active.is_(True))
    source_book = VocabularySource.book_id if kind == "vocabulary" else KanjiSource.book_id
    source_chapter = VocabularySource.chapter_id if kind == "vocabulary" else KanjiSource.chapter_id
    if book_id is not None: stmt = stmt.where(source_book == book_id)
    if chapter_id is not None: stmt = stmt.where(source_chapter == chapter_id)
    if knowledge == "unmarked": stmt = stmt.where(knowledge_col.is_(None))
    elif knowledge != "all": stmt = stmt.where(knowledge_col == knowledge)
    if practice_status == "new": stmt = stmt.where(or_(ItemProgress.id.is_(None), ItemProgress.attempts == 0))
    elif practice_status != "all": stmt = stmt.where(ItemProgress.status == practice_status, ItemProgress.attempts > 0)
    if importance == "important": stmt = stmt.where(important_col.is_(True))
    elif importance == "not_important": stmt = stmt.where(or_(important_col.is_(False), important_col.is_(None)))
    rows = db.execute(stmt.order_by(source_book, source_chapter, model.id).limit(2000)).all()
    return {"items": [{"id": row[0], "book_id": row[1], "chapter_id": row[2], "word": row[3], "reading": row[4], "meaning": row[5], "knowledge_status": row[6], "chapter_number": row[7], "chapter_title": row[8], "book_title": row[9], "practice_status": row[10], "is_important": bool(row[11])} for row in rows], "limited": len(rows) == 2000}


@router.patch("/items/bulk")
def bulk_review_update(payload: BulkReviewUpdate, db: Session = Depends(get_db)):
    if payload.kind == "vocabulary":
        rows = db.scalars(select(VocabularySource).where(VocabularySource.id.in_(payload.ids))).all()
    else:
        rows = db.scalars(select(KanjiExample).where(KanjiExample.id.in_(payload.ids))).all()
    if payload.action in ("known", "unknown", "clear_knowledge"):
        value = None if payload.action == "clear_knowledge" else payload.action
        for row in rows: row.knowledge_status = value
    elif payload.kind == "kanji_examples":
        for row in rows: row.is_important = payload.action == "important"
    elif payload.kind == "vocabulary":
        for vocabulary_id in {row.vocabulary_id for row in rows}:
            get_or_create_progress(db, "vocabulary", vocabulary_id).is_starred = payload.action == "important"
    else:
        raise InvalidOperation("Unsupported bulk action")
    db.commit()
    lookup_cache.invalidate_progress()
    return {"updated": len(rows)}
