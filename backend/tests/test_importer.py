import json

from app.models.book import Book, Chapter
from app.models.item import Kanji, KanjiSource, Vocabulary, VocabularySource
from app.services.importer import import_directory


def dataset(tmp_path):
    rows = {
        "books": [{"id": "genki_1", "title": "Genki I", "note": "Original scan"}],
        "chapters": [{"id": "genki_1_lesson_00", "book_id": "genki_1", "chapter_number": 0,
                      "title": "Greetings", "part": 1, "has_vocabulary": True, "has_kanji": False}],
        "vocabulary": [{"id": "vocab_000001", "expression": "こんにちは", "reading": ""}],
        "kanji": [{"id": "kanji_食", "character": "食"}],
        "vocabulary_sources": [{"id": "source_vocab_000001", "vocabulary_id": "vocab_000001", "book_id": "genki_1",
                                "chapter_id": "genki_1_lesson_00", "item_order": 1, "expression_as_printed": "こんにちは",
                                "reading_as_printed": "", "meaning_as_printed": "hello", "meanings_as_printed": ["hello"],
                                "source_line": 4, "repaired": False, "raw_line": "こんにちは hello"}],
        "kanji_sources": [{"id": "source_kanji_000001", "kanji_id": "kanji_食", "book_id": "genki_1",
                           "chapter_id": "genki_1_lesson_00", "item_order": 1, "meaning_as_printed": "eat",
                           "onyomi_as_printed": ["ショク"], "kunyomi_as_printed": ["たべる"], "uncertain": True,
                           "examples": [{"word": "食べる", "reading": "たべる", "meaning": "to eat"}]}],
    }
    for name, values in rows.items():
        (tmp_path / f"{name}.json").write_text(json.dumps(values))
    return rows


def test_dry_run_preserves_database(tmp_path, db_session):
    dataset(tmp_path)
    result = import_directory(db_session, tmp_path, dry_run=True)
    assert result["summary"] == {"dry_run": True, "rolled_back": True, "fatal_error": None}
    assert all(result[name]["would_insert"] == 1 for name in (
        "books", "chapters", "vocabulary", "kanji", "vocabulary_sources", "kanji_sources"))
    assert db_session.query(Book).count() == 0


def test_idempotent_import_and_source_fields(tmp_path, db_session, client):
    dataset(tmp_path)
    first = import_directory(db_session, tmp_path, dry_run=False)
    assert first["summary"]["rolled_back"] is False
    assert db_session.query(Chapter).one().chapter_number == 0
    assert db_session.query(VocabularySource).one().original_item_order == 1
    assert db_session.query(Vocabulary).one().reading == ""
    assert db_session.query(VocabularySource).one().raw_line == "こんにちは hello"
    assert db_session.query(KanjiSource).one().uncertain is True
    assert db_session.query(KanjiSource).one().examples[0].word == "食べる"
    assert db_session.query(Kanji).one().source_id == "kanji_食"
    books_response = client.get("/books")
    assert books_response.status_code == 200
    assert books_response.json()[0]["short_name"] is None
    second = import_directory(db_session, tmp_path, dry_run=False)
    assert all(second[name]["would_skip"] == 1 for name in (
        "books", "chapters", "vocabulary", "kanji", "vocabulary_sources", "kanji_sources"))
    assert db_session.query(Book).count() == 1


def test_reimport_preserves_corrected_order(tmp_path, db_session):
    dataset(tmp_path)
    import_directory(db_session, tmp_path, dry_run=False)
    source = db_session.query(VocabularySource).one()
    source.item_order = 7
    source.manually_reordered = True
    db_session.commit()
    import_directory(db_session, tmp_path, dry_run=False)
    db_session.refresh(source)
    assert source.item_order == 7
    assert source.original_item_order == 1
    assert source.manually_reordered is True


def test_fatal_validation_rolls_back_everything(tmp_path, db_session):
    rows = dataset(tmp_path)
    rows["kanji_sources"][0]["kanji_id"] = "missing"
    (tmp_path / "kanji_sources.json").write_text(json.dumps(rows["kanji_sources"]))
    result = import_directory(db_session, tmp_path, dry_run=False)
    assert result["summary"]["rolled_back"] is True
    assert result["summary"]["fatal_error"]
    assert result["kanji_sources"]["errors"]
    assert db_session.query(Book).count() == 0


def test_unknown_source_fields_cannot_be_silently_lost(tmp_path, db_session):
    rows = dataset(tmp_path)
    rows["books"][0]["future_field"] = "retain me"
    (tmp_path / "books.json").write_text(json.dumps(rows["books"]))
    result = import_directory(db_session, tmp_path, dry_run=True)
    assert "unpersisted fields: future_field" in result["summary"]["fatal_error"]
    assert result["books"]["would_insert"] == 0
