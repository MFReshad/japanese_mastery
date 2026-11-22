"""Run only against an explicitly supplied disposable PostgreSQL database."""

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from sqlalchemy import create_engine, func, select, text
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
from app.models.item import CanonicalKanjiExample, Kanji, KanjiExample, KanjiSource


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


def test_pg_canonical_example_migration_preserves_history_and_rebuilds_exact_answers(pg):
    """Two legacy source rows become one canonical progress row without losing history."""
    from sqlalchemy.engine import make_url

    engine = pg.kw["bind"]
    schema = "canonical_example_upgrade"
    with engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    url = make_url(os.environ["TEST_POSTGRES_URL"]).update_query_dict(
        {"options": f"-csearch_path={schema}"}
    )
    settings = get_settings()
    old = settings.database_url
    settings.database_url = url.render_as_string(hide_password=False)
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
    try:
        command.upgrade(cfg, "0015_practice_history_filters")
        with engine.begin() as conn:
            conn.execute(text(f"""
                SET search_path TO {schema};
                INSERT INTO books (id,title,short_name) VALUES (1,'A','A'),(2,'B','B');
                INSERT INTO chapters (id,book_id,chapter_number,title) VALUES (1,1,1,'One'),(2,2,1,'One');
                INSERT INTO kanji (id,character) VALUES (1,'家'),(2,'族');
                INSERT INTO kanji_sources (id,kanji_id,book_id,chapter_id,meaning_as_printed,onyomi_as_printed,kunyomi_as_printed)
                    VALUES (1,1,1,1,'house','[]','[]'),(2,2,2,2,'family','[]','[]');
                INSERT INTO kanji_examples (id,kanji_source_id,word,reading,meaning,knowledge_status)
                    VALUES (10,1,'家族','かぞく','family A','known'),(20,2,'家族','かぞく','family B','unknown');
                INSERT INTO item_progress (item_type,item_id,attempts,correct_count,wrong_count,current_correct_streak,mastery_score,status,is_starred,last_result)
                    VALUES ('kanji_example',10,1,0,1,0,0,'weak',false,'wrong'),('kanji_example',20,1,1,0,1,1,'learning',false,'correct');
                INSERT INTO practice_sessions (id,practice_type,mode,total_questions,correct_count,wrong_count)
                    VALUES (1,'kanji_example_words','random',1,0,1),(2,'kanji_example_words','random',1,1,0);
                INSERT INTO practice_questions (id,session_id,position,item_type,item_id,source_entry_id,question_type,prompt,answer_primary,answered_at)
                    VALUES (1,1,0,'kanji_example',10,1,'important_kanji_word','家族','かぞく',now()-interval '2 minutes'),
                           (2,2,0,'kanji_example',20,2,'important_kanji_word','家族','かぞく',now()-interval '1 minute');
                INSERT INTO practice_answers (question_id,session_id,item_type,item_id,source_entry_id,question_type,result,answered_at)
                    VALUES (1,1,'kanji_example',10,1,'important_kanji_word','wrong',now()-interval '2 minutes'),
                           (2,2,'kanji_example',20,2,'important_kanji_word','correct',now()-interval '1 minute');
                RESET search_path;
            """))
        command.upgrade(cfg, "head")
        with engine.connect() as conn:
            assert conn.scalar(text(f"SELECT count(*) FROM {schema}.canonical_kanji_examples")) == 1
            rows = conn.execute(text(f"SELECT canonical_id, knowledge_status FROM {schema}.kanji_examples ORDER BY id")).all()
            assert rows[0][0] == rows[1][0]
            assert [row[1] for row in rows] == ["known", "unknown"]
            progress = conn.execute(text(f"SELECT item_id, attempts, correct_count, wrong_count, status FROM {schema}.item_progress WHERE item_type='kanji_example'")).one()
            assert progress == (rows[0][0], 2, 1, 1, "weak")
            assert conn.execute(text(f"SELECT item_id, source_entry_id FROM {schema}.practice_questions ORDER BY id")).all() == [(rows[0][0], 1), (rows[0][0], 2)]
            assert conn.execute(text(f"SELECT item_id, source_entry_id FROM {schema}.practice_answers ORDER BY id")).all() == [(rows[0][0], 1), (rows[0][0], 2)]
    finally:
        settings.database_url = old
        with engine.begin() as conn:
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))


