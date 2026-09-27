from app.errors import Conflict
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.orm import Session, contains_eager

from app.services.item_management import vocab_out
from app.services.lookup_cache import lookup_cache
from app.models.item import VocabularySource
from app.models.practice import ItemProgress
from app.schemas.items import VocabularySourceRead
from app.services.vocabulary_order import (
    chapter_sources,
    insert_source,
    remove_source,
    reset_order,
    save_order,
)


class OrderRequest(BaseModel):
    source_ids: list[int]
    expected_source_ids: list[int]


class InsertRequest(BaseModel):
    expression: str = Field(min_length=1, max_length=255)
    reading: str = Field(max_length=255)
    meaning: str = Field(min_length=1)
    position: int = Field(ge=1)


def output(db: Session, rows: list[VocabularySource]) -> list[VocabularySourceRead]:
    ids = [row.id for row in rows]
    if not ids:
        return []
    loaded = {
        source.id: (source, status or "new")
        for source, status in db.execute(
            select(VocabularySource, ItemProgress.status)
            .join(VocabularySource.vocabulary)
            .options(contains_eager(VocabularySource.vocabulary))
            .outerjoin(
                ItemProgress,
                and_(
                    ItemProgress.item_type == "vocabulary",
                    ItemProgress.item_id == VocabularySource.vocabulary_id,
                ),
            )
            .where(VocabularySource.id.in_(ids))
        )
    }
    return [vocab_out(*loaded[id]) for id in ids]


def list_order(chapter_id: int, db: Session = None):
    return output(db, chapter_sources(db, chapter_id))


def reorder(chapter_id: int, payload: OrderRequest, db: Session = None):
    current = chapter_sources(db, chapter_id)
    if [row.id for row in current] != payload.expected_source_ids:
        raise Conflict("Chapter order changed; reload before saving")
    rows = save_order(db, chapter_id, payload.source_ids)
    db.commit()
    lookup_cache.invalidate_progress()
    lookup_cache.clear()
    return output(db, rows)


def insert(chapter_id: int, payload: InsertRequest, db: Session = None):
    row = insert_source(
        db,
        chapter_id,
        payload.expression,
        payload.reading,
        payload.meaning,
        payload.position,
    )
    db.commit()
    lookup_cache.invalidate_progress()
    lookup_cache.clear()
    return output(db, [row])[0]


def reset(chapter_id: int, db: Session = None):
    rows = reset_order(db, chapter_id)
    db.commit()
    lookup_cache.invalidate_progress()
    lookup_cache.clear()
    return output(db, rows)


def delete(source_id: int, db: Session = None):
    remove_source(db, source_id)
    db.commit()
    lookup_cache.invalidate_progress()
    lookup_cache.clear()
