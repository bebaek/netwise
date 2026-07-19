"""add retirement projection settings

Revision ID: 0017_retirement_projection
Revises: 0016_liquid_runway_optimization
Create Date: 2026-07-19 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0017_retirement_projection"
down_revision: str | Sequence[str] | None = "0016_liquid_runway_optimization"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "projection_settings",
        sa.Column("retirement_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "projection_settings",
        sa.Column("retirement_annual_spending", sa.Numeric(18, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("projection_settings", "retirement_annual_spending")
    op.drop_column("projection_settings", "retirement_date")
