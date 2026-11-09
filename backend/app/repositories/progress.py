from __future__ import annotations
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session
from app.models.book import Book, Chapter
from app.models.item import Kanji, KanjiExample, KanjiSource, Vocabulary, VocabularySource
from app.models.practice import ItemProgress
from app.schemas.practice import CoverageChapter, ProgressRead


def progress(db: Session = None):
    row = db.execute(
        select(
            select(func.count()).select_from(Vocabulary).scalar_subquery(),
            select(func.count()).select_from(Kanji).scalar_subquery(),
            *[
                func.count().filter(
                    and_(ItemProgress.item_type == kind, ItemProgress.attempts > 0)
                )
                for kind in ("vocabulary", "kanji")
            ],
            *[
                func.count().filter(
                    and_(
                        ItemProgress.item_type == kind,
                        ItemProgress.attempts > 0,
                        ItemProgress.status == status,
                    )
                )
                for kind in ("vocabulary", "kanji")
                for status in ("learning", "weak", "mastered")
            ],
        )
    ).one()
    result = []
    for index, item_type in enumerate(("vocabulary", "kanji")):
        total = row[index]
        practiced = row[2 + index]
        learning, weak, mastered = row[4 + index * 3 : 7 + index * 3]
        result.append(
            ProgressRead(
                item_type=item_type,
                total=total,
                new=max(total - practiced, 0),
                learning=learning,
                weak=weak,
                mastered=mastered,
            )
        )
    return result


def book_coverage(db: Session = None):
    def coverage_counts(model, item_type: str, id_column):
        return (
            select(
                model.chapter_id,
                func.count(model.id).label("total"),
                func.count(ItemProgress.id).label("mastered"),
            )
            .outerjoin(
                ItemProgress,
                and_(
                    ItemProgress.item_type == item_type,
                    ItemProgress.item_id == id_column,
                    ItemProgress.attempts > 0,
                    ItemProgress.status == "mastered",
                ),
            )
            .where(model.chapter_id.is_not(None))
            .group_by(model.chapter_id)
        ).subquery()

    vocabulary = coverage_counts(
        VocabularySource, "vocabulary", VocabularySource.vocabulary_id
    )
    kanji = coverage_counts(KanjiSource, "kanji", KanjiSource.kanji_id)
    vocab_lacking = (
        select(
            VocabularySource.chapter_id,
            func.count(VocabularySource.id).filter(VocabularySource.knowledge_status == "unknown").label("unknown"),
            func.count(VocabularySource.id).filter(ItemProgress.status == "weak").label("weak"),
        )
        .outerjoin(ItemProgress, and_(ItemProgress.item_type == "vocabulary", ItemProgress.item_id == VocabularySource.vocabulary_id))
        .where(VocabularySource.chapter_id.is_not(None))
        .group_by(VocabularySource.chapter_id)
    ).subquery()
    kanji_lacking = (
        select(
            KanjiSource.chapter_id,
            func.count(KanjiSource.id).filter(ItemProgress.status == "weak").label("weak"),
        )
        .outerjoin(ItemProgress, and_(ItemProgress.item_type == "kanji", ItemProgress.item_id == KanjiSource.kanji_id))
        .where(KanjiSource.chapter_id.is_not(None))
        .group_by(KanjiSource.chapter_id)
    ).subquery()
    example_lacking = (
        select(
            KanjiSource.chapter_id,
            func.count(KanjiExample.id).label("total"),
            func.count(KanjiExample.id).filter(KanjiExample.knowledge_status == "unknown").label("unknown"),
        )
        .join(KanjiExample, KanjiExample.kanji_source_id == KanjiSource.id)
        .where(KanjiSource.chapter_id.is_not(None))
        .group_by(KanjiSource.chapter_id)
    ).subquery()
    rows = []
    stmt = (
        select(
            Chapter,
            Book,
            func.coalesce(vocabulary.c.total, 0),
            func.coalesce(vocabulary.c.mastered, 0),
            func.coalesce(kanji.c.total, 0),
            func.coalesce(kanji.c.mastered, 0),
            func.coalesce(vocab_lacking.c.unknown, 0),
            func.coalesce(vocab_lacking.c.weak, 0),
            func.coalesce(example_lacking.c.total, 0),
            func.coalesce(example_lacking.c.unknown, 0),
            func.coalesce(kanji_lacking.c.weak, 0),
        )
        .join(Book)
        .outerjoin(vocabulary, vocabulary.c.chapter_id == Chapter.id)
        .outerjoin(kanji, kanji.c.chapter_id == Chapter.id)
        .outerjoin(vocab_lacking, vocab_lacking.c.chapter_id == Chapter.id)
        .outerjoin(example_lacking, example_lacking.c.chapter_id == Chapter.id)
        .outerjoin(kanji_lacking, kanji_lacking.c.chapter_id == Chapter.id)
        .order_by(Book.title, Chapter.sort_order)
    )
    for (
        chapter,
        book,
        vocab_total,
        vocab_mastered,
        kanji_total,
        kanji_mastered,
        vocab_unknown,
        vocab_weak,
        example_total,
        example_unknown,
        kanji_weak,
    ) in db.execute(stmt):
        rows.append(
            CoverageChapter(
                book_id=book.id,
                book_title=book.title,
                chapter_id=chapter.id,
                chapter_title=chapter.title,
                chapter_number=chapter.chapter_number,
                vocabulary_mastered_percent=round(
                    (vocab_mastered / vocab_total * 100) if vocab_total else 0, 1
                ),
                kanji_mastered_percent=round(
                    (kanji_mastered / kanji_total * 100) if kanji_total else 0, 1
                ),
                vocabulary_total=vocab_total,
                vocabulary_unknown=vocab_unknown,
                vocabulary_weak=vocab_weak,
                kanji_example_total=example_total,
                kanji_example_unknown=example_unknown,
                kanji_weak=kanji_weak,
            )
        )
    return rows
