"""add income and annual tax records

Revision ID: 0004_income_tax_records
Revises: 0003_real_estate_profiles
Create Date: 2026-07-16 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0004_income_tax_records"
down_revision: str | Sequence[str] | None = "0003_real_estate_profiles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "income_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("income_type", sa.String(length=80), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("frequency", sa.String(length=32), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("growth_rate", sa.Numeric(8, 6), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_income_sources_household_id", "income_sources", ["household_id"])

    op.create_table(
        "annual_tax_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("tax_year", sa.Integer(), nullable=False),
        sa.Column("gross_income", sa.Numeric(18, 2), nullable=True),
        sa.Column("total_taxes_paid", sa.Numeric(18, 2), nullable=False),
        sa.Column("refund_or_amount_due", sa.Numeric(18, 2), nullable=True),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("household_id", "tax_year", name="uq_annual_tax_records_household_year"),
    )
    op.create_index("ix_annual_tax_records_household_id", "annual_tax_records", ["household_id"])


def downgrade() -> None:
    op.drop_index("ix_annual_tax_records_household_id", table_name="annual_tax_records")
    op.drop_table("annual_tax_records")
    op.drop_index("ix_income_sources_household_id", table_name="income_sources")
    op.drop_table("income_sources")
