from app.errors import NotFound, InvalidOperation
from sqlalchemy import select
from sqlalchemy.orm import Session
from uuid import uuid4

from app.models.book import Chapter
from app.models.item import VocabularySource, SourceSuppression
from app.repositories.items import get_or_create_vocabulary


def chapter_sources(db: Session, chapter_id: int) -> list[VocabularySource]:
    if (
        db.scalar(select(Chapter).where(Chapter.id == chapter_id).with_for_update())
        is None
    ):
        raise NotFound("Chapter not found")
    return list(
        db.scalars(
            select(VocabularySource)
            .where(VocabularySource.chapter_id == chapter_id)
            .order_by(VocabularySource.item_order, VocabularySource.id)
        )
    )


def save_order(
    db: Session, chapter_id: int, source_ids: list[int]
) -> list[VocabularySource]:
    rows = chapter_sources(db, chapter_id)
    if len(source_ids) != len(rows) or set(source_ids) != {row.id for row in rows}:
        raise InvalidOperation("Order must contain every chapter source exactly once")
    by_id = {row.id: row for row in rows}
    offset = max((row.item_order for row in rows), default=0) + len(rows) + 1
    for position, row in enumerate(rows):
        row.item_order = offset + position
    db.flush()
    for position, source_id in enumerate(source_ids, 1):
        row = by_id[source_id]
        row.item_order = position
        row.manually_reordered = (
            row.original_item_order is not None and row.original_item_order != position
        )
    db.flush()
    return [by_id[source_id] for source_id in source_ids]


def insert_source(
    db: Session,
    chapter_id: int,
    expression: str,
    reading: str,
    meaning: str,
    position: int,
) -> VocabularySource:
    chapter = db.get(Chapter, chapter_id)
    if chapter is None:
        raise NotFound("Chapter not found")
    if not all(value.strip() for value in (expression, reading, meaning)):
        raise InvalidOperation("Expression, reading, and meaning are required")
    rows = chapter_sources(db, chapter_id)
    vocab = get_or_create_vocabulary(db, expression, reading)
    source = VocabularySource(
        source_id=f"manual_vocab_{uuid4().hex}",
        vocabulary_id=vocab.id,
        book_id=chapter.book_id,
        chapter_id=chapter_id,
        item_order=max((row.item_order for row in rows), default=0) + 1,
        original_item_order=None,
        manually_added=True,
        expression_as_printed=expression.strip(),
        reading_as_printed=reading.strip(),
        meaning_as_printed=meaning.strip(),
        meanings_as_printed=[meaning.strip()],
    )
    db.add(source)
    db.flush()
    rows.insert(max(0, min(position - 1, len(rows))), source)
    save_order(db, chapter_id, [row.id for row in rows])
    return source


def remove_source(db: Session, source_id: int) -> None:
    source = db.get(VocabularySource, source_id)
    if source is None:
        raise NotFound("Vocabulary source not found")
    chapter_id = source.chapter_id
    if chapter_id is not None:
        db.scalar(select(Chapter).where(Chapter.id == chapter_id).with_for_update())
    if source.source_id and not source.manually_added:
        db.merge(SourceSuppression(item_type="vocabulary", source_id=source.source_id))
    db.delete(source)
    db.flush()
    if chapter_id is not None:
        save_order(db, chapter_id, [row.id for row in chapter_sources(db, chapter_id)])


def reset_order(db: Session, chapter_id: int) -> list[VocabularySource]:
    rows = chapter_sources(db, chapter_id)
    imported = sorted(
        (row for row in rows if row.original_item_order is not None),
        key=lambda row: (row.original_item_order, row.id),
    )
    manual = [row for row in rows if row.original_item_order is None]
    for row in manual:
        imported.insert(min(max(row.item_order - 1, 0), len(imported)), row)
    return save_order(db, chapter_id, [row.id for row in imported])
