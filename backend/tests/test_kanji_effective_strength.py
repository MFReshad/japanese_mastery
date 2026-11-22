from app.models.book import Book, Chapter
from app.models.item import Kanji, KanjiExample, KanjiSource
from app.models.practice import ItemProgress


def test_kanji_strength_uses_majority_of_all_example_words(client, db_session):
    book = Book(title="Strength Book")
    db_session.add(book)
    db_session.flush()
    chapter = Chapter(book_id=book.id, chapter_number=1, title="Strength")
    kanji = Kanji(character="学")
    db_session.add_all([chapter, kanji])
    db_session.flush()
    source = KanjiSource(
        source_id="strength-kanji",
        kanji_id=kanji.id,
        book_id=book.id,
        chapter_id=chapter.id,
        item_order=1,
        meaning_as_printed="study",
        meanings_as_printed=["study"],
        onyomi_as_printed=[],
        kunyomi_as_printed=[],
    )
    db_session.add(source)
    db_session.flush()
    examples = [
        KanjiExample(kanji_source_id=source.id, word="学校", reading="がっこう", meaning="school", sort_order=0),
        KanjiExample(kanji_source_id=source.id, word="学生", reading="がくせい", meaning="student", sort_order=1),
        KanjiExample(kanji_source_id=source.id, word="大学", reading="だいがく", meaning="university", sort_order=2),
    ]
    db_session.add_all(examples)
    db_session.flush()
    db_session.add_all([
        ItemProgress(item_type="kanji_example", item_id=examples[0].id, attempts=1, wrong_count=1, last_result="wrong", status="weak"),
        ItemProgress(item_type="kanji_example", item_id=examples[1].id, attempts=2, wrong_count=2, last_result="wrong", status="weak"),
    ])
    db_session.commit()

    listing = client.get(f"/library/items?kind=kanji&book_id={book.id}").json()
    assert listing["items"][0]["status"] == "weak"
    weak = client.get(f"/library/items?kind=kanji&book_id={book.id}&status=weak").json()
    assert [item["source_id"] for item in weak["items"]] == ["strength-kanji"]
    assert client.get(f"/library/items?kind=kanji&book_id={book.id}&status=new").json()["total"] == 0

    detail = client.get("/study/kanji/strength-kanji").json()
    assert detail["practice_status"] == "weak"
    assert detail["example_status_counts"] == {"new": 1, "learning": 0, "weak": 2, "mastered": 0}
    coverage = client.get("/progress/books").json()[0]
    assert coverage["kanji_practiced"] == 1
    assert coverage["kanji_weak"] == 1


def test_one_practiced_example_makes_parent_kanji_learning(client, db_session):
    book = Book(title="Learning Book")
    db_session.add(book)
    db_session.flush()
    kanji = Kanji(character="読")
    db_session.add(kanji)
    db_session.flush()
    source = KanjiSource(
        source_id="learning-kanji",
        kanji_id=kanji.id,
        book_id=book.id,
        item_order=1,
        meaning_as_printed="read",
        meanings_as_printed=["read"],
        onyomi_as_printed=[],
        kunyomi_as_printed=[],
    )
    db_session.add(source)
    db_session.flush()
    example = KanjiExample(kanji_source_id=source.id, word="読書", reading="どくしょ", meaning="reading", sort_order=0)
    untouched = KanjiExample(kanji_source_id=source.id, word="読む", reading="よむ", meaning="to read", sort_order=1)
    db_session.add_all([example, untouched])
    db_session.flush()
    db_session.add(ItemProgress(item_type="kanji_example", item_id=example.id, attempts=1, correct_count=1, last_result="correct", status="learning"))
    db_session.commit()

    listing = client.get(f"/library/items?kind=kanji&book_id={book.id}").json()
    assert listing["items"][0]["status"] == "learning"
