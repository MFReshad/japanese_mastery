from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.item import Kanji, KanjiSource, VocabularySource
from app.models.practice import ItemProgress
from app.services.mastery import get_or_create_progress

router = APIRouter()


class StarUpdate(BaseModel):
    is_starred: bool


@router.get("/library/items")
def library_items(kind: str = Query("vocabulary", pattern="^(vocabulary|kanji)$"),
                  book_id: int | None = None, chapter_id: int | None = None,
                  status: str = Query("all", pattern="^(all|new|learning|weak|mastered|starred)$"),
                  search: str = "", page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100),
                  db: Session = Depends(get_db)):
    model = VocabularySource if kind == "vocabulary" else KanjiSource
    conditions = []
    if book_id is not None:
        conditions.append(model.book_id == book_id)
    if chapter_id is not None:
        conditions.append(model.chapter_id == chapter_id)
    term = search.strip()
    if term:
        pattern = f"%{term}%"
        if kind == "vocabulary":
            conditions.append(or_(model.expression_as_printed.ilike(pattern),
                                  model.reading_as_printed.ilike(pattern), model.meaning_as_printed.ilike(pattern)))
        else:
            conditions.append(or_(Kanji.character.ilike(pattern), model.meaning_as_printed.ilike(pattern)))
    progress_id = model.vocabulary_id if kind == "vocabulary" else model.kanji_id
    fields = [model.id, model.source_id, model.item_order, model.book_id, model.chapter_id,
              model.meaning_as_printed, func.coalesce(ItemProgress.status, "new"),
              func.coalesce(ItemProgress.is_starred, False)]
    if kind == "vocabulary":
        fields += [model.expression_as_printed, model.reading_as_printed]
    else:
        fields += [Kanji.character, model.onyomi_as_printed, model.kunyomi_as_printed]
    fields.append(func.count().over().label("total"))
    stmt = select(*fields).select_from(model)
    if kind == "kanji":
        stmt = stmt.join(Kanji, Kanji.id == model.kanji_id)
    stmt = (stmt.outerjoin(ItemProgress, and_(ItemProgress.item_type == kind, ItemProgress.item_id == progress_id))
            .where(*conditions))
    if status == "starred":
        stmt = stmt.where(ItemProgress.is_starred.is_(True))
    elif status != "all":
        if status == "new":
            stmt = stmt.where(or_(ItemProgress.id.is_(None), ItemProgress.status == "new"))
        else:
            stmt = stmt.where(ItemProgress.status == status)
    stmt = stmt.order_by(model.book_id, model.chapter_id, model.item_order, model.id).offset((page - 1) * page_size).limit(page_size)
    items = []
    total = 0
    for row in db.execute(stmt):
        item_id, source_id, item_order, row_book_id, row_chapter_id, meaning, item_status, is_starred, *detail, total = row
        item = {"id": item_id, "source_id": source_id or str(item_id), "item_order": item_order,
                "book_id": row_book_id, "chapter_id": row_chapter_id,
                "meaning_as_printed": meaning, "status": item_status, "is_starred": is_starred}
        if kind == "vocabulary":
            item.update(expression_as_printed=detail[0], reading_as_printed=detail[1])
        else:
            item.update(character=detail[0], onyomi=detail[1] or [], kunyomi=detail[2] or [])
        items.append(item)
    if not items:
        count_stmt = select(func.count()).select_from(model)
        if kind == "kanji" and term:
            count_stmt = count_stmt.join(Kanji, Kanji.id == model.kanji_id)
        count_stmt = count_stmt.outerjoin(ItemProgress, and_(ItemProgress.item_type == kind, ItemProgress.item_id == progress_id))
        if status == "starred":
            count_stmt = count_stmt.where(ItemProgress.is_starred.is_(True))
        elif status != "all":
            if status == "new":
                count_stmt = count_stmt.where(or_(ItemProgress.id.is_(None), ItemProgress.status == "new"))
            else:
                count_stmt = count_stmt.where(ItemProgress.status == status)
        total = db.scalar(count_stmt.where(*conditions)) or 0
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.patch("/library/items/{kind}/{source_id}/star")
def update_star(kind: str, source_id: int, payload: StarUpdate, db: Session = Depends(get_db)):
    if kind not in ("vocabulary", "kanji"):
        raise HTTPException(400, "Kind must be vocabulary or kanji")
    model = VocabularySource if kind == "vocabulary" else KanjiSource
    source = db.get(model, source_id)
    if source is None:
        raise HTTPException(404, "Library item not found")
    item_id = source.vocabulary_id if kind == "vocabulary" else source.kanji_id
    progress = get_or_create_progress(db, kind, item_id)
    progress.is_starred = payload.is_starred
    db.commit()
    return {"item_type": kind, "item_id": item_id, "source_id": source_id,
            "status": progress.status, "is_starred": progress.is_starred}
