from __future__ import annotations
from app.services.lookup_cache import lookup_cache

import json
import logging
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.book import Book, Chapter
from app.models.item import (
    SourceSuppression,
    Kanji,
    KanjiExample,
    KanjiSource,
    Vocabulary,
    VocabularySource,
)
from app.repositories.items import normalize_text
from app.services.integrity import meaning_fields


SOURCE_FIELDS = {
    "books": {"id", "title", "edition", "note", "short_name", "is_demo"},
    "chapters": {
        "id",
        "book_id",
        "chapter_number",
        "part",
        "title",
        "title_as_printed",
        "has_vocabulary",
        "has_kanji",
        "sort_order",
    },
    "vocabulary": {"id", "expression", "reading"},
    "kanji": {"id", "character"},
    "vocabulary_sources": {
        "id",
        "vocabulary_id",
        "book_id",
        "chapter_id",
        "book",
        "chapter",
        "item_order",
        "expression_as_printed",
        "reading_as_printed",
        "meaning_as_printed",
        "meanings_as_printed",
        "source_file",
        "source_line",
        "source_page",
        "repaired",
        "repair_note",
        "raw_line",
    },
    "kanji_sources": {
        "id",
        "kanji_id",
        "book_id",
        "chapter_id",
        "book",
        "chapter",
        "part",
        "item_order",
        "entry_number_as_printed",
        "chapter_title_as_printed",
        "meaning_as_printed",
        "meanings_as_printed",
        "onyomi_as_printed",
        "kunyomi_as_printed",
        "stroke_count_as_printed",
        "examples",
        "source_file",
        "source_page",
        "source_book_page",
        "source_section",
        "chapter_inferred",
        "uncertain",
        "notes",
        "extraction_batch",
    },
}


@dataclass
class ImportStats:
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    conflicts: int = 0
    preserved_overrides: int = 0
    suppressed: int = 0
    errors: list[str] = field(default_factory=list)
    plan: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "would_insert": self.inserted,
            "would_update": self.updated,
            "would_skip": self.skipped,
            "conflict_count": self.conflicts,
            "preserved_overrides": self.preserved_overrides,
            "suppressed_records": self.suppressed,
            "errors": self.errors,
            "plan": self.plan,
        }


