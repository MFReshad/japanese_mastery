"""Run only against an explicitly supplied disposable PostgreSQL database."""

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker
from alembic import command
from alembic.config import Config

from app.core import get_settings
from app.models.practice import ItemProgress, PracticeSession, PracticeQuestion
from app.services.mastery import record_answer
from app.services.practice import reveal_question, answer_practice
from app.services.practice_cache import practice_session_cache
from app.repositories.parts import part_matches
from app.models.book import Book, Chapter


@pytest.fixture(scope="module")
def pg():
    url = os.environ.get("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("TEST_POSTGRES_URL must point to a disposable PostgreSQL database")
    engine = create_engine(url)
    # Never use DATABASE_URL (which may be production) as this fixture's target.
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    old = get_settings().database_url
    get_settings().database_url = url
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option(
        "script_location", str(Path(__file__).resolve().parents[1] / "alembic")
    )
    try:
        command.upgrade(cfg, "head")
    finally:
        get_settings().database_url = old
    yield sessionmaker(bind=engine, expire_on_commit=False)
    engine.dispose()


def test_pg_concurrent_progress_and_unique(pg):
    barrier = Barrier(8)

    def answer(_):
        with pg() as db:
            barrier.wait()
            record_answer(db, "vocabulary", 9001, "correct")
            db.commit()

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(answer, range(8)))
    with pg() as db:
        rows = db.scalars(
            select(ItemProgress).where(ItemProgress.item_id == 9001)
        ).all()
        assert len(rows) == 1
        p = rows[0]
        assert (
            p.attempts,
            p.correct_count,
            p.wrong_count,
            p.current_correct_streak,
            p.status,
        ) == (8, 8, 0, 8, "mastered")


def test_pg_reveal_cache_loss_and_concurrent_duplicate_retry(pg):
    with pg() as db:
        session = PracticeSession(
            practice_type="vocabulary", mode="random", total_questions=1
        )
        db.add(session)
        db.flush()
        q = PracticeQuestion(
            session_id=session.id,
            position=0,
            item_type="vocabulary",
            item_id=9002,
            source_entry_id=1,
            question_type="meaning_to_japanese",
            prompt="word",
            answer_primary="語",
        )
        db.add(q)
        db.commit()
        sid, qid = session.id, q.id
        reveal_question(db, sid, qid)
    practice_session_cache.clear()
    barrier = Barrier(4)

    def answer(_):
        with pg() as db:
            barrier.wait()
            return answer_practice(db, sid, qid, "wrong")[0].attempts

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(answer, range(4))) == [1] * 4
    with pg() as db:
        assert answer_practice(db, sid, qid, "wrong")[0].attempts == 1
        session = db.get(PracticeSession, sid)
        assert (session.correct_count, session.wrong_count) == (0, 1)


def test_pg_part_scalar_semantics(pg):
    with pg() as db:
        book = Book(title="Parts")
        db.add(book)
        db.flush()
        db.add_all(
            [
                Chapter(book_id=book.id, chapter_number=i, title=str(i), part=part)
                for i, part in enumerate([1, "1", 2, None])
            ]
        )
        db.commit()
        assert (
            len(
                db.scalars(select(Chapter).where(part_matches(Chapter.part, [1]))).all()
            )
            == 2
        )
        assert (
            len(
                db.scalars(
                    select(Chapter).where(part_matches(Chapter.part, ["1"]))
                ).all()
            )
            == 2
        )


def test_pg_migrated_schema_matches_metadata(pg):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from app.db.session import Base

    def compare_defaults(context, inspected, metadata, reflected, default, rendered):
        from sqlalchemy import JSON

        if isinstance(metadata.type, JSON):
            return (reflected or "").removesuffix("::json").strip("'") != (
                rendered or ""
            ).strip("'")
        return None

    with pg().bind.connect() as conn:
        changes = compare_metadata(
            MigrationContext.configure(
                conn, opts={"compare_server_default": compare_defaults}
            ),
            Base.metadata,
        )
        assert changes == []


def test_pg_upgrade_refuses_duplicates_before_changing_schema(pg):
    """Use an isolated schema to exercise the actual legacy-to-head upgrade."""
    from sqlalchemy.engine import make_url

    engine = pg.kw["bind"]
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA legacy_upgrade"))
    url = make_url(os.environ["TEST_POSTGRES_URL"]).update_query_dict(
        {"options": "-csearch_path=legacy_upgrade"}
    )
    settings = get_settings()
    old = settings.database_url
    settings.database_url = url.render_as_string(hide_password=False)
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option(
        "script_location", str(Path(__file__).resolve().parents[1] / "alembic")
    )
    try:
        command.upgrade(cfg, "0007_starred_progress")
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO legacy_upgrade.item_progress (item_type,item_id,is_starred) VALUES ('vocabulary',1,false),('vocabulary',1,true)"
                )
            )
        with pytest.raises(RuntimeError, match="Duplicate progress"):
            command.upgrade(cfg, "head")
        with engine.begin() as conn:
            assert (
                conn.scalar(text("SELECT count(*) FROM legacy_upgrade.item_progress"))
                == 2
            )
            assert (
                conn.scalar(
                    text("SELECT version_num FROM legacy_upgrade.alembic_version")
                )
                == "0007_starred_progress"
            )
            # This fixture has only empty progress; retain the star preference.
            conn.execute(
                text("DELETE FROM legacy_upgrade.item_progress WHERE is_starred=false")
            )
        command.upgrade(cfg, "head")
        with engine.connect() as conn:
            assert (
                conn.scalar(text("SELECT is_starred FROM legacy_upgrade.item_progress"))
                is True
            )
    finally:
        settings.database_url = old
        with engine.begin() as conn:
            conn.execute(text("DROP SCHEMA legacy_upgrade CASCADE"))


def test_pg_answers_from_different_sessions_share_serialized_progress(pg):
    with pg() as db:
        questions = []
        for _ in range(8):
            session = PracticeSession(
                practice_type="kanji", mode="random", total_questions=1
            )
            db.add(session)
            db.flush()
            q = PracticeQuestion(
                session_id=session.id,
                position=0,
                item_type="kanji",
                item_id=9900,
                source_entry_id=1,
                question_type="kanji_to_meaning",
                prompt="食",
                answer_primary="eat",
            )
            db.add(q)
            db.commit()
            reveal_question(db, session.id, q.id)
            questions.append((session.id, q.id))
    barrier = Barrier(8)

    def answer(pair):
        with pg() as db:
            barrier.wait()
            answer_practice(db, pair[0], pair[1], "correct")

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(answer, questions))
    with pg() as db:
        progress = db.scalar(
            select(ItemProgress).where(
                ItemProgress.item_type == "kanji", ItemProgress.item_id == 9900
            )
        )
        assert (
            progress.attempts,
            progress.correct_count,
            progress.current_correct_streak,
            progress.status,
        ) == (8, 8, 8, "mastered")
