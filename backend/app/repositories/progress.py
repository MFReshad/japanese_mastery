from __future__ import annotations
from sqlalchemy import String, and_, case, cast, func, literal, or_, select
from sqlalchemy.orm import Session, aliased
from app.models.book import Book, Chapter
from app.models.item import Kanji, KanjiExample, KanjiSource, Vocabulary, VocabularySource
from app.models.practice import ItemProgress
from app.schemas.practice import CoverageChapter, ProgressRead
from app.services.kanji_strength import kanji_strength_subquery


def progress(db: Session = None):
    row = db.execute(
        select(
            select(func.count()).select_from(Vocabulary).scalar_subquery(),
            select(func.count()).select_from(Kanji).scalar_subquery(),
            select(func.count(func.distinct(KanjiExample.canonical_id))).scalar_subquery(),
            *[
                func.count().filter(
                    and_(ItemProgress.item_type == kind, ItemProgress.attempts > 0)
                )
                for kind in ("vocabulary", "kanji", "kanji_example")
            ],
            *[
                func.count().filter(
                    and_(
                        ItemProgress.item_type == kind,
                        ItemProgress.attempts > 0,
                        ItemProgress.status == status,
                    )
                )
                for kind in ("vocabulary", "kanji", "kanji_example")
                for status in ("learning", "weak", "mastered")
            ],
        )
    ).one()
    result = []
    for index, item_type in enumerate(("vocabulary", "kanji", "kanji_example")):
        total = row[index]
        practiced = row[3 + index]
        learning, weak, mastered = row[6 + index * 3 : 9 + index * 3]
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
                func.count(ItemProgress.id).label("practiced"),
                func.count(ItemProgress.id).filter(ItemProgress.status == "mastered").label("mastered"),
            )
            .outerjoin(
                ItemProgress,
                and_(
                    ItemProgress.item_type == item_type,
                    ItemProgress.item_id == id_column,
                    ItemProgress.attempts > 0,
                ),
            )
            .where(model.chapter_id.is_not(None))
            .group_by(model.chapter_id)
        ).subquery()

    vocabulary = coverage_counts(
        VocabularySource, "vocabulary", VocabularySource.vocabulary_id
    )
    strength = kanji_strength_subquery()
    kanji_effective_rows = (
        select(
            KanjiSource.chapter_id.label("chapter_id"),
            KanjiSource.id.label("source_id"),
            strength.c.status,
        )
        .join(strength, strength.c.source_id == KanjiSource.id)
        .where(KanjiSource.chapter_id.is_not(None))
    ).subquery()
    kanji = (
        select(
            kanji_effective_rows.c.chapter_id,
            func.count(kanji_effective_rows.c.source_id).label("total"),
            func.count(kanji_effective_rows.c.source_id)
            .filter(kanji_effective_rows.c.status != "new")
            .label("practiced"),
            func.count(kanji_effective_rows.c.source_id)
            .filter(kanji_effective_rows.c.status == "mastered")
            .label("mastered"),
        )
        .group_by(kanji_effective_rows.c.chapter_id)
    ).subquery()
    vocab_lacking = (
        select(
            VocabularySource.chapter_id,
            func.count(VocabularySource.id).filter(VocabularySource.knowledge_status == "unknown").label("unknown"),
            func.count(VocabularySource.id).filter(VocabularySource.knowledge_status == "known").label("known"),
            func.count(VocabularySource.id).filter(ItemProgress.status == "weak").label("weak"),
        )
        .outerjoin(ItemProgress, and_(ItemProgress.item_type == "vocabulary", ItemProgress.item_id == VocabularySource.vocabulary_id))
        .where(VocabularySource.chapter_id.is_not(None))
        .group_by(VocabularySource.chapter_id)
    ).subquery()
    kanji_lacking = (
        select(
            kanji_effective_rows.c.chapter_id,
            func.count(kanji_effective_rows.c.source_id)
            .filter(kanji_effective_rows.c.status == "weak")
            .label("weak"),
        )
        .group_by(kanji_effective_rows.c.chapter_id)
    ).subquery()
    example_lacking = (
        select(
            KanjiSource.chapter_id,
            func.count(KanjiExample.id).label("total"),
            func.count(KanjiExample.id).filter(KanjiExample.knowledge_status == "unknown").label("unknown"),
            func.count(KanjiExample.id).filter(KanjiExample.knowledge_status == "known").label("known"),
            func.count(KanjiExample.id).filter(ItemProgress.attempts > 0).label("practiced"),
            func.count(KanjiExample.id).filter(ItemProgress.status == "mastered").label("mastered"),
            func.count(KanjiExample.id).filter(ItemProgress.status == "weak").label("weak"),
        )
        .join(KanjiExample, KanjiExample.kanji_source_id == KanjiSource.id)
        .outerjoin(ItemProgress, and_(ItemProgress.item_type == "kanji_example", ItemProgress.item_id == KanjiExample.canonical_id))
        .where(KanjiSource.chapter_id.is_not(None))
        .group_by(KanjiSource.chapter_id)
    ).subquery()
    example_source_rollup = (
        select(
            KanjiSource.chapter_id.label("chapter_id"),
            KanjiSource.id.label("source_id"),
            func.count(func.distinct(KanjiExample.canonical_id)).label("total"),
            func.count(func.distinct(KanjiExample.canonical_id))
            .filter(ItemProgress.status == "mastered")
            .label("mastered"),
        )
        .join(KanjiExample, KanjiExample.kanji_source_id == KanjiSource.id)
        .outerjoin(
            ItemProgress,
            and_(
                ItemProgress.item_type == "kanji_example",
                ItemProgress.item_id == KanjiExample.canonical_id,
            ),
        )
        .where(KanjiSource.chapter_id.is_not(None))
        .group_by(KanjiSource.chapter_id, KanjiSource.id)
    ).subquery()
    completed_example_sets = (
        select(
            example_source_rollup.c.chapter_id,
            func.count(example_source_rollup.c.source_id)
            .filter(
                and_(
                    example_source_rollup.c.total > 0,
                    example_source_rollup.c.mastered
                    == example_source_rollup.c.total,
                )
            )
            .label("completed"),
        )
        .group_by(example_source_rollup.c.chapter_id)
    ).subquery()
    rows = []
    stmt = (
        select(
            Chapter,
            Book,
            func.coalesce(vocabulary.c.total, 0),
            func.coalesce(vocabulary.c.practiced, 0),
            func.coalesce(vocabulary.c.mastered, 0),
            func.coalesce(kanji.c.total, 0),
            func.coalesce(kanji.c.practiced, 0),
            func.coalesce(kanji.c.mastered, 0),
            func.coalesce(vocab_lacking.c.unknown, 0),
            func.coalesce(vocab_lacking.c.known, 0),
            func.coalesce(vocab_lacking.c.weak, 0),
            func.coalesce(example_lacking.c.total, 0),
            func.coalesce(example_lacking.c.unknown, 0),
            func.coalesce(example_lacking.c.known, 0),
            func.coalesce(example_lacking.c.practiced, 0),
            func.coalesce(example_lacking.c.mastered, 0),
            func.coalesce(example_lacking.c.weak, 0),
            func.coalesce(completed_example_sets.c.completed, 0),
            func.coalesce(kanji_lacking.c.weak, 0),
        )
        .join(Book)
        .where(Book.is_active.is_(True))
        .outerjoin(vocabulary, vocabulary.c.chapter_id == Chapter.id)
        .outerjoin(kanji, kanji.c.chapter_id == Chapter.id)
        .outerjoin(vocab_lacking, vocab_lacking.c.chapter_id == Chapter.id)
        .outerjoin(example_lacking, example_lacking.c.chapter_id == Chapter.id)
        .outerjoin(completed_example_sets, completed_example_sets.c.chapter_id == Chapter.id)
        .outerjoin(kanji_lacking, kanji_lacking.c.chapter_id == Chapter.id)
        .order_by(Book.title, Chapter.sort_order)
    )
    for (
        chapter,
        book,
        vocab_total,
        vocab_practiced,
        vocab_mastered,
        kanji_total,
        kanji_practiced,
        kanji_mastered,
        vocab_unknown,
        vocab_known,
        vocab_weak,
        example_total,
        example_unknown,
        example_known,
        example_practiced,
        example_mastered,
        example_weak,
        example_sets_mastered,
        kanji_weak,
    ) in db.execute(stmt):
        rows.append(
            CoverageChapter(
                book_id=book.id,
                book_title=book.title,
                chapter_id=chapter.id,
                chapter_title=chapter.title,
                chapter_number=chapter.chapter_number,
                chapter_part=chapter.part,
                chapter_sort_order=chapter.sort_order,
                vocabulary_mastered_percent=round(
                    (vocab_mastered / vocab_total * 100) if vocab_total else 0, 1
                ),
                kanji_mastered_percent=round(
                    (kanji_mastered / kanji_total * 100) if kanji_total else 0, 1
                ),
                vocabulary_total=vocab_total,
                vocabulary_practiced=vocab_practiced,
                vocabulary_mastered=vocab_mastered,
                vocabulary_unknown=vocab_unknown,
                vocabulary_known=vocab_known,
                vocabulary_weak=vocab_weak,
                kanji_example_total=example_total,
                kanji_total=kanji_total,
                kanji_practiced=kanji_practiced,
                kanji_mastered=kanji_mastered,
                kanji_example_unknown=example_unknown,
                kanji_example_known=example_known,
                kanji_example_practiced=example_practiced,
                kanji_example_mastered=example_mastered,
                kanji_example_weak=example_weak,
                kanji_example_sets_mastered=example_sets_mastered,
                kanji_weak=kanji_weak,
            )
        )
    return rows


