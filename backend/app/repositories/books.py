from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.models.book import Book
from app.models.item import VocabularySource, KanjiSource


def books_with_counts(db: Session):
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
        )
        .outerjoin(vocab_counts, vocab_counts.c.book_id == Book.id)
        .outerjoin(kanji_counts, kanji_counts.c.book_id == Book.id)
        .order_by(Book.title)
    )
    return list(rows)
