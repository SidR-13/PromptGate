"""add locale_checks table

Revision ID: 003
Revises: 002
Create Date: 2026-06-21
"""

from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "locale_checks",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("run_id", sa.Uuid(as_uuid=True), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("locale", sa.String(10), nullable=False),
        sa.Column("check_type", sa.String(50), nullable=False),
        sa.Column("passed", sa.Boolean, nullable=False),
        sa.Column("details", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_locale_checks_run_id", "locale_checks", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_locale_checks_run_id", table_name="locale_checks")
    op.drop_table("locale_checks")
