from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.book import Book, Chapter
from app.models.item import KanjiSource, VocabularySource
from app.schemas.books import BookCreate, BookRead, BookUpdate, ChapterCreate, ChapterRead, ChapterUpdate

router = APIRouter()


@router.get("/books", response_model=list[BookRead])
def list_books(db: Session = Depends(get_db)):
    vocab_counts = select(VocabularySource.book_id, func.count().label("count")).group_by(VocabularySource.book_id).subquery()
    kanji_counts = select(KanjiSource.book_id, func.count().label("count")).group_by(KanjiSource.book_id).subquery()
    rows = db.execute(select(Book, func.coalesce(vocab_counts.c.count, 0), func.coalesce(kanji_counts.c.count, 0))
        .outerjoin(vocab_counts, vocab_counts.c.book_id == Book.id)
        .outerjoin(kanji_counts, kanji_counts.c.book_id == Book.id).order_by(Book.title))
    return [
        BookRead.model_validate(book).model_copy(update={"vocabulary_count": vocab_count, "kanji_count": kanji_count})
        for book, vocab_count, kanji_count in rows
    ]


@router.post("/books", response_model=BookRead)
def create_book(payload: BookCreate, db: Session = Depends(get_db)):
    book = Book(**payload.model_dump())
    db.add(book)
    db.commit()
    db.refresh(book)
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
    return BookRead.model_validate(book)


@router.delete("/books/{book_id}")
def delete_book(book_id: int, db: Session = Depends(get_db)):
    book = db.get(Book, book_id)
    if not book:
        raise HTTPException(404, "Book not found")
    db.delete(book)
    db.commit()
    return {"deleted": True}


@router.get("/chapters", response_model=list[ChapterRead])
def list_chapters(book_id: int | None = None, db: Session = Depends(get_db)):
    stmt = select(Chapter).order_by(Chapter.book_id, Chapter.sort_order, Chapter.chapter_number)
    if book_id:
        stmt = stmt.where(Chapter.book_id == book_id)
    return db.scalars(stmt).all()


@router.post("/chapters", response_model=ChapterRead)
def create_chapter(payload: ChapterCreate, db: Session = Depends(get_db)):
    chapter = Chapter(**payload.model_dump())
    db.add(chapter)
    db.commit()
    db.refresh(chapter)
    return chapter


@router.patch("/chapters/{chapter_id}", response_model=ChapterRead)
def update_chapter(chapter_id: int, payload: ChapterUpdate, db: Session = Depends(get_db)):
    chapter = db.get(Chapter, chapter_id)
    if not chapter:
        raise HTTPException(404, "Chapter not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(chapter, key, value)
    db.commit()
    db.refresh(chapter)
    return chapter
