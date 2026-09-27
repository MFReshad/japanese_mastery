from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services import study_operations as operations

router = APIRouter(prefix="/study")


@router.get("/next-chapter")
def next_chapter(
    book_id: int,
    chapter_id: int,
    kind: str = Query(pattern="^(vocabulary|kanji)$"),
    db: Session = Depends(get_db),
):
    return operations.next_chapter(book_id, chapter_id, kind, db)


@router.get("/items")
def study_items(
    book_id: int,
    chapter_id: int,
    kind: str = Query(pattern="^(vocabulary|kanji)$"),
    db: Session = Depends(get_db),
):
    return operations.study_items(book_id, chapter_id, kind, db)


@router.get("/{kind}/{source_id}")
def study_detail(kind: str, source_id: str, db: Session = Depends(get_db)):
    return operations.study_detail(kind, source_id, db)
