"""add itemized projection spending

Revision ID: 0020_spending_items
Revises: 0019_property_tax_basis
Create Date: 2026-07-19 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0020_spending_items"
down_revision: str | Sequence[str] | None = "0019_property_tax_basis"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "projection_settings",
        sa.Column(
            "spending_mode",
            sa.String(length=32),
            nullable=False,
            server_default="manual",
        ),
    )
    op.alter_column("projection_settings", "spending_mode", server_default=None)
    op.create_table(
        "spending_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("annual_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("retirement_annual_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("growth_rate", sa.Numeric(8, 6), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_spending_items_household_id", "spending_items", ["household_id"])
    op.create_index(
        "ix_spending_items_household_category",
        "spending_items",
        ["household_id", "category"],
    )


def downgrade() -> None:
    op.drop_index("ix_spending_items_household_category", table_name="spending_items")
    op.drop_index("ix_spending_items_household_id", table_name="spending_items")
    op.drop_table("spending_items")
    op.drop_column("projection_settings", "spending_mode")
