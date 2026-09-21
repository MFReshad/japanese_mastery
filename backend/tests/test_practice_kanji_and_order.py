from app.models.item import Vocabulary, VocabularySource
from app.models.item import KanjiExample, KanjiSource
from app.models.practice import PracticeAnswer, PracticeQuestion
from app.services.practice import questions_from_kanji


def setup_book(client):
    book = client.post("/books", json={"title": "Practice Book", "short_name": "PB"}).json()
    chapter = client.post("/chapters", json={"book_id": book["id"], "chapter_number": 1,
                                             "title": "One", "sort_order": 1}).json()
    return book, chapter


def test_kanji_questions_use_only_source_examples(client, db_session):
    book, chapter = setup_book(client)
    source = client.post("/kanji-sources", json={"book_id": book["id"], "chapter_id": chapter["id"],
        "item_order": 1, "character": "同", "meaning": "same", "onyomi": ["ドウ", "トウ"],
        "kunyomi": ["おな", "とも"], "examples": [{"word": "同じ", "reading": "おなじ", "meaning": "same"}]}).json()
    started = client.post("/practice/start", json={"practice_type": "kanji", "book_ids": [book["id"]], "question_count": None}).json()
    questions = [db_session.get(PracticeQuestion, row["question_id"]) for row in started["questions"]]
    assert {q.question_type for q in questions} == {"kanji_to_meaning", "kanji_to_reading", "meaning_to_kanji",
        "example_kanji_to_reading", "example_kanji_to_meaning"}
    assert all(q.source_entry_id == source["id"] for q in questions)
    assert all(q.prompt != q.answer_primary for q in questions)
    assert "reading_to_kanji" not in {q.question_type for q in questions}
    single = next(q for q in questions if q.question_type == "kanji_to_reading")
    assert single.reveal_context["onyomi"] == ["ドウ", "トウ"]
    assert single.reveal_context["kunyomi"] == ["おな", "とも"]
    assert single.reveal_context["examples"] == [{"word": "同じ", "reading": "おなじ", "meaning": "same"}]
    example = next(q for q in questions if q.question_type == "example_kanji_to_reading")
    assert example.answer_primary == "おな"
    assert "Target kanji: 同" in example.prompt
    assert example.reveal_context["reading"] == "おなじ"
    assert "answer_primary" not in str(started)


def test_wrong_notes_are_individual_and_correct_needs_none(client, db_session):
    book, chapter = setup_book(client)
    source = client.post("/vocabulary-sources", json={"book_id": book["id"], "chapter_id": chapter["id"],
        "item_order": 1, "expression": "先生", "reading": "せんせい", "meaning": "teacher"}).json()
    for note in ("Forgot reading", "Mixed meaning", None):
        started = client.post("/practice/start", json={"practice_type": "vocabulary", "source_entry_ids": [source["id"]], "question_count": 1}).json()
        q = started["questions"][0]
        client.post(f"/practice/questions/{q['question_id']}/reveal", json={"session_id": started["session_id"]})
        result = "correct" if note is None else "wrong"
        assert client.post("/practice/answer", json={"session_id": started["session_id"],
            "question_id": q["question_id"], "result": result, "note": note}).status_code == 200
    assert [(row.result, row.wrong_note) for row in db_session.query(PracticeAnswer).order_by(PracticeAnswer.id)] == [
        ("wrong", "Forgot reading"), ("wrong", "Mixed meaning"), ("correct", None)]


def test_incomplete_example_never_invents_missing_values(client, db_session):
    book, chapter = setup_book(client)
    source = client.post("/kanji-sources", json={"book_id": book["id"], "chapter_id": chapter["id"],
        "item_order": 1, "character": "生", "meaning": "life", "onyomi": [], "kunyomi": [], "examples": []}).json()
    row = db_session.get(KanjiSource, source["id"])
    row.examples.append(KanjiExample(word="生活", reading="", meaning="daily life"))
    db_session.commit()
    drafts = questions_from_kanji(row)
    assert {draft.question_type for draft in drafts} == {"kanji_to_meaning", "meaning_to_kanji",
        "example_kanji_to_meaning"}
    assert all(draft.answer_primary and draft.prompt for draft in drafts)


