from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.practice import CoverageChapter, ProgressRead
from app.services import progress_operations as operations

router = APIRouter()


@router.get("/progress", response_model=list[ProgressRead])
def progress(db: Session = Depends(get_db)):
    return operations.progress(db)


@router.get("/progress/books", response_model=list[CoverageChapter])
def book_coverage(db: Session = Depends(get_db)):
    return operations.book_coverage(db)


@router.get("/progress/items")
def progress_items(
    book_id: int = Query(..., gt=0),
    material: str = Query(..., pattern="^(vocabulary|kanji_examples|kanji)$"),
    status: str = Query(..., pattern="^(new|weak|mastered)$"),
    chapter_id: int | None = Query(None, gt=0),
    search: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return operations.progress_items(book_id, material, status, chapter_id, search, page, page_size, db)
