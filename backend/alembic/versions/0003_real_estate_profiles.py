"""add real estate and mortgage profiles

Revision ID: 0003_real_estate_profiles
Revises: 0002_account_events
Create Date: 2026-07-16 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0003_real_estate_profiles"
down_revision: str | Sequence[str] | None = "0002_account_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "real_estate_properties",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("property_type", sa.String(length=64), nullable=False),
        sa.Column("purchase_date", sa.Date(), nullable=True),
        sa.Column("purchase_price", sa.Numeric(18, 2), nullable=True),
        sa.Column("down_payment", sa.Numeric(18, 2), nullable=True),
        sa.Column("expected_appreciation_rate", sa.Numeric(8, 6), nullable=True),
        sa.Column("property_tax_annual", sa.Numeric(18, 2), nullable=True),
        sa.Column("insurance_annual", sa.Numeric(18, 2), nullable=True),
        sa.Column("maintenance_rate", sa.Numeric(8, 6), nullable=True),
        sa.Column("hoa_monthly", sa.Numeric(18, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", name="uq_real_estate_properties_account"),
    )
    op.create_index(
        "ix_real_estate_properties_household_id", "real_estate_properties", ["household_id"]
    )

    op.create_table(
        "mortgage_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("liability_account_id", sa.Uuid(), nullable=False),
        sa.Column("property_account_id", sa.Uuid(), nullable=True),
        sa.Column("original_principal", sa.Numeric(18, 2), nullable=False),
        sa.Column("interest_rate", sa.Numeric(8, 6), nullable=False),
        sa.Column("term_months", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("monthly_payment", sa.Numeric(18, 2), nullable=True),
        sa.Column("rate_type", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.ForeignKeyConstraint(["liability_account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["property_account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("liability_account_id", name="uq_mortgage_profiles_liability_account"),
    )
    op.create_index("ix_mortgage_profiles_household_id", "mortgage_profiles", ["household_id"])
    op.create_index(
        "ix_mortgage_profiles_property_account_id", "mortgage_profiles", ["property_account_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_mortgage_profiles_property_account_id", table_name="mortgage_profiles")
    op.drop_index("ix_mortgage_profiles_household_id", table_name="mortgage_profiles")
    op.drop_table("mortgage_profiles")
    op.drop_index("ix_real_estate_properties_household_id", table_name="real_estate_properties")
    op.drop_table("real_estate_properties")
