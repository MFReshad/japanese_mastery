from __future__ import annotations

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from app.repositories.parts import part_matches
from app.models.book import Chapter
from app.models.item import Kanji, KanjiSource, Vocabulary, VocabularySource


def normalize_text(value: str) -> str:
    return " ".join(value.strip().split())


def get_or_create_vocabulary(db: Session, expression: str, reading: str) -> Vocabulary:
    normalized_expression = normalize_text(expression)
    normalized_reading = normalize_text(reading)
    item = db.scalar(
        select(Vocabulary).where(
            Vocabulary.normalized_expression == normalized_expression,
            Vocabulary.normalized_reading == normalized_reading,
        )
    )
    if item:
        return item
    item = Vocabulary(
        expression=expression.strip(),
        reading=reading.strip(),
        normalized_expression=normalized_expression,
        normalized_reading=normalized_reading,
    )
    db.add(item)
    db.flush()
    return item


def get_or_create_kanji(db: Session, character: str) -> Kanji:
    character = character.strip()
    item = db.scalar(select(Kanji).where(Kanji.character == character))
    if item:
        return item
    item = Kanji(character=character)
    db.add(item)
    db.flush()
    return item


def filter_vocabulary_sources(
    book_ids: list[int] | None = None,
    chapter_ids: list[int] | None = None,
    parts: list[int | str] | None = None,
    order_start: int | None = None,
    order_end: int | None = None,
) -> Select:
    stmt = (
        select(VocabularySource)
        .options(selectinload(VocabularySource.vocabulary))
        .order_by(VocabularySource.item_order)
    )
    if book_ids:
        stmt = stmt.where(VocabularySource.book_id.in_(book_ids))
    if chapter_ids:
        stmt = stmt.where(VocabularySource.chapter_id.in_(chapter_ids))
    if parts:
        stmt = stmt.join(Chapter, VocabularySource.chapter_id == Chapter.id).where(
            part_matches(Chapter.part, parts)
        )
    if order_start is not None:
        stmt = stmt.where(VocabularySource.item_order >= order_start)
    if order_end is not None:
        stmt = stmt.where(VocabularySource.item_order <= order_end)
    return stmt


def filter_kanji_sources(
    book_ids: list[int] | None = None,
    chapter_ids: list[int] | None = None,
    parts: list[int | str] | None = None,
    order_start: int | None = None,
    order_end: int | None = None,
) -> Select:
    stmt = (
        select(KanjiSource)
        .options(selectinload(KanjiSource.kanji), selectinload(KanjiSource.examples))
        .order_by(KanjiSource.item_order)
    )
    if book_ids:
        stmt = stmt.where(KanjiSource.book_id.in_(book_ids))
    if chapter_ids:
        stmt = stmt.where(KanjiSource.chapter_id.in_(chapter_ids))
    if parts:
        stmt = stmt.where(part_matches(KanjiSource.part, parts))
    if order_start is not None:
        stmt = stmt.where(KanjiSource.item_order >= order_start)
    if order_end is not None:
        stmt = stmt.where(KanjiSource.item_order <= order_end)
    return stmt


def book_counts(db: Session) -> dict[int, tuple[int, int]]:
    rows = {}
    for book_id, count in db.execute(
        select(VocabularySource.book_id, func.count()).group_by(
            VocabularySource.book_id
        )
    ):
        rows.setdefault(book_id, [0, 0])[0] = count
    for book_id, count in db.execute(
        select(KanjiSource.book_id, func.count()).group_by(KanjiSource.book_id)
    ):
        rows.setdefault(book_id, [0, 0])[1] = count
    return {key: (value[0], value[1]) for key, value in rows.items()}
