"""Regression contracts for the repository stabilization review."""

import json

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.item import KanjiSource, VocabularySource
from app.models.practice import ItemProgress, PracticeQuestion
from app.services.importer import import_directory
from app.services.practice_cache import practice_session_cache
from test_importer import dataset


def source(client, kind="vocabulary", **extra):
    book = client.post("/books", json={"title": "Regression"}).json()
    chapter = client.post(
        "/chapters", json={"book_id": book["id"], "chapter_number": 1, "title": "One"}
    ).json()
    data = dict(
        book_id=book["id"],
        chapter_id=chapter["id"],
        item_order=1,
        **(
            {"expression": "食べる", "reading": "たべる", "meaning": "eat"}
            if kind == "vocabulary"
            else {"character": "食", "meaning": "eat", "examples": []}
        ),
    )
    data.update(extra)
    return client.post(f"/{kind}-sources", json=data), data


def test_progress_unique(db_session):
    db_session.add_all(
        [
            ItemProgress(item_type="vocabulary", item_id=1),
            ItemProgress(item_type="vocabulary", item_id=1),
        ]
    )
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_reveal_survives_cache_loss(client, db_session):
    item, _ = source(client)
    started = client.post(
        "/practice/start", json={"practice_type": "vocabulary"}
    ).json()
    qid = started["questions"][0]["question_id"]
    assert (
        client.post(
            f"/practice/questions/{qid}/reveal",
            json={"session_id": started["session_id"]},
        ).status_code
        == 200
    )
    assert db_session.get(PracticeQuestion, qid).revealed_at is not None
    practice_session_cache.clear()
    data = dict(session_id=started["session_id"], question_id=qid, result="correct")
    assert client.post("/practice/answer", json=data).status_code == 200
    assert client.post("/practice/answer", json=data).json()["attempts"] == 1


def test_star_is_unpracticed(client):
    item, _ = source(client)
    client.patch(
        f"/library/items/vocabulary/{item.json()['id']}/star", json={"is_starred": True}
    )
    assert client.get("/progress").json()[0]["new"] == 1
    assert (
        len(
            client.post(
                "/practice/start",
                json={"practice_type": "vocabulary", "mode": "never_practiced"},
            ).json()["questions"]
        )
        == 1
    )


@pytest.mark.parametrize("kind", ["vocabulary", "kanji"])
def test_create_conflict_and_ownership(client, kind):
    item, data = source(client, kind)
    assert item.status_code == 200
    assert client.post(f"/{kind}-sources", json=data).status_code == 409
    other = client.post("/books", json={"title": "Other"}).json()
    data["book_id"] = other["id"]
    assert client.post(f"/{kind}-sources", json=data).status_code == 400


def test_meanings_consistent(client, db_session):
    item, _ = source(client, "kanji")
    client.patch(
        f"/kanji-sources/{item.json()['id']}", json={"meaning_as_printed": "eat / food"}
    )
    row = db_session.get(KanjiSource, item.json()["id"])
    assert row.meanings_as_printed == ["eat", "food"]


@pytest.mark.parametrize(
    "payload",
    [
        {"mode": "oops"},
        {"practice_type": "oops"},
        {"question_count": 0},
        {"question_count": -1},
        {"question_count": 100001},
        {"order_start": 5, "order_end": 2},
    ],
)
def test_practice_validation(client, payload):
    assert client.post("/practice/start", json=payload).status_code == 422


def test_vocabulary_question_rules(client, db_session):
    source(client)
    for _ in range(20):
        data = client.post(
            "/practice/start", json={"practice_type": "vocabulary"}
        ).json()
        row = db_session.get(PracticeQuestion, data["questions"][0]["question_id"])
        assert row.question_type != "japanese_to_reading"
        assert row.answer_primary and row.answer_primary not in row.prompt
        if row.question_type == "japanese_to_meaning":
            assert "たべる" in row.prompt


