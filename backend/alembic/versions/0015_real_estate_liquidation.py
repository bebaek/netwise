"""add automatic real estate liquidation strategies

Revision ID: 0015_real_estate_liquidation
Revises: 0014_property_sale_tax
Create Date: 2026-07-18 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0015_real_estate_liquidation"
down_revision: str | Sequence[str] | None = "0014_property_sale_tax"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "real_estate_liquidation_strategies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("property_account_id", sa.Uuid(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("earliest_sale_date", sa.Date(), nullable=True),
        sa.Column("proceeds_account_id", sa.Uuid(), nullable=False),
        sa.Column("selling_expense_rate", sa.Numeric(8, 6), nullable=True),
        sa.Column(
            "estimated_tax_rate",
            sa.Numeric(8, 6),
            nullable=False,
            server_default="0.150000",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.ForeignKeyConstraint(["proceeds_account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["property_account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "property_account_id",
            name="uq_real_estate_liquidation_strategies_property",
        ),
    )
    op.create_index(
        "ix_real_estate_liquidation_strategies_household_priority",
        "real_estate_liquidation_strategies",
        ["household_id", "priority"],
    )
    op.create_index(
        "ix_real_estate_liquidation_strategies_proceeds_account_id",
        "real_estate_liquidation_strategies",
        ["proceeds_account_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_real_estate_liquidation_strategies_proceeds_account_id",
        table_name="real_estate_liquidation_strategies",
    )
    op.drop_index(
        "ix_real_estate_liquidation_strategies_household_priority",
        table_name="real_estate_liquidation_strategies",
    )
    op.drop_table("real_estate_liquidation_strategies")
