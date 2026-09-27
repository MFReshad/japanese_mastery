from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.books import (
    BookCreate,
    BookRead,
    BookUpdate,
    ChapterCreate,
    ChapterRead,
    ChapterUpdate,
)
from app.services import books_operations as operations

router = APIRouter()


@router.get("/books", response_model=list[BookRead])
def list_books(db: Session = Depends(get_db)):
    return operations.list_books(db)


@router.post("/books", response_model=BookRead)
def create_book(payload: BookCreate, db: Session = Depends(get_db)):
    return operations.create_book(payload, db)


@router.patch("/books/{book_id}", response_model=BookRead)
def update_book(book_id: int, payload: BookUpdate, db: Session = Depends(get_db)):
    return operations.update_book(book_id, payload, db)


@router.delete("/books/{book_id}")
def delete_book(book_id: int, db: Session = Depends(get_db)):
    return operations.delete_book(book_id, db)


@router.get("/chapters", response_model=list[ChapterRead])
def list_chapters(book_id: int | None = None, db: Session = Depends(get_db)):
    return operations.list_chapters(book_id, db)


@router.post("/chapters", response_model=ChapterRead)
def create_chapter(payload: ChapterCreate, db: Session = Depends(get_db)):
    return operations.create_chapter(payload, db)


@router.patch("/chapters/{chapter_id}", response_model=ChapterRead)
def update_chapter(
    chapter_id: int, payload: ChapterUpdate, db: Session = Depends(get_db)
):
    return operations.update_chapter(chapter_id, payload, db)
