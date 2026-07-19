"""add property adjusted tax basis

Revision ID: 0019_property_tax_basis
Revises: 0018_projection_transfers
Create Date: 2026-07-19 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0019_property_tax_basis"
down_revision: str | Sequence[str] | None = "0018_projection_transfers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "real_estate_properties",
        sa.Column("adjusted_tax_basis", sa.Numeric(18, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("real_estate_properties", "adjusted_tax_basis")
