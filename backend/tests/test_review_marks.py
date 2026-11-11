from app.models.book import Book, Chapter
from app.models.item import Vocabulary, VocabularySource
from app.models.practice import ItemProgress


def test_filter_unknown_mastered_and_bulk_clear(client, db_session):
    book = Book(title="Review Book", short_name="REVIEW")
    db_session.add(book)
    db_session.flush()
    chapter = Chapter(book_id=book.id, chapter_number=1, title="Review", sort_order=1)
    vocabulary = Vocabulary(expression="住む", reading="すむ", normalized_expression="住む", normalized_reading="すむ")
    db_session.add_all([chapter, vocabulary])
    db_session.flush()
    source = VocabularySource(
        vocabulary_id=vocabulary.id, book_id=book.id, chapter_id=chapter.id, item_order=1,
        expression_as_printed="住む", reading_as_printed="すむ", meaning_as_printed="to live",
        knowledge_status="unknown",
    )
    progress = ItemProgress(item_type="vocabulary", item_id=vocabulary.id, attempts=5, correct_count=5,
                            current_correct_streak=5, mastery_score=1, status="mastered")
    db_session.add_all([source, progress])
    db_session.commit()

    result = client.get("/review/items?kind=vocabulary&knowledge=unknown&practice_status=mastered")
    assert result.status_code == 200
    assert [(row["word"], row["knowledge_status"], row["practice_status"]) for row in result.json()["items"]] == [
        ("住む", "unknown", "mastered")
    ]

    updated = client.patch("/review/items/bulk", json={
        "kind": "vocabulary", "ids": [source.id], "action": "clear_knowledge"
    })
    assert updated.status_code == 200
    assert updated.json()["updated"] == 1
    db_session.refresh(source)
    assert source.knowledge_status is None
