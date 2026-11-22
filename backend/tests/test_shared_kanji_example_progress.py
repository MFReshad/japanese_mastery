from app.models.item import KanjiExample
from app.models.practice import ItemProgress, PracticeAnswer, PracticeQuestion


def _source(client, title, character, reading="かぞく", knowledge=None, important=False):
    book = client.post("/books", json={"title": title}).json()
    chapter = client.post("/chapters", json={
        "book_id": book["id"], "chapter_number": 1, "title": "Family", "sort_order": 1,
    }).json()
    source = client.post("/kanji-sources", json={
        "book_id": book["id"], "chapter_id": chapter["id"], "item_order": 1,
        "character": character, "meaning": "family", "onyomi": [], "kunyomi": [],
        "examples": [{
            "word": "家族", "reading": reading, "meaning": f"family in {title}",
            "knowledge_status": knowledge, "is_important": important,
        }],
    }).json()
    example_id = source["examples"][0]["id"]
    if knowledge is not None:
        client.patch(f"/kanji-examples/{example_id}/knowledge", json={"knowledge_status": knowledge})
    if important:
        client.patch(f"/kanji-examples/{example_id}/important", json={"is_important": True})
    return book, chapter, source


def _answer(client, source_id, result):
    session = client.post("/practice/start", json={
        "practice_type": "kanji_example_words", "source_entry_ids": [source_id],
        "question_count": 1,
    }).json()
    question = session["questions"][0]
    assert client.post(
        f"/practice/questions/{question['question_id']}/reveal",
        json={"session_id": session["session_id"]},
    ).status_code == 200
    assert client.post("/practice/answer", json={
        "session_id": session["session_id"], "question_id": question["question_id"],
        "result": result,
    }).status_code == 200
    return session


def test_equivalent_examples_share_progress_without_sharing_source_marks(client, db_session):
    first_book, _, first = _source(client, "Genki II", "家", knowledge="known", important=True)
    second_book, _, second = _source(client, "Minna II", "族", knowledge="unknown", important=False)
    examples = db_session.query(KanjiExample).order_by(KanjiExample.id).all()
    assert examples[0].canonical_id == examples[1].canonical_id
    canonical_id = examples[0].canonical_id

    first_session = _answer(client, first["id"], "wrong")
    progress = db_session.query(ItemProgress).filter_by(item_type="kanji_example", item_id=canonical_id).one()
    assert (progress.attempts, progress.wrong_count, progress.status) == (1, 1, "weak")

    for source_id in (first["id"], second["id"]):
        detail = client.get(f"/study/kanji/{source_id}").json()
        assert detail["examples"][0]["practice_status"] == "weak"
        assert detail["examples"][0]["attempts"] == 1
        assert detail["practice_status"] == "weak"
    assert client.get(f"/progress/books").status_code == 200
    assert client.get(f"/review/items?kind=kanji_examples&book_id={second_book['id']}&practice_status=weak").json()["items"][0]["word"] == "家族"

    second_session = _answer(client, second["id"], "correct")
    db_session.refresh(progress)
    assert (progress.attempts, progress.correct_count, progress.wrong_count) == (2, 1, 1)
    assert db_session.query(ItemProgress).filter_by(item_type="kanji_example").count() == 1
    assert db_session.query(PracticeAnswer).filter_by(item_type="kanji_example", item_id=canonical_id).count() == 2

    history = client.get(f"/practice/history/{first_session['session_id']}").json()
    assert history["answers"][0]["book_title"] == "Genki II"
    assert client.get(f"/practice/history/{second_session['session_id']}").status_code == 200
    db_session.refresh(examples[0]); db_session.refresh(examples[1])
    assert examples[0].knowledge_status == "known" and examples[0].is_important is True
    assert examples[1].knowledge_status == "unknown" and examples[1].is_important is False


def test_new_occurrence_immediately_reuses_existing_progress(client, db_session):
    _, _, first = _source(client, "Existing progress", "家")
    _answer(client, first["id"], "wrong")

    _, _, added_later = _source(client, "Added later", "族")
    detail = client.get(f"/study/kanji/{added_later['id']}").json()
    assert detail["examples"][0]["attempts"] == 1
    assert detail["examples"][0]["practice_status"] == "weak"
    examples = db_session.query(KanjiExample).order_by(KanjiExample.id).all()
    assert len({example.canonical_id for example in examples}) == 1
    assert db_session.query(ItemProgress).filter_by(item_type="kanji_example").count() == 1


def test_different_readings_are_independent_and_duplicate_questions_are_removed(client, db_session):
    _, _, first = _source(client, "Book A", "家")
    _, _, duplicate = _source(client, "Book B", "族")
    _, _, different = _source(client, "Book C", "庭", reading="いえぞく")
    examples = db_session.query(KanjiExample).order_by(KanjiExample.id).all()
    assert examples[0].canonical_id == examples[1].canonical_id
    assert examples[2].canonical_id != examples[0].canonical_id

    started = client.post("/practice/start", json={
        "practice_type": "kanji_example_words",
        "source_entry_ids": [first["id"], duplicate["id"], different["id"]],
        "question_count": 10,
    }).json()
    assert len(started["questions"]) == 2
    assert len({question.item_id for question in db_session.query(PracticeQuestion).filter_by(session_id=started["session_id"])}) == 2


def test_editing_and_reordering_occurrence_preserves_shared_progress(client, db_session):
    _, _, first = _source(client, "Editing A", "家")
    _, _, second = _source(client, "Editing B", "族")
    _answer(client, first["id"], "wrong")
    first_example = db_session.get(KanjiExample, first["examples"][0]["id"])
    canonical_id = first_example.canonical_id

    updated = client.patch(f"/kanji-sources/{second['id']}", json={"examples": [{
        "id": second["examples"][0]["id"], "word": "家族", "reading": "かぞく",
        "meaning": "relatives", "sort_order": 9, "knowledge_status": "unknown",
    }]})
    assert updated.status_code == 200
    second_example = db_session.get(KanjiExample, second["examples"][0]["id"])
    assert second_example.canonical_id == canonical_id
    assert db_session.query(ItemProgress).filter_by(item_type="kanji_example", item_id=canonical_id).one().attempts == 1

    # Shared example practice never mutates the independent progress domains.
    assert db_session.query(ItemProgress).filter(ItemProgress.item_type.in_(["vocabulary", "kanji"])).count() == 0

    relinked = client.patch(f"/kanji-sources/{second['id']}", json={"examples": [{
        "id": second["examples"][0]["id"], "word": "家庭", "reading": "かてい",
        "meaning": "household", "sort_order": 9, "knowledge_status": "unknown",
    }]})
    assert relinked.status_code == 200
    db_session.refresh(second_example)
    assert second_example.id == second["examples"][0]["id"]
    assert second_example.canonical_id != canonical_id
    detail = client.get(f"/study/kanji/{second['id']}").json()
    assert detail["examples"][0]["attempts"] == 0
    assert detail["examples"][0]["practice_status"] == "new"
    assert db_session.query(ItemProgress).filter_by(
        item_type="kanji_example", item_id=canonical_id
    ).one().attempts == 1
