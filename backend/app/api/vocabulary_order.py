from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.orm import Session, contains_eager

from app.api.items import vocab_out
from app.db.session import get_db
from app.models.item import VocabularySource
from app.models.practice import ItemProgress
from app.schemas.items import VocabularySourceRead
from app.services.vocabulary_order import chapter_sources, insert_source, remove_source, reset_order, save_order

router = APIRouter()


class OrderRequest(BaseModel):
    source_ids: list[int]


class InsertRequest(BaseModel):
    expression: str
    reading: str
    meaning: str
    position: int = Field(ge=1)


def output(db: Session, rows: list[VocabularySource]) -> list[VocabularySourceRead]:
    ids = [row.id for row in rows]
    if not ids:
        return []
    loaded = {source.id: (source, status or "new") for source, status in db.execute(
        select(VocabularySource, ItemProgress.status)
        .join(VocabularySource.vocabulary).options(contains_eager(VocabularySource.vocabulary))
        .outerjoin(ItemProgress, and_(ItemProgress.item_type == "vocabulary",
                                       ItemProgress.item_id == VocabularySource.vocabulary_id))
        .where(VocabularySource.id.in_(ids))
    )}
    return [vocab_out(db, *loaded[id]) for id in ids]


@router.get("/chapters/{chapter_id}/vocabulary-order", response_model=list[VocabularySourceRead])
def list_order(chapter_id: int, db: Session = Depends(get_db)):
    return output(db, chapter_sources(db, chapter_id))


@router.put("/chapters/{chapter_id}/vocabulary-order", response_model=list[VocabularySourceRead])
def reorder(chapter_id: int, payload: OrderRequest, db: Session = Depends(get_db)):
    rows = save_order(db, chapter_id, payload.source_ids)
    db.commit()
    return output(db, rows)


@router.post("/chapters/{chapter_id}/vocabulary-order", response_model=VocabularySourceRead)
def insert(chapter_id: int, payload: InsertRequest, db: Session = Depends(get_db)):
    row = insert_source(db, chapter_id, payload.expression, payload.reading, payload.meaning, payload.position)
    db.commit()
    return output(db, [row])[0]


@router.post("/chapters/{chapter_id}/vocabulary-order/reset", response_model=list[VocabularySourceRead])
def reset(chapter_id: int, db: Session = Depends(get_db)):
    rows = reset_order(db, chapter_id)
    db.commit()
    return output(db, rows)


@router.delete("/vocabulary-sources/{source_id}", status_code=204)
def delete(source_id: int, db: Session = Depends(get_db)):
    remove_source(db, source_id)
    db.commit()
