from __future__ import annotations
from app.repositories.books import books_with_counts
from app.errors import NotFound, Conflict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.book import Book, Chapter
from app.models.item import KanjiSource, VocabularySource
from app.schemas.books import (
    BookCreate,
    BookRead,
    BookUpdate,
    ChapterCreate,
    ChapterRead,
    ChapterUpdate,
)
from app.services.lookup_cache import lookup_cache


def list_books(db: Session = None):
    def load():
        return [
            BookRead.model_validate(book).model_copy(
                update={
                    "vocabulary_count": vocabulary_count,
                    "kanji_count": kanji_count,
                }
            )
            for book, vocabulary_count, kanji_count in books_with_counts(db)
        ]

    return lookup_cache.get_books(load)


def create_book(payload: BookCreate, db: Session = None):
    book = Book(**payload.model_dump())
    db.add(book)
    db.commit()
    lookup_cache.invalidate_progress()
    db.refresh(book)
    lookup_cache.invalidate_books()
    return BookRead.model_validate(book)


def update_book(book_id: int, payload: BookUpdate, db: Session = None):
    book = db.get(Book, book_id)
    if not book:
        raise NotFound("Book not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(book, key, value)
    db.commit()
    lookup_cache.invalidate_progress()
    db.refresh(book)
    lookup_cache.invalidate_books()
    return BookRead.model_validate(book)


def delete_book(book_id: int, db: Session = None):
    book = db.get(Book, book_id)
    if not book:
        raise NotFound("Book not found")
    db.delete(book)
    db.commit()
    lookup_cache.invalidate_progress()
    lookup_cache.invalidate_books()
    lookup_cache.invalidate_chapters(book_id)
    return {"deleted": True}


def list_chapters(book_id: int | None = None, db: Session = None):
    def load() -> list[ChapterRead]:
        stmt = select(Chapter).order_by(
            Chapter.book_id, Chapter.sort_order, Chapter.chapter_number
        )
        if book_id:
            stmt = stmt.where(Chapter.book_id == book_id)
        return [
            ChapterRead.model_validate(chapter) for chapter in db.scalars(stmt).all()
        ]

    if book_id:
        return lookup_cache.get_chapters_by_book(book_id, load)
    return lookup_cache.get_chapters(load)


def create_chapter(payload: ChapterCreate, db: Session = None):
    chapter = Chapter(**payload.model_dump())
    db.add(chapter)
    db.commit()
    lookup_cache.invalidate_progress()
    db.refresh(chapter)
    lookup_cache.invalidate_chapters(chapter.book_id)
    return chapter


def update_chapter(chapter_id: int, payload: ChapterUpdate, db: Session = None):
    chapter = db.scalar(
        select(Chapter).where(Chapter.id == chapter_id).with_for_update()
    )
    if not chapter:
        raise NotFound("Chapter not found")
    old_book_id = chapter.book_id
    if payload.book_id is not None and payload.book_id != old_book_id:
        if db.scalar(
            select(VocabularySource.id)
            .where(VocabularySource.chapter_id == chapter_id)
            .limit(1)
        ) or db.scalar(
            select(KanjiSource.id).where(KanjiSource.chapter_id == chapter_id).limit(1)
        ):
            raise Conflict("Cannot move a populated chapter to another book")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(chapter, key, value)
    db.commit()
    lookup_cache.invalidate_progress()
    db.refresh(chapter)
    lookup_cache.invalidate_chapters(old_book_id)
    if chapter.book_id != old_book_id:
        lookup_cache.invalidate_chapters(chapter.book_id)
    return chapter
