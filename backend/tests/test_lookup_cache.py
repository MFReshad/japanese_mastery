from sqlalchemy import event


def _captured_sql(db_session, callback):
    statements = []

    def count_sql(*args):
        statements.append(args[2])

    event.listen(db_session.bind, "before_cursor_execute", count_sql)
    try:
        response = callback()
    finally:
        event.remove(db_session.bind, "before_cursor_execute", count_sql)
    return response, statements


def test_books_are_cached_and_invalidated(client, db_session):
    client.post("/books", json={"title": "Cache Book", "short_name": "CB"})

    first, first_sql = _captured_sql(db_session, lambda: client.get("/books"))
    second, second_sql = _captured_sql(db_session, lambda: client.get("/books"))
    assert first.status_code == 200
    assert second.status_code == 200
    assert first_sql
    assert second_sql == []

    client.post("/books", json={"title": "Fresh Book", "short_name": "FB"})
    after_write, after_write_sql = _captured_sql(db_session, lambda: client.get("/books"))
    assert after_write.status_code == 200
    assert after_write_sql


def test_chapters_are_cached_by_all_and_by_book(client, db_session):
    book = client.post("/books", json={"title": "Cache Book", "short_name": "CB"}).json()
    other = client.post("/books", json={"title": "Other Book", "short_name": "OB"}).json()
    client.post("/chapters", json={"book_id": book["id"], "chapter_number": 1, "title": "One", "sort_order": 1})
    client.post("/chapters", json={"book_id": other["id"], "chapter_number": 1, "title": "Other", "sort_order": 1})

    first_all, first_all_sql = _captured_sql(db_session, lambda: client.get("/chapters"))
    second_all, second_all_sql = _captured_sql(db_session, lambda: client.get("/chapters"))
    assert first_all.status_code == 200
    assert second_all.status_code == 200
    assert first_all_sql
    assert second_all_sql == []

    first_book, first_book_sql = _captured_sql(db_session, lambda: client.get(f"/chapters?book_id={book['id']}"))
    second_book, second_book_sql = _captured_sql(db_session, lambda: client.get(f"/chapters?book_id={book['id']}"))
    assert first_book.status_code == 200
    assert second_book.status_code == 200
    assert {chapter["book_id"] for chapter in first_book.json()} == {book["id"]}
    assert first_book_sql
    assert second_book_sql == []

    client.post("/chapters", json={"book_id": book["id"], "chapter_number": 2, "title": "Two", "sort_order": 2})
    after_write, after_write_sql = _captured_sql(db_session, lambda: client.get(f"/chapters?book_id={book['id']}"))
    assert after_write.status_code == 200
    assert after_write_sql