def test_import_preserves_manual_edit_and_suppression(tmp_path, client, db_session):
    dataset(tmp_path)
    import_directory(db_session, tmp_path, False)
    row = db_session.scalar(select(VocabularySource))
    client.patch(
        f"/vocabulary-sources/{row.id}",
        json={"meaning_as_printed": "greeting", "notes": "personal"},
    )
    result = import_directory(db_session, tmp_path, False)
    db_session.refresh(row)
    assert row.meaning_as_printed == "greeting"
    assert row.notes == "personal"
    assert result["vocabulary_sources"]["preserved_overrides"] >= 1


def test_duplicate_import_ids_rejected(tmp_path, db_session):
    rows = dataset(tmp_path)
    rows["books"].append(rows["books"][0])
    (tmp_path / "books.json").write_text(json.dumps(rows["books"]))
    assert import_directory(db_session, tmp_path)["summary"]["fatal_error"]


def test_access_gate(client, monkeypatch):
    from app.core import get_settings

    monkeypatch.setattr(get_settings(), "personal_access_token", "test-personal-secret")
    assert client.post("/books", json={"title": "Denied"}).status_code == 401
    assert (
        client.post(
            "/books",
            json={"title": "Allowed"},
            headers={"Authorization": "Bearer test-personal-secret"},
        ).status_code
        == 200
    )
    assert client.get("/books").status_code == 200


def test_import_path_restriction(client):
    assert (
        client.post("/import", json={"directory": "/tmp/unapproved"}).status_code == 400
    )


def test_sample_preview(db_session):
    from pathlib import Path

    sample = Path(__file__).resolve().parents[2] / "data/imports"
    assert import_directory(db_session, sample)["summary"]["fatal_error"] is None


def test_session_resume_hides_answers(client):
    source(client)
    start = client.post("/practice/start", json={"practice_type": "vocabulary"}).json()
    q = start["questions"][0]["question_id"]
    client.post(
        f"/practice/questions/{q}/reveal", json={"session_id": start["session_id"]}
    )
    practice_session_cache.clear()
    resumed = client.get(f"/practice/sessions/{start['session_id']}").json()
    assert resumed["version"] == 1
    assert resumed["questions"][0]["revealed"] is True
    assert resumed["questions"][0]["answered"] is False
    assert "answer_primary" not in str(resumed)


def test_suppression_preserves_canonical_and_history(tmp_path, client, db_session):
    from app.models.item import Vocabulary

    dataset(tmp_path)
    import_directory(db_session, tmp_path, False)
    row = db_session.scalar(select(VocabularySource))
    canonical_id = row.vocabulary_id
    start = client.post("/practice/start", json={"practice_type": "vocabulary"}).json()
    assert client.delete(f"/vocabulary-sources/{row.id}").status_code == 204
    result = import_directory(db_session, tmp_path, False)
    assert result["vocabulary_sources"]["suppressed_records"] == 1
    assert db_session.scalar(select(VocabularySource)) is None
    assert db_session.get(Vocabulary, canonical_id) is not None
    assert (
        db_session.get(PracticeQuestion, start["questions"][0]["question_id"])
        is not None
    )
    assert client.get("/progress").json()[0]["total"] == 1


def test_kanji_manual_content_survives_import(tmp_path, client, db_session):
    dataset(tmp_path)
    import_directory(db_session, tmp_path, False)
    row = db_session.scalar(select(KanjiSource))
    update = {
        "meaning_as_printed": "food / eat",
        "onyomi": ["NEW"],
        "notes": "mine",
        "examples": [
            {"word": "食事", "reading": "しょくじ", "meaning": "meal", "sort_order": 0}
        ],
    }
    assert client.patch(f"/kanji-sources/{row.id}", json=update).status_code == 200
    import_directory(db_session, tmp_path, False)
    db_session.refresh(row)
    assert row.meanings_as_printed == ["food", "eat"]
    assert row.onyomi == ["NEW"]
    assert row.notes == "mine"
    assert row.examples[0].word == "食事"


