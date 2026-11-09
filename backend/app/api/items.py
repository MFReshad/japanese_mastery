from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.items import (
    KanjiSourceCreate,
    KanjiSourceRead,
    KanjiSourceUpdate,
    KanjiExampleImportanceUpdate,
    VocabularySourceCreate,
    VocabularySourceRead,
    VocabularySourceUpdate,
)
from app.models.item import KanjiExample
from app.errors import NotFound
from app.services import item_management as operations

router = APIRouter()


@router.get("/vocabulary")
def list_vocabulary(
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return operations.list_vocabulary(db, offset, limit)


@router.get("/kanji")
def list_kanji(
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return operations.list_kanji(db, offset, limit)


@router.get("/vocabulary-sources", response_model=list[VocabularySourceRead])
def list_vocabulary_sources(
    book_id: int | None = None,
    chapter_id: int | None = None,
    unassigned: bool = False,
    offset: int = Query(0, ge=0),
    limit: int | None = Query(None, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return operations.list_vocabulary_sources(
        book_id, chapter_id, unassigned, db, offset, limit
    )


@router.post("/vocabulary-sources", response_model=VocabularySourceRead)
def add_vocabulary_source(
    payload: VocabularySourceCreate, db: Session = Depends(get_db)
):
    return operations.add_vocabulary_source(payload, db)


@router.patch("/vocabulary-sources/{source_id}", response_model=VocabularySourceRead)
def update_vocabulary_source(
    source_id: int, payload: VocabularySourceUpdate, db: Session = Depends(get_db)
):
    return operations.update_vocabulary_source(source_id, payload, db)


@router.get("/kanji-sources", response_model=list[KanjiSourceRead])
def list_kanji_sources(
    book_id: int | None = None,
    chapter_id: int | None = None,
    unassigned: bool = False,
    offset: int = Query(0, ge=0),
    limit: int | None = Query(None, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return operations.list_kanji_sources(
        book_id, chapter_id, unassigned, db, offset, limit
    )


@router.post("/kanji-sources", response_model=KanjiSourceRead)
def add_kanji_source(payload: KanjiSourceCreate, db: Session = Depends(get_db)):
    return operations.add_kanji_source(payload, db)


@router.patch("/kanji-sources/{source_id}", response_model=KanjiSourceRead)
def update_kanji_source(
    source_id: int, payload: KanjiSourceUpdate, db: Session = Depends(get_db)
):
    return operations.update_kanji_source(source_id, payload, db)


@router.patch("/kanji-examples/{example_id}/important")
def update_kanji_example_importance(
    example_id: int,
    payload: KanjiExampleImportanceUpdate,
    db: Session = Depends(get_db),
):
    example = db.get(KanjiExample, example_id)
    if example is None:
        raise NotFound("Kanji example not found")
    example.is_important = payload.is_important
    db.commit()
    return {"id": example.id, "is_important": example.is_important}


@router.delete("/kanji-sources/{source_id}", status_code=204)
def delete_kanji_source(source_id: int, db: Session = Depends(get_db)):
    return operations.delete_kanji_source(source_id, db)
