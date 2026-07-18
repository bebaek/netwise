"""add rental finance assumptions

Revision ID: 0011_rental_finance
Revises: 0010_real_estate_sales
Create Date: 2026-07-17 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0011_rental_finance"
down_revision: str | Sequence[str] | None = "0010_real_estate_sales"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "real_estate_properties", sa.Column("is_rental", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column("real_estate_properties", sa.Column("rental_start_date", sa.Date(), nullable=True))
    op.add_column("real_estate_properties", sa.Column("monthly_market_rent", sa.Numeric(18, 2), nullable=True))
    op.add_column("real_estate_properties", sa.Column("other_monthly_income", sa.Numeric(18, 2), nullable=True))
    op.add_column("real_estate_properties", sa.Column("rent_growth_rate", sa.Numeric(8, 6), nullable=True))
    op.add_column("real_estate_properties", sa.Column("vacancy_rate", sa.Numeric(8, 6), nullable=True))
    op.add_column("real_estate_properties", sa.Column("management_fee_rate", sa.Numeric(8, 6), nullable=True))
    op.add_column("real_estate_properties", sa.Column("utilities_annual", sa.Numeric(18, 2), nullable=True))
    op.add_column("real_estate_properties", sa.Column("other_operating_expense_annual", sa.Numeric(18, 2), nullable=True))
    op.add_column("real_estate_properties", sa.Column("capital_reserve_rate", sa.Numeric(8, 6), nullable=True))
    op.add_column("real_estate_properties", sa.Column("rental_deposit_account_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_real_estate_properties_rental_deposit_account_id_accounts",
        "real_estate_properties",
        "accounts",
        ["rental_deposit_account_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_real_estate_properties_rental_deposit_account_id_accounts",
        "real_estate_properties",
        type_="foreignkey",
    )
    for column in (
        "rental_deposit_account_id", "capital_reserve_rate", "other_operating_expense_annual",
        "utilities_annual", "management_fee_rate", "vacancy_rate", "rent_growth_rate",
        "other_monthly_income", "monthly_market_rent", "rental_start_date", "is_rental",
    ):
        op.drop_column("real_estate_properties", column)
