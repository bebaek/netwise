"""add liquid-runway property sale optimization mode

Revision ID: 0016_liquid_runway_optimization
Revises: 0015_real_estate_liquidation
Create Date: 2026-07-18 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0016_liquid_runway_optimization"
down_revision: str | Sequence[str] | None = "0015_real_estate_liquidation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "real_estate_liquidation_strategies",
        sa.Column(
            "optimization_mode",
            sa.String(),
            nullable=False,
            server_default="liquidity_shortfall",
        ),
    )


def downgrade() -> None:
    op.drop_column("real_estate_liquidation_strategies", "optimization_mode")