def test_populated_chapter_cannot_move(client):
    _, data = source(client)
    other = client.post("/books", json={"title": "Other"}).json()
    assert (
        client.patch(
            f"/chapters/{data['chapter_id']}", json={"book_id": other["id"]}
        ).status_code
        == 409
    )


def test_relink_does_not_inherit_mastery(client, db_session):
    item, _ = source(client)
    sid = item.json()["id"]
    old_id = item.json()["vocabulary_id"]
    db_session.add(
        ItemProgress(
            item_type="vocabulary",
            item_id=old_id,
            attempts=1,
            correct_count=1,
            status="learning",
        )
    )
    db_session.commit()
    changes = {"expression_as_printed": "朝", "reading_as_printed": "あさ"}
    assert client.patch(f"/vocabulary-sources/{sid}", json=changes).status_code == 400
    changed = client.patch(
        f"/vocabulary-sources/{sid}", json={**changes, "identity_action": "relink"}
    ).json()
    assert changed["vocabulary_id"] != old_id
    assert changed["status"] == "new"


def test_stale_order_rejected(client):
    item, data = source(client)
    other = client.post(
        "/vocabulary-sources",
        json={**data, "expression": "朝", "reading": "あさ", "item_order": 2},
    ).json()
    ids = [item.json()["id"], other["id"]]
    endpoint = f"/chapters/{data['chapter_id']}/vocabulary-order"
    assert (
        client.put(
            endpoint, json={"source_ids": ids[::-1], "expected_source_ids": ids}
        ).status_code
        == 200
    )
    assert (
        client.put(
            endpoint, json={"source_ids": ids, "expected_source_ids": ids}
        ).status_code
        == 409
    )


def test_lookup_ttl():
    from app.cache.lookups import LookupCache

    cache = LookupCache(ttl_seconds=0)
    assert cache.get_books(lambda: ["first"]) == ["first"]
    assert cache.get_books(lambda: ["second"]) == ["second"]


def test_coverage_counts_occurrences(client, db_session):
    item, data = source(client)
    client.post("/vocabulary-sources", json={**data, "item_order": 2})
    db_session.add(
        ItemProgress(
            item_type="vocabulary",
            item_id=item.json()["vocabulary_id"],
            attempts=5,
            correct_count=5,
            current_correct_streak=5,
            status="mastered",
        )
    )
    db_session.commit()
    assert client.get("/progress/books").json()[0]["vocabulary_mastered_percent"] == 100


def test_kanji_suppression(tmp_path, client, db_session):
    dataset(tmp_path)
    import_directory(db_session, tmp_path, False)
    source = db_session.scalar(select(KanjiSource))
    assert client.delete(f"/kanji-sources/{source.id}").status_code == 204
    result = import_directory(db_session, tmp_path, False)
    assert result["kanji_sources"]["suppressed_records"] == 1
    assert db_session.scalar(select(KanjiSource)) is None


def test_auth_rejection_has_cors_for_error_classification(client, monkeypatch):
    from app.core import get_settings

    monkeypatch.setattr(get_settings(), "personal_access_token", "test-secret")
    response = client.post(
        "/practice/start", headers={"Origin": "http://localhost:3000"}, json={}
    )
    assert response.status_code == 401
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_original_order_changes_are_reported(tmp_path, db_session):
    rows = dataset(tmp_path)
    import_directory(db_session, tmp_path, False)
    rows["vocabulary_sources"][0]["item_order"] = 3
    (tmp_path / "vocabulary_sources.json").write_text(
        json.dumps(rows["vocabulary_sources"])
    )
    result = import_directory(db_session, tmp_path, False)
    assert result["vocabulary_sources"]["would_update"] == 1
    source = db_session.scalar(select(VocabularySource))
    assert source.original_item_order == 3
    assert source.imported_baseline["_original_source"]["item_order"] == 1
    assert source.imported_baseline["_source"]["item_order"] == 3
