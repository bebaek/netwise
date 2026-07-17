"""add account liquidation expense rates

Revision ID: 0009_liquidation_expense_rates
Revises: 0008_projection_settings
Create Date: 2026-07-17 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0009_liquidation_expense_rates"
down_revision: str | Sequence[str] | None = "0008_projection_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("liquidation_expense_rate", sa.Numeric(8, 6), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("accounts", "liquidation_expense_rate")
