"""add recurring projection transfers

Revision ID: 0018_projection_transfers
Revises: 0017_retirement_projection
Create Date: 2026-07-19 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0018_projection_transfers"
down_revision: str | Sequence[str] | None = "0017_retirement_projection"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "projection_transfers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("from_account_id", sa.Uuid(), nullable=False),
        sa.Column("to_account_id", sa.Uuid(), nullable=False),
        sa.Column("annual_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("growth_rate", sa.Numeric(8, 6), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["from_account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.ForeignKeyConstraint(["to_account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_projection_transfers_household_id",
        "projection_transfers",
        ["household_id"],
    )
    op.create_index(
        "ix_projection_transfers_from_account_id",
        "projection_transfers",
        ["from_account_id"],
    )
    op.create_index(
        "ix_projection_transfers_to_account_id",
        "projection_transfers",
        ["to_account_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_projection_transfers_to_account_id", table_name="projection_transfers")
    op.drop_index("ix_projection_transfers_from_account_id", table_name="projection_transfers")
    op.drop_index("ix_projection_transfers_household_id", table_name="projection_transfers")
    op.drop_table("projection_transfers")
