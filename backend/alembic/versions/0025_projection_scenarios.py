"""add projection scenario identity and baseline backfill

Revision ID: 0025_projection_scenarios
Revises: 0024_user_authentication
Create Date: 2026-07-25 00:00:00.000000
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision: str = "0025_projection_scenarios"
down_revision: str | Sequence[str] | None = "0024_user_authentication"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "projection_scenarios",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("is_baseline", sa.Boolean(), nullable=False),
        sa.Column("created_from_scenario_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_from_scenario_id"],
            ["projection_scenarios.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "household_id",
            "name",
            name="uq_projection_scenarios_household_name",
        ),
    )
    op.create_index(
        "ix_projection_scenarios_household_created",
        "projection_scenarios",
        ["household_id", "created_at"],
    )
    op.create_index(
        "ix_projection_scenarios_created_from",
        "projection_scenarios",
        ["created_from_scenario_id"],
    )
    op.create_index(
        "uq_projection_scenarios_household_baseline",
        "projection_scenarios",
        ["household_id"],
        unique=True,
        postgresql_where=sa.text("is_baseline"),
        sqlite_where=sa.text("is_baseline = 1"),
    )

    households = sa.table("households", sa.column("id", sa.Uuid()))
    scenarios = sa.table(
        "projection_scenarios",
        sa.column("id", sa.Uuid()),
        sa.column("household_id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("description", sa.String()),
        sa.column("is_baseline", sa.Boolean()),
        sa.column("created_from_scenario_id", sa.Uuid()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    household_ids = op.get_bind().execute(sa.select(households.c.id)).scalars().all()
    now = datetime.now(UTC)
    if household_ids:
        op.bulk_insert(
            scenarios,
            [
                {
                    "id": uuid4(),
                    "household_id": household_id,
                    "name": "Baseline",
                    "description": "Default household projection assumptions",
                    "is_baseline": True,
                    "created_from_scenario_id": None,
                    "created_at": now,
                    "updated_at": now,
                }
                for household_id in household_ids
            ],
        )


def downgrade() -> None:
    op.drop_index(
        "uq_projection_scenarios_household_baseline",
        table_name="projection_scenarios",
    )
    op.drop_index("ix_projection_scenarios_created_from", table_name="projection_scenarios")
    op.drop_index("ix_projection_scenarios_household_created", table_name="projection_scenarios")
    op.drop_table("projection_scenarios")
