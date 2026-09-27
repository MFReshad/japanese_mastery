from sqlalchemy import event, select

from app.models.book import Book, Chapter
from app.models.item import Kanji, KanjiExample, KanjiSource, Vocabulary, VocabularySource
from app.models.practice import ItemProgress


def seed_chapter(db_session, count=60):
    book = Book(title="Measured Book", short_name="MEASURED")
    db_session.add(book)
    db_session.flush()
    chapter = Chapter(book_id=book.id, chapter_number=1, title="Measured Lesson", sort_order=1)
    db_session.add(chapter)
    db_session.flush()
    for position in range(1, count + 1):
        expression = f"語{position:03d}"
        vocabulary = Vocabulary(expression=expression, reading=expression,
            normalized_expression=expression, normalized_reading=expression)
        db_session.add(vocabulary)
        db_session.flush()
        db_session.add(VocabularySource(source_id=f"source_{position}", vocabulary_id=vocabulary.id,
            book_id=book.id, chapter_id=chapter.id, item_order=position,
            expression_as_printed=expression, reading_as_printed=expression,
            meaning_as_printed=f"meaning {position}", meanings_as_printed=[f"meaning {position}"]))
    db_session.commit()
    return book, chapter


def test_library_paginates_and_filters_in_database(client, db_session):
    book, chapter = seed_chapter(db_session)
    base = f"/library/items?kind=vocabulary&book_id={book.id}&chapter_id={chapter.id}"
    first = client.get(base).json()
    second = client.get(f"{base}&page=2").json()
    assert first["total"] == 60 and len(first["items"]) == 50
    assert [row["item_order"] for row in second["items"]] == list(range(51, 61))
    assert "notes" not in first["items"][0]
    assert "examples" not in first["items"][0]
    matching = client.get(f"{base}&search=meaning%2057").json()
    assert matching["total"] == 1 and matching["items"][0]["item_order"] == 57


def test_library_kanji_is_lightweight_and_searchable(client, db_session):
    book, chapter = seed_chapter(db_session, 1)
    kanji = Kanji(character="同")
    db_session.add(kanji)
    db_session.flush()
    source = KanjiSource(source_id="source_kanji_same", kanji_id=kanji.id, book_id=book.id,
        chapter_id=chapter.id, item_order=1, meaning_as_printed="same",
        meanings_as_printed=["same"], onyomi_as_printed=["ドウ", "トウ"], kunyomi_as_printed=["おな", "とも"])
    source.examples.append(KanjiExample(word="同じ", reading="おなじ", meaning="same"))
    db_session.add(source)
    db_session.commit()
    result = client.get(f"/library/items?kind=kanji&book_id={book.id}&search=同").json()
    assert result["total"] == 1
    assert result["items"][0]["onyomi"] == ["ドウ", "トウ"]
    assert result["items"][0]["kunyomi"] == ["おな", "とも"]
    assert "examples" not in result["items"][0]


def test_practice_start_limits_materialized_sources(client, db_session):
    book, chapter = seed_chapter(db_session)
    loaded = []
    def track(session, instance):
        if isinstance(instance, VocabularySource):
            loaded.append(instance.id)
    event.listen(type(db_session), "loaded_as_persistent", track)
    try:
        started = client.post("/practice/start", json={"practice_type": "vocabulary", "book_ids": [book.id],
            "chapter_ids": [chapter.id], "question_count": 10}).json()
    finally:
        event.remove(type(db_session), "loaded_as_persistent", track)
    assert len(started["questions"]) == 10
    assert len(loaded) <= 10
    assert all("answer_primary" not in question for question in started["questions"])


def test_progress_coverage_uses_bounded_queries(client, db_session):
    book, chapter = seed_chapter(db_session, 3)
    first = db_session.scalar(select(Vocabulary).where(Vocabulary.expression == "語001"))
    db_session.add(ItemProgress(item_type="vocabulary", item_id=first.id, status="mastered", attempts=5, correct_count=5, current_correct_streak=5))
    db_session.commit()
    statements = []
    def count(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)
    event.listen(db_session.bind, "before_cursor_execute", count)
    try:
        response = client.get("/progress/books")
    finally:
        event.remove(db_session.bind, "before_cursor_execute", count)
    assert response.status_code == 200
    assert len(statements) == 1
    assert response.json()[0]["vocabulary_mastered_percent"] == 33.3
