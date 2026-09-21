"""Replace unanswered vocabulary-style kanji prompts without touching answer history."""

from alembic import op
import sqlalchemy as sa

revision = "0006_repair_kanji_questions"
down_revision = "0005_read_path_indexes"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(sa.text("""
        UPDATE practice_questions AS question
        SET question_type = 'kanji_to_meaning',
            prompt = kanji.character,
            answer_primary = source.meaning_as_printed,
            answer_secondary = NULL,
            reveal_context = jsonb_build_object(
                'kind', 'kanji',
                'kanji', kanji.character,
                'meanings', CASE
                    WHEN jsonb_array_length(source.meanings_as_printed::jsonb) > 0
                    THEN source.meanings_as_printed::jsonb
                    ELSE jsonb_build_array(source.meaning_as_printed)
                END,
                'onyomi', source.onyomi_as_printed::jsonb,
                'kunyomi', source.kunyomi_as_printed::jsonb,
                'examples', COALESCE((
                    SELECT jsonb_agg(jsonb_build_object(
                        'word', example.word, 'reading', example.reading, 'meaning', example.meaning
                    ) ORDER BY example.sort_order, example.id)
                    FROM kanji_examples AS example
                    WHERE example.kanji_source_id = source.id
                ), '[]'::jsonb)
            )::json,
            revealed_at = NULL
        FROM kanji_sources AS source
        JOIN kanji ON kanji.id = source.kanji_id
        WHERE question.item_type = 'kanji'
          AND question.source_entry_id = source.id
          AND question.answered_at IS NULL
          AND question.question_type IN (
              'example_to_reading', 'example_to_meaning',
              'reading_to_example', 'meaning_to_example', 'reading_to_kanji'
          )
    """))


def downgrade():
    pass
