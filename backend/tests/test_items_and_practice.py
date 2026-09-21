from app.models.item import Kanji, Vocabulary, VocabularySource
from app.models.practice import PracticeQuestion


def test_duplicate_vocabulary_reuses_canonical_and_preserves_meanings(client, db_session):
    book1 = client.post("/books", json={"title": "Genki I", "short_name": "GENKI1"}).json()
    book2 = client.post("/books", json={"title": "Minna I", "short_name": "MINNA1"}).json()
    ch1 = client.post("/chapters", json={"book_id": book1["id"], "chapter_number": 3, "title": "Lesson 3", "sort_order": 3}).json()
    ch2 = client.post("/chapters", json={"book_id": book2["id"], "chapter_number": 6, "title": "Lesson 6", "sort_order": 6}).json()

    client.post("/vocabulary-sources", json={"book_id": book1["id"], "chapter_id": ch1["id"], "item_order": 1, "expression": "食べる", "reading": "たべる", "meaning": "to eat"})
    client.post("/vocabulary-sources", json={"book_id": book2["id"], "chapter_id": ch2["id"], "item_order": 1, "expression": "食べる", "reading": "たべる", "meaning": "eat / have a meal"})

    assert db_session.query(Vocabulary).count() == 1
    sources = db_session.query(VocabularySource).order_by(VocabularySource.book_id).all()
    assert [source.meaning_as_printed for source in sources] == ["to eat", "eat / have a meal"]
    response = client.get(f"/vocabulary-sources?book_id={book1['id']}")
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_duplicate_kanji_reuses_canonical(client, db_session):
    book = client.post("/books", json={"title": "Kanji Challenge", "short_name": "KC"}).json()
    chapter = client.post("/chapters", json={"book_id": book["id"], "chapter_number": 1, "title": "One", "sort_order": 1}).json()
    payload = {"book_id": book["id"], "chapter_id": chapter["id"], "item_order": 1, "character": "食", "meaning": "eat", "onyomi": ["ショク"], "kunyomi": ["た.べる"], "examples": []}
    client.post("/kanji-sources", json=payload)
    payload["item_order"] = 2
    client.post("/kanji-sources", json=payload)
    assert db_session.query(Kanji).count() == 1
    response = client.get(f"/kanji-sources?book_id={book['id']}")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_answer_tracking_and_range_filter(client, db_session):
    book = client.post("/books", json={"title": "Demo", "short_name": "D"}).json()
    chapter = client.post("/chapters", json={"book_id": book["id"], "chapter_number": 1, "title": "One", "sort_order": 1}).json()
    for i in range(1, 4):
        client.post("/vocabulary-sources", json={"book_id": book["id"], "chapter_id": chapter["id"], "item_order": i, "expression": f"語{i}", "reading": f"ご{i}", "meaning": f"word {i}"})
    started = client.post("/practice/start", json={"practice_type": "vocabulary", "mode": "random", "book_ids": [book["id"]], "order_start": 2, "order_end": 3, "question_count": 10}).json()
    assert len(started["questions"]) == 2
    assert all(set(question) == {"question_id", "item_type", "question_type", "prompt"} for question in started["questions"])
    q = started["questions"][0]
    assert "answer_primary" not in str(started) and "answer_secondary" not in str(started)
    assert db_session.get(PracticeQuestion, q["question_id"]).prompt == q["prompt"]
    assert client.post("/practice/answer", json={"session_id": started["session_id"], "question_id": q["question_id"], "result": "wrong"}).status_code == 409
    assert client.post(f"/practice/questions/{started['questions'][1]['question_id']}/reveal", json={"session_id": started["session_id"]}).status_code == 200
    reveal = client.post(f"/practice/questions/{q['question_id']}/reveal", json={"session_id": started["session_id"]})
    assert reveal.status_code == 200
    assert set(reveal.json()) == {"answer_primary", "answer_secondary", "context"}
    wrong = client.post("/practice/answer", json={"session_id": started["session_id"], "question_id": q["question_id"], "result": "wrong"}).json()
    assert wrong["status"] == "weak"
    assert client.post("/practice/answer", json={"session_id": started["session_id"], "question_id": q["question_id"], "result": "wrong"}).status_code == 200
    assert client.post("/practice/answer", json={"session_id": started["session_id"], "question_id": q["question_id"], "result": "correct"}).status_code == 409
    assert db_session.get(PracticeQuestion, q["question_id"]).prompt == q["prompt"]
    for _ in range(5):
        fresh = client.post("/practice/start", json={"practice_type": "vocabulary", "source_entry_ids": [db_session.get(PracticeQuestion, q["question_id"]).source_entry_id], "question_count": 1}).json()
        fresh_question = fresh["questions"][0]
        client.post(f"/practice/questions/{fresh_question['question_id']}/reveal", json={"session_id": fresh["session_id"]})
        client.post("/practice/answer", json={"session_id": fresh["session_id"], "question_id": fresh_question["question_id"], "result": "correct"})
    progress = client.get("/progress").json()
    assert progress[0]["learning"] + progress[0]["mastered"] >= 1
