from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.book import Book, Chapter
from app.models.item import KanjiSource, VocabularySource
from app.schemas.books import BookCreate, BookRead, BookUpdate, ChapterCreate, ChapterRead, ChapterUpdate
from app.services.lookup_cache import lookup_cache

router = APIRouter()


@router.get("/books", response_model=list[BookRead])
def list_books(db: Session = Depends(get_db)):
    def load() -> list[BookRead]:
        vocab_counts = select(VocabularySource.book_id, func.count().label("count")).group_by(VocabularySource.book_id).subquery()
        kanji_counts = select(KanjiSource.book_id, func.count().label("count")).group_by(KanjiSource.book_id).subquery()
        rows = db.execute(select(Book, func.coalesce(vocab_counts.c.count, 0), func.coalesce(kanji_counts.c.count, 0))
            .outerjoin(vocab_counts, vocab_counts.c.book_id == Book.id)
            .outerjoin(kanji_counts, kanji_counts.c.book_id == Book.id).order_by(Book.title))
        return [
            BookRead.model_validate(book).model_copy(update={"vocabulary_count": vocab_count, "kanji_count": kanji_count})
            for book, vocab_count, kanji_count in rows
        ]

    return lookup_cache.get_books(load)


@router.post("/books", response_model=BookRead)
def create_book(payload: BookCreate, db: Session = Depends(get_db)):
    book = Book(**payload.model_dump())
    db.add(book)
    db.commit()
    db.refresh(book)
    lookup_cache.invalidate_books()
    return BookRead.model_validate(book)


@router.patch("/books/{book_id}", response_model=BookRead)
def update_book(book_id: int, payload: BookUpdate, db: Session = Depends(get_db)):
    book = db.get(Book, book_id)
    if not book:
        raise HTTPException(404, "Book not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(book, key, value)
    db.commit()
    db.refresh(book)
    lookup_cache.invalidate_books()
    return BookRead.model_validate(book)


@router.delete("/books/{book_id}")
def delete_book(book_id: int, db: Session = Depends(get_db)):
    book = db.get(Book, book_id)
    if not book:
        raise HTTPException(404, "Book not found")
    db.delete(book)
    db.commit()
    lookup_cache.invalidate_books()
    lookup_cache.invalidate_chapters(book_id)
    return {"deleted": True}


@router.get("/chapters", response_model=list[ChapterRead])
def list_chapters(book_id: int | None = None, db: Session = Depends(get_db)):
    def load() -> list[ChapterRead]:
        stmt = select(Chapter).order_by(Chapter.book_id, Chapter.sort_order, Chapter.chapter_number)
        if book_id:
            stmt = stmt.where(Chapter.book_id == book_id)
        return [ChapterRead.model_validate(chapter) for chapter in db.scalars(stmt).all()]

    if book_id:
        return lookup_cache.get_chapters_by_book(book_id, load)
    return lookup_cache.get_chapters(load)


@router.post("/chapters", response_model=ChapterRead)
def create_chapter(payload: ChapterCreate, db: Session = Depends(get_db)):
    chapter = Chapter(**payload.model_dump())
    db.add(chapter)
    db.commit()
    db.refresh(chapter)
    lookup_cache.invalidate_chapters(chapter.book_id)
    return chapter


@router.patch("/chapters/{chapter_id}", response_model=ChapterRead)
def update_chapter(chapter_id: int, payload: ChapterUpdate, db: Session = Depends(get_db)):
    chapter = db.get(Chapter, chapter_id)
    if not chapter:
        raise HTTPException(404, "Chapter not found")
    old_book_id = chapter.book_id
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(chapter, key, value)
    db.commit()
    db.refresh(chapter)
    lookup_cache.invalidate_chapters(old_book_id)
    if chapter.book_id != old_book_id:
        lookup_cache.invalidate_chapters(chapter.book_id)
    return chapter
