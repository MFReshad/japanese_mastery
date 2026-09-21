from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models.item import Kanji, KanjiExample, KanjiSource, Vocabulary, VocabularySource
from app.models.practice import ItemProgress
from app.repositories.items import create_kanji_source, create_vocabulary_source, filter_kanji_sources, filter_vocabulary_sources
from app.schemas.items import KanjiExampleIn, KanjiSourceCreate, KanjiSourceRead, KanjiSourceUpdate, VocabularySourceCreate, VocabularySourceRead, VocabularySourceUpdate

router = APIRouter()


@router.get("/vocabulary")
def list_vocabulary(db: Session = Depends(get_db)):
    return db.scalars(select(Vocabulary).order_by(Vocabulary.normalized_expression, Vocabulary.normalized_reading)).all()


@router.get("/kanji")
def list_kanji(db: Session = Depends(get_db)):
    return db.scalars(select(Kanji).order_by(Kanji.character)).all()


def vocab_out(db: Session, source: VocabularySource, status: str | None = None) -> VocabularySourceRead:
    if status is None:
        progress = db.scalar(select(ItemProgress).where(ItemProgress.item_type == "vocabulary", ItemProgress.item_id == source.vocabulary_id))
        status = progress.status if progress else "new"
    return VocabularySourceRead.model_validate(
        {
            "id": source.id,
            "source_id": source.source_id,
            "vocabulary_id": source.vocabulary_id,
            "book_id": source.book_id,
            "chapter_id": source.chapter_id,
            "item_order": source.item_order,
            "original_item_order": source.original_item_order,
            "manually_added": source.manually_added,
            "manually_reordered": source.manually_reordered,
            "expression_as_printed": source.expression_as_printed,
            "reading_as_printed": source.reading_as_printed,
            "meaning_as_printed": source.meaning_as_printed,
            "notes": source.notes,
            "source_file": source.source_file,
            "source_page": source.source_page,
            "source_section": source.source_section,
            "created_at": source.created_at,
            "updated_at": source.updated_at,
            "expression": source.vocabulary.expression,
            "reading": source.vocabulary.reading,
            "status": status,
        }
    )


def kanji_out(db: Session, source: KanjiSource, status: str | None = None) -> KanjiSourceRead:
    if status is None:
        progress = db.scalar(select(ItemProgress).where(ItemProgress.item_type == "kanji", ItemProgress.item_id == source.kanji_id))
        status = progress.status if progress else "new"
    return KanjiSourceRead.model_validate(
        {
            "id": source.id,
            "source_id": source.source_id,
            "kanji_id": source.kanji_id,
            "book_id": source.book_id,
            "chapter_id": source.chapter_id,
            "item_order": source.item_order,
            "meaning_as_printed": source.meaning_as_printed,
            "onyomi": source.onyomi,
            "kunyomi": source.kunyomi,
            "notes": source.notes,
            "uncertain": source.uncertain,
            "source_file": source.source_file,
            "source_page": source.source_page,
            "source_section": source.source_section,
            "created_at": source.created_at,
            "updated_at": source.updated_at,
            "character": source.kanji.character,
            "examples": [KanjiExampleIn.model_validate(example) for example in source.examples],
            "status": status,
        }
    )


@router.get("/vocabulary-sources", response_model=list[VocabularySourceRead])
def list_vocabulary_sources(book_id: int | None = None, chapter_id: int | None = None,
                            unassigned: bool = False, db: Session = Depends(get_db)):
    stmt = filter_vocabulary_sources([book_id] if book_id else None, [chapter_id] if chapter_id else None)
    if unassigned:
        stmt = stmt.where(VocabularySource.chapter_id.is_(None))
    sources = db.scalars(stmt).all()
    item_ids = {source.vocabulary_id for source in sources}
    statuses = dict(db.execute(select(ItemProgress.item_id, ItemProgress.status).where(
        ItemProgress.item_type == "vocabulary", ItemProgress.item_id.in_(item_ids)
    )).all()) if item_ids else {}
    return [vocab_out(db, source, statuses.get(source.vocabulary_id, "new")) for source in sources]


@router.post("/vocabulary-sources", response_model=VocabularySourceRead)
def add_vocabulary_source(payload: VocabularySourceCreate, db: Session = Depends(get_db)):
    source = create_vocabulary_source(db, payload)
    db.commit()
    db.refresh(source)
    source = db.scalar(select(VocabularySource).options(selectinload(VocabularySource.vocabulary)).where(VocabularySource.id == source.id))
    return vocab_out(db, source)


@router.patch("/vocabulary-sources/{source_id}", response_model=VocabularySourceRead)
def update_vocabulary_source(source_id: int, payload: VocabularySourceUpdate, db: Session = Depends(get_db)):
    source = db.scalar(select(VocabularySource).options(selectinload(VocabularySource.vocabulary)).where(VocabularySource.id == source_id))
    if not source:
        raise HTTPException(404, "Vocabulary source not found")
    changes = payload.model_dump(exclude_unset=True)
    if "item_order" in changes or "chapter_id" in changes:
        raise HTTPException(400, "Use chapter vocabulary ordering to move entries")
    for key, value in changes.items():
        setattr(source, key, value)
    if "meaning_as_printed" in changes:
        source.meanings_as_printed = [changes["meaning_as_printed"]]
    db.commit()
    db.refresh(source)
    return vocab_out(db, source)


@router.get("/kanji-sources", response_model=list[KanjiSourceRead])
def list_kanji_sources(book_id: int | None = None, chapter_id: int | None = None,
                       unassigned: bool = False, db: Session = Depends(get_db)):
    stmt = filter_kanji_sources([book_id] if book_id else None, [chapter_id] if chapter_id else None)
    if unassigned:
        stmt = stmt.where(KanjiSource.chapter_id.is_(None))
    sources = db.scalars(stmt).all()
    item_ids = {source.kanji_id for source in sources}
    statuses = dict(db.execute(select(ItemProgress.item_id, ItemProgress.status).where(
        ItemProgress.item_type == "kanji", ItemProgress.item_id.in_(item_ids)
    )).all()) if item_ids else {}
    return [kanji_out(db, source, statuses.get(source.kanji_id, "new")) for source in sources]


@router.post("/kanji-sources", response_model=KanjiSourceRead)
def add_kanji_source(payload: KanjiSourceCreate, db: Session = Depends(get_db)):
    source = create_kanji_source(db, payload)
    db.commit()
    source = db.scalar(select(KanjiSource).options(selectinload(KanjiSource.kanji), selectinload(KanjiSource.examples)).where(KanjiSource.id == source.id))
    return kanji_out(db, source)


@router.patch("/kanji-sources/{source_id}", response_model=KanjiSourceRead)
def update_kanji_source(source_id: int, payload: KanjiSourceUpdate, db: Session = Depends(get_db)):
    source = db.scalar(select(KanjiSource).options(selectinload(KanjiSource.kanji), selectinload(KanjiSource.examples)).where(KanjiSource.id == source_id))
    if not source:
        raise HTTPException(404, "Kanji source not found")
    changes = payload.model_dump(exclude_unset=True)
    examples = changes.pop("examples", None)
    for key, value in changes.items():
        setattr(source, key, value)
    if examples is not None:
        source.examples.clear()
        source.examples.extend(KanjiExample(**example) for example in examples)
    db.commit()
    db.refresh(source)
    return kanji_out(db, source)
