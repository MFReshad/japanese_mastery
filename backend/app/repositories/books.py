from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.models.book import Book, Chapter
from app.models.item import VocabularySource, KanjiSource


def books_with_counts(db: Session):
    chapter_counts = (
        select(Chapter.book_id, func.count().label("count"))
        .group_by(Chapter.book_id)
        .subquery()
    )
    vocab_counts = (
        select(VocabularySource.book_id, func.count().label("count"))
        .group_by(VocabularySource.book_id)
        .subquery()
    )
    kanji_counts = (
        select(KanjiSource.book_id, func.count().label("count"))
        .group_by(KanjiSource.book_id)
        .subquery()
    )
    rows = db.execute(
        select(
            Book,
            func.coalesce(vocab_counts.c.count, 0),
            func.coalesce(kanji_counts.c.count, 0),
            func.coalesce(chapter_counts.c.count, 0),
        )
        .outerjoin(vocab_counts, vocab_counts.c.book_id == Book.id)
        .outerjoin(kanji_counts, kanji_counts.c.book_id == Book.id)
        .outerjoin(chapter_counts, chapter_counts.c.book_id == Book.id)
        .order_by(Book.title)
    )
    return list(rows)


def chapters_with_counts(db: Session, book_id: int | None = None):
    vocabulary = (
        select(VocabularySource.chapter_id, func.count().label("count"))
        .group_by(VocabularySource.chapter_id)
        .subquery()
    )
    kanji = (
        select(KanjiSource.chapter_id, func.count().label("count"))
        .group_by(KanjiSource.chapter_id)
        .subquery()
    )
    stmt = (
        select(
            Chapter,
            func.coalesce(vocabulary.c.count, 0),
            func.coalesce(kanji.c.count, 0),
        )
        .outerjoin(vocabulary, vocabulary.c.chapter_id == Chapter.id)
        .outerjoin(kanji, kanji.c.chapter_id == Chapter.id)
        .order_by(Chapter.book_id, Chapter.sort_order, Chapter.chapter_number)
    )
    if book_id is not None:
        stmt = stmt.where(Chapter.book_id == book_id)
    return list(db.execute(stmt))
