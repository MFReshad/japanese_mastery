from __future__ import annotations
from app.mappers.items import vocab_out, kanji_out
from app.errors import NotFound, Conflict, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.item import (
    Kanji,
    KanjiExample,
    KanjiSource,
    Vocabulary,
    VocabularySource,
)
from app.models.practice import ItemProgress
from app.repositories.items import (
    get_or_create_vocabulary,
    get_or_create_kanji,
    filter_kanji_sources,
    filter_vocabulary_sources,
)
from uuid import uuid4
from app.schemas.items import (
    KanjiSourceCreate,
    KanjiSourceUpdate,
    VocabularySourceCreate,
    VocabularySourceUpdate,
)
from app.services.lookup_cache import lookup_cache
from app.services.integrity import validate_ownership, meaning_fields


def list_vocabulary(db: Session, offset: int = 0, limit: int = 100):
    return db.scalars(
        select(Vocabulary)
        .order_by(Vocabulary.normalized_expression, Vocabulary.normalized_reading)
        .offset(offset)
        .limit(limit)
    ).all()


def list_kanji(db: Session, offset: int = 0, limit: int = 100):
    return db.scalars(
        select(Kanji).order_by(Kanji.character).offset(offset).limit(limit)
    ).all()


def list_vocabulary_sources(
    book_id: int | None = None,
    chapter_id: int | None = None,
    unassigned: bool = False,
    db: Session = None,
    offset: int = 0,
    limit: int | None = None,
):
    stmt = filter_vocabulary_sources(
        [book_id] if book_id else None, [chapter_id] if chapter_id else None
    )
    if unassigned:
        stmt = stmt.where(VocabularySource.chapter_id.is_(None))
    if limit is not None or (book_id is None and chapter_id is None):
        stmt = stmt.offset(offset).limit(limit or 100)
    sources = db.scalars(stmt).all()
    item_ids = {source.vocabulary_id for source in sources}
    statuses = (
        dict(
            db.execute(
                select(ItemProgress.item_id, ItemProgress.status).where(
                    ItemProgress.item_type == "vocabulary",
                    ItemProgress.item_id.in_(item_ids),
                )
            ).all()
        )
        if item_ids
        else {}
    )
    return [
        vocab_out(source, statuses.get(source.vocabulary_id, "new"))
        for source in sources
    ]


def add_vocabulary_source(payload: VocabularySourceCreate, db: Session = None):
    source = create_vocabulary_source(db, payload)
    db.commit()
    lookup_cache.invalidate_progress()
    db.refresh(source)
    lookup_cache.invalidate_books()
    source = db.scalar(
        select(VocabularySource)
        .options(selectinload(VocabularySource.vocabulary))
        .where(VocabularySource.id == source.id)
    )
    return vocab_out(source, _status(db, "vocabulary", source.vocabulary_id))


