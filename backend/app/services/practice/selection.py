from __future__ import annotations


from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.repositories.parts import part_matches
from app.models.book import Chapter
from app.models.item import KanjiSource, VocabularySource
from app.models.practice import ItemProgress
from app.schemas.practice import PracticeStartRequest


def _eligible_sources(db: Session, payload: PracticeStartRequest, item_type: str):
    model = VocabularySource if item_type == "vocabulary" else KanjiSource
    item_id = model.vocabulary_id if item_type == "vocabulary" else model.kanji_id
    stmt = select(model)
    if item_type == "kanji":
        if payload.question_count is None:
            stmt = stmt.options(
                selectinload(KanjiSource.kanji), selectinload(KanjiSource.examples)
            )
        else:
            stmt = stmt.options(
                joinedload(KanjiSource.kanji), joinedload(KanjiSource.examples)
            )
    if payload.book_ids:
        stmt = stmt.where(model.book_id.in_(payload.book_ids))
    if payload.chapter_ids:
        stmt = stmt.where(model.chapter_id.in_(payload.chapter_ids))
    if payload.source_entry_ids:
        stmt = stmt.where(model.id.in_(payload.source_entry_ids))
    if payload.parts:
        if item_type == "vocabulary":
            stmt = stmt.join(Chapter, Chapter.id == model.chapter_id).where(
                part_matches(Chapter.part, payload.parts)
            )
        else:
            stmt = stmt.where(part_matches(model.part, payload.parts))
    if payload.order_start is not None:
        stmt = stmt.where(model.item_order >= payload.order_start)
    if payload.order_end is not None:
        stmt = stmt.where(model.item_order <= payload.order_end)
    if payload.mode != "random":
        stmt = stmt.outerjoin(
            ItemProgress,
            and_(ItemProgress.item_type == item_type, ItemProgress.item_id == item_id),
        )
        if payload.mode == "never_practiced":
            stmt = stmt.where(
                or_(ItemProgress.id.is_(None), ItemProgress.attempts == 0)
            )
        elif payload.mode == "weak":
            stmt = stmt.where(ItemProgress.status == "weak")
        elif payload.mode == "wrong":
            stmt = stmt.where(
                or_(ItemProgress.status == "weak", ItemProgress.last_result == "wrong")
            )
        elif payload.mode == "mastery_review":
            stmt = stmt.where(
                or_(
                    ItemProgress.id.is_(None),
                    ItemProgress.attempts == 0,
                    ItemProgress.status != "mastered",
                )
            )
        elif payload.mode in ("starred", "starred_priority"):
            stmt = stmt.where(ItemProgress.is_starred.is_(True))
    if payload.question_count is not None:
        if payload.mode == "starred_priority":
            stmt = stmt.order_by(
                case(
                    (ItemProgress.status == "weak", 0),
                    (ItemProgress.status == "learning", 1),
                    (ItemProgress.status == "new", 2),
                    (ItemProgress.status == "mastered", 3),
                    else_=4,
                ),
                model.book_id,
                model.chapter_id,
                model.item_order,
                model.id,
            )
        else:
            stmt = stmt.order_by(func.random())
        stmt = stmt.limit(payload.question_count)
    else:
        if payload.mode == "starred_priority":
            stmt = stmt.order_by(
                case(
                    (ItemProgress.status == "weak", 0),
                    (ItemProgress.status == "learning", 1),
                    (ItemProgress.status == "new", 2),
                    (ItemProgress.status == "mastered", 3),
                    else_=4,
                ),
                model.book_id,
                model.chapter_id,
                model.item_order,
                model.id,
            )
        else:
            stmt = stmt.order_by(
                model.book_id, model.chapter_id, model.item_order, model.id
            )
    if payload.question_count is None:
        stmt = stmt.limit(2000)
    return db.execute(stmt).unique().scalars().all()
