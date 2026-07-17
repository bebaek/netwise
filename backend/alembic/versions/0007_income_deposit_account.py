"""add income deposit account

Revision ID: 0007_income_deposit_account
Revises: 0006_user_management
Create Date: 2026-07-17 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0007_income_deposit_account"
down_revision: str | Sequence[str] | None = "0006_user_management"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("income_sources", sa.Column("deposit_account_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_income_sources_deposit_account_id_accounts",
        "income_sources",
        "accounts",
        ["deposit_account_id"],
        ["id"],
    )
    op.create_index(
        "ix_income_sources_deposit_account_id",
        "income_sources",
        ["deposit_account_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_income_sources_deposit_account_id", table_name="income_sources")
    op.drop_constraint(
        "fk_income_sources_deposit_account_id_accounts",
        "income_sources",
        type_="foreignkey",
    )
    op.drop_column("income_sources", "deposit_account_id")