def update_vocabulary_source(
    source_id: int, payload: VocabularySourceUpdate, db: Session = None
):
    source = db.scalar(
        select(VocabularySource)
        .options(selectinload(VocabularySource.vocabulary))
        .where(VocabularySource.id == source_id)
    )
    if not source:
        raise NotFound("Vocabulary source not found")
    validate_ownership(db, source.book_id, source.chapter_id)
    source = db.scalar(
        select(type(source))
        .where(type(source).id == source.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    changes = payload.model_dump(exclude_unset=True)
    identity_action = changes.pop("identity_action", None)
    identity_changed = any(
        key in changes and changes[key] != getattr(source, key)
        for key in ("expression_as_printed", "reading_as_printed")
    )
    if identity_changed:
        if identity_action is None:
            raise InvalidOperation(
                "Choose correction (keep mastery) or relink (different word)"
            )
        if identity_action == "relink":
            vocabulary = get_or_create_vocabulary(
                db,
                changes.get("expression_as_printed", source.expression_as_printed),
                changes.get("reading_as_printed", source.reading_as_printed),
            )
            source.vocabulary_id = vocabulary.id
            source.vocabulary = vocabulary
            changes["vocabulary_id"] = vocabulary.id
    if "item_order" in changes or "chapter_id" in changes:
        raise InvalidOperation("Use chapter vocabulary ordering to move entries")
    source.manual_overrides = {**(source.manual_overrides or {}), **changes}
    for key, value in changes.items():
        setattr(source, key, value)
    if "meaning_as_printed" in changes:
        source.meanings_as_printed = [changes["meaning_as_printed"]]
        source.manual_overrides = {
            **source.manual_overrides,
            "meanings_as_printed": source.meanings_as_printed,
        }
    db.commit()
    lookup_cache.invalidate_progress()
    db.refresh(source)
    return vocab_out(source, _status(db, "vocabulary", source.vocabulary_id))


def list_kanji_sources(
    book_id: int | None = None,
    chapter_id: int | None = None,
    unassigned: bool = False,
    db: Session = None,
    offset: int = 0,
    limit: int | None = None,
):
    stmt = filter_kanji_sources(
        [book_id] if book_id else None, [chapter_id] if chapter_id else None
    )
    if unassigned:
        stmt = stmt.where(KanjiSource.chapter_id.is_(None))
    if limit is not None or (book_id is None and chapter_id is None):
        stmt = stmt.offset(offset).limit(limit or 100)
    sources = db.scalars(stmt).all()
    item_ids = {source.kanji_id for source in sources}
    statuses = (
        dict(
            db.execute(
                select(ItemProgress.item_id, ItemProgress.status).where(
                    ItemProgress.item_type == "kanji",
                    ItemProgress.item_id.in_(item_ids),
                )
            ).all()
        )
        if item_ids
        else {}
    )
    return [
        kanji_out(source, statuses.get(source.kanji_id, "new")) for source in sources
    ]


def add_kanji_source(payload: KanjiSourceCreate, db: Session = None):
    source = create_kanji_source(db, payload)
    db.commit()
    lookup_cache.invalidate_progress()
    lookup_cache.invalidate_books()
    source = db.scalar(
        select(KanjiSource)
        .options(selectinload(KanjiSource.kanji), selectinload(KanjiSource.examples))
        .where(KanjiSource.id == source.id)
    )
    return kanji_out(source, _status(db, "kanji", source.kanji_id))


def update_kanji_source(source_id: int, payload: KanjiSourceUpdate, db: Session = None):
    source = db.scalar(
        select(KanjiSource)
        .options(selectinload(KanjiSource.kanji), selectinload(KanjiSource.examples))
        .where(KanjiSource.id == source_id)
    )
    if not source:
        raise NotFound("Kanji source not found")
    validate_ownership(db, source.book_id, source.chapter_id)
    source = db.scalar(
        select(type(source))
        .where(type(source).id == source.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    changes = payload.model_dump(exclude_unset=True)
    validate_ownership(db, source.book_id, changes.get("chapter_id", source.chapter_id))
    if "meaning_as_printed" in changes or "meanings_as_printed" in changes:
        changes.update(
            meaning_fields(
                changes.get("meaning_as_printed", source.meaning_as_printed),
                changes.get("meanings_as_printed"),
            )
        )
    examples = changes.pop("examples", None)
    if examples is not None:
        source.manual_overrides = {
            **(source.manual_overrides or {}),
            "examples": examples,
        }
    changes = {
        ({"onyomi": "onyomi_as_printed", "kunyomi": "kunyomi_as_printed"}.get(k, k)): v
        for k, v in changes.items()
    }
    source.manual_overrides = {**(source.manual_overrides or {}), **changes}
    for key, value in changes.items():
        setattr(source, key, value)
    if examples is not None:
        source.examples.clear()
        source.examples.extend(KanjiExample(**example) for example in examples)
    db.commit()
    lookup_cache.invalidate_progress()
    db.refresh(source)
    return kanji_out(source, _status(db, "kanji", source.kanji_id))


def create_vocabulary_source(db: Session, data) -> VocabularySource:
    validate_ownership(db, data.book_id, data.chapter_id)
    vocab = get_or_create_vocabulary(db, data.expression, data.reading)
    source = db.scalar(
        select(VocabularySource).where(
            VocabularySource.vocabulary_id == vocab.id,
            VocabularySource.book_id == data.book_id,
            VocabularySource.chapter_id == data.chapter_id,
            VocabularySource.item_order == data.item_order,
        )
    )
    if source:
        raise Conflict("Source occurrence already exists; update it explicitly")
    source = VocabularySource(
        source_id=f"manual_vocab_{uuid4().hex}",
        vocabulary_id=vocab.id,
        book_id=data.book_id,
        chapter_id=data.chapter_id,
        item_order=data.item_order,
        manually_added=True,
        expression_as_printed=data.expression,
        reading_as_printed=data.reading,
        **meaning_fields(data.meaning),
        notes=data.notes,
        source_file=data.source_file,
        source_page=data.source_page,
        source_section=data.source_section,
    )
    db.add(source)
    db.flush()
    return source


def create_kanji_source(db: Session, data) -> KanjiSource:
    validate_ownership(db, data.book_id, data.chapter_id)
    kanji = get_or_create_kanji(db, data.character)
    source = db.scalar(
        select(KanjiSource).where(
            KanjiSource.kanji_id == kanji.id,
            KanjiSource.book_id == data.book_id,
            KanjiSource.chapter_id == data.chapter_id,
            KanjiSource.item_order == data.item_order,
        )
    )
    if not source:
        source = KanjiSource(
            kanji_id=kanji.id,
            book_id=data.book_id,
            chapter_id=data.chapter_id,
            item_order=data.item_order,
            **meaning_fields(data.meaning),
            onyomi=data.onyomi,
            kunyomi=data.kunyomi,
            notes=data.notes,
            source_file=data.source_file,
            source_page=data.source_page,
            source_section=data.source_section,
        )
        db.add(source)
        db.flush()
    else:
        raise Conflict("Source occurrence already exists; update it explicitly")
    source.examples.clear()
    for example in data.examples:
        source.examples.append(
            KanjiExample(
                word=example.word,
                reading=example.reading,
                meaning=example.meaning,
                sort_order=example.sort_order,
            )
        )
    return source


def _status(db, kind, item_id):
    return (
        db.scalar(
            select(ItemProgress.status).where(
                ItemProgress.item_type == kind, ItemProgress.item_id == item_id
            )
        )
        or "new"
    )


def delete_kanji_source(source_id: int, db: Session):
    from app.models.item import SourceSuppression

    source = db.get(KanjiSource, source_id)
    if source is None:
        raise NotFound("Kanji source not found")
    validate_ownership(db, source.book_id, source.chapter_id)
    if source.source_id:
        db.merge(SourceSuppression(item_type="kanji", source_id=source.source_id))
    db.delete(source)
    db.commit()
    lookup_cache.clear()
