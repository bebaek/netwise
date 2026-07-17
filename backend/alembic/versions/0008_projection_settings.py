"""add projection settings

Revision ID: 0008_projection_settings
Revises: 0007_income_deposit_account
Create Date: 2026-07-17 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0008_projection_settings"
down_revision: str | Sequence[str] | None = "0007_income_deposit_account"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "projection_settings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("annual_spending", sa.Numeric(18, 2), nullable=True),
        sa.Column("spending_inflation_rate", sa.Numeric(8, 6), nullable=True),
        sa.Column("spending_account_id", sa.Uuid(), nullable=True),
        sa.Column("tax_account_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.ForeignKeyConstraint(["spending_account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["tax_account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("household_id", name="uq_projection_settings_household"),
    )
    op.create_index("ix_projection_settings_household_id", "projection_settings", ["household_id"])
    op.create_index(
        "ix_projection_settings_spending_account_id",
        "projection_settings",
        ["spending_account_id"],
    )
    op.create_index(
        "ix_projection_settings_tax_account_id",
        "projection_settings",
        ["tax_account_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_projection_settings_tax_account_id", table_name="projection_settings")
    op.drop_index("ix_projection_settings_spending_account_id", table_name="projection_settings")
    op.drop_index("ix_projection_settings_household_id", table_name="projection_settings")
    op.drop_table("projection_settings")
