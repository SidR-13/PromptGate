"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-20
"""

from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prompts",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("template", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("name", "version", name="uq_prompt_name_version"),
    )
    op.create_index("ix_prompts_name", "prompts", ["name"])

    op.create_table(
        "runs",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("prompt_id", sa.Uuid(as_uuid=True), sa.ForeignKey("prompts.id"), nullable=False),
        sa.Column("input", sa.Text, nullable=False),
        sa.Column("output", sa.Text, nullable=False),
        sa.Column("locale", sa.String(10), nullable=False),
        sa.Column("score", sa.Float, nullable=True),
        sa.Column("judge_reasoning", sa.Text, nullable=True),
        sa.Column("blocked", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("block_reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("runs")
    op.drop_index("ix_prompts_name", table_name="prompts")
    op.drop_table("prompts")
