"""add golden_sets table

Revision ID: 002
Revises: 001
Create Date: 2026-06-20
"""

from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "golden_sets",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("prompt_id", sa.Uuid(as_uuid=True), sa.ForeignKey("prompts.id"), nullable=False),
        sa.Column("input", sa.Text, nullable=False),
        sa.Column("expected_behavior", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_golden_sets_prompt_id", "golden_sets", ["prompt_id"])


def downgrade() -> None:
    op.drop_index("ix_golden_sets_prompt_id", table_name="golden_sets")
    op.drop_table("golden_sets")
