"""persist practice questions and keep answers off the start response

Revision ID: 0003_practice_questions
Revises: 0002_dataset_compatibility
Create Date: 2026-09-21
"""
from alembic import op
import sqlalchemy as sa


revision = "0003_practice_questions"
down_revision = "0002_dataset_compatibility"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "practice_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("practice_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("item_type", sa.String(20), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("source_entry_id", sa.Integer(), nullable=False),
        sa.Column("question_type", sa.String(60), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("answer_primary", sa.Text(), nullable=False),
        sa.Column("answer_secondary", sa.Text()),
        sa.Column("revealed_at", sa.DateTime(timezone=True)),
        sa.Column("answered_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("session_id", "position", name="uq_practice_question_position"),
    )
    op.create_index("ix_practice_questions_session_id", "practice_questions", ["session_id"])
    with op.batch_alter_table("practice_answers") as batch:
        batch.add_column(sa.Column("question_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_practice_answers_question_id", "practice_questions", ["question_id"], ["id"], ondelete="SET NULL")
        batch.create_unique_constraint("uq_practice_answers_question_id", ["question_id"])


def downgrade() -> None:
    with op.batch_alter_table("practice_answers") as batch:
        batch.drop_constraint("uq_practice_answers_question_id", type_="unique")
        batch.drop_constraint("fk_practice_answers_question_id", type_="foreignkey")
        batch.drop_column("question_id")
    op.drop_index("ix_practice_questions_session_id", table_name="practice_questions")
    op.drop_table("practice_questions")
