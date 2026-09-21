from __future__ import annotations

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload
from uuid import uuid4

from app.models.book import Chapter
from app.models.item import Kanji, KanjiExample, KanjiSource, Vocabulary, VocabularySource


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


def create_vocabulary_source(db: Session, data) -> VocabularySource:
    vocab = get_or_create_vocabulary(db, data.expression, data.reading)
    source = db.scalar(
        select(VocabularySource).where(
            VocabularySource.vocabulary_id == vocab.id,
            VocabularySource.book_id == data.book_id,
            VocabularySource.chapter_id == data.chapter_id,
            VocabularySource.item_order == data.item_order,
        )
    )
    if source:
        source.expression_as_printed = data.expression
        source.reading_as_printed = data.reading
        source.meaning_as_printed = data.meaning
        source.notes = data.notes
        source.source_file = data.source_file
        source.source_page = data.source_page
        source.source_section = data.source_section
        return source
    source = VocabularySource(
        source_id=f"manual_vocab_{uuid4().hex}",
        vocabulary_id=vocab.id,
        book_id=data.book_id,
        chapter_id=data.chapter_id,
        item_order=data.item_order,
        manually_added=True,
        expression_as_printed=data.expression,
        reading_as_printed=data.reading,
        meaning_as_printed=data.meaning,
        notes=data.notes,
        source_file=data.source_file,
        source_page=data.source_page,
        source_section=data.source_section,
    )
    db.add(source)
    db.flush()
    return source


def create_kanji_source(db: Session, data) -> KanjiSource:
    kanji = get_or_create_kanji(db, data.character)
    source = db.scalar(
        select(KanjiSource).where(
            KanjiSource.kanji_id == kanji.id,
            KanjiSource.book_id == data.book_id,
            KanjiSource.chapter_id == data.chapter_id,
            KanjiSource.item_order == data.item_order,
        )
    )
    if not source:
        source = KanjiSource(
            kanji_id=kanji.id,
            book_id=data.book_id,
            chapter_id=data.chapter_id,
            item_order=data.item_order,
            meaning_as_printed=data.meaning,
            onyomi=data.onyomi,
            kunyomi=data.kunyomi,
            notes=data.notes,
            source_file=data.source_file,
            source_page=data.source_page,
            source_section=data.source_section,
        )
        db.add(source)
        db.flush()
    else:
        source.meaning_as_printed = data.meaning
        source.onyomi = data.onyomi
        source.kunyomi = data.kunyomi
        source.notes = data.notes
        source.source_file = data.source_file
        source.source_page = data.source_page
        source.source_section = data.source_section
    source.examples.clear()
    for example in data.examples:
        source.examples.append(
            KanjiExample(
                word=example.word,
                reading=example.reading,
                meaning=example.meaning,
                sort_order=example.sort_order,
            )
        )
    return source


def filter_vocabulary_sources(
    book_ids: list[int] | None = None,
    chapter_ids: list[int] | None = None,
    parts: list[int | str] | None = None,
    order_start: int | None = None,
    order_end: int | None = None,
) -> Select:
    stmt = select(VocabularySource).options(selectinload(VocabularySource.vocabulary)).order_by(VocabularySource.item_order)
    if book_ids:
        stmt = stmt.where(VocabularySource.book_id.in_(book_ids))
    if chapter_ids:
        stmt = stmt.where(VocabularySource.chapter_id.in_(chapter_ids))
    if parts:
        stmt = stmt.join(Chapter, VocabularySource.chapter_id == Chapter.id).where(Chapter.part.in_(parts))
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
    stmt = select(KanjiSource).options(selectinload(KanjiSource.kanji), selectinload(KanjiSource.examples)).order_by(KanjiSource.item_order)
    if book_ids:
        stmt = stmt.where(KanjiSource.book_id.in_(book_ids))
    if chapter_ids:
        stmt = stmt.where(KanjiSource.chapter_id.in_(chapter_ids))
    if parts:
        stmt = stmt.where(KanjiSource.part.in_(parts))
    if order_start is not None:
        stmt = stmt.where(KanjiSource.item_order >= order_start)
    if order_end is not None:
        stmt = stmt.where(KanjiSource.item_order <= order_end)
    return stmt


def book_counts(db: Session) -> dict[int, tuple[int, int]]:
    rows = {}
    for book_id, count in db.execute(select(VocabularySource.book_id, func.count()).group_by(VocabularySource.book_id)):
        rows.setdefault(book_id, [0, 0])[0] = count
    for book_id, count in db.execute(select(KanjiSource.book_id, func.count()).group_by(KanjiSource.book_id)):
        rows.setdefault(book_id, [0, 0])[1] = count
    return {key: (value[0], value[1]) for key, value in rows.items()}
