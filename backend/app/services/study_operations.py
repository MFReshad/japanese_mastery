from __future__ import annotations
from app.repositories import study_queries as queries

from sqlalchemy.orm import Session

from app.models.book import Chapter


def _model(kind: str):
    return queries._model(kind)


def _key(source) -> str:
    return queries._key(source)


def _chapter_order(chapter: Chapter):
    return queries._chapter_order(chapter)


def _next_chapter(db: Session, kind: str, book_id: int, chapter_id: int) -> dict | None:
    return queries._next_chapter(db, kind, book_id, chapter_id)


def next_chapter(
    book_id: int, chapter_id: int, kind: str = "vocabulary", db: Session = None
):
    return queries.next_chapter(book_id, chapter_id, kind, db)


def study_items(
    book_id: int, chapter_id: int, kind: str = "vocabulary", db: Session = None
):
    return queries.study_items(book_id, chapter_id, kind, db)


def study_detail(kind: str, source_id: str, db: Session = None):
    return queries.study_detail(kind, source_id, db)
