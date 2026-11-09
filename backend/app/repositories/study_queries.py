from __future__ import annotations
from app.errors import NotFound
from sqlalchemy import String, cast, func, select
from sqlalchemy.orm import Session, joinedload, selectinload
from app.models.book import Book, Chapter
from app.models.item import Kanji, KanjiExample, KanjiSource, VocabularySource


def _model(kind: str):
    if kind == "vocabulary":
        return VocabularySource
    if kind == "kanji":
        return KanjiSource
    raise NotFound("Study type not found")


def _key(source) -> str:
    return source.source_id or str(source.id)


def _chapter_order(chapter: Chapter):
    part = chapter.part
    part_key = (
        (0, 0, "")
        if part is None
        else (1, int(part), "")
        if str(part).isdecimal()
        else (2, 0, str(part))
    )
    return (part_key, chapter.sort_order, chapter.chapter_number, chapter.id)


def _next_chapter(db: Session, kind: str, book_id: int, chapter_id: int) -> dict | None:
    model = _model(kind)
    first_id = (
        select(model.id)
        .where(model.chapter_id == Chapter.id)
        .order_by(model.item_order, model.id)
        .limit(1)
        .correlate(Chapter)
        .scalar_subquery()
    )
    chapters_with_first = db.execute(
        select(Chapter, model.source_id, model.id)
        .outerjoin(model, model.id == first_id)
        .where(Chapter.book_id == book_id)
    ).all()
    chapters = sorted(chapters_with_first, key=lambda row: _chapter_order(row[0]))
    positions = {chapter.id: index for index, (chapter, _, _) in enumerate(chapters)}
    if chapter_id not in positions:
        raise NotFound("Chapter not found in book")
    for chapter, source_id, item_id in chapters[positions[chapter_id] + 1 :]:
        if item_id is not None:
            return {
                "chapter_id": chapter.id,
                "chapter_number": chapter.chapter_number,
                "chapter_title": chapter.title,
                "part": chapter.part,
                "first_source_id": source_id or str(item_id),
            }
    return None


def next_chapter(
    book_id: int, chapter_id: int, kind: str = "vocabulary", db: Session = None
):
    return _next_chapter(db, kind, book_id, chapter_id)


def study_items(
    book_id: int, chapter_id: int, kind: str = "vocabulary", db: Session = None
):
    if kind == "vocabulary":
        rows = db.execute(
            select(
                VocabularySource.id,
                VocabularySource.source_id,
                VocabularySource.item_order,
                VocabularySource.meaning_as_printed,
                VocabularySource.expression_as_printed,
                VocabularySource.reading_as_printed,
            )
            .where(
                VocabularySource.book_id == book_id,
                VocabularySource.chapter_id == chapter_id,
            )
            .order_by(VocabularySource.item_order, VocabularySource.id)
        ).all()
        result = [
            {
                "source_id": source_id or str(item_id),
                "source_entry_id": item_id,
                "item_order": order,
                "meaning": meaning,
                "expression": expression,
                "reading": reading,
            }
            for item_id, source_id, order, meaning, expression, reading in rows
        ]
    else:
        example_counts = (
            select(KanjiExample.kanji_source_id, func.count().label("count"))
            .join(KanjiSource)
            .where(KanjiSource.book_id == book_id, KanjiSource.chapter_id == chapter_id)
            .group_by(KanjiExample.kanji_source_id)
            .subquery()
        )
        rows = db.execute(
            select(
                KanjiSource.id,
                KanjiSource.source_id,
                KanjiSource.item_order,
                KanjiSource.meaning_as_printed,
                Kanji.character,
                KanjiSource.onyomi_as_printed,
                KanjiSource.kunyomi_as_printed,
                func.coalesce(example_counts.c.count, 0),
            )
            .join(Kanji, Kanji.id == KanjiSource.kanji_id)
            .outerjoin(
                example_counts, example_counts.c.kanji_source_id == KanjiSource.id
            )
            .where(KanjiSource.book_id == book_id, KanjiSource.chapter_id == chapter_id)
            .order_by(KanjiSource.item_order, KanjiSource.id)
        ).all()
        result = [
            {
                "source_id": source_id or str(item_id),
                "source_entry_id": item_id,
                "item_order": order,
                "meaning": meaning,
                "character": character,
                "onyomi": onyomi or [],
                "kunyomi": kunyomi or [],
                "example_count": example_count,
            }
            for item_id, source_id, order, meaning, character, onyomi, kunyomi, example_count in rows
        ]
    if not result:
        chapter = db.get(Chapter, chapter_id)
        if chapter is None or chapter.book_id != book_id:
            raise NotFound("Chapter not found in book")
    return result


