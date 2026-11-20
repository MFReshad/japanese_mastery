"""Reset legacy kanji progress that came only from example-word answers."""

from alembic import op


revision = "0014_reset_example_rollup"
down_revision = "0013_example_progress"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        UPDATE item_progress AS progress
        SET attempts = 0,
            correct_count = 0,
            wrong_count = 0,
            current_correct_streak = 0,
            mastery_score = 0,
            status = 'new',
            last_result = NULL,
            last_practiced_at = NULL,
            updated_at = now()
        WHERE progress.item_type = 'kanji'
          AND EXISTS (
              SELECT 1
              FROM practice_answers AS answer
              JOIN kanji_examples AS example
                ON example.id = answer.item_id
              JOIN kanji_sources AS source
                ON source.id = example.kanji_source_id
              WHERE answer.item_type = 'kanji_example'
                AND source.kanji_id = progress.item_id
          )
          AND NOT EXISTS (
              SELECT 1
              FROM practice_answers AS answer
              WHERE answer.item_type = 'kanji'
                AND answer.item_id = progress.item_id
          )
        """
    )


def downgrade():
    # The former mixed counters cannot be reconstructed without deliberately
    # combining the two independent histories again.
    pass
