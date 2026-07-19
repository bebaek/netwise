"""make property appreciation the real-estate growth source

Revision ID: 0021_property_appreciation
Revises: 0020_spending_items
Create Date: 2026-07-19 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0021_property_appreciation"
down_revision: str | Sequence[str] | None = "0020_spending_items"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Preserve a legacy account-level assumption when the property profile does
    # not already have one, then remove the duplicate source from the account.
    op.execute(
        """
        UPDATE real_estate_properties
        SET expected_appreciation_rate = COALESCE(
            expected_appreciation_rate,
            (
                SELECT accounts.expected_annual_yield
                FROM accounts
                WHERE accounts.id = real_estate_properties.account_id
            ),
            0
        )
        """
    )
    op.execute(
        """
        UPDATE accounts
        SET expected_annual_yield = NULL
        WHERE category = 'real_estate'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE accounts
        SET expected_annual_yield = (
            SELECT real_estate_properties.expected_appreciation_rate
            FROM real_estate_properties
            WHERE real_estate_properties.account_id = accounts.id
        )
        WHERE category = 'real_estate'
        """
    )
