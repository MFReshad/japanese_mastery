from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services import library_operations as operations
from app.services.library_operations import StarUpdate

router = APIRouter()


@router.get("/library/compare")
def compare_library_items(
    kind: str = Query("vocabulary", pattern="^(vocabulary|kanji)$"),
    book_ids: list[int] = Query(..., min_length=1, max_length=12),
    db: Session = Depends(get_db),
):
    return operations.comparison_items(kind, list(dict.fromkeys(book_ids)), db)


@router.get("/library/items")
def library_items(
    kind: str = Query("vocabulary", pattern="^(vocabulary|kanji)$"),
    book_id: int | None = None,
    chapter_id: int | None = None,
    status: str = Query("all", pattern="^(all|new|learning|weak|mastered|starred)$"),
    search: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return operations.library_items(
        kind, book_id, chapter_id, status, search, page, page_size, db
    )


@router.patch("/library/items/{kind}/{source_id}/star")
def update_star(
    kind: str, source_id: int, payload: StarUpdate, db: Session = Depends(get_db)
):
    return operations.update_star(kind, source_id, payload, db)
