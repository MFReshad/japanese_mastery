from __future__ import annotations
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session, selectinload
from app.models.book import Chapter
from app.models.item import Kanji, KanjiSource, VocabularySource
from app.models.practice import ItemProgress


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
            conditions.append(
                or_(
                    model.expression_as_printed.ilike(pattern),
                    model.reading_as_printed.ilike(pattern),
                    model.meaning_as_printed.ilike(pattern),
                )
            )
        else:
            conditions.append(
                or_(
                    Kanji.character.ilike(pattern),
                    model.meaning_as_printed.ilike(pattern),
                )
            )
    progress_id = model.vocabulary_id if kind == "vocabulary" else model.kanji_id
    fields = [
        model.id,
        model.source_id,
        model.item_order,
        model.book_id,
        model.chapter_id,
        model.meaning_as_printed,
        case(
            (func.coalesce(ItemProgress.attempts, 0) == 0, "new"),
            else_=ItemProgress.status,
        ),
        func.coalesce(ItemProgress.is_starred, False),
    ]
    if kind == "vocabulary":
        fields += [model.expression_as_printed, model.reading_as_printed]
    else:
        fields += [Kanji.character, model.onyomi_as_printed, model.kunyomi_as_printed]
    fields.append(progress_id.label("canonical_id"))
    fields.append(func.count().over().label("total"))
    stmt = select(*fields).select_from(model)
    if kind == "kanji":
        stmt = stmt.join(Kanji, Kanji.id == model.kanji_id)
    stmt = stmt.outerjoin(
        ItemProgress,
        and_(ItemProgress.item_type == kind, ItemProgress.item_id == progress_id),
    ).where(*conditions)
    if status == "starred":
        stmt = stmt.where(ItemProgress.is_starred.is_(True))
    elif status != "all":
        if status == "new":
            stmt = stmt.where(
                or_(ItemProgress.id.is_(None), ItemProgress.attempts == 0)
            )
        else:
            stmt = stmt.where(ItemProgress.status == status, ItemProgress.attempts > 0)
    stmt = (
        stmt.order_by(model.book_id, model.chapter_id, model.item_order, model.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = []
    total = 0
    for row in db.execute(stmt):
        (
            item_id,
            source_id,
            item_order,
            row_book_id,
            row_chapter_id,
            meaning,
            item_status,
            is_starred,
            *detail,
            total,
        ) = row
        canonical_id = detail.pop()
        item = {
            "canonical_id": canonical_id,
            "id": item_id,
            "source_id": source_id or str(item_id),
            "item_order": item_order,
            "book_id": row_book_id,
            "chapter_id": row_chapter_id,
            "meaning_as_printed": meaning,
            "status": item_status,
            "is_starred": is_starred,
        }
        if kind == "vocabulary":
            item.update(expression_as_printed=detail[0], reading_as_printed=detail[1])
        else:
            item.update(
                character=detail[0], onyomi=detail[1] or [], kunyomi=detail[2] or []
            )
        items.append(item)
    if not items:
        count_stmt = select(func.count()).select_from(model)
        if kind == "kanji" and term:
            count_stmt = count_stmt.join(Kanji, Kanji.id == model.kanji_id)
        count_stmt = count_stmt.outerjoin(
            ItemProgress,
            and_(ItemProgress.item_type == kind, ItemProgress.item_id == progress_id),
        )
        if status == "starred":
            count_stmt = count_stmt.where(ItemProgress.is_starred.is_(True))
        elif status != "all":
            if status == "new":
                count_stmt = count_stmt.where(
                    or_(ItemProgress.id.is_(None), ItemProgress.attempts == 0)
                )
            else:
                count_stmt = count_stmt.where(
                    ItemProgress.status == status, ItemProgress.attempts > 0
                )
        total = db.scalar(count_stmt.where(*conditions)) or 0
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def comparison_items(kind: str, book_ids: list[int], db: Session):
    model = VocabularySource if kind == "vocabulary" else KanjiSource
    stmt = (
        select(model, Chapter.chapter_number, Chapter.title, Chapter.part)
        .outerjoin(Chapter, Chapter.id == model.chapter_id)
        .where(model.book_id.in_(book_ids))
        .order_by(model.book_id, Chapter.sort_order, model.item_order, model.id)
    )
    if kind == "vocabulary":
        stmt = stmt.options(selectinload(VocabularySource.vocabulary))
    else:
        stmt = stmt.options(
            selectinload(KanjiSource.kanji), selectinload(KanjiSource.examples)
        )

    rows = db.execute(stmt).all()
    canonical_ids = {
        source.vocabulary_id if kind == "vocabulary" else source.kanji_id
        for source, *_ in rows
    }
    starred_ids = set(db.scalars(
        select(ItemProgress.item_id).where(
            ItemProgress.item_type == kind,
            ItemProgress.item_id.in_(canonical_ids),
            ItemProgress.is_starred.is_(True),
        )
    )) if canonical_ids else set()

    items = []
    for source, chapter_number, chapter_title, part in rows:
        common = {
            "source_id": source.source_id or str(source.id),
            "source_entry_id": source.id,
            "book_id": source.book_id,
            "chapter_id": source.chapter_id,
            "chapter_number": chapter_number,
            "chapter_title": chapter_title,
            "part": part,
            "item_order": source.item_order,
            "meaning": source.meaning_as_printed,
        }
        if kind == "vocabulary":
            items.append({
                **common,
                "match_key": str(source.vocabulary_id),
                "display": source.expression_as_printed,
                "reading": source.reading_as_printed,
                "is_important": source.vocabulary_id in starred_ids,
            })
        else:
            items.append({
                **common,
                "match_key": str(source.kanji_id),
                "display": source.kanji.character,
                "onyomi": source.onyomi_as_printed or [],
                "kunyomi": source.kunyomi_as_printed or [],
                "examples": [
                    {"id": example.id, "word": example.word, "reading": example.reading, "meaning": example.meaning, "is_important": example.is_important}
                    for example in sorted(source.examples, key=lambda row: (row.sort_order, row.id))
                ],
            })
    return {"kind": kind, "book_ids": book_ids, "items": items}
