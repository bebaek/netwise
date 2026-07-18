"""add explicit retirement tax treatment

Revision ID: 0013_retirement_tax_treatment
Revises: 0012_combined_tax_insurance
Create Date: 2026-07-18 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0013_retirement_tax_treatment"
down_revision: str | Sequence[str] | None = "0012_combined_tax_insurance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("retirement_tax_treatment", sa.String(length=32), nullable=True),
    )
    op.execute(
        """
        UPDATE accounts
        SET retirement_tax_treatment = 'roth'
        WHERE category = 'retirement' AND lower(name) LIKE '%roth%'
        """
    )
    op.execute(
        """
        UPDATE accounts
        SET retirement_tax_treatment = 'traditional'
        WHERE category = 'retirement' AND retirement_tax_treatment IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("accounts", "retirement_tax_treatment")
