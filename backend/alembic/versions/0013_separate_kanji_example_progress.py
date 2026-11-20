"""Track kanji example-word practice independently from kanji characters."""

from collections import defaultdict

import sqlalchemy as sa
from alembic import op


revision = "0013_example_progress"
down_revision = "0012_vocab_directions"
branch_labels = None
depends_on = None


def _status(attempts, correct, streak, last_result):
    if attempts == 0:
        return "new", 0.0
    accuracy = correct / attempts
    if last_result == "wrong" or accuracy < 0.7:
        return "weak", round(accuracy, 4)
    if attempts >= 5 and accuracy >= 0.9 and streak >= 3:
        return "mastered", round(accuracy, 4)
    return "learning", round(accuracy, 4)


def _rebuild_progress(item_types):
    bind = op.get_bind()
    answers = bind.execute(
        sa.text(
            """
            SELECT item_type, item_id, result, answered_at
            FROM practice_answers
            WHERE item_type = ANY(:item_types)
            ORDER BY answered_at, id
            """
        ),
        {"item_types": list(item_types)},
    ).mappings()
    stats = defaultdict(
        lambda: {"attempts": 0, "correct": 0, "wrong": 0, "streak": 0,
                 "last": None, "last_at": None}
    )
    for answer in answers:
        row = stats[(answer["item_type"], answer["item_id"])]
        row["attempts"] += 1
        row["last"] = answer["result"]
        row["last_at"] = answer["answered_at"]
        if answer["result"] == "correct":
            row["correct"] += 1
            row["streak"] += 1
        else:
            row["wrong"] += 1
            row["streak"] = 0

    parameters = []
    for (item_type, item_id), row in stats.items():
        status, score = _status(
            row["attempts"], row["correct"], row["streak"], row["last"]
        )
        parameters.append(
            {
                "item_type": item_type,
                "item_id": item_id,
                **row,
                "score": score,
                "status": status,
            }
        )
    if parameters:
        bind.execute(
            sa.text(
                """
                INSERT INTO item_progress
                    (item_type, item_id, attempts, correct_count, wrong_count,
                     current_correct_streak, mastery_score, status, is_starred,
                     last_result, last_practiced_at, created_at, updated_at)
                VALUES
                    (:item_type, :item_id, :attempts, :correct, :wrong, :streak,
                     :score, :status, false, :last, :last_at, now(), now())
                ON CONFLICT (item_type, item_id) DO UPDATE SET
                    attempts = EXCLUDED.attempts,
                    correct_count = EXCLUDED.correct_count,
                    wrong_count = EXCLUDED.wrong_count,
                    current_correct_streak = EXCLUDED.current_correct_streak,
                    mastery_score = EXCLUDED.mastery_score,
                    status = EXCLUDED.status,
                    last_result = EXCLUDED.last_result,
                    last_practiced_at = EXCLUDED.last_practiced_at,
                    updated_at = now()
                """
            ),
            parameters,
        )


def upgrade():
    op.drop_constraint("ck_progress_item_type", "item_progress", type_="check")
    op.create_check_constraint(
        "ck_progress_item_type",
        "item_progress",
        "item_type in ('vocabulary', 'kanji', 'kanji_example')",
    )
    op.drop_constraint("ck_answer_item_type", "practice_answers", type_="check")
    op.create_check_constraint(
        "ck_answer_item_type",
        "practice_answers",
        "item_type in ('vocabulary', 'kanji', 'kanji_example')",
    )

    # A repeated printed word can exist in malformed imported data. The first
    # printed occurrence is the canonical target, matching study/practice order.
    op.execute(
        """
        WITH ranked_examples AS (
            SELECT id, kanji_source_id, word,
                   row_number() OVER (
                       PARTITION BY kanji_source_id, word ORDER BY sort_order, id
                   ) AS occurrence
            FROM kanji_examples
        )
        UPDATE practice_questions AS question
        SET item_type = 'kanji_example', item_id = example.id
        FROM ranked_examples AS example
        WHERE question.question_type = 'important_kanji_word'
          AND example.occurrence = 1
          AND example.kanji_source_id = question.source_entry_id
          AND example.word = question.prompt
        """
    )
    op.execute(
        """
        UPDATE practice_answers AS answer
        SET item_type = question.item_type, item_id = question.item_id
        FROM practice_questions AS question
        WHERE answer.question_id = question.id
          AND question.item_type = 'kanji_example'
        """
    )
    op.execute(
        """
        UPDATE item_progress AS progress
        SET attempts = 0, correct_count = 0, wrong_count = 0,
            current_correct_streak = 0, mastery_score = 0, status = 'new',
            last_result = NULL, last_practiced_at = NULL, updated_at = now()
        WHERE progress.item_type = 'kanji'
          AND EXISTS (
              SELECT 1
              FROM practice_answers AS answer
              JOIN kanji_examples AS example ON example.id = answer.item_id
              JOIN kanji_sources AS source ON source.id = example.kanji_source_id
              WHERE answer.item_type = 'kanji_example'
                AND source.kanji_id = progress.item_id
          )
          AND NOT EXISTS (
              SELECT 1 FROM practice_answers AS answer
              WHERE answer.item_type = 'kanji'
                AND answer.item_id = progress.item_id
          )
        """
    )
    _rebuild_progress({"kanji", "kanji_example"})


def downgrade():
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE practice_questions AS question
            SET item_type = 'kanji', item_id = source.kanji_id
            FROM kanji_examples AS example
            JOIN kanji_sources AS source ON source.id = example.kanji_source_id
            WHERE question.item_type = 'kanji_example'
              AND question.item_id = example.id
            """
        )
    )
    op.execute(
        """
        UPDATE practice_answers AS answer
        SET item_type = question.item_type, item_id = question.item_id
        FROM practice_questions AS question
        WHERE answer.question_id = question.id
          AND answer.item_type = 'kanji_example'
        """
    )
    op.execute("DELETE FROM item_progress WHERE item_type = 'kanji_example'")
    _rebuild_progress({"kanji"})
    op.drop_constraint("ck_answer_item_type", "practice_answers", type_="check")
    op.create_check_constraint(
        "ck_answer_item_type",
        "practice_answers",
        "item_type in ('vocabulary', 'kanji')",
    )
    op.drop_constraint("ck_progress_item_type", "item_progress", type_="check")
    op.create_check_constraint(
        "ck_progress_item_type",
        "item_progress",
        "item_type in ('vocabulary', 'kanji')",
    )
