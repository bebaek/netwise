"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-07-16 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial_schema"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "households",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("institution_name", sa.String(length=200), nullable=True),
        sa.Column("account_kind", sa.String(length=32), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("liquidity_class", sa.String(length=80), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_accounts_household_id", "accounts", ["household_id"])

    op.create_table(
        "balance_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("balance", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("confidence_level", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "as_of_date", name="uq_balance_snapshots_account_date"),
    )
    op.create_index(
        "ix_balance_snapshots_account_date", "balance_snapshots", ["account_id", "as_of_date"]
    )
    op.create_index(
        "ix_balance_snapshots_household_date", "balance_snapshots", ["household_id", "as_of_date"]
    )


def downgrade() -> None:
    op.drop_index("ix_balance_snapshots_household_date", table_name="balance_snapshots")
    op.drop_index("ix_balance_snapshots_account_date", table_name="balance_snapshots")
    op.drop_table("balance_snapshots")
    op.drop_index("ix_accounts_household_id", table_name="accounts")
    op.drop_table("accounts")
    op.drop_table("households")
