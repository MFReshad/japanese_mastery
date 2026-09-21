from app.models.book import Book, Chapter
from app.models.item import Kanji, KanjiExample, KanjiSource, Vocabulary, VocabularySource


def test_study_kanji_keeps_every_source_value_and_lesson_order(client, db_session):
    book = Book(title="First Book")
    other_book = Book(title="Second Book")
    db_session.add_all([book, other_book])
    db_session.flush()
    chapter = Chapter(book_id=book.id, chapter_number=0, part=1, title="Greetings", sort_order=0)
    empty_chapter = Chapter(book_id=book.id, chapter_number=1, part=1, title="No kanji", sort_order=1)
    next_chapter = Chapter(book_id=book.id, chapter_number=1, part=2, title="Part 2", sort_order=1)
    other_chapter = Chapter(book_id=other_book.id, chapter_number=1, title="Another lesson")
    kanji = Kanji(character="生")
    db_session.add_all([chapter, empty_chapter, next_chapter, other_chapter, kanji])
    db_session.flush()
    first = KanjiSource(source_id="source_kanji_1", kanji_id=kanji.id, book_id=book.id, chapter_id=chapter.id,
                        item_order=2, meaning_as_printed="life", meanings_as_printed=["life", "birth"],
                        onyomi_as_printed=["セイ", "ショウ"], kunyomi_as_printed=["い.きる", "う.まれる"],
                        stroke_count_as_printed=5, uncertain=True, source_page="3", source_book_page=42)
    second = KanjiSource(source_id="source_kanji_2", kanji_id=kanji.id, book_id=book.id, chapter_id=chapter.id,
                         item_order=3, meaning_as_printed="living", meanings_as_printed=["living"],
                         onyomi_as_printed=["セイ"], kunyomi_as_printed=[])
    elsewhere = KanjiSource(source_id="source_kanji_elsewhere", kanji_id=kanji.id, book_id=other_book.id,
                             chapter_id=other_chapter.id, item_order=1, meaning_as_printed="different source meaning",
                             meanings_as_printed=["different source meaning"], onyomi_as_printed=[], kunyomi_as_printed=[])
    next_part = KanjiSource(source_id="source_kanji_next_part", kanji_id=kanji.id, book_id=book.id,
                            chapter_id=next_chapter.id, item_order=1, meaning_as_printed="new part",
                            meanings_as_printed=["new part"], onyomi_as_printed=[], kunyomi_as_printed=[])
    db_session.add_all([second, first, elsewhere, next_part])
    db_session.flush()
    first.examples.extend([
        KanjiExample(word="生活", reading="せいかつ", meaning="daily life", sort_order=0),
        KanjiExample(word="学生", reading="がくせい", meaning="student", sort_order=1),
        KanjiExample(word="生まれる", reading="うまれる", meaning="to be born", sort_order=2),
    ])
    db_session.commit()

    listing = client.get(f"/study/items?book_id={book.id}&chapter_id={chapter.id}&kind=kanji")
    assert listing.status_code == 200
    assert [row["source_id"] for row in listing.json()] == ["source_kanji_1", "source_kanji_2"]
    detail = client.get("/study/kanji/source_kanji_1")
    assert detail.status_code == 200
    data = detail.json()
    assert data["meanings_as_printed"] == ["life", "birth"]
    assert data["onyomi_as_printed"] == ["セイ", "ショウ"]
    assert data["kunyomi_as_printed"] == ["い.きる", "う.まれる"]
    assert [row["word"] for row in data["examples"]] == ["生活", "学生", "生まれる"]
    assert data["part"] == 1
    assert data["previous_source_id"] is None
    assert data["next_source_id"] == "source_kanji_2"
    assert data["next_chapter"]["chapter_id"] == next_chapter.id
    assert data["next_chapter"]["first_source_id"] == "source_kanji_next_part"
    assert client.get(f"/study/next-chapter?book_id={book.id}&chapter_id={chapter.id}&kind=kanji").json() == data["next_chapter"]
    assert client.get("/study/kanji/source_kanji_next_part").json()["next_chapter"] is None
    assert client.get("/study/kanji/source_kanji_elsewhere").json()["meaning_as_printed"] == "different source meaning"
    started = client.post("/practice/start", json={"practice_type": "kanji", "book_ids": [book.id],
                                                    "chapter_ids": [chapter.id], "source_entry_ids": [first.id],
                                                    "question_count": 1}).json()
    assert len(started["questions"]) == 1
    assert set(started["questions"][0]) == {"question_id", "item_type", "question_type", "prompt"}


def test_study_vocabulary_uses_selected_occurrence(client, db_session):
    book = Book(title="Book")
    db_session.add(book)
    db_session.flush()
    chapter = Chapter(book_id=book.id, chapter_number=1, title="Lesson 1")
    next_chapter = Chapter(book_id=book.id, chapter_number=3, title="Lesson 3", sort_order=3)
    vocab = Vocabulary(expression="橋", reading="はし", normalized_expression="橋", normalized_reading="はし")
    db_session.add_all([chapter, next_chapter, vocab])
    db_session.flush()
    source = VocabularySource(source_id="source_vocab_1", vocabulary_id=vocab.id, book_id=book.id,
                              chapter_id=chapter.id, item_order=4, expression_as_printed="橋",
                              reading_as_printed="はし", meaning_as_printed="bridge in this book",
                              meanings_as_printed=["bridge in this book", "span"])
    db_session.add(source)
    db_session.add(VocabularySource(source_id="source_vocab_2", vocabulary_id=vocab.id, book_id=book.id,
                                    chapter_id=next_chapter.id, item_order=1, expression_as_printed="橋",
                                    reading_as_printed="はし", meaning_as_printed="span",
                                    meanings_as_printed=["span"]))
    db_session.commit()
    detail = client.get("/study/vocabulary/source_vocab_1")
    assert detail.status_code == 200
    assert detail.json()["meanings_as_printed"] == ["bridge in this book", "span"]
    assert detail.json()["item_order"] == 4
    assert detail.json()["next_chapter"]["first_source_id"] == "source_vocab_2"
    assert client.get("/study/vocabulary/source_vocab_2").json()["next_chapter"] is None
