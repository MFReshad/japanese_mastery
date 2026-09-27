"""Reproducible synthetic benchmark. Requires an explicit disposable TEST_POSTGRES_URL."""

import os
import sys
import statistics
from pathlib import Path
from time import perf_counter

url = os.environ.get("TEST_POSTGRES_URL")
if not url:
    raise SystemExit(
        "Set TEST_POSTGRES_URL to a disposable migrated PostgreSQL database"
    )
os.environ["DATABASE_URL"] = url
os.environ["PERSONAL_ACCESS_TOKEN"] = "local-benchmark-only"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from sqlalchemy import text, event
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal, engine
from app.models.book import Book, Chapter
from app.models.item import Vocabulary, VocabularySource

with SessionLocal() as db:
    book = Book(title="Synthetic benchmark")
    db.add(book)
    db.flush()
    chapter = Chapter(book_id=book.id, chapter_number=1, title="Synthetic lesson")
    db.add(chapter)
    db.flush()
    for index in range(2000):
        expression = f"計測{book.id}-{index}"
        item = Vocabulary(
            expression=expression,
            reading="けいそく",
            normalized_expression=expression,
            normalized_reading="けいそく",
        )
        db.add(item)
        db.flush()
        db.add(
            VocabularySource(
                vocabulary_id=item.id,
                book_id=book.id,
                chapter_id=chapter.id,
                item_order=index + 1,
                expression_as_printed=expression,
                reading_as_printed="けいそく",
                meaning_as_printed=f"measurement {index}",
            )
        )
    db.commit()
    book_id, chapter_id = book.id, chapter.id

queries = []


@event.listens_for(engine, "before_cursor_execute")
def count(*args):
    queries.append(args[2])


print("# Local synthetic performance results\n")
print(
    "PostgreSQL 16 in Docker; 2,000 vocabulary occurrences in one chapter. TestClient wall time includes HTTP dispatch. These are local measurements, not Neon latency estimates.\n"
)
print("| Operation | Median ms | First/warm SQL statements |")
print("|---|---:|---:|")
with TestClient(app) as client:
    headers = {"Authorization": "Bearer local-benchmark-only"}

    def measure(label, callback):
        durations, counts = [], []
        for _ in range(10):
            queries.clear()
            started = perf_counter()
            response = callback()
            if response.status_code != 200:
                raise RuntimeError(f"{label}: HTTP {response.status_code}")
            durations.append((perf_counter() - started) * 1000)
            counts.append(len(queries))
        print(
            f"| {label} | {statistics.median(durations):.2f} | {counts[0]}/{counts[-1]} |"
        )

    measure("Books", lambda: client.get("/books"))
    measure("Chapters", lambda: client.get(f"/chapters?book_id={book_id}"))
    measure(
        "Library (50 rows)", lambda: client.get(f"/library/items?book_id={book_id}")
    )
    measure(
        "Study (2,000 rows)",
        lambda: client.get(
            f"/study/items?book_id={book_id}&chapter_id={chapter_id}&kind=vocabulary"
        ),
    )

    def start():
        return client.post(
            "/practice/start",
            headers=headers,
            json={
                "practice_type": "vocabulary",
                "book_ids": [book_id],
                "question_count": 10,
            },
        )

    measure("Practice start (10)", start)
    current = start().json()
    qid = current["questions"][0]["question_id"]
    sid = current["session_id"]
    measure(
        "Reveal (durable)",
        lambda: client.post(
            f"/practice/questions/{qid}/reveal",
            headers=headers,
            json={"session_id": sid},
        ),
    )
    for result in ["correct", "wrong"]:
        durations, counts = [], []
        for _ in range(10):
            current = start().json()
            qid = current["questions"][0]["question_id"]
            sid = current["session_id"]
            client.post(
                f"/practice/questions/{qid}/reveal",
                headers=headers,
                json={"session_id": sid},
            )
            queries.clear()
            started = perf_counter()
            response = client.post(
                "/practice/answer",
                headers=headers,
                json={"session_id": sid, "question_id": qid, "result": result},
            )
            assert response.status_code == 200
            durations.append((perf_counter() - started) * 1000)
            counts.append(len(queries))
        print(
            f"| Save {result} | {statistics.median(durations):.2f} | {counts[0]}/{counts[-1]} |"
        )
    measure("Progress / Home statistics", lambda: client.get("/progress"))
    measure("Chapter coverage", lambda: client.get("/progress/books"))
with engine.connect() as db:
    plan = (
        db.execute(
            text(
                "EXPLAIN (ANALYZE, BUFFERS) SELECT id FROM vocabulary_sources WHERE book_id=:book ORDER BY random() LIMIT 10"
            ),
            {"book": book_id},
        )
        .scalars()
        .all()
    )
    print(
        "\n`ORDER BY random()` plan for this fixture:\n\n```text\n"
        + "\n".join(plan)
        + "\n```"
    )
print(
    "\nNo replacement for random ordering or additional performance indexes is justified by this fixture. Measure real Neon plans before changing either."
)
