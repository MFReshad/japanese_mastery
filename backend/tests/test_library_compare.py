from app.models.book import Book, Chapter
from app.models.item import Kanji, KanjiExample, KanjiSource, Vocabulary, VocabularySource
from app.models.practice import ItemProgress


def test_compare_returns_shared_and_unmatched_items(client, db_session):
    first = Book(title="Book One", short_name="ONE")
    second = Book(title="Book Two", short_name="TWO")
    db_session.add_all([first, second])
    db_session.flush()
    first_chapter = Chapter(book_id=first.id, chapter_number=1, title="First", sort_order=1)
    second_chapter = Chapter(book_id=second.id, chapter_number=3, title="Third", sort_order=3)
    db_session.add_all([first_chapter, second_chapter])
    db_session.flush()
    shared = Vocabulary(expression="住む", reading="すむ", normalized_expression="住む", normalized_reading="すむ")
    unmatched = Vocabulary(expression="山", reading="やま", normalized_expression="山", normalized_reading="やま")
    db_session.add_all([shared, unmatched])
    db_session.flush()
    db_session.add_all([
        VocabularySource(vocabulary_id=shared.id, book_id=first.id, chapter_id=first_chapter.id, item_order=1,
                         expression_as_printed="住む", reading_as_printed="すむ", meaning_as_printed="to live"),
        VocabularySource(vocabulary_id=shared.id, book_id=second.id, chapter_id=second_chapter.id, item_order=2,
                         expression_as_printed="住む", reading_as_printed="すむ", meaning_as_printed="to reside"),
        VocabularySource(vocabulary_id=unmatched.id, book_id=first.id, chapter_id=first_chapter.id, item_order=2,
                         expression_as_printed="山", reading_as_printed="やま", meaning_as_printed="mountain"),
    ])
    db_session.add(ItemProgress(item_type="vocabulary", item_id=shared.id, is_starred=True))
    db_session.commit()

    response = client.get(
        f"/library/compare?kind=vocabulary&book_ids={first.id}&book_ids={second.id}"
    )
    assert response.status_code == 200
    items = response.json()["items"]
    shared_items = [item for item in items if item["display"] == "住む"]
    unmatched_items = [item for item in items if item["display"] == "山"]
    assert {item["book_id"] for item in shared_items} == {first.id, second.id}
    assert len({item["match_key"] for item in shared_items}) == 1
    assert all(item["is_important"] is True for item in shared_items)
    assert {item["book_id"] for item in unmatched_items} == {first.id}
    assert unmatched_items[0]["is_important"] is False


def test_kanji_library_searches_example_word_reading_and_meaning(client, db_session):
    book = Book(title="Kanji Book", short_name="KANJI")
    db_session.add(book)
    db_session.flush()
    chapter = Chapter(book_id=book.id, chapter_number=1, title="First", sort_order=1)
    kanji = Kanji(character="住")
    db_session.add_all([chapter, kanji])
    db_session.flush()
    source = KanjiSource(
        kanji_id=kanji.id,
        book_id=book.id,
        chapter_id=chapter.id,
        item_order=1,
        meaning_as_printed="reside",
        meanings_as_printed=["reside"],
        onyomi_as_printed=["ジュウ"],
        kunyomi_as_printed=["す.む"],
    )
    db_session.add(source)
    db_session.flush()
    db_session.add(KanjiExample(
        kanji_source_id=source.id,
        word="住民",
        reading="じゅうみん",
        meaning="inhabitants",
        sort_order=1,
    ))
    db_session.commit()

    for term in ("住民", "じゅうみん", "inhabitants"):
        result = client.get(f"/library/items?kind=kanji&book_id={book.id}&search={term}").json()
        assert result["total"] == 1
        assert result["items"][0]["character"] == "住"
        assert result["items"][0]["matching_examples"][0]["word"] == "住民"
