from app.models.item import KanjiExample
from app.models.practice import PracticeQuestion


def _book_and_chapter(client):
    book = client.post("/books", json={"title": "Important words", "short_name": "IW"}).json()
    chapter = client.post(
        "/chapters",
        json={"book_id": book["id"], "chapter_number": 1, "title": "Lesson 1"},
    ).json()
    return book, chapter


def test_mark_and_practice_important_kanji_word(client, db_session):
    book, chapter = _book_and_chapter(client)
    source = client.post(
        "/kanji-sources",
        json={
            "book_id": book["id"],
            "chapter_id": chapter["id"],
            "item_order": 1,
            "character": "住",
            "meaning": "live",
            "kunyomi": ["す.む"],
            "examples": [
                {"word": "住む", "reading": "すむ", "meaning": "to live"},
                {"word": "住所", "reading": "じゅうしょ", "meaning": "address"},
            ],
        },
    ).json()
    detail = client.get(f"/study/kanji/{source['id']}").json()
    marked = next(example for example in detail["examples"] if example["word"] == "住む")
    assert marked["is_important"] is False
    assert client.patch(
        f"/kanji-examples/{marked['id']}/important",
        json={"is_important": True},
    ).json()["is_important"] is True

    response = client.post(
        "/practice/start",
        json={
            "practice_type": "important_kanji_words",
            "book_ids": [book["id"]],
            "question_count": 10,
        },
    )
    assert response.status_code == 200, response.text
    started = response.json()
    assert len(started["questions"]) == 1
    assert started["questions"][0]["prompt"] == "住む"
    assert started["questions"][0]["question_type"] == "important_kanji_word"
    question = db_session.get(PracticeQuestion, started["questions"][0]["question_id"])
    assert question.answer_primary == "すむ"
    assert question.answer_secondary == "to live"


def test_regular_kanji_practice_is_unchanged(client, db_session):
    book, chapter = _book_and_chapter(client)
    source = client.post(
        "/kanji-sources",
        json={
            "book_id": book["id"], "chapter_id": chapter["id"], "item_order": 1,
            "character": "住", "meaning": "live", "kunyomi": ["す"],
            "examples": [{"word": "住む", "reading": "すむ", "meaning": "to live"}],
        },
    ).json()
    example = db_session.query(KanjiExample).one()
    example.is_important = True
    db_session.commit()
    started = client.post(
        "/practice/start",
        json={"practice_type": "kanji", "source_entry_ids": [source["id"]], "question_count": None},
    ).json()
    assert any("Target kanji: 住" in question["prompt"] for question in started["questions"] if question["question_type"].startswith("example_kanji_"))


def test_custom_unknown_condition_and_multiple_chapters(client):
    book = client.post("/books", json={"title": "Custom", "short_name": "C"}).json()
    chapters = [client.post("/chapters", json={"book_id": book["id"], "chapter_number": number, "title": f"L{number}"}).json() for number in (1, 2)]
    sources = []
    for number, chapter in enumerate(chapters, 1):
        sources.append(client.post("/vocabulary-sources", json={"book_id": book["id"], "chapter_id": chapter["id"], "item_order": 1, "expression": f"言葉{number}", "reading": f"ことば{number}", "meaning": f"word {number}"}).json())
    client.patch(f"/vocabulary-sources/{sources[0]['id']}/knowledge", json={"knowledge_status": "unknown"})
    client.patch(f"/vocabulary-sources/{sources[1]['id']}/knowledge", json={"knowledge_status": "known"})
    started = client.post("/practice/start", json={"practice_type": "vocabulary", "chapter_ids": [chapter["id"] for chapter in chapters], "conditions": ["unknown"], "question_count": 10})
    assert started.status_code == 200, started.text
    assert len(started.json()["questions"]) == 1


def test_kanji_example_knowledge_filter(client):
    book, chapter = _book_and_chapter(client)
    source = client.post("/kanji-sources", json={"book_id": book["id"], "chapter_id": chapter["id"], "item_order": 1, "character": "住", "meaning": "live", "examples": [{"word": "住む", "reading": "すむ", "meaning": "to live"}, {"word": "住所", "reading": "じゅうしょ", "meaning": "address"}]}).json()
    detail = client.get(f"/study/kanji/{source['id']}").json()
    target = next(example for example in detail["examples"] if example["word"] == "住所")
    client.patch(f"/kanji-examples/{target['id']}/knowledge", json={"knowledge_status": "unknown"})
    started = client.post("/practice/start", json={"practice_type": "kanji_example_words", "chapter_ids": [chapter["id"]], "conditions": ["unknown"], "question_count": 10})
    assert started.status_code == 200, started.text
    assert [question["prompt"] for question in started.json()["questions"]] == ["住所"]
