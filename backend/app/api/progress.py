from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.book import Book, Chapter
from app.models.item import Kanji, KanjiSource, Vocabulary, VocabularySource
from app.models.practice import ItemProgress
from app.schemas.practice import CoverageChapter, ProgressRead

router = APIRouter()


@router.get("/progress", response_model=list[ProgressRead])
def progress(db: Session = Depends(get_db)):
    row = db.execute(select(
        select(func.count()).select_from(Vocabulary).scalar_subquery(),
        select(func.count()).select_from(Kanji).scalar_subquery(),
        *[func.count().filter(ItemProgress.item_type == kind) for kind in ("vocabulary", "kanji")],
        *[func.count().filter(and_(ItemProgress.item_type == kind, ItemProgress.status == status))
          for kind in ("vocabulary", "kanji") for status in ("learning", "weak", "mastered")],
    )).one()
    result = []
    for index, item_type in enumerate(("vocabulary", "kanji")):
        total = row[index]
        practiced = row[2 + index]
        learning, weak, mastered = row[4 + index * 3:7 + index * 3]
        result.append(ProgressRead(item_type=item_type, total=total, new=max(total - practiced, 0),
            learning=learning, weak=weak, mastered=mastered))
    return result


@router.get("/progress/books", response_model=list[CoverageChapter])
def book_coverage(db: Session = Depends(get_db)):
    def coverage_counts(model, item_type: str, id_column):
        return (
            select(model.chapter_id, func.count(model.id).label("total"),
                   func.count(func.distinct(ItemProgress.id)).label("mastered"))
            .outerjoin(ItemProgress, and_(ItemProgress.item_type == item_type,
                ItemProgress.item_id == id_column, ItemProgress.status == "mastered"))
            .where(model.chapter_id.is_not(None)).group_by(model.chapter_id)
        ).subquery()

    vocabulary = coverage_counts(VocabularySource, "vocabulary", VocabularySource.vocabulary_id)
    kanji = coverage_counts(KanjiSource, "kanji", KanjiSource.kanji_id)
    rows = []
    stmt = (select(Chapter, Book, func.coalesce(vocabulary.c.total, 0), func.coalesce(vocabulary.c.mastered, 0),
                   func.coalesce(kanji.c.total, 0), func.coalesce(kanji.c.mastered, 0))
            .join(Book).outerjoin(vocabulary, vocabulary.c.chapter_id == Chapter.id)
            .outerjoin(kanji, kanji.c.chapter_id == Chapter.id).order_by(Book.title, Chapter.sort_order))
    for chapter, book, vocab_total, vocab_mastered, kanji_total, kanji_mastered in db.execute(stmt):
        rows.append(
            CoverageChapter(
                book_id=book.id,
                book_title=book.title,
                chapter_id=chapter.id,
                chapter_title=chapter.title,
                chapter_number=chapter.chapter_number,
                vocabulary_mastered_percent=round((vocab_mastered / vocab_total * 100) if vocab_total else 0, 1),
                kanji_mastered_percent=round((kanji_mastered / kanji_total * 100) if kanji_total else 0, 1),
            )
        )
    return rows
