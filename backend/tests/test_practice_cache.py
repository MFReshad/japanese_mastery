from sqlalchemy import event, select

from app.models.practice import ItemProgress, PracticeAnswer


def test_cached_reveal_and_idempotent_answer(client, db_session):
    book = client.post("/books", json={"title": "Cache", "short_name": "C"}).json()
    chapter = client.post("/chapters", json={"book_id": book["id"], "chapter_number": 1,
                                              "title": "One", "sort_order": 1}).json()
    source = client.post("/vocabulary-sources", json={"book_id": book["id"], "chapter_id": chapter["id"],
                                                    "item_order": 1, "expression": "語", "reading": "ご",
                                                    "meaning": "word"}).json()
    started = client.post("/practice/start", json={"practice_type": "vocabulary",
                                                  "source_entry_ids": [source["id"]],
                                                  "question_count": 1}).json()
    question_id = started["questions"][0]["question_id"]
    statements = []

    def count_sql(*args):
        statements.append(args[2])

    event.listen(db_session.bind, "before_cursor_execute", count_sql)
    try:
        revealed = client.post(f"/practice/questions/{question_id}/reveal",
                               json={"session_id": started["session_id"]})
    finally:
        event.remove(db_session.bind, "before_cursor_execute", count_sql)
    assert revealed.status_code == 200
    assert any("UPDATE practice_questions" in statement for statement in statements)

    payload = {"session_id": started["session_id"], "question_id": question_id, "result": "wrong",
               "note": "Forgot this"}
    assert client.post("/practice/answer", json=payload).status_code == 200
    assert client.post("/practice/answer", json=payload).status_code == 200
    assert db_session.scalar(select(PracticeAnswer).where(PracticeAnswer.question_id == question_id)).wrong_note == "Forgot this"
    progress = db_session.scalar(select(ItemProgress).where(ItemProgress.item_type == "vocabulary"))
    assert progress.attempts == 1

    second = client.post("/practice/start", json={"practice_type": "vocabulary",
                                                "source_entry_ids": [source["id"]],
                                                "question_count": 1}).json()
    next_id = second["questions"][0]["question_id"]
    assert client.post(f"/practice/questions/{next_id}/reveal",
                       json={"session_id": second["session_id"]}).status_code == 200
    correct = {"session_id": second["session_id"], "question_id": next_id,
               "result": "correct", "note": "Remembered from lesson 2"}
    assert client.post("/practice/answer", json=correct).status_code == 200
    assert client.post("/practice/answer", json=correct).status_code == 200
    assert db_session.scalar(select(PracticeAnswer).where(PracticeAnswer.question_id == next_id)).wrong_note == correct["note"]
    assert progress.attempts == 2
