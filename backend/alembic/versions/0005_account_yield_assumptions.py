"""add account yield assumptions

Revision ID: 0005_account_yield_assumptions
Revises: 0004_income_tax_records
Create Date: 2026-07-17 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0005_account_yield_assumptions"
down_revision: str | Sequence[str] | None = "0004_income_tax_records"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("expected_annual_yield", sa.Numeric(8, 6), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("accounts", "expected_annual_yield")