def study_detail(kind: str, source_id: str, db: Session = None):
    model = _model(kind)
    stmt = (
        select(model, Book, Chapter)
        .join(Book, Book.id == model.book_id)
        .outerjoin(Chapter, Chapter.id == model.chapter_id)
    )
    if kind == "kanji":
        stmt = stmt.options(
            joinedload(KanjiSource.kanji), selectinload(KanjiSource.examples)
        )
    row = db.execute(stmt.where(model.source_id == source_id)).first()
    if row is None and source_id.isdecimal():
        row = db.execute(stmt.where(model.id == int(source_id))).first()
    if row is None:
        raise NotFound("Source occurrence not found")
    source, book, chapter = row
    if chapter:
        source_key = func.coalesce(model.source_id, cast(model.id, String))
        ordering = (model.item_order, model.id)
        navigation = (
            select(
                model.id.label("id"),
                func.lag(source_key)
                .over(order_by=ordering)
                .label("previous_source_id"),
                func.lead(source_key).over(order_by=ordering).label("next_source_id"),
                func.row_number().over(order_by=ordering).label("position"),
                func.count().over().label("lesson_count"),
            )
            .where(
                model.book_id == source.book_id, model.chapter_id == source.chapter_id
            )
            .subquery()
        )
        previous_source_id, next_source_id, position, lesson_count = db.execute(
            select(
                navigation.c.previous_source_id,
                navigation.c.next_source_id,
                navigation.c.position,
                navigation.c.lesson_count,
            ).where(navigation.c.id == source.id)
        ).one()
    else:
        previous_source_id, next_source_id, position, lesson_count = None, None, 1, 1
    common = {
        "source_id": _key(source),
        "source_entry_id": source.id,
        "book_id": source.book_id,
        "book_title": book.title,
        "chapter_id": source.chapter_id,
        "chapter_number": chapter.chapter_number if chapter else None,
        "chapter_title": chapter.title if chapter else None,
        "part": (
            source.part
            if kind == "kanji" and source.part is not None
            else chapter.part
            if chapter
            else None
        ),
        "item_order": source.item_order,
        "meaning_as_printed": source.meaning_as_printed,
        "meanings_as_printed": source.meanings_as_printed or [],
        "notes": source.notes,
        "source_page": source.source_page_as_imported
        if source.source_page_as_imported is not None
        else source.source_page,
        "previous_source_id": previous_source_id,
        "next_source_id": next_source_id,
        "next_chapter": _next_chapter(db, kind, source.book_id, source.chapter_id)
        if chapter
        else None,
        "position": position,
        "lesson_count": lesson_count,
    }
    if kind == "vocabulary":
        return {
            **common,
            "expression_as_printed": source.expression_as_printed,
            "reading_as_printed": source.reading_as_printed,
        }
    return {
        **common,
        "character": source.kanji.character,
        "entry_number_as_printed": source.entry_number_as_printed,
        "onyomi_as_printed": source.onyomi_as_printed or [],
        "kunyomi_as_printed": source.kunyomi_as_printed or [],
        "stroke_count_as_printed": source.stroke_count_as_printed,
        "examples": [
            {
                "id": example.id,
                "word": example.word,
                "reading": example.reading,
                "meaning": example.meaning,
                "is_important": example.is_important,
            }
            for example in sorted(source.examples, key=lambda e: (e.sort_order, e.id))
        ],
        "uncertain": source.uncertain,
        "source_book_page": source.source_book_page,
    }
