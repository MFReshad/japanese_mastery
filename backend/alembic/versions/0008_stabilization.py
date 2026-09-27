"""Progress uniqueness and durable import/manual-edit separation.

Refuses ambiguous data instead of silently deleting progress.
"""

from alembic import op
import sqlalchemy as sa

revision = "0008_stabilization"
down_revision = "0007_starred_progress"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    # Exclude concurrent writers between audit and constraint creation.
    bind.execute(sa.text("LOCK TABLE item_progress IN ACCESS EXCLUSIVE MODE"))
    duplicate = bind.execute(
        sa.text(
            "SELECT item_type, item_id FROM item_progress GROUP BY item_type, item_id HAVING count(*) > 1 LIMIT 1"
        )
    ).first()
    if duplicate:
        raise RuntimeError(
            "Duplicate progress exists. Run scripts/audit_progress.py and reconcile before upgrading; no rows were changed."
        )
    op.create_unique_constraint(
        "uq_progress_item", "item_progress", ["item_type", "item_id"]
    )
    for table in ("vocabulary_sources", "kanji_sources"):
        op.add_column(table, sa.Column("imported_baseline", sa.JSON(), nullable=True))
        op.add_column(table, sa.Column("manual_overrides", sa.JSON(), nullable=True))
    op.create_table(
        "source_suppressions",
        sa.Column("item_type", sa.String(20), primary_key=True),
        sa.Column("source_id", sa.String(255), primary_key=True),
    )


def downgrade():
    raise RuntimeError(
        "Downgrade would discard manual-edit provenance. Restore a backup instead."
    )
