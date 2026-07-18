"""add estimated property sale tax rate

Revision ID: 0014_property_sale_tax
Revises: 0013_retirement_tax_treatment
Create Date: 2026-07-18 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0014_property_sale_tax"
down_revision: str | Sequence[str] | None = "0013_retirement_tax_treatment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "real_estate_sales",
        sa.Column(
            "estimated_tax_rate",
            sa.Numeric(8, 6),
            nullable=False,
            server_default="0.150000",
        ),
    )


def downgrade() -> None:
    op.drop_column("real_estate_sales", "estimated_tax_rate")