def _read_json(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise ValueError(f"Required import file is missing: {path.name}")
    data = json.loads(path.read_text())
    if not isinstance(data, list):
        raise ValueError(f"{path.name} must contain a JSON array")
    return data


def _set_fields(instance: Any, fields: dict[str, Any]) -> bool:
    changed = False
    for key, value in fields.items():
        if getattr(instance, key) != value:
            setattr(instance, key, value)
            changed = True
    return changed


def _record(
    stats: ImportStats, existing: bool, changed: bool = False, source_id=None
) -> None:
    stats.plan.append(
        {
            "source_id": source_id,
            "action": "insert" if not existing else "update" if changed else "skip",
        }
    )
    if not existing:
        stats.inserted += 1
    elif changed:
        stats.updated += 1
    else:
        stats.skipped += 1


def _required(
    row: dict[str, Any], fields: tuple[str, ...], label: str, stats: ImportStats
) -> bool:
    missing = [name for name in fields if row.get(name) is None]
    if missing:
        stats.errors.append(
            f"{label} {row.get('id', '<unknown>')} missing: {', '.join(missing)}"
        )
        return False
    return True


def import_directory(
    db: Session, directory: Path, dry_run: bool = True
) -> dict[str, Any]:
    names = (
        "books",
        "chapters",
        "vocabulary",
        "kanji",
        "vocabulary_sources",
        "kanji_sources",
    )
    stats = {name: ImportStats() for name in names}
    transaction = db.begin_nested()
    fatal_error: str | None = None
    try:
        for name in names:
            if (
                not (directory / f"{name}.json")
                .resolve()
                .is_relative_to(directory.resolve())
            ):
                raise ValueError("Import files must stay within the selected directory")
        rows = {name: _read_json(directory / f"{name}.json") for name in names}
        for name, entries in rows.items():
            seen = set()
            for index, row in enumerate(entries):
                if not isinstance(row, dict):
                    raise ValueError(f"{name}.json row {index} must be an object")
                if row.get("id") in seen:
                    raise ValueError(
                        f"{name}.json has duplicate source id: {row.get('id')}"
                    )
                seen.add(row.get("id"))
                unknown = set(row) - SOURCE_FIELDS[name]
                if unknown:
                    raise ValueError(
                        f"{name}.json row {index} has unpersisted fields: {', '.join(sorted(unknown))}"
                    )
                if name == "kanji_sources":
                    for example in row.get("examples", []):
                        unknown_example = set(example) - {
                            "word",
                            "reading",
                            "meaning",
                            "sort_order",
                        }
                        if unknown_example:
                            raise ValueError(
                                f"Kanji source {row.get('id')} has unpersisted example fields: {', '.join(sorted(unknown_example))}"
                            )
        _import_books(db, rows["books"], stats["books"])
        _import_chapters(db, rows["chapters"], stats["chapters"])
        _import_vocabulary(db, rows["vocabulary"], stats["vocabulary"])
        _import_kanji(db, rows["kanji"], stats["kanji"])
        _import_vocabulary_sources(
            db, rows["vocabulary_sources"], stats["vocabulary_sources"]
        )
        _import_kanji_sources(db, rows["kanji_sources"], stats["kanji_sources"])
        error_count = sum(len(item.errors) for item in stats.values())
        if error_count:
            fatal_error = f"Import validation failed with {error_count} error(s)"
            transaction.rollback()
        elif dry_run:
            transaction.rollback()
        else:
            transaction.commit()
            db.commit()
            lookup_cache.invalidate_progress()
    except Exception as exc:
        if transaction.is_active:
            transaction.rollback()
        db.rollback()
        if isinstance(exc, (ValueError, OSError)):
            fatal_error = (
                str(exc) if isinstance(exc, ValueError) else "Cannot read import files"
            )
        else:
            logging.getLogger(__name__).error(
                "Import failed (%s)\n%s",
                type(exc).__name__,
                "".join(traceback.format_tb(exc.__traceback__)),
            )
            fatal_error = "Import failed; no changes were saved"
        stats["books"].errors.append(fatal_error)

    if fatal_error:
        for item in stats.values():
            item.inserted = item.updated = item.skipped = 0
            item.plan.clear()

    result = {key: value.as_dict() for key, value in stats.items()}
    result["summary"] = {
        "dry_run": dry_run,
        "rolled_back": dry_run or fatal_error is not None,
        "fatal_error": fatal_error,
    }
    return result


def _import_books(db: Session, rows: list[dict[str, Any]], stats: ImportStats) -> None:
    by_source = {
        item.source_id: item for item in db.scalars(select(Book)) if item.source_id
    }
    for row in rows:
        if not _required(row, ("id", "title"), "Book", stats):
            continue
        item = by_source.get(row["id"])
        fields = {
            "title": row["title"],
            "edition": row.get("edition"),
            "note": row.get("note"),
            "short_name": row.get("short_name"),
            "is_demo": row.get("is_demo", False),
        }
        existed = item is not None
        if item:
            changed = _set_fields(item, fields)
        else:
            item, changed = Book(source_id=row["id"], **fields), False
            db.add(item)
            by_source[row["id"]] = item
        _record(stats, existed, changed, row["id"])
    db.flush()


def _import_chapters(
    db: Session, rows: list[dict[str, Any]], stats: ImportStats
) -> None:
    books = {
        item.source_id: item for item in db.scalars(select(Book)) if item.source_id
    }
    by_source = {
        item.source_id: item
        for item in db.scalars(select(Chapter).order_by(Chapter.id).with_for_update())
        if item.source_id
    }
    for row in rows:
        if not _required(
            row, ("id", "book_id", "chapter_number", "title"), "Chapter", stats
        ):
            continue
        book = books.get(row["book_id"])
        if not book:
            stats.errors.append(
                f"Chapter {row['id']} references unknown book {row['book_id']}"
            )
            continue
        item = by_source.get(row["id"])
        if (
            item
            and item.book_id != book.id
            and (
                db.scalar(
                    select(VocabularySource.id)
                    .where(VocabularySource.chapter_id == item.id)
                    .limit(1)
                )
                or db.scalar(
                    select(KanjiSource.id)
                    .where(KanjiSource.chapter_id == item.id)
                    .limit(1)
                )
            )
        ):
            stats.errors.append(f"Chapter {row['id']} cannot move while populated")
            continue
        fields = {
            "book_id": book.id,
            "chapter_number": row["chapter_number"],
            "title": row["title"],
            "part": row.get("part"),
            "title_as_printed": row.get("title_as_printed"),
            "has_vocabulary": row.get("has_vocabulary"),
            "has_kanji": row.get("has_kanji"),
            "sort_order": row.get("sort_order", row["chapter_number"]),
        }
        existed = item is not None
        if item:
            changed = _set_fields(item, fields)
        else:
            item, changed = Chapter(source_id=row["id"], **fields), False
            db.add(item)
            by_source[row["id"]] = item
        _record(stats, existed, changed, row["id"])
    db.flush()


def _import_vocabulary(
    db: Session, rows: list[dict[str, Any]], stats: ImportStats
) -> None:
    existing_items = db.scalars(select(Vocabulary)).all()
    by_source = {item.source_id: item for item in existing_items if item.source_id}
    by_natural = {
        (item.normalized_expression, item.normalized_reading): item
        for item in existing_items
    }
    for row in rows:
        if not _required(row, ("id", "expression", "reading"), "Vocabulary", stats):
            continue
        item = by_source.get(row["id"])
        fields = {
            "expression": row["expression"],
            "reading": row["reading"],
            "normalized_expression": normalize_text(row["expression"]),
            "normalized_reading": normalize_text(row["reading"]),
        }
        existed = item is not None
        if item and (item.normalized_expression, item.normalized_reading) != (
            fields["normalized_expression"],
            fields["normalized_reading"],
        ):
            stats.conflicts += 1
            stats.errors.append(
                f"Vocabulary {row['id']} changes canonical identity; explicitly relink occurrences first"
            )
            continue
        natural = by_natural.get(
            (fields["normalized_expression"], fields["normalized_reading"])
        )
        if natural and natural is not item:
            if natural.source_id is not None:
                stats.conflicts += 1
                stats.errors.append(
                    f"Vocabulary {row['id']} conflicts with {natural.source_id}"
                )
                continue
            item, existed = natural, True
            item.source_id = row["id"]
            by_source[row["id"]] = item
            changed = _set_fields(item, fields)
            _record(stats, existed, True, row["id"])
            continue
        if item:
            changed = _set_fields(item, fields)
        else:
            item, changed = Vocabulary(source_id=row["id"], **fields), False
            db.add(item)
            by_source[row["id"]] = item
            by_natural[
                (fields["normalized_expression"], fields["normalized_reading"])
            ] = item
        _record(stats, existed, changed, row["id"])
    db.flush()


def _import_kanji(db: Session, rows: list[dict[str, Any]], stats: ImportStats) -> None:
    existing_items = db.scalars(select(Kanji)).all()
    by_source = {item.source_id: item for item in existing_items if item.source_id}
    by_character = {item.character: item for item in existing_items}
    for row in rows:
        if not _required(row, ("id", "character"), "Kanji", stats):
            continue
        item = by_source.get(row["id"])
        fields = {"character": row["character"]}
        existed = item is not None
        if item and item.character != row["character"]:
            stats.conflicts += 1
            stats.errors.append(f"Kanji {row['id']} changes canonical identity")
            continue
        natural = by_character.get(row["character"])
        if natural and natural is not item:
            if natural.source_id is not None:
                stats.conflicts += 1
                stats.errors.append(
                    f"Kanji {row['id']} conflicts with {natural.source_id}"
                )
                continue
            item, existed = natural, True
            item.source_id = row["id"]
            by_source[row["id"]] = item
            _set_fields(item, fields)
            _record(stats, existed, True, row["id"])
            continue
        if item:
            changed = _set_fields(item, fields)
        else:
            item, changed = Kanji(source_id=row["id"], **fields), False
            db.add(item)
            by_source[row["id"]] = item
            by_character[row["character"]] = item
        _record(stats, existed, changed, row["id"])
    db.flush()


def _import_vocabulary_sources(
    db: Session, rows: list[dict[str, Any]], stats: ImportStats
) -> None:
    required = (
        "id",
        "vocabulary_id",
        "book_id",
        "item_order",
        "expression_as_printed",
        "reading_as_printed",
        "meaning_as_printed",
    )
    vocabularies = {
        item.source_id: item
        for item in db.scalars(select(Vocabulary))
        if item.source_id
    }
    books = {
        item.source_id: item for item in db.scalars(select(Book)) if item.source_id
    }
    chapters = {
        item.source_id: item
        for item in db.scalars(select(Chapter).order_by(Chapter.id).with_for_update())
        if item.source_id
    }
    by_source = {
        item.source_id: item
        for item in db.scalars(
            select(VocabularySource).order_by(VocabularySource.id).with_for_update()
        )
        if item.source_id
    }
    suppressed = set(
        db.scalars(
            select(SourceSuppression.source_id).where(
                SourceSuppression.item_type == "vocabulary"
            )
        )
    )
    for row in rows:
        if row.get("id") in suppressed:
            stats.suppressed += 1
            stats.plan.append({"source_id": row["id"], "action": "suppressed"})
            continue
        if not _required(row, required, "Vocabulary source", stats):
            continue
        vocab = vocabularies.get(row["vocabulary_id"])
        book = books.get(row["book_id"])
        chapter = chapters.get(row.get("chapter_id"))
        if (
            not vocab
            or not book
            or (row.get("chapter_id") and not chapter)
            or (chapter and book and chapter.book_id != book.id)
        ):
            stats.errors.append(
                f"Vocabulary source {row['id']} has an unresolved foreign key"
            )
            continue
        item = by_source.get(row["id"])
        fields = {
            "vocabulary_id": vocab.id,
            "book_id": book.id,
            "chapter_id": chapter.id if chapter else None,
            "book_as_printed": row.get("book"),
            "chapter_as_printed": row.get("chapter"),
            "expression_as_printed": row["expression_as_printed"],
            "reading_as_printed": row["reading_as_printed"],
            "meaning_as_printed": row["meaning_as_printed"],
            "meanings_as_printed": row.get("meanings_as_printed", []),
            "source_file": row.get("source_file"),
            "source_line": row.get("source_line"),
            "source_page": str(row["source_page"])
            if row.get("source_page") is not None
            else None,
            "source_page_as_imported": row.get("source_page"),
            "repaired": row.get("repaired"),
            "repair_note": row.get("repair_note"),
            "raw_line": row.get("raw_line"),
        }
        existed = item is not None
        if item:
            fields["original_item_order"] = row["item_order"]
            changed = _merge_source(item, fields, stats)
        else:
            fields["imported_baseline"] = dict(fields)
            item, changed = (
                VocabularySource(
                    source_id=row["id"],
                    item_order=row["item_order"],
                    original_item_order=row["item_order"],
                    **fields,
                ),
                False,
            )
            db.add(item)
            by_source[row["id"]] = item
        baseline = dict(item.imported_baseline or {})
        baseline.setdefault("_original_source", row)
        baseline["_source"] = row
        item.imported_baseline = baseline
        _record(stats, existed, changed, row["id"])
    db.flush()


def _example_values(source: KanjiSource) -> list[dict[str, Any]]:
    return [
        {
            "word": e.word,
            "reading": e.reading,
            "meaning": e.meaning,
            "sort_order": e.sort_order,
        }
        for e in sorted(source.examples, key=lambda e: (e.sort_order, e.id or 0))
    ]


def _import_kanji_sources(
    db: Session, rows: list[dict[str, Any]], stats: ImportStats
) -> None:
    required = ("id", "kanji_id", "book_id", "item_order", "meaning_as_printed")
    kanji_items = {
        item.source_id: item for item in db.scalars(select(Kanji)) if item.source_id
    }
    books = {
        item.source_id: item for item in db.scalars(select(Book)) if item.source_id
    }
    chapters = {
        item.source_id: item
        for item in db.scalars(select(Chapter).order_by(Chapter.id).with_for_update())
        if item.source_id
    }
    by_source = {
        item.source_id: item
        for item in db.scalars(
            select(KanjiSource)
            .options(selectinload(KanjiSource.examples))
            .order_by(KanjiSource.id)
            .with_for_update()
        )
        if item.source_id
    }
    suppressed = set(
        db.scalars(
            select(SourceSuppression.source_id).where(
                SourceSuppression.item_type == "kanji"
            )
        )
    )
    for row in rows:
        if row.get("id") in suppressed:
            stats.suppressed += 1
            stats.plan.append({"source_id": row["id"], "action": "suppressed"})
            continue
        if not _required(row, required, "Kanji source", stats):
            continue
        kanji = kanji_items.get(row["kanji_id"])
        book = books.get(row["book_id"])
        chapter = chapters.get(row.get("chapter_id"))
        if (
            not kanji
            or not book
            or (row.get("chapter_id") and not chapter)
            or (chapter and book and chapter.book_id != book.id)
        ):
            stats.errors.append(
                f"Kanji source {row['id']} has an unresolved foreign key"
            )
            continue
        item = by_source.get(row["id"])
        fields = {
            "kanji_id": kanji.id,
            "book_id": book.id,
            "chapter_id": chapter.id if chapter else None,
            "item_order": row["item_order"],
            "book_as_printed": row.get("book"),
            "chapter_as_printed": row.get("chapter"),
            "part": row.get("part"),
            "entry_number_as_printed": row.get("entry_number_as_printed"),
            "chapter_title_as_printed": row.get("chapter_title_as_printed"),
            "meaning_as_printed": row["meaning_as_printed"],
            "meanings_as_printed": row.get("meanings_as_printed", []),
            "onyomi_as_printed": row.get("onyomi_as_printed", []),
            "kunyomi_as_printed": row.get("kunyomi_as_printed", []),
            "stroke_count_as_printed": row.get("stroke_count_as_printed"),
            "source_file": row.get("source_file"),
            "source_page": str(row["source_page"])
            if row.get("source_page") is not None
            else None,
            "source_page_as_imported": row.get("source_page"),
            "source_book_page": row.get("source_book_page"),
            "source_section": row.get("source_section"),
            "chapter_inferred": row.get("chapter_inferred"),
            "uncertain": row.get("uncertain"),
            "notes": row.get("notes"),
            "extraction_batch": row.get("extraction_batch"),
        }
        fields.update(
            meaning_fields(
                row["meaning_as_printed"], row.get("meanings_as_printed") or None
            )
        )
        examples = sorted(
            [
                dict(example, sort_order=example.get("sort_order", index))
                for index, example in enumerate(row.get("examples", []))
            ],
            key=lambda e: e["sort_order"],
        )
        existed = item is not None
        changed = False
        if item:
            prior = item.imported_baseline or {}
            overrides = dict(item.manual_overrides or {})
            if "examples" not in prior and _example_values(item) != examples:
                overrides["examples"] = _example_values(item)
            item.manual_overrides = overrides
            changed = _merge_source(item, fields, stats)
            item.imported_baseline = {**item.imported_baseline, "examples": examples}
            if "examples" in overrides:
                stats.preserved_overrides += 1
                if overrides["examples"] != examples:
                    stats.conflicts += 1
                examples = overrides["examples"]
            examples_changed = _example_values(item) != examples
            changed = changed or examples_changed
        else:
            item = KanjiSource(
                source_id=row["id"],
                imported_baseline={**fields, "examples": examples},
                **fields,
            )
            db.add(item)
            by_source[row["id"]] = item
            examples_changed = True
        if examples_changed:
            preferences = {
                (example.word, example.reading, example.meaning): (
                    example.is_important,
                    example.knowledge_status,
                )
                for example in item.examples
            }
            item.examples.clear()
            item.examples.extend(
                KanjiExample(
                    **example,
                    is_important=preferences.get(
                        (example["word"], example["reading"], example["meaning"]),
                        (False, None),
                    )[0],
                    knowledge_status=preferences.get(
                        (example["word"], example["reading"], example["meaning"]),
                        (False, None),
                    )[1],
                )
                for example in examples
            )
        baseline = dict(item.imported_baseline or {})
        baseline.setdefault("_original_source", row)
        baseline["_source"] = row
        item.imported_baseline = baseline
        _record(stats, existed, changed, row["id"])
    db.flush()


EDITABLE = {
    "expression_as_printed",
    "reading_as_printed",
    "meaning_as_printed",
    "meanings_as_printed",
    "notes",
    "onyomi_as_printed",
    "kunyomi_as_printed",
    "uncertain",
    "source_page",
    "source_section",
    "item_order",
    "chapter_id",
}


def _merge_source(item, fields, stats):
    baseline = item.imported_baseline
    overrides = dict(item.manual_overrides or {})
    for key, value in fields.items():
        if key in EDITABLE and baseline is None and getattr(item, key) != value:
            overrides.setdefault(key, getattr(item, key))
    effective = dict(fields)
    for key, value in overrides.items():
        if key in effective:
            stats.preserved_overrides += 1
            if baseline and baseline.get(key) != fields[key] and value != fields[key]:
                stats.conflicts += 1
            effective[key] = value
    item.imported_baseline = {
        **{k: v for k, v in (baseline or {}).items() if k.startswith("_")},
        **fields,
    }
    item.manual_overrides = overrides
    return _set_fields(item, effective)
