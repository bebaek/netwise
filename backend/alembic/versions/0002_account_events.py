"""add account events

Revision ID: 0002_account_events
Revises: 0001_initial_schema
Create Date: 2026-07-16 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0002_account_events"
down_revision: str | Sequence[str] | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "account_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("projection_behavior", sa.String(length=64), nullable=False),
        sa.Column("scenario_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_account_events_account_date", "account_events", ["account_id", "event_date"])
    op.create_index(
        "ix_account_events_household_date", "account_events", ["household_id", "event_date"]
    )


def downgrade() -> None:
    op.drop_index("ix_account_events_household_date", table_name="account_events")
    op.drop_index("ix_account_events_account_date", table_name="account_events")
    op.drop_table("account_events")