def test_pg_canonical_example_migration_rolls_back_ambiguous_history(pg):
    from sqlalchemy.engine import make_url

    engine = pg.kw["bind"]
    schema = "canonical_example_ambiguous"
    with engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
    url = make_url(os.environ["TEST_POSTGRES_URL"]).update_query_dict(
        {"options": f"-csearch_path={schema}"}
    )
    settings = get_settings()
    old = settings.database_url
    settings.database_url = url.render_as_string(hide_password=False)
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
    try:
        command.upgrade(cfg, "0015_practice_history_filters")
        with engine.begin() as conn:
            conn.execute(text(f"""
                SET search_path TO {schema};
                INSERT INTO books (id,title) VALUES (1,'A'),(2,'B');
                INSERT INTO chapters (id,book_id,chapter_number,title) VALUES (1,1,1,'One'),(2,2,1,'One');
                INSERT INTO kanji (id,character) VALUES (1,'開'),(2,'門');
                INSERT INTO kanji_sources (id,kanji_id,book_id,chapter_id,meaning_as_printed,onyomi_as_printed,kunyomi_as_printed)
                    VALUES (1,1,1,1,'open','[]','[]'),(2,2,2,2,'gate','[]','[]');
                INSERT INTO kanji_examples (id,kanji_source_id,word,reading,meaning)
                    VALUES (10,1,'開く','ひらく','open'),(20,2,'開く','ひらく','open');
                INSERT INTO item_progress (item_type,item_id,attempts,correct_count,wrong_count,current_correct_streak,mastery_score,status,is_starred)
                    VALUES ('kanji_example',10,2,1,1,1,.5,'weak',false),
                           ('kanji_example',20,2,2,0,2,1,'learning',false);
                INSERT INTO practice_sessions (id,practice_type,mode,total_questions)
                    VALUES (1,'kanji_example_words','random',1);
                INSERT INTO practice_answers (session_id,item_type,item_id,source_entry_id,question_type,result)
                    VALUES (1,'kanji_example',10,1,'important_kanji_word','correct');
                RESET search_path;
            """))
        with pytest.raises(RuntimeError, match="Ambiguous Kanji example progress"):
            command.upgrade(cfg, "head")
        with engine.connect() as conn:
            assert conn.scalar(text(f"SELECT version_num FROM {schema}.alembic_version")) == "0015_practice_history_filters"
            assert conn.scalar(text(f"SELECT to_regclass('{schema}.canonical_kanji_examples')")) is None
            assert conn.scalar(text(f"SELECT count(*) FROM {schema}.item_progress WHERE item_type='kanji_example'")) == 2
            assert conn.scalar(text(f"SELECT count(*) FROM {schema}.practice_answers WHERE item_type='kanji_example'")) == 1
    finally:
        settings.database_url = old
        with engine.begin() as conn:
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))


def test_pg_concurrent_canonical_example_creation_reuses_identity(pg):
    with pg() as db:
        first_book = Book(title="Canonical concurrent A")
        second_book = Book(title="Canonical concurrent B")
        db.add_all([first_book, second_book])
        db.flush()
        first_chapter = Chapter(book_id=first_book.id, chapter_number=1, title="One")
        second_chapter = Chapter(book_id=second_book.id, chapter_number=1, title="One")
        first_kanji = Kanji(character="競")
        second_kanji = Kanji(character="合")
        db.add_all([first_chapter, second_chapter, first_kanji, second_kanji])
        db.flush()
        sources = [
            KanjiSource(
                kanji_id=kanji.id, book_id=book.id, chapter_id=chapter.id,
                meaning_as_printed="match", onyomi_as_printed=[], kunyomi_as_printed=[],
            )
            for kanji, book, chapter in (
                (first_kanji, first_book, first_chapter),
                (second_kanji, second_book, second_chapter),
            )
        ]
        db.add_all(sources)
        db.commit()
        source_ids = [source.id for source in sources]

    barrier = Barrier(2)

    def create(source_id):
        with pg() as db:
            db.add(KanjiExample(
                kanji_source_id=source_id, word="試合", reading="しあい", meaning="match"
            ))
            barrier.wait()
            db.commit()

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(create, source_ids))
    with pg() as db:
        examples = db.scalars(
            select(KanjiExample).where(KanjiExample.kanji_source_id.in_(source_ids))
        ).all()
        assert len(examples) == 2
        assert len({example.canonical_id for example in examples}) == 1
        assert db.scalar(
            select(func.count()).select_from(CanonicalKanjiExample).where(
                CanonicalKanjiExample.normalized_word == "試合",
                CanonicalKanjiExample.normalized_reading == "しあい",
            )
        ) == 1


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