def progress_items(book_id, material, status, chapter_id, search, page, page_size, db):
    progress_row = aliased(ItemProgress)
    conditions = []
    if material == "vocabulary":
        source = VocabularySource
        item_status = case((func.coalesce(progress_row.attempts, 0) == 0, "new"), else_=progress_row.status)
        stmt = select(
            source.id, func.coalesce(source.source_id, cast(source.id, String)), source.expression_as_printed, source.reading_as_printed,
            source.meaning_as_printed, Chapter.id, Chapter.chapter_number, Chapter.title,
            Chapter.part, Chapter.sort_order, source.item_order, item_status,
        ).select_from(source).join(Chapter, Chapter.id == source.chapter_id).outerjoin(
            progress_row, and_(progress_row.item_type == "vocabulary", progress_row.item_id == source.vocabulary_id)
        )
        conditions.append(source.book_id == book_id)
        search_columns = (source.expression_as_printed, source.reading_as_printed, source.meaning_as_printed)
        study_kind = "vocabulary"
    elif material == "kanji_examples":
        source = KanjiSource
        item_status = case((func.coalesce(progress_row.attempts, 0) == 0, "new"), else_=progress_row.status)
        stmt = select(
            KanjiExample.id, func.coalesce(source.source_id, cast(source.id, String)), KanjiExample.word, KanjiExample.reading,
            KanjiExample.meaning, Chapter.id, Chapter.chapter_number, Chapter.title,
            Chapter.part, Chapter.sort_order, KanjiExample.sort_order, item_status,
        ).select_from(KanjiExample).join(source, source.id == KanjiExample.kanji_source_id).join(
            Chapter, Chapter.id == source.chapter_id
        ).outerjoin(
            progress_row, and_(progress_row.item_type == "kanji_example", progress_row.item_id == KanjiExample.canonical_id)
        )
        conditions.append(source.book_id == book_id)
        search_columns = (KanjiExample.word, KanjiExample.reading, KanjiExample.meaning)
        study_kind = "kanji"
    else:
        source = KanjiSource
        strength = kanji_strength_subquery()
        item_status = strength.c.status
        stmt = select(
            source.id, func.coalesce(source.source_id, cast(source.id, String)), Kanji.character, literal(""),
            source.meaning_as_printed, Chapter.id, Chapter.chapter_number, Chapter.title,
            Chapter.part, Chapter.sort_order, source.item_order, item_status,
        ).select_from(source).join(Kanji, Kanji.id == source.kanji_id).join(
            Chapter, Chapter.id == source.chapter_id
        ).join(strength, strength.c.source_id == source.id)
        conditions.append(source.book_id == book_id)
        search_columns = (Kanji.character, source.meaning_as_printed)
        study_kind = "kanji"

    if chapter_id is not None:
        conditions.append(Chapter.id == chapter_id)
    conditions.append(item_status == status)
    term = search.strip()
    if term:
        pattern = f"%{term}%"
        conditions.append(or_(*(column.ilike(pattern) for column in search_columns)))
    filtered = stmt.where(*conditions)
    count = db.scalar(select(func.count()).select_from(filtered.subquery())) or 0
    rows = db.execute(
        filtered.order_by(Chapter.sort_order, Chapter.chapter_number, source.item_order if material != "kanji_examples" else KanjiExample.sort_order)
        .offset((page - 1) * page_size).limit(page_size)
    )
    items = []
    for row in rows:
        item_id, source_id, content, reading, meaning, row_chapter_id, number, title, part, _, _, row_status = row
        items.append({
            "id": item_id, "content": content, "reading": reading, "meaning": meaning,
            "status": row_status, "chapter_id": row_chapter_id, "chapter_number": number,
            "chapter_title": title, "chapter_part": part, "study_kind": study_kind,
            "study_source_id": source_id or str(item_id),
        })
    return {"items": items, "total": count, "page": page, "page_size": page_size}
