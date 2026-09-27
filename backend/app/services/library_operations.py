from __future__ import annotations
from app.services.lookup_cache import lookup_cache
from app.repositories import library_queries as queries
from app.errors import NotFound, InvalidOperation

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.item import KanjiSource, VocabularySource
from app.services.mastery import get_or_create_progress


class StarUpdate(BaseModel):
    is_starred: bool


def library_items(
    kind: str = "vocabulary",
    book_id: int | None = None,
    chapter_id: int | None = None,
    status: str = "all",
    search: str = "",
    page: int = 1,
    page_size: int = 50,
    db: Session = None,
):
    return queries.library_items(
        kind, book_id, chapter_id, status, search, page, page_size, db
    )


def update_star(kind: str, source_id: int, payload: StarUpdate, db: Session = None):
    if kind not in ("vocabulary", "kanji"):
        raise InvalidOperation("Kind must be vocabulary or kanji")
    model = VocabularySource if kind == "vocabulary" else KanjiSource
    source = db.get(model, source_id)
    if source is None:
        raise NotFound("Library item not found")
    item_id = source.vocabulary_id if kind == "vocabulary" else source.kanji_id
    progress = get_or_create_progress(db, kind, item_id)
    progress.is_starred = payload.is_starred
    db.commit()
    lookup_cache.invalidate_progress()
    return {
        "item_type": kind,
        "item_id": item_id,
        "source_id": source_id,
        "status": progress.status,
        "is_starred": progress.is_starred,
    }
