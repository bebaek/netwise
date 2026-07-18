"""add combined annual property tax and insurance

Revision ID: 0012_combined_tax_insurance
Revises: 0011_rental_finance
Create Date: 2026-07-18 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0012_combined_tax_insurance"
down_revision: str | Sequence[str] | None = "0011_rental_finance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "real_estate_properties",
        sa.Column("tax_and_insurance_annual", sa.Numeric(18, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("real_estate_properties", "tax_and_insurance_annual")
