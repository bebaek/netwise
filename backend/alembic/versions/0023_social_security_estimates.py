"""add household people and Social Security estimates

Revision ID: 0023_social_security_estimates
Revises: 0022_account_cost_basis
Create Date: 2026-07-20 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0023_social_security_estimates"
down_revision: str | Sequence[str] | None = "0022_account_cost_basis"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "household_people",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_household_people_household_id", "household_people", ["household_id"])
    op.create_table(
        "social_security_estimates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column("income_source_id", sa.Uuid(), nullable=False),
        sa.Column("calculation_mode", sa.String(length=32), nullable=False),
        sa.Column("claiming_date", sa.Date(), nullable=False),
        sa.Column("current_covered_earnings", sa.Numeric(18, 2), nullable=True),
        sa.Column("completed_work_years", sa.Integer(), nullable=True),
        sa.Column("expected_work_end_date", sa.Date(), nullable=True),
        sa.Column("earnings_pattern", sa.String(length=32), nullable=True),
        sa.Column("manual_monthly_benefit", sa.Numeric(18, 2), nullable=True),
        sa.Column("cola_rate", sa.Numeric(8, 6), nullable=False),
        sa.Column("estimated_monthly_benefit", sa.Numeric(18, 2), nullable=False),
        sa.Column("lower_monthly_benefit", sa.Numeric(18, 2), nullable=False),
        sa.Column("upper_monthly_benefit", sa.Numeric(18, 2), nullable=False),
        sa.Column("full_retirement_age_months", sa.Integer(), nullable=False),
        sa.Column("benefit_at_full_retirement_age", sa.Numeric(18, 2), nullable=False),
        sa.Column("calculation_version", sa.String(length=80), nullable=False),
        sa.Column("law_assumption_year", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"]),
        sa.ForeignKeyConstraint(["person_id"], ["household_people.id"]),
        sa.ForeignKeyConstraint(["income_source_id"], ["income_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("income_source_id"),
        sa.UniqueConstraint("person_id", name="uq_social_security_estimates_person_id"),
    )
    op.create_index(
        "ix_social_security_estimates_household_id",
        "social_security_estimates",
        ["household_id"],
    )
    op.create_index(
        "ix_social_security_estimates_person_id", "social_security_estimates", ["person_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_social_security_estimates_person_id", table_name="social_security_estimates")
    op.drop_index("ix_social_security_estimates_household_id", table_name="social_security_estimates")
    op.drop_table("social_security_estimates")
    op.drop_index("ix_household_people_household_id", table_name="household_people")
    op.drop_table("household_people")
