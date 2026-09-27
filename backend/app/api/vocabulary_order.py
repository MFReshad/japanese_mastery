from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.items import VocabularySourceRead
from app.services import vocabulary_order_operations as operations
from app.services.vocabulary_order_operations import OrderRequest, InsertRequest

router = APIRouter()


@router.get(
    "/chapters/{chapter_id}/vocabulary-order", response_model=list[VocabularySourceRead]
)
def list_order(chapter_id: int, db: Session = Depends(get_db)):
    return operations.list_order(chapter_id, db)


@router.put(
    "/chapters/{chapter_id}/vocabulary-order", response_model=list[VocabularySourceRead]
)
def reorder(chapter_id: int, payload: OrderRequest, db: Session = Depends(get_db)):
    return operations.reorder(chapter_id, payload, db)


@router.post(
    "/chapters/{chapter_id}/vocabulary-order", response_model=VocabularySourceRead
)
def insert(chapter_id: int, payload: InsertRequest, db: Session = Depends(get_db)):
    return operations.insert(chapter_id, payload, db)


@router.post(
    "/chapters/{chapter_id}/vocabulary-order/reset",
    response_model=list[VocabularySourceRead],
)
def reset(chapter_id: int, db: Session = Depends(get_db)):
    return operations.reset(chapter_id, db)


@router.delete("/vocabulary-sources/{source_id}", status_code=204)
def delete(source_id: int, db: Session = Depends(get_db)):
    return operations.delete(source_id, db)
