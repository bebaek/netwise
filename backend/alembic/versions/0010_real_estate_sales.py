"""add real estate sales

Revision ID: 0010_real_estate_sales
Revises: 0009_liquidation_expense_rates
Create Date: 2026-07-17 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0010_real_estate_sales"
down_revision: str | Sequence[str] | None = "0009_liquidation_expense_rates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "real_estate_sales",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("property_account_id", sa.Uuid(), nullable=False),
        sa.Column("sale_date", sa.Date(), nullable=False),
        sa.Column("gross_sale_price", sa.Numeric(18, 2), nullable=False),
        sa.Column("proceeds_account_id", sa.Uuid(), nullable=False),
        sa.Column("selling_expense_rate", sa.Numeric(8, 6), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.ForeignKeyConstraint(["proceeds_account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["property_account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("property_account_id", name="uq_real_estate_sales_property_account"),
    )
    op.create_index(
        "ix_real_estate_sales_household_date",
        "real_estate_sales",
        ["household_id", "sale_date"],
    )
    op.create_index(
        "ix_real_estate_sales_proceeds_account_id",
        "real_estate_sales",
        ["proceeds_account_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_real_estate_sales_proceeds_account_id", table_name="real_estate_sales")
    op.drop_index("ix_real_estate_sales_household_date", table_name="real_estate_sales")
    op.drop_table("real_estate_sales")
