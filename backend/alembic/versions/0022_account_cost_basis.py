"""add account cost basis for capital-gain taxation

Revision ID: 0022_account_cost_basis
Revises: 0021_property_appreciation
Create Date: 2026-07-20 00:00:00.000000

Taxable investment withdrawals should be taxed on the capital gain, not the
full gross amount. An explicit per-account cost basis wins when provided; the
projection falls back to the account's oldest balance snapshot as a simple
estimate, and to the current balance (zero gain) when no snapshots exist.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0022_account_cost_basis"
down_revision: str | Sequence[str] | None = "0021_property_appreciation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("cost_basis", sa.Numeric(18, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("accounts", "cost_basis")
