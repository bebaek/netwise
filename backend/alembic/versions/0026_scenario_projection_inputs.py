"""make projection inputs scenario aware

Revision ID: 0026_scenario_projection_inputs
Revises: 0025_projection_scenarios
Create Date: 2026-07-25 00:00:00.000000
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision: str = "0026_scenario_projection_inputs"
down_revision: str | Sequence[str] | None = "0025_projection_scenarios"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCENARIO_TABLES = (
    "projection_settings",
    "spending_items",
    "income_sources",
    "social_security_estimates",
    "projection_transfers",
    "real_estate_sales",
    "real_estate_liquidation_strategies",
)


def _baseline_id_subquery(target: sa.TableClause) -> sa.ScalarSelect:
    scenarios = sa.table(
        "projection_scenarios",
        sa.column("id", sa.Uuid()),
        sa.column("household_id", sa.Uuid()),
        sa.column("is_baseline", sa.Boolean()),
    )
    return (
        sa.select(scenarios.c.id)
        .where(
            scenarios.c.household_id == target.c.household_id,
            scenarios.c.is_baseline.is_(True),
        )
        .correlate(target)
        .scalar_subquery()
    )


def _add_scenario_column(table_name: str) -> None:
    with op.batch_alter_table(table_name) as batch:
        batch.add_column(sa.Column("scenario_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            f"fk_{table_name}_scenario_id",
            "projection_scenarios",
            ["scenario_id"],
            ["id"],
            ondelete="CASCADE",
        )
    target = sa.table(
        table_name,
        sa.column("household_id", sa.Uuid()),
        sa.column("scenario_id", sa.Uuid()),
    )
    op.execute(target.update().values(scenario_id=_baseline_id_subquery(target)))
    with op.batch_alter_table(table_name) as batch:
        batch.alter_column("scenario_id", existing_type=sa.Uuid(), nullable=False)
    op.create_index(f"ix_{table_name}_scenario_id", table_name, ["scenario_id"])


def _create_assumption_tables() -> None:
    op.create_table(
        "projection_scenario_account_assumptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scenario_id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("expected_annual_yield", sa.Numeric(8, 6), nullable=True),
        sa.Column("liquidation_expense_rate", sa.Numeric(8, 6), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["scenario_id"], ["projection_scenarios.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "scenario_id",
            "account_id",
            name="uq_projection_scenario_account_assumptions_scenario_account",
        ),
    )
    op.create_index(
        "ix_projection_scenario_account_assumptions_household",
        "projection_scenario_account_assumptions",
        ["household_id"],
    )
    op.create_index(
        "ix_projection_scenario_account_assumptions_account",
        "projection_scenario_account_assumptions",
        ["account_id"],
    )

    op.create_table(
        "projection_scenario_property_assumptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scenario_id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("property_account_id", sa.Uuid(), nullable=False),
        sa.Column("expected_appreciation_rate", sa.Numeric(8, 6), nullable=True),
        sa.Column("rent_growth_rate", sa.Numeric(8, 6), nullable=True),
        sa.Column("vacancy_rate", sa.Numeric(8, 6), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["property_account_id"], ["accounts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["scenario_id"], ["projection_scenarios.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "scenario_id",
            "property_account_id",
            name="uq_projection_scenario_property_assumptions_scenario_property",
        ),
    )
    op.create_index(
        "ix_projection_scenario_property_assumptions_household",
        "projection_scenario_property_assumptions",
        ["household_id"],
    )
    op.create_index(
        "ix_projection_scenario_property_assumptions_property",
        "projection_scenario_property_assumptions",
        ["property_account_id"],
    )


def _materialize_assumptions() -> None:
    connection = op.get_bind()
    scenarios = sa.table(
        "projection_scenarios",
        sa.column("id", sa.Uuid()),
        sa.column("household_id", sa.Uuid()),
    )
    accounts = sa.table(
        "accounts",
        sa.column("id", sa.Uuid()),
        sa.column("household_id", sa.Uuid()),
        sa.column("expected_annual_yield", sa.Numeric(8, 6)),
        sa.column("liquidation_expense_rate", sa.Numeric(8, 6)),
    )
    properties = sa.table(
        "real_estate_properties",
        sa.column("account_id", sa.Uuid()),
        sa.column("household_id", sa.Uuid()),
        sa.column("expected_appreciation_rate", sa.Numeric(8, 6)),
        sa.column("rent_growth_rate", sa.Numeric(8, 6)),
        sa.column("vacancy_rate", sa.Numeric(8, 6)),
    )
    account_assumptions = sa.table(
        "projection_scenario_account_assumptions",
        sa.column("id", sa.Uuid()),
        sa.column("scenario_id", sa.Uuid()),
        sa.column("household_id", sa.Uuid()),
        sa.column("account_id", sa.Uuid()),
        sa.column("expected_annual_yield", sa.Numeric(8, 6)),
        sa.column("liquidation_expense_rate", sa.Numeric(8, 6)),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    property_assumptions = sa.table(
        "projection_scenario_property_assumptions",
        sa.column("id", sa.Uuid()),
        sa.column("scenario_id", sa.Uuid()),
        sa.column("household_id", sa.Uuid()),
        sa.column("property_account_id", sa.Uuid()),
        sa.column("expected_appreciation_rate", sa.Numeric(8, 6)),
        sa.column("rent_growth_rate", sa.Numeric(8, 6)),
        sa.column("vacancy_rate", sa.Numeric(8, 6)),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    scenario_rows = connection.execute(
        sa.select(scenarios.c.id, scenarios.c.household_id)
    ).all()
    account_rows = connection.execute(
        sa.select(
            accounts.c.id,
            accounts.c.household_id,
            accounts.c.expected_annual_yield,
            accounts.c.liquidation_expense_rate,
        )
    ).all()
    property_rows = connection.execute(
        sa.select(
            properties.c.account_id,
            properties.c.household_id,
            properties.c.expected_appreciation_rate,
            properties.c.rent_growth_rate,
            properties.c.vacancy_rate,
        )
    ).all()
    now = datetime.now(UTC)
    account_records = [
        {
            "id": uuid4(),
            "scenario_id": scenario.id,
            "household_id": scenario.household_id,
            "account_id": account.id,
            "expected_annual_yield": account.expected_annual_yield,
            "liquidation_expense_rate": account.liquidation_expense_rate,
            "created_at": now,
            "updated_at": now,
        }
        for scenario in scenario_rows
        for account in account_rows
        if account.household_id == scenario.household_id
    ]
    property_records = [
        {
            "id": uuid4(),
            "scenario_id": scenario.id,
            "household_id": scenario.household_id,
            "property_account_id": property_record.account_id,
            "expected_appreciation_rate": property_record.expected_appreciation_rate,
            "rent_growth_rate": property_record.rent_growth_rate,
            "vacancy_rate": property_record.vacancy_rate,
            "created_at": now,
            "updated_at": now,
        }
        for scenario in scenario_rows
        for property_record in property_rows
        if property_record.household_id == scenario.household_id
    ]
    if account_records:
        op.bulk_insert(account_assumptions, account_records)
    if property_records:
        op.bulk_insert(property_assumptions, property_records)


def upgrade() -> None:
    for table_name in _SCENARIO_TABLES:
        _add_scenario_column(table_name)

    with op.batch_alter_table("projection_settings") as batch:
        batch.drop_constraint("uq_projection_settings_household", type_="unique")
        batch.create_unique_constraint("uq_projection_settings_scenario", ["scenario_id"])
    with op.batch_alter_table("social_security_estimates") as batch:
        batch.drop_constraint("uq_social_security_estimates_person_id", type_="unique")
        batch.create_unique_constraint(
            "uq_social_security_estimates_scenario_person",
            ["scenario_id", "person_id"],
        )
    with op.batch_alter_table("real_estate_sales") as batch:
        batch.drop_constraint("uq_real_estate_sales_property_account", type_="unique")
        batch.create_unique_constraint(
            "uq_real_estate_sales_scenario_property",
            ["scenario_id", "property_account_id"],
        )
    with op.batch_alter_table("real_estate_liquidation_strategies") as batch:
        batch.drop_constraint(
            "uq_real_estate_liquidation_strategies_property", type_="unique"
        )
        batch.create_unique_constraint(
            "uq_real_estate_liquidation_strategies_scenario_property",
            ["scenario_id", "property_account_id"],
        )

    events = sa.table(
        "account_events",
        sa.column("household_id", sa.Uuid()),
        sa.column("projection_behavior", sa.String()),
        sa.column("scenario_id", sa.Uuid()),
    )
    op.execute(
        events.update()
        .where(events.c.projection_behavior == "projection_only")
        .values(scenario_id=_baseline_id_subquery(events))
    )
    op.execute(
        events.update()
        .where(events.c.projection_behavior != "projection_only")
        .values(scenario_id=None)
    )
    with op.batch_alter_table("account_events") as batch:
        batch.create_foreign_key(
            "fk_account_events_scenario_id",
            "projection_scenarios",
            ["scenario_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch.create_check_constraint(
            "ck_account_events_projection_scenario",
            "(projection_behavior = 'projection_only' AND scenario_id IS NOT NULL) OR "
            "(projection_behavior != 'projection_only' AND scenario_id IS NULL)",
        )
    op.create_index("ix_account_events_scenario_id", "account_events", ["scenario_id"])

    _create_assumption_tables()
    _materialize_assumptions()


def _retain_only_baseline_rows(table_name: str) -> None:
    target = sa.table(table_name, sa.column("scenario_id", sa.Uuid()))
    scenarios = sa.table(
        "projection_scenarios",
        sa.column("id", sa.Uuid()),
        sa.column("is_baseline", sa.Boolean()),
    )
    baseline_ids = sa.select(scenarios.c.id).where(scenarios.c.is_baseline.is_(True))
    op.execute(target.delete().where(target.c.scenario_id.not_in(baseline_ids)))


def _drop_scenario_column(table_name: str) -> None:
    op.drop_index(f"ix_{table_name}_scenario_id", table_name=table_name)
    with op.batch_alter_table(table_name) as batch:
        batch.drop_constraint(f"fk_{table_name}_scenario_id", type_="foreignkey")
        batch.drop_column("scenario_id")


def downgrade() -> None:
    for table_name in (
        "social_security_estimates",
        "income_sources",
        "projection_settings",
        "spending_items",
        "projection_transfers",
        "real_estate_sales",
        "real_estate_liquidation_strategies",
    ):
        _retain_only_baseline_rows(table_name)

    op.drop_index(
        "ix_projection_scenario_property_assumptions_property",
        table_name="projection_scenario_property_assumptions",
    )
    op.drop_index(
        "ix_projection_scenario_property_assumptions_household",
        table_name="projection_scenario_property_assumptions",
    )
    op.drop_table("projection_scenario_property_assumptions")
    op.drop_index(
        "ix_projection_scenario_account_assumptions_account",
        table_name="projection_scenario_account_assumptions",
    )
    op.drop_index(
        "ix_projection_scenario_account_assumptions_household",
        table_name="projection_scenario_account_assumptions",
    )
    op.drop_table("projection_scenario_account_assumptions")

    op.drop_index("ix_account_events_scenario_id", table_name="account_events")
    with op.batch_alter_table("account_events") as batch:
        batch.drop_constraint("ck_account_events_projection_scenario", type_="check")
        batch.drop_constraint("fk_account_events_scenario_id", type_="foreignkey")

    with op.batch_alter_table("projection_settings") as batch:
        batch.drop_constraint("uq_projection_settings_scenario", type_="unique")
        batch.create_unique_constraint("uq_projection_settings_household", ["household_id"])
    with op.batch_alter_table("social_security_estimates") as batch:
        batch.drop_constraint(
            "uq_social_security_estimates_scenario_person", type_="unique"
        )
        batch.create_unique_constraint(
            "uq_social_security_estimates_person_id", ["person_id"]
        )
    with op.batch_alter_table("real_estate_sales") as batch:
        batch.drop_constraint("uq_real_estate_sales_scenario_property", type_="unique")
        batch.create_unique_constraint(
            "uq_real_estate_sales_property_account", ["property_account_id"]
        )
    with op.batch_alter_table("real_estate_liquidation_strategies") as batch:
        batch.drop_constraint(
            "uq_real_estate_liquidation_strategies_scenario_property", type_="unique"
        )
        batch.create_unique_constraint(
            "uq_real_estate_liquidation_strategies_property", ["property_account_id"]
        )

    for table_name in reversed(_SCENARIO_TABLES):
        _drop_scenario_column(table_name)
