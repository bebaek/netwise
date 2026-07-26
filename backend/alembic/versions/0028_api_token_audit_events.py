"""add API token audit events

Revision ID: 0028_api_token_audit_events
Revises: 0027_api_tokens
Create Date: 2026-07-26 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0028_api_token_audit_events"
down_revision: str | Sequence[str] | None = "0027_api_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "api_token_audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("api_token_id", sa.Uuid(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("token_name", sa.String(length=100), nullable=False),
        sa.Column("token_prefix", sa.String(length=16), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("path", sa.String(length=500), nullable=False),
        sa.Column("tool_name", sa.String(length=100), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["api_token_id"], ["api_tokens.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_api_token_audit_events_token_id",
        "api_token_audit_events",
        ["api_token_id"],
    )
    op.create_index(
        "ix_api_token_audit_events_user_created",
        "api_token_audit_events",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_api_token_audit_events_household_created",
        "api_token_audit_events",
        ["household_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_api_token_audit_events_household_created",
        table_name="api_token_audit_events",
    )
    op.drop_index(
        "ix_api_token_audit_events_user_created",
        table_name="api_token_audit_events",
    )
    op.drop_index(
        "ix_api_token_audit_events_token_id",
        table_name="api_token_audit_events",
    )
    op.drop_table("api_token_audit_events")
