from sqlalchemy import select

from app.models.book import Book, Chapter
from app.models.item import Vocabulary, VocabularySource
from app.models.practice import ItemProgress


def seed_chapter(db_session, count=3):
    book = Book(title="Star Book", short_name="STAR")
    db_session.add(book)
    db_session.flush()
    chapter = Chapter(book_id=book.id, chapter_number=1, title="Stars", sort_order=1)
    db_session.add(chapter)
    db_session.flush()
    for position in range(1, count + 1):
        expression = f"星{position}"
        vocabulary = Vocabulary(expression=expression, reading=f"ほし{position}",
                                normalized_expression=expression, normalized_reading=f"ほし{position}")
        db_session.add(vocabulary)
        db_session.flush()
        db_session.add(VocabularySource(source_id=f"star_source_{position}", vocabulary_id=vocabulary.id,
            book_id=book.id, chapter_id=chapter.id, item_order=position,
            expression_as_printed=expression, reading_as_printed=f"ほし{position}",
            meaning_as_printed=f"star {position}", meanings_as_printed=[f"star {position}"]))
    db_session.commit()
    return book, chapter


def test_star_unstar_and_persistence_after_reload(client, db_session):
    book, chapter = seed_chapter(db_session, 1)
    item = client.get(f"/library/items?kind=vocabulary&book_id={book.id}&chapter_id={chapter.id}").json()["items"][0]
    assert item["is_starred"] is False
    assert item["status"] == "new"

    starred = client.patch(f"/library/items/vocabulary/{item['id']}/star", json={"is_starred": True})
    assert starred.status_code == 200
    assert starred.json()["is_starred"] is True

    reloaded = client.get(f"/library/items?kind=vocabulary&book_id={book.id}&chapter_id={chapter.id}").json()["items"][0]
    assert reloaded["is_starred"] is True
    progress = db_session.scalar(select(ItemProgress).where(ItemProgress.item_type == "vocabulary"))
    assert progress.is_starred is True
    assert progress.status == "new"

    unstarred = client.patch(f"/library/items/vocabulary/{item['id']}/star", json={"is_starred": False})
    assert unstarred.status_code == 200
    assert unstarred.json()["is_starred"] is False
    again = client.get(f"/library/items?kind=vocabulary&book_id={book.id}&chapter_id={chapter.id}").json()["items"][0]
    assert again["is_starred"] is False


def test_starred_and_weak_coexist_and_starred_filter(client, db_session):
    book, chapter = seed_chapter(db_session, 2)
    items = client.get(f"/library/items?kind=vocabulary&book_id={book.id}&chapter_id={chapter.id}").json()["items"]
    first, second = items
    first_source = db_session.get(VocabularySource, first["id"])
    second_source = db_session.get(VocabularySource, second["id"])
    first_progress = ItemProgress(item_type="vocabulary", item_id=first_source.vocabulary_id, status="weak",
                                  attempts=1, wrong_count=1, last_result="wrong", is_starred=True)
    second_progress = ItemProgress(item_type="vocabulary", item_id=second_source.vocabulary_id, status="learning",
                                   attempts=2, correct_count=2, current_correct_streak=2)
    db_session.add_all([first_progress, second_progress])
    db_session.commit()

    weak = client.get(f"/library/items?kind=vocabulary&book_id={book.id}&chapter_id={chapter.id}&status=weak").json()
    assert weak["total"] == 1
    assert weak["items"][0]["id"] == first["id"]
    assert weak["items"][0]["status"] == "weak"
    assert weak["items"][0]["is_starred"] is True

    starred = client.get(f"/library/items?kind=vocabulary&book_id={book.id}&chapter_id={chapter.id}&status=starred").json()
    assert starred["total"] == 1
    assert starred["items"][0]["id"] == first["id"]
    assert starred["items"][0]["status"] == "weak"
    assert starred["items"][0]["is_starred"] is True


def test_starred_practice_modes_use_starred_items(client, db_session):
    book, chapter = seed_chapter(db_session, 3)
    items = client.get(f"/library/items?kind=vocabulary&book_id={book.id}&chapter_id={chapter.id}").json()["items"]
    sources = [db_session.get(VocabularySource, item["id"]) for item in items]
    db_session.add_all([
        ItemProgress(item_type="vocabulary", item_id=sources[0].vocabulary_id, status="mastered", attempts=5, correct_count=5, current_correct_streak=5, is_starred=True),
        ItemProgress(item_type="vocabulary", item_id=sources[1].vocabulary_id, status="weak", attempts=1, wrong_count=1,
                     last_result="wrong", is_starred=True),
        ItemProgress(item_type="vocabulary", item_id=sources[2].vocabulary_id, status="weak", attempts=1, wrong_count=1,
                     last_result="wrong", is_starred=False),
    ])
    db_session.commit()

    starred = client.post("/practice/start", json={"practice_type": "vocabulary", "mode": "starred",
                                                   "book_ids": [book.id], "question_count": None}).json()
    assert {question["prompt"].split("\n")[0] for question in starred["questions"]} <= {
        items[0]["expression_as_printed"], items[0]["meaning_as_printed"],
        items[1]["expression_as_printed"], items[1]["meaning_as_printed"],
    }

    priority = client.post("/practice/start", json={"practice_type": "vocabulary", "mode": "starred_priority",
                                                    "book_ids": [book.id], "question_count": 1}).json()
    assert priority["questions"][0]["prompt"].split("\n")[0] in {items[1]["expression_as_printed"], items[1]["meaning_as_printed"]}
