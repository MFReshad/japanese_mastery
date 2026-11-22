import pytest

from app.models.book import Book, Chapter
from app.models.item import Kanji, KanjiExample, KanjiSource
from app.models.practice import ItemProgress
from app.services.kanji_strength import calculate_kanji_strength


@pytest.mark.parametrize(
    ("statuses", "expected", "weakness"),
    [
        (["new", "new", "new"], "new", 0.0),
        (["learning", "new", "new"], "learning", 0.0),
        (["weak", "new", "new"], "weak", 100.0),
        (["weak", "weak", "mastered", "new", "new"], "weak", 66.7),
        (["weak", "mastered", "new"], "learning", 50.0),
        (["weak", "weak", "weak", "mastered", "new"], "weak", 75.0),
        (["mastered", "mastered", "mastered"], "mastered", 0.0),
        (["mastered", "learning", "new"], "learning", 0.0),
    ],
)
def test_example_based_strength_matrix(statuses, expected, weakness):
    result = calculate_kanji_strength(direct_status="weak", direct_attempts=7, example_statuses=statuses)
    assert result.status == expected
    assert result.weakness_percent == weakness


def test_kanji_without_examples_preserves_direct_status():
    result = calculate_kanji_strength(direct_status="weak", direct_attempts=2, example_statuses=[])
    assert result.status == "weak"
    assert result.direct_status == "weak"


def test_kanji_strength_uses_majority_of_practiced_example_words(client, db_session):
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
    managed = client.get(f"/kanji-sources?book_id={book.id}&chapter_id={chapter.id}").json()[0]
    assert managed["status"] == "weak"
    assert managed["practiced_examples"] == 2
    assert managed["weakness_percent"] == 100.0
    practice = client.post("/practice/start", json={
        "practice_type": "kanji", "mode": "random", "book_ids": [book.id],
        "chapter_ids": [chapter.id], "conditions": ["weak"], "question_count": 1,
    })
    assert practice.status_code == 200
    assert practice.json()["questions"][0]["item_type"] == "kanji"


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
    assert listing["items"][0]["practiced_examples"] == 1


def test_example_edit_and_reorder_preserve_identity_and_progress(client, db_session):
    book = Book(title="Editing Book")
    db_session.add(book)
    db_session.flush()
    kanji = Kanji(character="話")
    db_session.add(kanji)
    db_session.flush()
    source = KanjiSource(source_id="editing-kanji", kanji_id=kanji.id, book_id=book.id, item_order=1,
                         meaning_as_printed="talk", meanings_as_printed=["talk"], onyomi_as_printed=[], kunyomi_as_printed=[])
    db_session.add(source)
    db_session.flush()
    first = KanjiExample(kanji_source_id=source.id, word="会話", reading="かいわ", meaning="conversation", sort_order=0)
    second = KanjiExample(kanji_source_id=source.id, word="電話", reading="でんわ", meaning="telephone", sort_order=1)
    db_session.add_all([first, second])
    db_session.flush()
    first_id, second_id = first.id, second.id
    db_session.add(ItemProgress(item_type="kanji_example", item_id=first_id, attempts=3, correct_count=2, wrong_count=1,
                                current_correct_streak=1, last_result="correct", status="learning", mastery_score=2 / 3))
    db_session.commit()

    updated = client.patch(f"/kanji-sources/{source.id}", json={"examples": [
        {"id": second_id, "word": "電話", "reading": "でんわ", "meaning": "phone", "sort_order": 0},
        {"id": first_id, "word": "会話", "reading": "かいわ", "meaning": "conversation", "sort_order": 1},
    ]})
    assert updated.status_code == 200
    assert [row["id"] for row in updated.json()["examples"]] == [second_id, first_id]
    progress = db_session.query(ItemProgress).filter_by(item_type="kanji_example", item_id=first_id).one()
    assert (progress.attempts, progress.correct_count, progress.wrong_count) == (3, 2, 1)

    rejected = client.patch(f"/kanji-sources/{source.id}", json={"examples": [
        {"id": second_id, "word": "電話", "reading": "でんわ", "meaning": "phone", "sort_order": 0},
    ]})
    assert rejected.status_code >= 400
    assert db_session.get(KanjiExample, first_id) is not None


def test_answer_refreshes_parent_status_cache_without_touching_direct_progress(client, db_session):
    book = Book(title="Cache Book")
    db_session.add(book)
    db_session.flush()
    chapter = Chapter(book_id=book.id, chapter_number=1, title="Cache")
    kanji = Kanji(character="聞")
    db_session.add_all([chapter, kanji])
    db_session.flush()
    source = KanjiSource(source_id="cache-kanji", kanji_id=kanji.id, book_id=book.id, chapter_id=chapter.id,
                         item_order=1, meaning_as_printed="hear", meanings_as_printed=["hear"],
                         onyomi_as_printed=[], kunyomi_as_printed=[])
    db_session.add(source)
    db_session.flush()
    db_session.add(KanjiExample(kanji_source_id=source.id, word="新聞", reading="しんぶん", meaning="newspaper", sort_order=0))
    db_session.commit()

    before = client.get("/progress/books").json()[0]
    assert before["kanji_practiced"] == 0
    started = client.post("/practice/start", json={"practice_type": "kanji_example_words", "mode": "random",
                          "source_entry_ids": [source.id], "question_count": 1}).json()
    question_id = started["questions"][0]["question_id"]
    assert client.post(f"/practice/questions/{question_id}/reveal", json={"session_id": started["session_id"]}).status_code == 200
    assert client.post("/practice/answer", json={"session_id": started["session_id"], "question_id": question_id, "result": "wrong"}).status_code == 200

    resumed = client.get(f"/practice/sessions/{started['session_id']}").json()
    assert resumed["questions"][0]["answered"] is True
    after = client.get("/progress/books").json()[0]
    assert after["kanji_practiced"] == 1
    detail = client.get("/study/kanji/cache-kanji").json()
    assert detail["practice_status"] == "weak"
    assert "needs_attention" not in detail["kanji_strength"]
    listing = client.get(f"/library/items?kind=kanji&book_id={book.id}").json()
    assert listing["items"][0]["status"] == "weak"
    assert "needs_attention" not in listing["items"][0]
    managed = client.get(f"/kanji-sources?book_id={book.id}&chapter_id={chapter.id}").json()[0]
    assert managed["status"] == "weak"
    weak_practice = client.post("/practice/start", json={
        "practice_type": "kanji", "mode": "random", "book_ids": [book.id],
        "chapter_ids": [chapter.id], "conditions": ["weak"], "question_count": 1,
    })
    assert weak_practice.status_code == 200
    assert weak_practice.json()["questions"][0]["item_type"] == "kanji"
    assert db_session.query(ItemProgress).filter_by(item_type="kanji", item_id=kanji.id).one_or_none() is None
