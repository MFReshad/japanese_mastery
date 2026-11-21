from app.models.practice import PracticeSession


def _seed_vocabulary(client):
    book = client.post("/books", json={"title": "History Book", "short_name": "HB"}).json()
    chapter = client.post("/chapters", json={"book_id": book["id"], "chapter_number": 4, "title": "History Lesson", "sort_order": 4}).json()
    source = client.post("/vocabulary-sources", json={
        "book_id": book["id"], "chapter_id": chapter["id"], "item_order": 1,
        "expression": "履歴", "reading": "りれき", "meaning": "history",
    }).json()
    return book, chapter, source


def test_practice_history_preserves_filters_and_answer_context(client):
    book, chapter, source = _seed_vocabulary(client)
    payload = {
        "practice_type": "vocabulary",
        "mode": "random",
        "book_ids": [book["id"]],
        "chapter_ids": [chapter["id"]],
        "question_count": 10,
        "conditions": ["known", "weak", "starred"],
    }
    # Make the source eligible for every selected category.
    client.patch(f"/vocabulary-sources/{source['id']}/knowledge", json={"knowledge_status": "known"})
    progress_session = client.post("/practice/start", json={
        "practice_type": "vocabulary", "source_entry_ids": [source["id"]], "question_count": 1,
    }).json()
    progress_question = progress_session["questions"][0]
    client.post(f"/practice/questions/{progress_question['question_id']}/reveal", json={"session_id": progress_session["session_id"]})
    client.post("/practice/answer", json={"session_id": progress_session["session_id"], "question_id": progress_question["question_id"], "result": "wrong"})
    client.patch(f"/library/items/vocabulary/{source['id']}/star", json={"is_starred": True})

    started = client.post("/practice/start", json=payload)
    assert started.status_code == 200
    session = started.json()
    question = session["questions"][0]
    client.post(f"/practice/questions/{question['question_id']}/reveal", json={"session_id": session["session_id"]})
    client.post("/practice/answer", json={
        "session_id": session["session_id"], "question_id": question["question_id"],
        "result": "wrong", "note": "Review this word",
    })

    page = client.get("/practice/history?limit=1").json()
    assert page["total"] == 2
    assert page["sessions"][0]["session_id"] == session["session_id"]
    assert page["sessions"][0]["filter_snapshot"]["book_ids"] == [book["id"]]
    assert page["sessions"][0]["filter_snapshot"]["chapter_ids"] == [chapter["id"]]
    assert page["sessions"][0]["filter_snapshot"]["conditions"] == ["known", "weak", "starred"]
    assert page["sessions"][0]["wrong_count"] == 1

    detail = client.get(f"/practice/history/{session['session_id']}").json()
    assert len(detail["answers"]) == 1
    answer = detail["answers"][0]
    assert answer["result"] == "wrong"
    assert answer["wrong_note"] == "Review this word"
    assert answer["book_title"] == "History Book"
    assert answer["chapter_number"] == 4
    assert answer["chapter_title"] == "History Lesson"
    assert answer["study_kind"] == "vocabulary"
    assert answer["study_source_id"] == source["source_id"]


def test_practice_history_keeps_legacy_sessions_with_no_snapshot(client, db_session):
    legacy = PracticeSession(practice_type="mixed", mode="random", total_questions=0)
    db_session.add(legacy)
    db_session.commit()
    response = client.get("/practice/history").json()
    assert response["sessions"][0]["filter_snapshot"] is None
    assert client.get(f"/practice/history/{legacy.id}").json()["answers"] == []


def test_kanji_example_history_exposes_its_parent_kanji(client):
    book = client.post("/books", json={"title": "Kanji History"}).json()
    chapter = client.post("/chapters", json={"book_id": book["id"], "chapter_number": 2, "title": "Two"}).json()
    source = client.post("/kanji-sources", json={
        "book_id": book["id"], "chapter_id": chapter["id"], "item_order": 1,
        "character": "年", "meaning": "year", "onyomi": ["ネン"], "kunyomi": [],
        "examples": [{"word": "去年", "reading": "きょねん", "meaning": "last year"}],
    }).json()
    example_id = source["examples"][0]["id"]
    client.patch(f"/kanji-examples/{example_id}/important", json={"is_important": True})
    started = client.post("/practice/start", json={
        "practice_type": "kanji_example_words", "source_entry_ids": [source["id"]],
        "conditions": ["starred"], "question_count": 1,
    }).json()
    detail = client.get(f"/practice/history/{started['session_id']}").json()
    assert detail["answers"][0]["main_kanji"] == "年"