def test_kanji_mode_never_asks_for_example_word_from_meaning_or_reading(client, db_session):
    book, chapter = setup_book(client)
    cases = [
        ("港", "port", ["コウ"], [], "空港", "くうこう", "airport", "こう"),
        ("昼", "noon / daytime", [], ["ひる"], "昼ご飯", "ひるごはん", "lunch", "ひる"),
    ]
    for position, (character, meaning, onyomi, kunyomi, word, reading, example_meaning, target_reading) in enumerate(cases, 1):
        source = client.post("/kanji-sources", json={"book_id": book["id"], "chapter_id": chapter["id"],
            "item_order": position, "character": character, "meaning": meaning,
            "onyomi": onyomi, "kunyomi": kunyomi,
            "examples": [{"word": word, "reading": reading, "meaning": example_meaning}]}).json()
        row = db_session.get(KanjiSource, source["id"])
        drafts = questions_from_kanji(row)
        assert {draft.question_type for draft in drafts} == {"kanji_to_meaning", "kanji_to_reading",
            "meaning_to_kanji", "example_kanji_to_meaning", "example_kanji_to_reading"}
        assert all(draft.answer_primary != word for draft in drafts)
        assert all(draft.prompt != reading and draft.prompt != example_meaning for draft in drafts)
        assert all(example_meaning not in draft.prompt for draft in drafts)
        reading_draft = next(draft for draft in drafts if draft.question_type == "example_kanji_to_reading")
        assert reading_draft.answer_primary == target_reading
        assert reading_draft.reveal_context["reading"] == reading
        assert reading_draft.reveal_context["meaning"] == example_meaning
    started = client.post("/practice/start", json={"practice_type": "kanji", "book_ids": [book["id"]],
        "question_count": None}).json()
    assert all(row["question_type"] not in {"meaning_to_example", "reading_to_example",
        "example_to_meaning", "example_to_reading", "reading_to_kanji"} for row in started["questions"])
    assert all(row["prompt"] not in {"airport", "ひるごはん"} for row in started["questions"])


def test_example_target_reading_requires_printed_match(client, db_session):
    book, chapter = setup_book(client)
    source = client.post("/kanji-sources", json={"book_id": book["id"], "chapter_id": chapter["id"],
        "item_order": 1, "character": "港", "meaning": "port", "onyomi": ["コウ"], "kunyomi": [],
        "examples": [{"word": "空港", "reading": "くうみなと", "meaning": "airport"}]}).json()
    drafts = questions_from_kanji(db_session.get(KanjiSource, source["id"]))
    assert "example_kanji_to_reading" not in {draft.question_type for draft in drafts}
    assert "example_kanji_to_meaning" in {draft.question_type for draft in drafts}


def test_vocabulary_order_insert_reuse_remove_and_reset(client, db_session):
    book, chapter = setup_book(client)
    base = f"/chapters/{chapter['id']}/vocabulary-order"
    initial = []
    for position, expression in enumerate(("私", "学生", "先生"), 1):
        initial.append(client.post("/vocabulary-sources", json={"book_id": book["id"], "chapter_id": chapter["id"],
            "item_order": position, "expression": expression, "reading": expression, "meaning": expression}).json())
    # Simulate imported provenance; manual additions below must retain NULL provenance.
    for row in initial:
        source = db_session.get(VocabularySource, row["id"])
        source.original_item_order = source.item_order
        source.manually_added = False
    db_session.commit()
    reordered = client.put(base, json={"source_ids": [initial[0]["id"], initial[2]["id"], initial[1]["id"]]}).json()
    assert [row["item_order"] for row in reordered] == [1, 2, 3]
    assert reordered[1]["original_item_order"] == 3 and reordered[1]["manually_reordered"]
    assert [row["source_entry_id"] for row in client.get(f"/study/items?book_id={book['id']}&chapter_id={chapter['id']}&kind=vocabulary").json()] == [initial[0]["id"], initial[2]["id"], initial[1]["id"]]
    assert client.get(f"/study/vocabulary/{initial[2]['source_id']}").json()["next_source_id"] == initial[1]["source_id"]
    inserted = client.post(base, json={"expression": "学生", "reading": "学生", "meaning": "student again", "position": 3}).json()
    assert inserted["manually_added"] and inserted["original_item_order"] is None
    assert inserted["vocabulary_id"] == initial[1]["vocabulary_id"]
    assert [row["item_order"] for row in client.get(base).json()] == [1, 2, 3, 4]
    new = client.post(base, json={"expression": "日本", "reading": "にほん", "meaning": "Japan", "position": 2}).json()
    assert db_session.query(Vocabulary).count() == 4
    assert new["original_item_order"] is None
    assert new["source_id"].startswith("manual_vocab_")
    assert client.get(f"/study/vocabulary/{new['source_id']}").status_code == 200
    assert client.delete(f"/vocabulary-sources/{inserted['id']}").status_code == 204
    assert db_session.get(Vocabulary, initial[1]["vocabulary_id"]) is not None
    reset = client.post(f"{base}/reset").json()
    assert [row["item_order"] for row in reset] == [1, 2, 3, 4]
    assert {row["id"] for row in reset} == {initial[0]["id"], initial[1]["id"], initial[2]["id"], new["id"]}
