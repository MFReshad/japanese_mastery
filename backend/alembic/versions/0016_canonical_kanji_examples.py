"""share kanji example progress through canonical word and reading identity

Revision ID: 0016_canonical_examples
Revises: 0015_practice_history_filters
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import unicodedata

from alembic import op
import sqlalchemy as sa


revision = "0016_canonical_examples"
down_revision = "0015_practice_history_filters"
branch_labels = None
depends_on = None


def _normalize(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).strip().split())


def _calculated_progress(answers):
    attempts = correct = wrong = streak = 0
    last_result = last_at = None
    for answer in answers:
        attempts += 1
        last_result, last_at = answer["result"], answer["answered_at"]
        if last_result == "correct":
            correct += 1
            streak += 1
        else:
            wrong += 1
            streak = 0
    accuracy = correct / attempts if attempts else 0.0
    status = "new" if not attempts else "weak" if last_result == "wrong" or accuracy < 0.7 else "mastered" if attempts >= 5 and accuracy >= 0.9 and streak >= 3 else "learning"
    return {
        "attempts": attempts, "correct_count": correct, "wrong_count": wrong,
        "current_correct_streak": streak, "mastery_score": round(accuracy, 4),
        "status": status, "last_result": last_result, "last_practiced_at": last_at,
    }


def upgrade() -> None:
    op.create_table(
        "canonical_kanji_examples",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("word", sa.String(255), nullable=False),
        sa.Column("reading", sa.String(255), nullable=False),
        sa.Column("normalized_word", sa.String(255), nullable=False),
        sa.Column("normalized_reading", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("normalized_word", "normalized_reading", name="uq_canonical_kanji_example_normalized"),
    )
    op.add_column("kanji_examples", sa.Column("canonical_id", sa.Integer(), nullable=True))
    bind = op.get_bind()
    examples = bind.execute(sa.text("SELECT id, word, reading FROM kanji_examples ORDER BY id")).mappings().all()
    canonical_by_key = {}
    old_to_canonical = {}
    for example in examples:
        key = (_normalize(example["word"]), _normalize(example["reading"]))
        canonical_id = canonical_by_key.get(key)
        if canonical_id is None:
            canonical_id = bind.execute(
                sa.text("""
                    INSERT INTO canonical_kanji_examples
                        (word, reading, normalized_word, normalized_reading)
                    VALUES (:word, :reading, :normalized_word, :normalized_reading)
                    RETURNING id
                """),
                {"word": example["word"].strip(), "reading": example["reading"].strip(),
                 "normalized_word": key[0], "normalized_reading": key[1]},
            ).scalar_one()
            canonical_by_key[key] = canonical_id
        old_to_canonical[example["id"]] = canonical_id
        bind.execute(sa.text("UPDATE kanji_examples SET canonical_id = :canonical WHERE id = :old"), {"canonical": canonical_id, "old": example["id"]})

    progress_rows = bind.execute(sa.text("SELECT * FROM item_progress WHERE item_type = 'kanji_example' ORDER BY id")).mappings().all()
    answers = bind.execute(sa.text("SELECT id, item_id, result, answered_at FROM practice_answers WHERE item_type = 'kanji_example' ORDER BY answered_at, id")).mappings().all()
    progress_by_canonical = defaultdict(list)
    answers_by_canonical = defaultdict(list)
    for row in progress_rows:
        progress_by_canonical[old_to_canonical[row["item_id"]]].append(row)
    for row in answers:
        answers_by_canonical[old_to_canonical[row["item_id"]]].append(row)

    consolidated = []
    now = datetime.now(timezone.utc)
    for canonical_id in set(progress_by_canonical) | set(answers_by_canonical):
        rows = progress_by_canonical[canonical_id]
        nonzero = [row for row in rows if row["attempts"] > 0]
        history = answers_by_canonical[canonical_id]
        if len(nonzero) > 1 and len(history) != sum(row["attempts"] for row in nonzero):
            raise RuntimeError(
                "Ambiguous Kanji example progress consolidation detected. "
                f"Canonical example {canonical_id} has {len(nonzero)} progressed source rows but "
                "its answer history does not exactly account for their attempts. "
                "No data was consolidated; resolve this group explicitly before retrying."
            )
        if len(nonzero) <= 1:
            basis = nonzero[0] if nonzero else rows[0] if rows else None
            values = {key: basis[key] for key in (
                "attempts", "correct_count", "wrong_count", "current_correct_streak",
                "mastery_score", "status", "last_result", "last_practiced_at",
            )} if basis else _calculated_progress(history)
        else:
            values = _calculated_progress(history)
        consolidated.append({
            "item_id": canonical_id, **values,
            "is_starred": any(row["is_starred"] for row in rows),
            "created_at": min((row["created_at"] for row in rows), default=now),
            "updated_at": now,
        })

    # Historical rows retain their IDs and source_entry_id; only their automatic
    # progress identity changes to the shared canonical target. A temporary map
    # makes the rewrite atomic and avoids numeric-ID collision during remapping.
    bind.execute(sa.text("CREATE TEMPORARY TABLE canonical_example_map (old_id INTEGER PRIMARY KEY, canonical_id INTEGER NOT NULL)"))
    if old_to_canonical:
        bind.execute(
            sa.text("INSERT INTO canonical_example_map (old_id, canonical_id) VALUES (:old_id, :canonical_id)"),
            [{"old_id": old_id, "canonical_id": canonical_id} for old_id, canonical_id in old_to_canonical.items()],
        )
    bind.execute(sa.text("""
        UPDATE practice_questions AS question
        SET item_id = mapping.canonical_id
        FROM canonical_example_map AS mapping
        WHERE question.item_type = 'kanji_example' AND question.item_id = mapping.old_id
    """))
    bind.execute(sa.text("""
        UPDATE practice_answers AS answer
        SET item_id = mapping.canonical_id
        FROM canonical_example_map AS mapping
        WHERE answer.item_type = 'kanji_example' AND answer.item_id = mapping.old_id
    """))
    bind.execute(sa.text("DROP TABLE canonical_example_map"))
    bind.execute(sa.text("DELETE FROM item_progress WHERE item_type = 'kanji_example'"))
    if consolidated:
        bind.execute(sa.text("""
            INSERT INTO item_progress
                (item_type, item_id, attempts, correct_count, wrong_count,
                 current_correct_streak, mastery_score, status, is_starred,
                 last_result, last_practiced_at, created_at, updated_at)
            VALUES
                ('kanji_example', :item_id, :attempts, :correct_count, :wrong_count,
                 :current_correct_streak, :mastery_score, :status, :is_starred,
                 :last_result, :last_practiced_at, :created_at, :updated_at)
        """), consolidated)

    op.alter_column("kanji_examples", "canonical_id", nullable=False)
    op.create_foreign_key("fk_kanji_examples_canonical_id", "kanji_examples", "canonical_kanji_examples", ["canonical_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_kanji_examples_canonical_id", "kanji_examples", ["canonical_id"])


def downgrade() -> None:
    raise RuntimeError(
        "0016 cannot be automatically downgraded because shared progress cannot be "
        "safely split back into source-specific counters without inventing attempts."
    )
